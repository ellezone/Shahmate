from flask import Flask, render_template_string, request, redirect, url_for
from threading import Thread
import os
import time
import requests
import pytz
import datetime
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
from binance.client import Client
from binance.enums import *
import logging

# Configure logging
logging.basicConfig(filename='bot_log.txt', level=logging.INFO, 
                   format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

# Global variables
api_key = ""
api_secret = ""
client = None
intervals = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d"]
usdt_pairs = []
running_live = False
running_backtest = False
bot_output = []
MAX_OUTPUT = 50

# Trading variables
current_total_money = 15000  # Default starting amount for backtesting
reserve_money_usdc = 5000    # Reserve USDC
total_spent = 0
total_coins = 0
total_profit_accumulated = 0
buy_counter = 0
last_buy_price = None
base_amount = 0
avg_price = 0
trailing_active = False
trailing_peak_rsi = 0
trailing_peak_value = 0

# Strategy variables
rsi_length = 7
oversold_level = 28
overbought_level = 68
proximity_range_percent = 2.5
profit_range = 2.5
max_buy_steps = 15
interval = "1m"
ema_period = 10
trailing_start_rsi = 73
trailing_stop_enabled = True
rsi_threshold = 28
price_change_threshold = 1.0
volume_change_threshold = 0.5
volatility_threshold = 2.0
vars_password = "123qwe"  # Simple password for variables page

# Create the static directory and style.css file if they don't exist
def create_static_files():
    os.makedirs("static", exist_ok=True)
    
    style_css = """
    body {
        font-family: Arial, sans-serif;
        margin: 0;
        padding: 20px;
        background-color: #2c3e50;
        color: #ecf0f1;
        text-align: center;
    }
    h2 {
        color: #e67e22;
    }
    .container {
        max-width: 800px;
        margin: 0 auto;
        background-color: #34495e;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    select, input, button {
        padding: 10px;
        margin: 5px;
        border-radius: 5px;
        border: none;
        background-color: #2c3e50;
        color: #ecf0f1;
    }
    button {
        background-color: #e67e22;
        cursor: pointer;
        font-weight: bold;
    }
    button:hover {
        background-color: #d35400;
    }
    table {
        width: 100%;
        border-collapse: collapse;
        margin: 20px 0;
    }
    table, th, td {
        border: 1px solid #2c3e50;
    }
    th, td {
        padding: 10px;
        text-align: left;
    }
    th {
        background-color: #2c3e50;
    }
    tr:nth-child(even) {
        background-color: #2c3e50;
    }
    .bot-output {
        height: 300px;
        overflow-y: auto;
        background-color: #2c3e50;
        border-radius: 5px;
        padding: 10px;
        text-align: left;
        font-family: monospace;
        margin-top: 20px;
    }
    .status {
        display: inline-block;
        width: 10px;
        height: 10px;
        border-radius: 50%;
        margin-right: 5px;
    }
    .running {
        background-color: #2ecc71;
    }
    .stopped {
        background-color: #e74c3c;
    }
    .grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
        gap: 20px;
        margin-bottom: 20px;
    }
    .card {
        background-color: #2c3e50;
        border-radius: 5px;
        padding: 15px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }
    .card h3 {
        margin-top: 0;
        color: #e67e22;
    }
    .navbar {
        background-color: #2c3e50;
        overflow: hidden;
        margin-bottom: 20px;
        border-radius: 5px;
    }
    .navbar a {
        float: left;
        display: block;
        color: #ecf0f1;
        text-align: center;
        padding: 14px 16px;
        text-decoration: none;
    }
    .navbar a:hover {
        background-color: #e67e22;
    }
    .navbar a.active {
        background-color: #e67e22;
    }
    .footer {
        margin-top: 20px;
        padding: 10px;
        background-color: #2c3e50;
        border-radius: 5px;
    }
    """
    
    with open("static/style.css", "w") as f:
        f.write(style_css)

# Template for homepage
home_html = """
<!DOCTYPE html>
<html>
<head>
    <title>ShahMate Trading Bot</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body>
    <div class="container">
        <img src="{{ url_for('static', filename='shahmate_logo.png') }}" alt="Shahmate Logo" style="width: 80%; max-width: 300px; margin: 20px auto; display: block;">
        
        <div class="navbar">
            <a href="{{ url_for('index') }}" class="active">Home</a>
            <a href="{{ url_for('live') }}">Live Mode</a>
            <a href="{{ url_for('backtest') }}">Backtest</a>
            <a href="{{ url_for('recommend') }}">Recommend</a>
            <a href="{{ url_for('api') }}">API Settings</a>
            <a href="{{ url_for('variables') }}">Variables</a>
        </div>
        
        <div class="grid">
            <div class="card">
                <h3>Live Trading</h3>
                <p>Status: <span class="status {% if running_live %}running{% else %}stopped{% endif %}"></span> {{ 'Running' if running_live else 'Stopped' }}</p>
                <a href="{{ url_for('live') }}"><button>Open</button></a>
            </div>
            
            <div class="card">
                <h3>Backtest</h3>
                <p>Status: <span class="status {% if running_backtest %}running{% else %}stopped{% endif %}"></span> {{ 'Running' if running_backtest else 'Stopped' }}</p>
                <a href="{{ url_for('backtest') }}"><button>Open</button></a>
            </div>
            
            <div class="card">
                <h3>Recommend</h3>
                <p>Find the best trading opportunities</p>
                <a href="{{ url_for('recommend') }}"><button>Open</button></a>
            </div>
            
            <div class="card">
                <h3>API Settings</h3>
                <p>Configure your Binance API</p>
                <a href="{{ url_for('api') }}"><button>Open</button></a>
            </div>
        </div>
        
        <div class="bot-output">
            {% for msg in bot_output %}
                <div>{{ msg }}</div>
            {% endfor %}
        </div>
        
        <div class="footer">
            ShahMate Trading Bot &copy; 2025
        </div>
    </div>
</body>
</html>
"""

# Template for live mode
live_html = """
<!DOCTYPE html>
<html>
<head>
    <title>Live Trading - ShahMate</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="30">
</head>
<body>
    <div class="container">
        <img src="{{ url_for('static', filename='shahmate_logo.png') }}" alt="Shahmate Logo" style="width: 80%; max-width: 300px; margin: 20px auto; display: block;">
        
        <div class="navbar">
            <a href="{{ url_for('index') }}">Home</a>
            <a href="{{ url_for('live') }}" class="active">Live Mode</a>
            <a href="{{ url_for('backtest') }}">Backtest</a>
            <a href="{{ url_for('recommend') }}">Recommend</a>
            <a href="{{ url_for('api') }}">API Settings</a>
            <a href="{{ url_for('variables') }}">Variables</a>
        </div>
        
        <div class="grid">
            <div class="card">
                <h3>USDT Balance</h3>
                <p>{{ usdt_balance }}</p>
            </div>
            
            <div class="card">
                <h3>USDC Balance</h3>
                <p>{{ usdc_balance }}</p>
            </div>
            
            <div class="card">
                <h3>FDUSD Balance</h3>
                <p>{{ fdusd_balance }}</p>
            </div>
            
            <div class="card">
                <h3>Status</h3>
                <p><span class="status {% if running_live %}running{% else %}stopped{% endif %}"></span> {{ 'Running' if running_live else 'Stopped' }}</p>
            </div>
        </div>
        
        <form method="POST">
            <select name="pair">
                {% for pair in usdt_pairs %}
                    <option value="{{ pair }}" {% if pair == current_pair %}selected{% endif %}>{{ pair }}</option>
                {% endfor %}
            </select>
            
            <select name="interval">
                {% for inter in intervals %}
                    <option value="{{ inter }}" {% if inter == current_interval %}selected{% endif %}>{{ inter }}</option>
                {% endfor %}
            </select>
            
            {% if running_live %}
                <button type="submit" name="action" value="stop">Stop Trading</button>
            {% else %}
                <button type="submit" name="action" value="start">Start Trading</button>
            {% endif %}
        </form>
        
        <div class="bot-output">
            {% for msg in bot_output %}
                <div>{{ msg }}</div>
            {% endfor %}
        </div>
        
        <div class="footer">
            ShahMate Trading Bot &copy; 2025
        </div>
    </div>
</body>
</html>
"""

# Template for backtest
backtest_html = """
<!DOCTYPE html>
<html>
<head>
    <title>Backtest - ShahMate</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
</head>
<body>
    <div class="container">
        <img src="{{ url_for('static', filename='shahmate_logo.png') }}" alt="Shahmate Logo" style="width: 80%; max-width: 300px; margin: 20px auto; display: block;">
        
        <div class="navbar">
            <a href="{{ url_for('index') }}">Home</a>
            <a href="{{ url_for('live') }}">Live Mode</a>
            <a href="{{ url_for('backtest') }}" class="active">Backtest</a>
            <a href="{{ url_for('recommend') }}">Recommend</a>
            <a href="{{ url_for('api') }}">API Settings</a>
            <a href="{{ url_for('variables') }}">Variables</a>
        </div>
        
        <div class="grid">
            <div class="card">
                <h3>Initial USDT</h3>
                <p>{{ current_total_money }}</p>
            </div>
            
            <div class="card">
                <h3>Status</h3>
                <p><span class="status {% if running_backtest %}running{% else %}stopped{% endif %}"></span> {{ 'Running' if running_backtest else 'Stopped' }}</p>
            </div>
            
            {% if backtest_results %}
            <div class="card">
                <h3>Final Balance</h3>
                <p>{{ backtest_results.final_balance }}</p>
            </div>
            
            <div class="card">
                <h3>Profit</h3>
                <p>{{ backtest_results.total_profit }}</p>
            </div>
            
            <div class="card">
                <h3>ROI</h3>
                <p>{{ backtest_results.roi }}%</p>
            </div>
            
            <div class="card">
                <h3>Win Rate</h3>
                <p>{{ backtest_results.win_rate }}%</p>
            </div>
            {% endif %}
        </div>
        
        <form method="POST">
            <select name="pair">
                {% for pair in usdt_pairs %}
                    <option value="{{ pair }}" {% if pair == current_pair %}selected{% endif %}>{{ pair }}</option>
                {% endfor %}
            </select>
            
            <select name="interval">
                {% for inter in intervals %}
                    <option value="{{ inter }}" {% if inter == current_interval %}selected{% endif %}>{{ inter }}</option>
                {% endfor %}
            </select>
            
            <input type="date" name="start_date" value="{{ start_date }}" max="{{ today_date }}">
            <input type="date" name="end_date" value="{{ end_date }}" max="{{ today_date }}">
            
            {% if running_backtest %}
                <button type="submit" name="action" value="stop">Stop Backtest</button>
            {% else %}
                <button type="submit" name="action" value="start">Start Backtest</button>
            {% endif %}
        </form>
        
        {% if chart_div %}
        <div class="chart-container">
            {{ chart_div|safe }}
        </div>
        {% endif %}
        
        <div class="bot-output">
            {% for msg in bot_output %}
                <div>{{ msg }}</div>
            {% endfor %}
        </div>
        
        <div class="footer">
            ShahMate Trading Bot &copy; 2025
        </div>
    </div>
</body>
</html>
"""

# Template for API settings
api_html = """
<!DOCTYPE html>
<html>
<head>
    <title>API Settings - ShahMate</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body>
    <div class="container">
        <img src="{{ url_for('static', filename='shahmate_logo.png') }}" alt="Shahmate Logo" style="width: 80%; max-width: 300px; margin: 20px auto; display: block;">
        
        <div class="navbar">
            <a href="{{ url_for('index') }}">Home</a>
            <a href="{{ url_for('live') }}">Live Mode</a>
            <a href="{{ url_for('backtest') }}">Backtest</a>
            <a href="{{ url_for('recommend') }}">Recommend</a>
            <a href="{{ url_for('api') }}" class="active">API Settings</a>
            <a href="{{ url_for('variables') }}">Variables</a>
        </div>
        
        <form method="POST">
            <div style="text-align: left; margin-bottom: 20px;">
                <p><strong>API Key:</strong> <input type="text" name="api_key" value="{{ api_key }}" style="width: 100%;"></p>
                <p><strong>API Secret:</strong> <input type="password" name="api_secret" value="{{ api_secret }}" style="width: 100%;"></p>
            </div>
            
            <button type="submit">Save API Settings</button>
        </form>
        
        <div class="bot-output">
            {% for msg in bot_output %}
                <div>{{ msg }}</div>
            {% endfor %}
        </div>
        
        <div class="footer">
            ShahMate Trading Bot &copy; 2025
        </div>
    </div>
</body>
</html>
"""

# Template for variables
variables_html = """
<!DOCTYPE html>
<html>
<head>
    <title>Variables - ShahMate</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body>
    <div class="container">
        <img src="{{ url_for('static', filename='shahmate_logo.png') }}" alt="Shahmate Logo" style="width: 80%; max-width: 300px; margin: 20px auto; display: block;">
        
        <div class="navbar">
            <a href="{{ url_for('index') }}">Home</a>
            <a href="{{ url_for('live') }}">Live Mode</a>
            <a href="{{ url_for('backtest') }}">Backtest</a>
            <a href="{{ url_for('recommend') }}">Recommend</a>
            <a href="{{ url_for('api') }}">API Settings</a>
            <a href="{{ url_for('variables') }}" class="active">Variables</a>
        </div>
        
        {% if not unlocked %}
            <form method="POST">
                <p>Enter password to edit variables:</p>
                <input type="password" name="password">
                <button type="submit" name="action" value="unlock">Unlock</button>
            </form>
        {% else %}
            <form method="POST">
                <div style="text-align: left;">
                    <p><strong>RSI Length:</strong> <input type="number" name="rsi_length" value="{{ rsi_length }}" min="2" max="50"></p>
                    <p><strong>Oversold Level:</strong> <input type="number" name="oversold_level" value="{{ oversold_level }}" min="1" max="49"></p>
                    <p><strong>Overbought Level:</strong> <input type="number" name="overbought_level" value="{{ overbought_level }}" min="51" max="99"></p>
                    <p><strong>Proximity Range %:</strong> <input type="number" name="proximity_range_percent" value="{{ proximity_range_percent }}" min="0.1" max="10" step="0.1"></p>
                    <p><strong>Profit Range %:</strong> <input type="number" name="profit_range" value="{{ profit_range }}" min="0.1" max="10" step="0.1"></p>
                    <p><strong>Max Buy Steps:</strong> <input type="number" name="max_buy_steps" value="{{ max_buy_steps }}" min="1" max="50"></p>
                    <p><strong>Default Interval:</strong> 
                        <select name="interval">
                            {% for inter in intervals %}
                                <option value="{{ inter }}" {% if inter == interval %}selected{% endif %}>{{ inter }}</option>
                            {% endfor %}
                        </select>
                    </p>
                    <p><strong>EMA Period:</strong> <input type="number" name="ema_period" value="{{ ema_period }}" min="3" max="50"></p>
                    <p><strong>Trailing Start RSI:</strong> <input type="number" name="trailing_start_rsi" value="{{ trailing_start_rsi }}" min="50" max="99"></p>
                    <p><strong>Trailing Stop:</strong> 
                        <select name="trailing_stop_enabled">
                            <option value="1" {% if trailing_stop_enabled %}selected{% endif %}>Enabled</option>
                            <option value="0" {% if not trailing_stop_enabled %}selected{% endif %}>Disabled</option>
                        </select>
                    </p>
                    <p><strong>RSI Threshold:</strong> <input type="number" name="rsi_threshold" value="{{ rsi_threshold }}" min="1" max="50"></p>
                    <p><strong>Price Change Threshold %:</strong> <input type="number" name="price_change_threshold" value="{{ price_change_threshold }}" min="0.1" max="10" step="0.1"></p>
                    <p><strong>Volume Change Threshold:</strong> <input type="number" name="volume_change_threshold" value="{{ volume_change_threshold }}" min="0.1" max="10" step="0.1"></p>
                    <p><strong>Volatility Threshold:</strong> <input type="number" name="volatility_threshold" value="{{ volatility_threshold }}" min="0.1" max="10" step="0.1"></p>
                </div>
                
                <button type="submit" name="action" value="save">Save Variables</button>
                <button type="submit" name="action" value="lock">Lock</button>
            </form>
        {% endif %}
        
        <div class="bot-output">
            {% for msg in bot_output %}
                <div>{{ msg }}</div>
            {% endfor %}
        </div>
        
        <div class="footer">
            ShahMate Trading Bot &copy; 2025
        </div>
    </div>
</body>
</html>
"""

# Template for recommend
recommend_html = """
<!DOCTYPE html>
<html>
<head>
    <title>Recommend - ShahMate</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body>
    <div class="container">
        <img src="{{ url_for('static', filename='shahmate_logo.png') }}" alt="Shahmate Logo" style="width: 80%; max-width: 300px; margin: 20px auto; display: block;">
        
        <div class="navbar">
            <a href="{{ url_for('index') }}">Home</a>
            <a href="{{ url_for('live') }}">Live Mode</a>
            <a href="{{ url_for('backtest') }}">Backtest</a>
            <a href="{{ url_for('recommend') }}" class="active">Recommend</a>
            <a href="{{ url_for('api') }}">API Settings</a>
            <a href="{{ url_for('variables') }}">Variables</a>
        </div>
        
        <form method="POST">
            <p>Find coins with good trading setup based on current strategy variables</p>
            <button type="submit" name="action" value="recommend">Find Recommendations</button>
        </form>
        
        {% if recommended_coins %}
            <table>
                <tr>
                    <th>Symbol</th>
                    <th>RSI</th>
                    <th>Price</th>
                    <th>24h Change</th>
                    <th>EMA Verified</th>
                    <th>Action</th>
                </tr>
                {% for coin in recommended_coins %}
                <tr>
                    <td>{{ coin.symbol }}</td>
                    <td>{{ coin.rsi|round(2) }}</td>
                    <td>{{ coin.price }}</td>
                    <td>{{ coin.change_24h|round(2) }}%</td>
                    <td>{{ 'Yes' if coin.ema_verified else 'No' }}</td>
                    <td>
                        <a href="{{ url_for('live', pair=coin.symbol) }}"><button>Trade</button></a>
                        <a href="{{ url_for('backtest', pair=coin.symbol) }}"><button>Backtest</button></a>
                    </td>
                </tr>
                {% endfor %}
            </table>
        {% endif %}
        
        <div class="bot-output">
            {% for msg in bot_output %}
                <div>{{ msg }}</div>
            {% endfor %}
        </div>
        
        <div class="footer">
            ShahMate Trading Bot &copy; 2025
        </div>
    </div>
</body>
</html>
"""

# Function to add bot output messages
def add_bot_output(message, context=None):
    global bot_output
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    
    # Add context prefix if provided
    if context == "live":
        prefix = "🔴 LIVE"
    elif context == "backtest":
        prefix = "📊 BACKTEST"
    elif context == "recommend":
        prefix = "🔍 RECOMMEND"
    elif context == "api":
        prefix = "🔑 API"
    else:
        prefix = "ℹ️ INFO"
    
    formatted_message = f"{timestamp}: {prefix}: {message}"
    
    bot_output.append(formatted_message)
    if len(bot_output) > MAX_OUTPUT:
        bot_output = bot_output[-MAX_OUTPUT:]
    
    # Also log to file
    logging.info(f"{prefix}: {message}")

# Initialize Binance client
def initialize_client():
    global client, api_key, api_secret
    if api_key and api_secret:
        try:
            client = Client(api_key, api_secret)
            add_bot_output("Connected to Binance API successfully")
            return True
        except Exception as e:
            add_bot_output(f"Failed to connect to Binance: {str(e)}")
            return False
    else:
        add_bot_output("API key or secret not set")
        return False

# Get all USDT trading pairs
def get_usdt_pairs():
    global usdt_pairs
    
    # Always refresh the list to ensure we have the latest pairs
    try:
        if client:
            # Get exchange info from authenticated client
            exchange_info = client.get_exchange_info()
            
            # Filter for USDT pairs
            updated_pairs = [s['symbol'] for s in exchange_info['symbols'] 
                           if s['symbol'].endswith('USDT') and s['status'] == 'TRADING']
            
            # Check if list has changed
            if not usdt_pairs or set(updated_pairs) != set(usdt_pairs):
                usdt_pairs = updated_pairs
                add_bot_output(f"Updated to {len(usdt_pairs)} USDT trading pairs from Binance API")
            
        else:
            # Fallback to public API if client not initialized
            url = "https://api.binance.com/api/v3/exchangeInfo"
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                updated_pairs = [s['symbol'] for s in data['symbols'] 
                               if s['symbol'].endswith('USDT') and s['status'] == 'TRADING']
                
                # Check if list has changed
                if not usdt_pairs or set(updated_pairs) != set(usdt_pairs):
                    usdt_pairs = updated_pairs
                    add_bot_output(f"Updated to {len(usdt_pairs)} USDT trading pairs using public API")
            else:
                add_bot_output(f"Failed to get trading pairs: {response.status_code}")
                # Only use fallback if we don't already have pairs
                if not usdt_pairs:
                    usdt_pairs = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT", "DOGEUSDT", "XRPUSDT", 
                                "AVAXUSDT", "DOTUSDT", "LTCUSDT", "LINKUSDT", "MATICUSDT", "TRXUSDT", "UNIUSDT"]
                    add_bot_output("Using fallback USDT trading pairs list")
                    
    except Exception as e:
        add_bot_output(f"Error getting USDT pairs: {str(e)}")
        # Only use fallback if we don't already have pairs
        if not usdt_pairs:
            usdt_pairs = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT", "DOGEUSDT", "XRPUSDT", 
                        "AVAXUSDT", "DOTUSDT", "LTCUSDT", "LINKUSDT", "MATICUSDT", "TRXUSDT", "UNIUSDT"]
            add_bot_output("Using fallback USDT trading pairs list")
    
    # Always sort the list for consistent display
    if usdt_pairs:
        usdt_pairs.sort()
    
    return usdt_pairs

# Get account balances
def get_spot_balance():
    if client:
        try:
            account = client.get_account()
            balances = {}
            for balance in account['balances']:
                asset = balance['asset']
                free = float(balance['free'])
                locked = float(balance['locked'])
                total = free + locked
                if total > 0:
                    balances[asset] = total
            add_bot_output(f"Successfully fetched real balances from Binance")
            return balances
        except Exception as e:
            add_bot_output(f"Error getting balances: {str(e)}")
            # Return simulated balances as fallback
            return {"USDT": 15000, "USDC": 5000, "FDUSD": 0}
    else:
        # Return simulated balances if client not initialized
        return {"USDT": 15000, "USDC": 5000, "FDUSD": 0}

# Function to place a market buy order
def place_market_buy_order(symbol, quantity):
    if client:
        try:
            order = client.create_order(
                symbol=symbol,
                side=SIDE_BUY,
                type=ORDER_TYPE_MARKET,
                quantity=quantity)
            return order
        except Exception as e:
            add_bot_output(f"Buy order error: {str(e)}")
            return None
    else:
        # Simulated order response for testing
        add_bot_output(f"Simulated buy for {quantity} {symbol}")
        return {
            "symbol": symbol,
            "orderId": 12345,
            "status": "FILLED",
            "type": "MARKET",
            "side": "BUY",
            "price": "0",
            "origQty": str(quantity),
            "executedQty": str(quantity),
            "cummulativeQuoteQty": "0",
            "fills": []
        }

# Function to place a market sell order
def place_market_sell_order(symbol, quantity):
    if client:
        try:
            order = client.create_order(
                symbol=symbol,
                side=SIDE_SELL,
                type=ORDER_TYPE_MARKET,
                quantity=quantity)
            return order
        except Exception as e:
            add_bot_output(f"Sell order error: {str(e)}")
            return None
    else:
        # Simulated order response for testing
        add_bot_output(f"Simulated sell for {quantity} {symbol}")
        return {
            "symbol": symbol,
            "orderId": 12345,
            "status": "FILLED",
            "type": "MARKET",
            "side": "SELL",
            "price": "0",
            "origQty": str(quantity),
            "executedQty": str(quantity),
            "cummulativeQuoteQty": "0",
            "fills": []
        }

# Convert USDC to USDT
def convert_usdc_to_usdt(amount):
    if client:
        try:
            # This is a placeholder - actual implementation would depend on Binance's API
            add_bot_output(f"Converting {amount} USDC to USDT")
            # In a real implementation, you would use Binance's API to convert
            return True
        except Exception as e:
            add_bot_output(f"Error converting USDC to USDT: {str(e)}")
            return False
    else:
        add_bot_output(f"Simulated conversion of {amount} USDC to USDT")
        return True

# Convert USDT to FDUSD
def convert_usdt_to_fdusd(amount):
    if client:
        try:
            # This is a placeholder - actual implementation would depend on Binance's API
            add_bot_output(f"Converting {amount} USDT to FDUSD")
            # In a real implementation, you would use Binance's API to convert
            return True
        except Exception as e:
            add_bot_output(f"Error converting USDT to FDUSD: {str(e)}")
            return False
    else:
        add_bot_output(f"Simulated conversion of {amount} USDT to FDUSD")
        return True

# Function to get historical klines (candles)
def get_historical_klines(symbol, interval, limit=1000, start_time=None, end_time=None):
    try:
        if client:
            klines = client.get_historical_klines(
                symbol=symbol, 
                interval=interval, 
                limit=limit,
                start_str=start_time,
                end_str=end_time
            )
            return klines
        else:
            # Fallback to public API
            url = "https://api.binance.com/api/v3/klines"
            params = {
                "symbol": symbol,
                "interval": interval,
                "limit": limit
            }
            if start_time:
                params["startTime"] = start_time
            if end_time:
                params["endTime"] = end_time
                
            response = requests.get(url, params=params)
            if response.status_code == 200:
                return response.json()
            else:
                add_bot_output(f"Failed to get klines: {response.status_code}")
                return []
    except Exception as e:
        add_bot_output(f"Error getting klines: {str(e)}")
        return []

# Function to get live market data
def get_live_data(symbol, interval):
    try:
        # Get recent klines (candlesticks)
        klines = get_historical_klines(symbol, interval, limit=100)
        
        if not klines:
            add_bot_output(f"No klines data received for {symbol}")
            return None
            
        # Parse klines data
        open_time = [int(entry[0]) for entry in klines]
        open_price = [float(entry[1]) for entry in klines]
        high_price = [float(entry[2]) for entry in klines]
        low_price = [float(entry[3]) for entry in klines]
        close_price = [float(entry[4]) for entry in klines]
        volume = [float(entry[5]) for entry in klines]
        
        # Get ticker price for current price
        if client:
            ticker = client.get_symbol_ticker(symbol=symbol)
            current_price = float(ticker['price'])
        else:
            # Use the last close price if client is not available
            current_price = close_price[-1]
        
        # Calculate RSI
        rsi_value = calculate_rsi(close_price)
        
        # Calculate EMA
        ema_value = calculate_ema(close_price)
        
        # Check if price is above EMA (a simple trend confirmation)
        ema_verified = current_price > ema_value[-1] if ema_value else False
        
        return {
            'symbol': symbol,
            'current_price': current_price,
            'close_prices': close_price,
            'rsi': rsi_value[-1] if rsi_value else None,
            'ema': ema_value[-1] if ema_value else None,
            'ema_verified': ema_verified
        }
    except Exception as e:
        add_bot_output(f"Error getting live data: {str(e)}")
        return None

# Calculate Relative Strength Index (RSI)
def calculate_rsi(prices, length=None):
    if length is None:
        length = rsi_length
        
    if len(prices) < length + 1:
        return None
        
    # Calculate price changes
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    
    # Calculate gains and losses
    gains = [delta if delta > 0 else 0 for delta in deltas]
    losses = [-delta if delta < 0 else 0 for delta in deltas]
    
    # Calculate average gains and losses
    avg_gain = sum(gains[:length]) / length
    avg_loss = sum(losses[:length]) / length
    
    # Calculate subsequent average gains and losses
    rsi_values = []
    for i in range(length, len(deltas)):
        avg_gain = (avg_gain * (length - 1) + gains[i]) / length
        avg_loss = (avg_loss * (length - 1) + losses[i]) / length
        
        if avg_loss == 0:
            rs = 100
        else:
            rs = avg_gain / avg_loss
            
        rsi = 100 - (100 / (1 + rs))
        rsi_values.append(rsi)
    
    return rsi_values

# Calculate Exponential Moving Average (EMA)
def calculate_ema(prices, period=None):
    if period is None:
        period = ema_period
        
    if len(prices) < period:
        return None
        
    ema_values = []
    multiplier = 2 / (period + 1)
    
    # Start with SMA for the first EMA value
    sma = sum(prices[:period]) / period
    ema_values.append(sma)
    
    # Calculate EMA for remaining prices
    for price in prices[period:]:
        ema = (price - ema_values[-1]) * multiplier + ema_values[-1]
        ema_values.append(ema)
    
    return ema_values

# Function to run live trading
def run_live(symbol, interval):
    global running_live, current_total_money, total_spent, total_coins, buy_counter, last_buy_price, base_amount, avg_price
    global trailing_active, trailing_peak_rsi, trailing_peak_value
    
    add_bot_output(f"Starting live trading for {symbol} with {interval} interval", context="live")
    
    # Reset trading variables
    total_spent = 0
    total_coins = 0
    buy_counter = 0
    last_buy_price = None
    base_amount = current_total_money / max_buy_steps if max_buy_steps > 0 else 0
    avg_price = 0
    trailing_active = False
    trailing_peak_rsi = 0
    trailing_peak_value = 0
    
    balances = get_spot_balance()
    add_bot_output(f"Current balances: USDT={balances.get('USDT', 0)}, USDC={balances.get('USDC', 0)}, FDUSD={balances.get('FDUSD', 0)}")
    
    while running_live:
        try:
            # Get live market data
            data = get_live_data(symbol, interval)
            
            if not data:
                add_bot_output(f"Failed to get data for {symbol}, retrying in 10 seconds...")
                time.sleep(10)
                continue
                
            current_price = data['current_price']
            rsi = data['rsi']
            ema_verified = data['ema_verified']
            
            # Add current price and RSI to bot output
            add_bot_output(f"Price: {current_price}, RSI: {rsi}, EMA verified: {ema_verified}")
            
            # Buy-side logic
            if rsi < oversold_level and ema_verified:
                # Calculate how much to buy based on tier
                tier = min(buy_counter + 1, max_buy_steps)
                buy_amount = base_amount * (1 + (tier - 1) * 0.1)  # Increase amount by 10% for each tier
                
                # Calculate coins to buy
                quantity_to_buy = buy_amount / current_price
                
                # Check if we have enough balance
                if buy_amount <= current_total_money:
                    # Place a market buy order
                    add_bot_output(f"BUY: Tier {tier}, Amount: {buy_amount} USDT, Quantity: {quantity_to_buy}, RSI: {rsi}")
                    
                    order = place_market_buy_order(symbol, quantity_to_buy)
                    
                    if order:
                        buy_counter += 1
                        last_buy_price = current_price
                        total_spent += buy_amount
                        total_coins += quantity_to_buy
                        current_total_money -= buy_amount
                        avg_price = total_spent / total_coins if total_coins > 0 else 0
                        
                        add_bot_output(f"Buy order executed. Total coins: {total_coins}, Avg price: {avg_price}, Remaining USDT: {current_total_money}")
                else:
                    add_bot_output("Not enough balance for buy order")
            
            # Sell-side logic with profit target
            if total_coins > 0:
                # Calculate profit percentage
                profit_percent = ((current_price - avg_price) / avg_price) * 100
                
                # Check for trailing stop activation
                if trailing_stop_enabled and rsi > trailing_start_rsi and not trailing_active:
                    trailing_active = True
                    trailing_peak_rsi = rsi
                    trailing_peak_value = current_price
                    add_bot_output(f"Trailing stop activated at price {current_price}, RSI {rsi}")
                
                # Update trailing peak if price is rising
                if trailing_active and current_price > trailing_peak_value:
                    trailing_peak_value = current_price
                    trailing_peak_rsi = max(trailing_peak_rsi, rsi)
                    add_bot_output(f"Updated trailing peak: {trailing_peak_value}, RSI: {trailing_peak_rsi}")
                
                # Check for profit target or trailing stop trigger
                sell_signal = False
                
                # Regular profit target
                if profit_percent >= profit_range:
                    sell_signal = True
                    add_bot_output(f"Profit target reached: {profit_percent}%")
                
                # Trailing stop logic
                if trailing_active:
                    # If price drops more than 1% from peak or RSI drops significantly from peak
                    if current_price < trailing_peak_value * 0.99 or rsi < trailing_peak_rsi * 0.9:
                        sell_signal = True
                        add_bot_output(f"Trailing stop triggered. Current: {current_price}, Peak: {trailing_peak_value}, RSI: {rsi}, Peak RSI: {trailing_peak_rsi}")
                
                if sell_signal:
                    # Place market sell order for all coins
                    add_bot_output(f"SELL: Quantity: {total_coins}, Price: {current_price}, Profit: {profit_percent}%")
                    
                    order = place_market_sell_order(symbol, total_coins)
                    
                    if order:
                        # Calculate profit
                        sell_value = total_coins * current_price
                        profit = sell_value - total_spent
                        
                        # Update balances
                        current_total_money += sell_value
                        
                        add_bot_output(f"Sell order executed. Profit: {profit} USDT ({profit_percent}%), Total USDT: {current_total_money}")
                        
                        # Reset position tracking
                        total_spent = 0
                        total_coins = 0
                        buy_counter = 0
                        last_buy_price = None
                        avg_price = 0
                        trailing_active = False
                        trailing_peak_rsi = 0
                        trailing_peak_value = 0
            
            # Wait for next check
            time.sleep(10)
            
        except Exception as e:
            add_bot_output(f"Error in live trading: {str(e)}")
            time.sleep(30)  # Wait longer on error

# Generate a backtest chart with plotly
def generate_backtest_chart(symbol, prices, times, rsi_values, ema_values, buy_points, sell_points):
    try:
        # Create figure with secondary y-axis
        fig = make_subplots(rows=2, cols=1, 
                            shared_xaxes=True, 
                            vertical_spacing=0.05, 
                            row_heights=[0.7, 0.3],
                            subplot_titles=(f"{symbol} Price Chart", "RSI Indicator"))
        
        # Add price line to the first row
        fig.add_trace(
            go.Scatter(
                x=times, 
                y=prices, 
                mode='lines',
                name='Price',
                line=dict(color='#3498db')
            ),
            row=1, col=1
        )
        
        # Add EMA line to the first row
        if ema_values and len(ema_values) > 0:
            # EMA values typically start after a certain period, so we need to align with times
            ema_times = times[-len(ema_values):]
            fig.add_trace(
                go.Scatter(
                    x=ema_times, 
                    y=ema_values, 
                    mode='lines',
                    name=f'EMA-{ema_period}',
                    line=dict(color='#f39c12')
                ),
                row=1, col=1
            )
        
        # Add buy points to the first row
        if buy_points:
            buy_x, buy_y = zip(*buy_points)
            fig.add_trace(
                go.Scatter(
                    x=buy_x, 
                    y=buy_y, 
                    mode='markers',
                    name='Buy',
                    marker=dict(
                        color='#2ecc71',
                        size=10,
                        symbol='triangle-up'
                    )
                ),
                row=1, col=1
            )
        
        # Add sell points to the first row
        if sell_points:
            sell_x, sell_y = zip(*sell_points)
            fig.add_trace(
                go.Scatter(
                    x=sell_x, 
                    y=sell_y, 
                    mode='markers',
                    name='Sell',
                    marker=dict(
                        color='#e74c3c',
                        size=10,
                        symbol='triangle-down'
                    )
                ),
                row=1, col=1
            )
        
        # Add RSI line to the second row
        if rsi_values and len(rsi_values) > 0:
            # RSI values typically start after a certain period, so we need to align with times
            rsi_times = times[-len(rsi_values):]
            fig.add_trace(
                go.Scatter(
                    x=rsi_times, 
                    y=rsi_values, 
                    mode='lines',
                    name='RSI',
                    line=dict(color='#9b59b6')
                ),
                row=2, col=1
            )
            
            # Add horizontal lines for overbought and oversold levels
            fig.add_shape(
                type="line",
                x0=min(times),
                x1=max(times),
                y0=oversold_level,
                y1=oversold_level,
                line=dict(color="#2ecc71", width=1, dash="dash"),
                row=2, col=1
            )
            
            fig.add_shape(
                type="line",
                x0=min(times),
                x1=max(times),
                y0=overbought_level,
                y1=overbought_level,
                line=dict(color="#e74c3c", width=1, dash="dash"),
                row=2, col=1
            )
        
        # Update layout
        fig.update_layout(
            title_text=f"Backtest Results for {symbol}",
            autosize=True,
            height=700,
            template="plotly_dark",
            plot_bgcolor='#2c3e50',
            paper_bgcolor='#2c3e50',
            font=dict(color='#ecf0f1'),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        # Update axes
        fig.update_xaxes(
            title_text="Date",
            showgrid=True,
            gridcolor='#34495e',
            row=2, col=1
        )
        
        fig.update_yaxes(
            title_text="Price",
            showgrid=True,
            gridcolor='#34495e',
            row=1, col=1
        )
        
        fig.update_yaxes(
            title_text="RSI",
            showgrid=True,
            gridcolor='#34495e',
            range=[0, 100],
            row=2, col=1
        )
        
        # Convert plot to HTML
        chart_div = fig.to_html(full_html=False, include_plotlyjs=False)
        return chart_div
    
    except Exception as e:
        add_bot_output(f"Error generating chart: {str(e)}")
        return None

# Function to run backtesting
def run_backtest(symbol, interval, start_date=None, end_date=None):
    global running_backtest, current_total_money, total_spent, total_coins, buy_counter, last_buy_price, base_amount, avg_price
    global trailing_active, trailing_peak_rsi, trailing_peak_value
    
    # Convert dates to timestamps
    if start_date and end_date:
        start_time = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp() * 1000)
        end_time = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp() * 1000)
        add_bot_output(f"Starting backtest for {symbol} with {interval} interval from {start_date} to {end_date}", context="backtest")
    else:
        # Default to last 30 days if dates not provided
        end_time = int(time.time() * 1000)  # Current time in milliseconds
        start_time = end_time - (30 * 24 * 60 * 60 * 1000)  # 30 days ago in milliseconds
        add_bot_output(f"Starting backtest for {symbol} with {interval} interval over the last 30 days", context="backtest")
    
    try:
        # Get historical klines for the specified period
        klines = get_historical_klines(symbol, interval, limit=1000, start_time=start_time, end_time=end_time)
        
        if not klines or len(klines) < 50:  # Need enough data for indicators
            add_bot_output(f"Not enough historical data for {symbol} in the specified period")
            running_backtest = False
            return None
            
        # Parse klines data
        open_time = [int(entry[0]) for entry in klines]
        open_price = [float(entry[1]) for entry in klines]
        high_price = [float(entry[2]) for entry in klines]
        low_price = [float(entry[3]) for entry in klines]
        close_price = [float(entry[4]) for entry in klines]
        volume = [float(entry[5]) for entry in klines]
        
        # Convert timestamps to readable dates for the chart
        chart_dates = [datetime.fromtimestamp(ts/1000) for ts in open_time]
        
        add_bot_output(f"Loaded {len(klines)} candles for backtest")
        
        # Reset trading variables for backtest
        initial_balance = current_total_money
        current_balance = initial_balance
        total_spent = 0
        total_coins = 0
        buy_counter = 0
        last_buy_price = None
        base_amount = current_balance / max_buy_steps if max_buy_steps > 0 else 0
        avg_price = 0
        trailing_active = False
        trailing_peak_rsi = 0
        trailing_peak_value = 0
        
        # Statistics tracking
        buy_count = 0
        sell_count = 0
        winning_trades = 0
        losing_trades = 0
        
        # For tracking chart points
        buy_points = []
        sell_points = []
        
        # Calculate RSI and EMA for the entire dataset
        full_rsi_values = calculate_rsi(close_price)
        full_ema_values = calculate_ema(close_price)
        
        # Loop through the candles starting from the point where indicators can be calculated
        for i in range(rsi_length + 1, len(close_price)):
            if not running_backtest:
                add_bot_output("Backtest stopped by user")
                break
                
            # Current values from precalculated indicators
            current_price = close_price[i]
            current_time = chart_dates[i]
            current_rsi = full_rsi_values[i - rsi_length - 1] if i - rsi_length - 1 < len(full_rsi_values) else 50
            current_ema = full_ema_values[i - ema_period] if i - ema_period < len(full_ema_values) else current_price
            
            # Check if price is above EMA (trend confirmation)
            ema_verified = current_price > current_ema
            
            # Occasionally log the current state
            if i % 100 == 0 or i == len(close_price) - 1:
                timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(open_time[i] / 1000))
                add_bot_output(f"Backtesting {timestamp}: Price: {current_price}, RSI: {current_rsi}, EMA verified: {ema_verified}", context="backtest")
            
            # Buy-side logic
            if current_rsi < oversold_level and ema_verified and current_balance > 0:
                # Calculate how much to buy based on tier
                tier = min(buy_counter + 1, max_buy_steps)
                buy_amount = base_amount * (1 + (tier - 1) * 0.1)  # Increase amount by 10% for each tier
                
                # Calculate coins to buy
                quantity_to_buy = buy_amount / current_price
                
                # Check if we have enough balance
                if buy_amount <= current_balance:
                    # Simulate buy order
                    buy_count += 1
                    buy_counter += 1
                    last_buy_price = current_price
                    total_spent += buy_amount
                    total_coins += quantity_to_buy
                    current_balance -= buy_amount
                    avg_price = total_spent / total_coins if total_coins > 0 else 0
                    
                    # Add buy point for chart
                    buy_points.append((current_time, current_price))
                    
                    # Log less frequently during backtest
                    if buy_count % 5 == 0 or buy_count < 5:
                        timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(open_time[i] / 1000))
                        add_bot_output(f"BUY {timestamp}: Tier {tier}, Price: {current_price}, Quantity: {quantity_to_buy}, RSI: {current_rsi}", context="backtest")
            
            # Sell-side logic
            if total_coins > 0:
                # Calculate profit percentage
                profit_percent = ((current_price - avg_price) / avg_price) * 100
                
                # Check for trailing stop activation
                if trailing_stop_enabled and current_rsi > trailing_start_rsi and not trailing_active:
                    trailing_active = True
                    trailing_peak_rsi = current_rsi
                    trailing_peak_value = current_price
                
                # Update trailing peak if price is rising
                if trailing_active and current_price > trailing_peak_value:
                    trailing_peak_value = current_price
                    trailing_peak_rsi = max(trailing_peak_rsi, current_rsi)
                
                # Check for profit target or trailing stop trigger
                sell_signal = False
                
                # Regular profit target
                if profit_percent >= profit_range:
                    sell_signal = True
                
                # Trailing stop logic
                if trailing_active:
                    # If price drops more than 1% from peak or RSI drops significantly from peak
                    if current_price < trailing_peak_value * 0.99 or current_rsi < trailing_peak_rsi * 0.9:
                        sell_signal = True
                
                if sell_signal:
                    # Simulate sell order
                    sell_count += 1
                    
                    # Calculate profit
                    sell_value = total_coins * current_price
                    profit = sell_value - total_spent
                    
                    # Update statistics
                    if profit > 0:
                        winning_trades += 1
                    else:
                        losing_trades += 1
                    
                    # Update balance
                    current_balance += sell_value
                    
                    # Add sell point for chart
                    sell_points.append((current_time, current_price))
                    
                    # Log the sell
                    timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(open_time[i] / 1000))
                    add_bot_output(f"SELL {timestamp}: Price: {current_price}, Quantity: {total_coins}, Profit: {profit} USDT ({profit_percent:.2f}%)", context="backtest")
                    
                    # Reset position tracking
                    total_spent = 0
                    total_coins = 0
                    buy_counter = 0
                    last_buy_price = None
                    avg_price = 0
                    trailing_active = False
                    trailing_peak_rsi = 0
                    trailing_peak_value = 0
        
        # Calculate final statistics
        total_profit = current_balance - initial_balance
        roi_percent = (total_profit / initial_balance) * 100
        win_rate = (winning_trades / sell_count * 100) if sell_count > 0 else 0
        
        add_bot_output(f"===== Backtest Complete =====", context="backtest")
        add_bot_output(f"Symbol: {symbol}, Interval: {interval}", context="backtest")
        add_bot_output(f"Initial USDT: {initial_balance}", context="backtest")
        add_bot_output(f"Final USDT: {current_balance}", context="backtest")
        add_bot_output(f"Total profit: {total_profit}", context="backtest")
        add_bot_output(f"ROI: {roi_percent:.2f}%", context="backtest")
        add_bot_output(f"Total trades: {buy_count} buys, {sell_count} sells", context="backtest")
        add_bot_output(f"Winning trades: {winning_trades}, Losing trades: {losing_trades}", context="backtest")
        add_bot_output(f"Win rate: {win_rate:.2f}%", context="backtest")
        
        # Generate chart
        chart_div = generate_backtest_chart(
            symbol=symbol,
            prices=close_price,
            times=chart_dates,
            rsi_values=full_rsi_values,
            ema_values=full_ema_values,
            buy_points=buy_points,
            sell_points=sell_points
        )
        
        # Return results for display on the web page
        return {
            'chart_div': chart_div,
            'final_balance': f"{current_balance:.2f} USDT",
            'total_profit': f"{total_profit:.2f} USDT",
            'roi': f"{roi_percent:.2f}",
            'win_rate': f"{win_rate:.2f}",
            'buy_count': buy_count,
            'sell_count': sell_count,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades
        }
        
    except Exception as e:
        add_bot_output(f"Error in backtest: {str(e)}", context="backtest")
        return None
    
    finally:
        running_backtest = False

# Function to find recommended coins
def run_recommend():
    add_bot_output("Finding recommended coins...", context="recommend")
    
    recommended = []
    pairs = get_usdt_pairs()
    
    # Limit to avoid rate limits
    max_pairs_to_check = min(50, len(pairs))
    
    for i, symbol in enumerate(pairs[:max_pairs_to_check]):
        try:
            # Get live data for the symbol
            data = get_live_data(symbol, interval)
            
            if not data or 'rsi' not in data or data['rsi'] is None:
                continue
                
            # Check if RSI is oversold or overbought
            rsi = data['rsi']
            
            # Only consider coins with RSI below the threshold
            if rsi < rsi_threshold:
                # Get 24h price change
                if client:
                    ticker = client.get_ticker(symbol=symbol)
                    price_change_24h = float(ticker.get('priceChangePercent', 0))
                else:
                    price_change_24h = 0  # Default if client not available
                
                # Add to recommended list if it meets the criteria
                if (abs(price_change_24h) >= price_change_threshold and 
                    data.get('ema_verified', False)):
                    
                    recommended.append({
                        'symbol': symbol,
                        'rsi': rsi,
                        'price': data['current_price'],
                        'change_24h': price_change_24h,
                        'ema_verified': data.get('ema_verified', False)
                    })
            
            # Log progress occasionally
            if (i+1) % 5 == 0:
                add_bot_output(f"Checked {i+1}/{max_pairs_to_check} pairs...", context="recommend")
                
        except Exception as e:
            add_bot_output(f"Error checking {symbol}: {str(e)}", context="recommend")
    
    # Sort by RSI (lowest first)
    recommended.sort(key=lambda x: x['rsi'])
    
    # Log results
    add_bot_output(f"Found {len(recommended)} recommended coins", context="recommend")
    
    return recommended

# Routes
@app.route('/')
def index():
    get_usdt_pairs()  # Make sure we have the pairs list
    return render_template_string(home_html, 
                                 running_live=running_live, 
                                 running_backtest=running_backtest, 
                                 bot_output=bot_output)

@app.route('/live', methods=['GET', 'POST'])
def live():
    global running_live, running_backtest
    
    # Get pairs and balances
    pairs = get_usdt_pairs()
    balances = get_spot_balance()
    
    current_pair = request.args.get('pair', 'BTCUSDT')
    current_interval = request.args.get('interval', interval)
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'start':
            # Stop backtest if running
            running_backtest = False
            
            # Start live trading
            current_pair = request.form.get('pair', 'BTCUSDT')
            current_interval = request.form.get('interval', interval)
            
            if not running_live:
                running_live = True
                
                # Initialize client if needed
                initialize_client()
                
                # Start trading in a background thread
                trading_thread = Thread(target=run_live, args=(current_pair, current_interval))
                trading_thread.daemon = True
                trading_thread.start()
                
                add_bot_output(f"Started live trading for {current_pair}", context="live")
        
        elif action == 'stop':
            # Stop live trading
            running_live = False
            add_bot_output("Stopping live trading", context="live")
    
    return render_template_string(live_html, 
                                 usdt_pairs=pairs, 
                                 intervals=intervals, 
                                 current_pair=current_pair,
                                 current_interval=current_interval, 
                                 running_live=running_live,
                                 usdt_balance=balances.get('USDT', 0),
                                 usdc_balance=balances.get('USDC', 0),
                                 fdusd_balance=balances.get('FDUSD', 0),
                                 bot_output=bot_output)

@app.route('/backtest', methods=['GET', 'POST'])
def backtest():
    global running_backtest, running_live
    
    # Get pairs and set defaults
    pairs = get_usdt_pairs()
    current_pair = request.args.get('pair', 'BTCUSDT')
    current_interval = request.args.get('interval', interval)
    
    # Date handling
    today = datetime.now().strftime("%Y-%m-%d")
    start_date = request.args.get('start_date', (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"))
    end_date = request.args.get('end_date', today)
    
    # For chart display
    backtest_results = None
    chart_div = None
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'start':
            # Stop live trading if running
            running_live = False
            
            # Start backtest
            current_pair = request.form.get('pair', 'BTCUSDT')
            current_interval = request.form.get('interval', interval)
            start_date = request.form.get('start_date', start_date)
            end_date = request.form.get('end_date', end_date)
            
            # Clear previous backtest logs
            while len(bot_output) > 0:
                bot_output.pop(0)
            
            if not running_backtest:
                running_backtest = True
                
                # Initialize client if needed
                initialize_client()
                
                add_bot_output(f"Started backtest for {current_pair} from {start_date} to {end_date}", context="backtest")
                
                # Run backtest synchronously to get results
                backtest_results = run_backtest(current_pair, current_interval, start_date, end_date)
                
                if backtest_results:
                    chart_div = backtest_results.get('chart_div')
                    add_bot_output(f"Backtest completed with profit: {backtest_results.get('total_profit')}", context="backtest")
                else:
                    add_bot_output("Failed to generate backtest results", context="backtest")
                
                running_backtest = False
        
        elif action == 'stop':
            # Stop backtest
            running_backtest = False
            add_bot_output("Stopping backtest", context="backtest")
    
    return render_template_string(backtest_html, 
                                 usdt_pairs=pairs, 
                                 intervals=intervals, 
                                 current_pair=current_pair,
                                 current_interval=current_interval,
                                 start_date=start_date,
                                 end_date=end_date, 
                                 today_date=today,
                                 running_backtest=running_backtest,
                                 current_total_money=current_total_money,
                                 bot_output=bot_output,
                                 backtest_results=backtest_results,
                                 chart_div=chart_div)

@app.route('/recommend', methods=['GET', 'POST'])
def recommend():
    recommended_coins = []
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'recommend':
            # Initialize client if needed
            initialize_client()
            
            # Find recommended coins
            recommended_coins = run_recommend()
    
    return render_template_string(recommend_html, 
                                 recommended_coins=recommended_coins,
                                 bot_output=bot_output)

@app.route('/api', methods=['GET', 'POST'])
def api():
    global api_key, api_secret, client
    
    if request.method == 'POST':
        api_key = request.form.get('api_key', '')
        api_secret = request.form.get('api_secret', '')
        
        # Initialize client with new API keys
        if api_key and api_secret:
            initialize_client()
    
    return render_template_string(api_html, 
                                 api_key=api_key, 
                                 api_secret=api_secret, 
                                 bot_output=bot_output)

@app.route('/variables', methods=['GET', 'POST'])
def variables():
    global rsi_length, oversold_level, overbought_level, proximity_range_percent, profit_range
    global max_buy_steps, interval, ema_period, trailing_start_rsi, trailing_stop_enabled
    global rsi_threshold, price_change_threshold, volume_change_threshold, volatility_threshold
    
    unlocked = False
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'unlock':
            password = request.form.get('password')
            if password == vars_password:
                unlocked = True
            else:
                add_bot_output("Invalid password for variables", context="api")
        
        elif action == 'save':
            # Update variables
            rsi_length = int(request.form.get('rsi_length', rsi_length))
            oversold_level = int(request.form.get('oversold_level', oversold_level))
            overbought_level = int(request.form.get('overbought_level', overbought_level))
            proximity_range_percent = float(request.form.get('proximity_range_percent', proximity_range_percent))
            profit_range = float(request.form.get('profit_range', profit_range))
            max_buy_steps = int(request.form.get('max_buy_steps', max_buy_steps))
            interval = request.form.get('interval', interval)
            ema_period = int(request.form.get('ema_period', ema_period))
            trailing_start_rsi = int(request.form.get('trailing_start_rsi', trailing_start_rsi))
            trailing_stop_enabled = request.form.get('trailing_stop_enabled', '0') == '1'
            rsi_threshold = int(request.form.get('rsi_threshold', rsi_threshold))
            price_change_threshold = float(request.form.get('price_change_threshold', price_change_threshold))
            volume_change_threshold = float(request.form.get('volume_change_threshold', volume_change_threshold))
            volatility_threshold = float(request.form.get('volatility_threshold', volatility_threshold))
            
            add_bot_output("Strategy variables updated", context="api")
            unlocked = True
    
    return render_template_string(variables_html, 
                                 unlocked=unlocked,
                                 rsi_length=rsi_length,
                                 oversold_level=oversold_level,
                                 overbought_level=overbought_level,
                                 proximity_range_percent=proximity_range_percent,
                                 profit_range=profit_range,
                                 max_buy_steps=max_buy_steps,
                                 intervals=intervals,
                                 interval=interval,
                                 ema_period=ema_period,
                                 trailing_start_rsi=trailing_start_rsi,
                                 trailing_stop_enabled=trailing_stop_enabled,
                                 rsi_threshold=rsi_threshold,
                                 price_change_threshold=price_change_threshold,
                                 volume_change_threshold=volume_change_threshold,
                                 volatility_threshold=volatility_threshold,
                                 bot_output=bot_output)

if __name__ == '__main__':
    # Create static files
    create_static_files()
    
    # Initial bot message
    add_bot_output("ShahMate Trading Bot started", context="info")
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=5000, debug=False)