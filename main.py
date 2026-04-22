import pandas as pd
import matplotlib.pyplot as plt
import mplfinance as mpf
import talib
import os
from tensorflow.keras.utils import load_img, img_to_array
from keras.models import load_model
import tensorflow as tf
import numpy as np
from datetime import datetime, timedelta
from binance.client import Client
import time
import requests

# Configure for fast processing
plt.ioff()
import warnings
warnings.filterwarnings('ignore')

# GPU Configuration
gpus = tf.config.list_physical_devices('GPU')
if gpus:
    try:
        tf.config.set_logical_device_configuration(
            gpus[0], [tf.config.LogicalDeviceConfiguration(memory_limit=7492)]
        )
    except Exception as e:
        print(f"GPU configuration warning: {e}")

# Trading configuration
symbol = "BTCUSDT"
interval = Client.KLINE_INTERVAL_15MINUTE
crypto_pair = "BTC/USDT"

# LEVERAGE SETTINGS
LEVERAGE = 2  # 2x leverage

# Initialize Binance client (no API key needed for public market data)
client = Client()

# Initialize trading variables
initial_amount_usdt = 1000
current_amount_usdt = initial_amount_usdt
amount_in_crypto = 0

# NEW: Enhanced position tracking with stop loss and profit booking
long_position = 0  # Amount of BTC in long position
long_entry_price = 0  # Entry price for long position
long_stop_loss = 0  # Stop loss price for long position
long_initial_size = 0  # Original position size before profit booking

short_position = 0  # Amount of BTC in short position  
short_entry_price = 0  # Entry price for short position
short_stop_loss = 0  # Stop loss price for short position
short_initial_size = 0  # Original position size before profit booking
short_entry_value = 0  # USDT value when we entered short

# Position status
current_trend = None  # 'U' for uptrend, 'D' for downtrend, None for no position
profit_bookings = 0  # Count of profit bookings in current position

trade_count = 0
trade_data = []
last_processed_time = None
signal_coords = []  # Store signal timestamps
signal_trends = []  # Store signal directions (U/D)

# Data storage
data = pd.DataFrame(columns=['Time', 'Open', 'High', 'Low', 'Close', 'Volume'])

# FIXED: Initialize persistent CSV file paths
session_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
reports_folder = f"realtime_trading_session_{session_timestamp}"
os.makedirs(reports_folder, exist_ok=True)

# Define persistent file paths
accuracy_csv_path = os.path.join(reports_folder, f"{crypto_pair.replace('/', '_')}_accuracy_data.csv")
detailed_csv_path = os.path.join(reports_folder, f"{crypto_pair.replace('/', '_')}_detailed_analysis.csv")
strength_csv_path = os.path.join(reports_folder, f"{crypto_pair.replace('/', '_')}_strength_analysis.csv")
trade_log_path = os.path.join(reports_folder, f"{crypto_pair.replace('/', '_')}_trading_log.csv")

def get_latest_klines():
    """Fetch the latest kline data from Binance"""
    try:
        klines = client.get_klines(symbol=symbol, interval=interval, limit=50)
        candle_data = []
        for kline in klines:
            candle_data.append({
                'Time': pd.to_datetime(kline[0], unit='ms'),
                'Open': float(kline[1]),
                'High': float(kline[2]),
                'Low': float(kline[3]),
                'Close': float(kline[4]),
                'Volume': float(kline[5])
            })
        return pd.DataFrame(candle_data)
    except Exception as e:
        print(f"Error fetching klines: {e}")
        return None

def generate_candlestick_image(df, output_path, window_size=5):
    """Generate candlestick chart image"""
    if len(df) < window_size:
        print(f"Not enough data for image generation: {len(df)} < {window_size}")
        return False
    try:
        window = df.iloc[-window_size:].copy()
        window = window.set_index('Time')
        if len(df) >= 20:
            sma_data = talib.SMA(df['Close'].values, timeperiod=20)
            window['SMA'] = sma_data[-window_size:]
            ap = [mpf.make_addplot(window['SMA'], color='blue', secondary_y=False)]
        else:
            ap = []
        mpf.plot(window, type='candle', style='yahoo', addplot=ap, volume=True,
                 axisoff=True, ylabel='',
                 savefig=dict(fname=output_path, dpi=100, bbox_inches='tight'))
        plt.close('all')
        return True
    except Exception as e:
        print(f"Error generating candlestick image: {e}")
        return False

def make_prediction(image_path):
    """Make trend prediction using the trained model"""
    try:
        if not os.path.exists("trend_classification_model.h5"):
            print("⚠️ Model file 'trend_classification_model.h5' not found!")
            return None, None
        image = load_img(image_path, color_mode='rgb', interpolation="bilinear", target_size=(150, 150))
        image = img_to_array(image) / 255.0
        X = np.array([image])
        model = load_model("trend_classification_model.h5")
        prediction = model.predict(X, verbose=0)[0][0]
        confidence_threshold = 0.8
        if prediction >= confidence_threshold:
            return "U", prediction  # UP signal with UP confidence
        elif prediction <= (1 - confidence_threshold):
            return "D", (1 - prediction)  # DOWN signal with DOWN confidence
        else:
            return None, prediction
    except Exception as e:
        print(f"Error making prediction: {e}")
        return None, None

def check_stop_loss(current_price):
    """Check if stop loss should be triggered"""
    global long_position, short_position, current_amount_usdt, current_trend
    global long_stop_loss, short_stop_loss, trade_count, trade_data, profit_bookings
    
    stop_loss_triggered = False
    
    if long_position > 0 and current_price <= long_stop_loss:
        # Long stop loss triggered
        loss_amount = long_position * current_price
        current_amount_usdt = loss_amount / LEVERAGE  # Account for leverage
        
        trade_count += 1
        trade_record = {
            'Timestamp': datetime.now(),
            'Signal': 'STOP_LOSS',
            'Price': current_price,
            'Action': 'STOP_LOSS_LONG',
            'Amount_Crypto': 0,
            'Amount_USDT': current_amount_usdt,
            'Long_Position': 0,
            'Short_Position': 0,
            'Portfolio_Value': current_amount_usdt,
            'Trade_Number': trade_count,
            'Stop_Loss_Price': long_stop_loss,
            'Entry_Price': long_entry_price
        }
        trade_data.append(trade_record)
        
        print(f"🛑 LONG STOP LOSS TRIGGERED #{trade_count}: ${current_price:.2f}")
        print(f"   Entry: ${long_entry_price:.2f} | Stop: ${long_stop_loss:.2f}")
        print(f"   Loss: ${(long_entry_price - current_price) * long_position:.2f}")
        
        # Reset position
        long_position = 0
        long_entry_price = 0
        long_stop_loss = 0
        long_initial_size = 0
        current_trend = None
        profit_bookings = 0
        stop_loss_triggered = True
        
    elif short_position > 0 and current_price >= short_stop_loss:
        # Short stop loss triggered
        cost_to_cover = short_position * current_price
        loss = cost_to_cover - short_entry_value
        current_amount_usdt = (short_entry_value - loss) / LEVERAGE  # Account for leverage
        
        trade_count += 1
        trade_record = {
            'Timestamp': datetime.now(),
            'Signal': 'STOP_LOSS',
            'Price': current_price,
            'Action': 'STOP_LOSS_SHORT',
            'Amount_Crypto': 0,
            'Amount_USDT': current_amount_usdt,
            'Long_Position': 0,
            'Short_Position': 0,
            'Portfolio_Value': current_amount_usdt,
            'Trade_Number': trade_count,
            'Stop_Loss_Price': short_stop_loss,
            'Entry_Price': short_entry_price
        }
        trade_data.append(trade_record)
        
        print(f"🛑 SHORT STOP LOSS TRIGGERED #{trade_count}: ${current_price:.2f}")
        print(f"   Entry: ${short_entry_price:.2f} | Stop: ${short_stop_loss:.2f}")
        print(f"   Loss: ${loss:.2f}")
        
        # Reset position
        short_position = 0
        short_entry_price = 0
        short_stop_loss = 0
        short_initial_size = 0
        short_entry_value = 0
        current_trend = None
        profit_bookings = 0
        stop_loss_triggered = True
    
    if stop_loss_triggered:
        update_trading_log()
    
    return stop_loss_triggered

def check_profit_booking(current_price, candle_data):
    """Check if profit should be booked based on reverse candle formation"""
    global long_position, short_position, current_amount_usdt, profit_bookings
    global trade_count, trade_data, long_initial_size, short_initial_size
    
    profit_booked = False
    
    # Get the latest completed candle
    if len(candle_data) < 2:
        return False
    
    latest_candle = candle_data.iloc[-1]  # Current candle
    candle_color = 'green' if latest_candle['Close'] > latest_candle['Open'] else 'red'
    
    # LONG POSITION: Book profit on red candle during uptrend
    if long_position > 0 and current_trend == 'U' and candle_color == 'red':
        # Check if price moved 100+ points from entry
        points_moved = current_price - long_entry_price
        if points_moved >= 100:
            # Book 25% profit
            profit_amount = long_position * 0.25
            profit_value = profit_amount * current_price
            
            # Add profit to USDT (accounting for leverage)
            current_amount_usdt += (profit_value / LEVERAGE)
            long_position -= profit_amount
            profit_bookings += 1
            
            trade_count += 1
            trade_record = {
                'Timestamp': datetime.now(),
                'Signal': 'PROFIT_BOOK',
                'Price': current_price,
                'Action': 'BOOK_LONG_PROFIT_25%',
                'Amount_Crypto': long_position,
                'Amount_USDT': current_amount_usdt,
                'Long_Position': long_position,
                'Short_Position': 0,
                'Portfolio_Value': (long_position * current_price / LEVERAGE) + current_amount_usdt,
                'Trade_Number': trade_count,
                'Profit_Booked': profit_value / LEVERAGE,
                'Points_Moved': points_moved,
                'Profit_Booking_Count': profit_bookings
            }
            trade_data.append(trade_record)
            
            print(f"📈💰 LONG PROFIT BOOKED #{trade_count}: 25% @ ${current_price:.2f}")
            print(f"   Red candle in uptrend | Points moved: {points_moved:.0f}")
            print(f"   Profit booked: ${profit_value / LEVERAGE:.2f} | Remaining position: {long_position:.6f} BTC")
            
            profit_booked = True
    
    # SHORT POSITION: Book profit on green candle during downtrend  
    elif short_position > 0 and current_trend == 'D' and candle_color == 'green':
        # Check if price moved 100+ points from entry
        points_moved = short_entry_price - current_price
        if points_moved >= 100:
            # Book 25% profit
            profit_amount = short_position * 0.25
            current_cost = profit_amount * current_price
            original_cost = profit_amount * short_entry_price
            profit_value = original_cost - current_cost
            
            # Add profit to USDT (accounting for leverage)
            current_amount_usdt += (profit_value / LEVERAGE)
            short_position -= profit_amount
            short_entry_value -= (original_cost / LEVERAGE)
            profit_bookings += 1
            
            trade_count += 1
            trade_record = {
                'Timestamp': datetime.now(),
                'Signal': 'PROFIT_BOOK',
                'Price': current_price,
                'Action': 'BOOK_SHORT_PROFIT_25%',
                'Amount_Crypto': 0,
                'Amount_USDT': current_amount_usdt,
                'Long_Position': 0,
                'Short_Position': short_position,
                'Portfolio_Value': current_amount_usdt + (short_entry_value - (short_position * current_price / LEVERAGE)),
                'Trade_Number': trade_count,
                'Profit_Booked': profit_value / LEVERAGE,
                'Points_Moved': points_moved,
                'Profit_Booking_Count': profit_bookings
            }
            trade_data.append(trade_record)
            
            print(f"📉💰 SHORT PROFIT BOOKED #{trade_count}: 25% @ ${current_price:.2f}")
            print(f"   Green candle in downtrend | Points moved: {points_moved:.0f}")
            print(f"   Profit booked: ${profit_value / LEVERAGE:.2f} | Remaining position: {short_position:.6f} BTC")
            
            profit_booked = True
    
    if profit_booked:
        update_trading_log()
    
    return profit_booked

def execute_trade_with_enhanced_features(signal, price, timestamp):
    """Execute trades with stop loss, profit booking, and 2x leverage"""
    global current_amount_usdt, long_position, short_position, trade_count, trade_data
    global long_entry_price, short_entry_price, long_stop_loss, short_stop_loss
    global current_trend, profit_bookings, long_initial_size, short_initial_size, short_entry_value
    
    trade_records = []
    
    print(f"🔍 ENHANCED DEBUG: Signal={signal}, USDT=${current_amount_usdt:.2f}")
    print(f"   Long: {long_position:.6f} BTC @ ${long_entry_price:.2f}")
    print(f"   Short: {short_position:.6f} BTC @ ${short_entry_price:.2f}")
    
    if signal == 'U':  # UP signal
        # STEP 1: Close any existing SHORT position
        if short_position > 0:
            cost_to_cover = short_position * price
            short_profit = short_entry_value - (cost_to_cover / LEVERAGE)
            current_amount_usdt = short_entry_value + short_profit
            
            trade_count += 1
            trade_record = {
                'Timestamp': timestamp,
                'Signal': signal,
                'Price': price,
                'Action': 'COVER_SHORT',
                'Amount_Crypto': 0,
                'Amount_USDT': current_amount_usdt,
                'Long_Position': 0,
                'Short_Position': 0,
                'Portfolio_Value': current_amount_usdt,
                'Trade_Number': trade_count
            }
            trade_records.append(trade_record)
            
            print(f"📈 COVER SHORT #{trade_count}: @ ${price:.2f}")
            print(f"   Short Profit: ${short_profit:.2f}")
            
            # Reset short position
            short_position = 0
            short_entry_price = 0
            short_stop_loss = 0
            short_entry_value = 0
            short_initial_size = 0
        
        # STEP 2: Open LONG position with 2x leverage
        if current_amount_usdt > 10:
            leveraged_capital = current_amount_usdt * LEVERAGE
            long_position = leveraged_capital / price
            long_entry_price = price
            long_stop_loss = price - 100  # Stop loss 100 points below entry
            long_initial_size = long_position
            current_trend = 'U'
            profit_bookings = 0
            current_amount_usdt = 0  # Capital is now in position
            
            trade_count += 1
            trade_record = {
                'Timestamp': timestamp,
                'Signal': signal,
                'Price': price,
                'Action': 'OPEN_LONG_2X',
                'Amount_Crypto': long_position,
                'Amount_USDT': 0,
                'Long_Position': long_position,
                'Short_Position': 0,
                'Portfolio_Value': long_position * price / LEVERAGE,
                'Trade_Number': trade_count,
                'Entry_Price': long_entry_price,
                'Stop_Loss': long_stop_loss,
                'Leverage': LEVERAGE
            }
            trade_records.append(trade_record)
            
            print(f"🚀 OPEN LONG 2X #{trade_count}: @ ${price:.2f}")
            print(f"   Position: {long_position:.6f} BTC (2x leveraged)")
            print(f"   Stop Loss: ${long_stop_loss:.2f}")
    
    elif signal == 'D':  # DOWN signal
        # STEP 1: Close any existing LONG position
        if long_position > 0:
            position_value = long_position * price / LEVERAGE
            current_amount_usdt = position_value
            
            trade_count += 1
            trade_record = {
                'Timestamp': timestamp,
                'Signal': signal,
                'Price': price,
                'Action': 'CLOSE_LONG',
                'Amount_Crypto': 0,
                'Amount_USDT': current_amount_usdt,
                'Long_Position': 0,
                'Short_Position': 0,
                'Portfolio_Value': current_amount_usdt,
                'Trade_Number': trade_count
            }
            trade_records.append(trade_record)
            
            print(f"💸 CLOSE LONG #{trade_count}: @ ${price:.2f} = ${current_amount_usdt:.2f}")
            
            # Reset long position
            long_position = 0
            long_entry_price = 0
            long_stop_loss = 0
            long_initial_size = 0
        
        # STEP 2: Open SHORT position with 2x leverage
        if current_amount_usdt > 10 and short_position == 0:
            leveraged_capital = current_amount_usdt * LEVERAGE
            short_position = leveraged_capital / price
            short_entry_price = price
            short_stop_loss = price + 100  # Stop loss 100 points above entry
            short_entry_value = current_amount_usdt
            short_initial_size = short_position
            current_trend = 'D'
            profit_bookings = 0
            current_amount_usdt = 0  # Capital is now in position
            
            trade_count += 1
            trade_record = {
                'Timestamp': timestamp,
                'Signal': signal,
                'Price': price,
                'Action': 'OPEN_SHORT_2X',
                'Amount_Crypto': 0,
                'Amount_USDT': 0,
                'Long_Position': 0,
                'Short_Position': short_position,
                'Portfolio_Value': short_entry_value,
                'Trade_Number': trade_count,
                'Entry_Price': short_entry_price,
                'Stop_Loss': short_stop_loss,
                'Leverage': LEVERAGE
            }
            trade_records.append(trade_record)
            
            print(f"📉 OPEN SHORT 2X #{trade_count}: @ ${price:.2f}")
            print(f"   Position: {short_position:.6f} BTC (2x leveraged)")
            print(f"   Stop Loss: ${short_stop_loss:.2f}")
    
    # Add all trade records
    for record in trade_records:
        trade_data.append(record)
    
    # Update trading log
    if trade_records:
        update_trading_log()
        return True
    
    return False

def update_trading_log():
    """Update the persistent trading log CSV file"""
    if trade_data:
        trade_df = pd.DataFrame(trade_data)
        trade_df.to_csv(trade_log_path, index=False)
        print(f"📝 Trading log updated: {trade_log_path}")

def calculate_improved_accuracy(signal_coords, signal_trends, df):
    """Calculate accuracy by tracking price movement until next signal"""
    accuracy_data = []
    detailed_analysis = []
    for i in range(len(signal_coords) - 1):
        current_signal_time = signal_coords[i]
        current_trend = signal_trends[i]
        next_signal_time = signal_coords[i + 1]
        if current_signal_time in df['Time'].values and next_signal_time in df['Time'].values:
            try:
                current_idx = df[df['Time'] == current_signal_time].index[0]
                next_idx = df[df['Time'] == next_signal_time].index[0]
                signal_range = df.loc[current_idx:next_idx-1].copy()
                if len(signal_range) < 2:
                    continue
                signal_candle = signal_range.iloc[0]
                signal_price = signal_candle['Close']
                signal_high = signal_candle['High']
                signal_low = signal_candle['Low']
                future_candles = signal_range.iloc[1:]
                highest_price = future_candles['High'].max()
                lowest_price = future_candles['Low'].min()
                final_price = future_candles['Close'].iloc[-1]
                max_up_move = ((highest_price - signal_price) / signal_price) * 100
                max_down_move = ((signal_price - lowest_price) / signal_price) * 100
                final_move = ((final_price - signal_price) / signal_price) * 100
                if current_trend == 'U':
                    price_moved_up = highest_price > signal_price
                    strongest_move = max_up_move
                    prediction_correct = price_moved_up
                    net_favorable = max_up_move > max_down_move
                else:
                    price_moved_down = lowest_price < signal_price
                    strongest_move = max_down_move
                    prediction_correct = price_moved_down
                    net_favorable = max_down_move > max_up_move
                detailed_analysis.append({
                    'signal_number': i + 1,
                    'signal_time': current_signal_time,
                    'predicted_trend': current_trend,
                    'signal_price': signal_price,
                    'candles_tracked': len(future_candles),
                    'highest_price': highest_price,
                    'lowest_price': lowest_price,
                    'final_price': final_price,
                    'max_up_move_pct': max_up_move,
                    'max_down_move_pct': max_down_move,
                    'final_move_pct': final_move,
                    'strongest_move_pct': strongest_move,
                    'prediction_correct': prediction_correct,
                    'net_favorable': net_favorable,
                    'duration_minutes': len(future_candles) * 15
                })
                accuracy_data.append({
                    'signal_number': i + 1,
                    'predicted_trend': current_trend,
                    'correct': prediction_correct,
                    'net_favorable': net_favorable,
                    'strongest_move_pct': strongest_move,
                    'abs_strongest_move': abs(strongest_move)
                })
            except Exception as e:
                print(f"Error processing signal {i}: {str(e)}")
                continue
    accuracy_df = pd.DataFrame(accuracy_data)
    detailed_df = pd.DataFrame(detailed_analysis)
    if not accuracy_df.empty:
        basic_accuracy = (accuracy_df['correct'].sum() / len(accuracy_df)) * 100
        net_favorable_accuracy = (accuracy_df['net_favorable'].sum() / len(accuracy_df)) * 100
        strength_results = []
        strength_thresholds = [0.5, 1.0, 2.0, 3.0, 5.0]
        for threshold in strength_thresholds:
            strong_moves = accuracy_df[accuracy_df['abs_strongest_move'] >= threshold]
            if len(strong_moves) > 0:
                strong_accuracy = (strong_moves['correct'].sum() / len(strong_moves)) * 100
                strong_net_accuracy = (strong_moves['net_favorable'].sum() / len(strong_moves)) * 100
                strength_results.append({
                    'threshold': threshold,
                    'basic_accuracy': strong_accuracy,
                    'net_accuracy': strong_net_accuracy,
                    'signal_count': len(strong_moves)
                })
            else:
                strength_results.append({
                    'threshold': threshold,
                    'basic_accuracy': 0,
                    'net_accuracy': 0,
                    'signal_count': 0
                })
        return strength_results, accuracy_df, detailed_df, basic_accuracy, net_favorable_accuracy
    return [], pd.DataFrame(), pd.DataFrame(), 0, 0

def update_accuracy_reports(accuracy_df, detailed_df, strength_results, basic_accuracy, net_accuracy):
    """Update the persistent accuracy report CSV files"""
    try:
        accuracy_df.to_csv(accuracy_csv_path, index=False)
        detailed_df.to_csv(detailed_csv_path, index=False)
        pd.DataFrame(strength_results).to_csv(strength_csv_path, index=False)
        print(f"📄 Accuracy reports updated in: {reports_folder}")
        return reports_folder
    except Exception as e:
        print(f"Error updating accuracy reports: {e}")
        return reports_folder

def print_performance(current_price):
    """Print current performance metrics with enhanced position tracking"""
    global current_amount_usdt, long_position, short_position, initial_amount_usdt
    global long_entry_price, short_entry_price, long_stop_loss, short_stop_loss, profit_bookings
    
    if long_position > 0:
        unrealized_pnl = (current_price - long_entry_price) * long_position
        position_value = long_position * current_price / LEVERAGE
        current_portfolio_value = position_value + current_amount_usdt
        position_type = f"LONG 2X ({long_position:.6f} BTC @ ${long_entry_price:.2f})"
        print(f"   Unrealized P&L: ${unrealized_pnl / LEVERAGE:.2f}")
        print(f"   Stop Loss: ${long_stop_loss:.2f} | Distance: {current_price - long_stop_loss:.0f} points")
        
    elif short_position > 0:
        unrealized_pnl = (short_entry_price - current_price) * short_position
        current_portfolio_value = short_entry_value + (unrealized_pnl / LEVERAGE) + current_amount_usdt
        position_type = f"SHORT 2X ({short_position:.6f} BTC @ ${short_entry_price:.2f})"
        print(f"   Unrealized P&L: ${unrealized_pnl / LEVERAGE:.2f}")
        print(f"   Stop Loss: ${short_stop_loss:.2f} | Distance: {short_stop_loss - current_price:.0f} points")
        
    else:
        current_portfolio_value = current_amount_usdt
        position_type = "USDT"
    
    profit_loss = current_portfolio_value - initial_amount_usdt
    profit_percentage = (profit_loss / initial_amount_usdt) * 100
    
    print(f"\n💰 ENHANCED PORTFOLIO STATUS:")
    print(f"Initial Capital: ${initial_amount_usdt}")
    print(f"Current Value: ${current_portfolio_value:.2f}")
    print(f"P&L: ${profit_loss:.2f} ({profit_percentage:.2f}%)")
    print(f"Total Trades: {trade_count}")
    print(f"Position: {position_type}")
    print(f"Leverage: {LEVERAGE}x")
    if current_trend:
        print(f"Current Trend: {current_trend} | Profit Bookings: {profit_bookings}")

def main():
    global data, last_processed_time, signal_coords, signal_trends
    print("🤖 ENHANCED Real-time Crypto Trading Bot Starting...")
    print(f"💱 Trading Pair: {crypto_pair}")
    print(f"⏱️ Interval: 15 minutes")
    print(f"💰 Initial Capital: ${initial_amount_usdt}")
    print(f"🔄 Strategy: Long + Short with 2x Leverage")
    print(f"🛑 Stop Loss: 100 points from entry")
    print(f"💎 Profit Booking: 25% on reverse candle after 100+ point move")
    print(f"📁 Session folder: {reports_folder}")
    print("=" * 60)
    print("📊 Fetching initial data...")
    
    data = get_latest_klines()
    if data is None or len(data) == 0:
        print("❌ Failed to fetch initial data. Exiting...")
        return
    
    print(f"✅ Loaded {len(data)} historical candles")
    print(f"Latest candle: {data['Time'].iloc[-1]} - Close: ${data['Close'].iloc[-1]:.2f}")
    last_processed_time = data['Time'].iloc[-1]
    
    print("\n🔄 Starting real-time monitoring with enhanced features...")
    print("Press Ctrl+C to stop the bot")
    
    try:
        while True:
            new_data = get_latest_klines()
            if new_data is None:
                print("⚠️ Failed to fetch data, retrying...")
                time.sleep(30)
                continue
            
            current_price = new_data['Close'].iloc[-1]
            
            # LIVE MONITORING: Check stop loss first (highest priority)
            stop_loss_hit = check_stop_loss(current_price)
            if stop_loss_hit:
                print_performance(current_price)
                time.sleep(30)
                continue
            
            # LIVE MONITORING: Check for profit booking opportunities
            profit_booking_executed = check_profit_booking(current_price, new_data)
            if profit_booking_executed:
                print_performance(current_price)
            
            latest_candle_time = new_data['Time'].iloc[-1]
            if latest_candle_time > last_processed_time:
                print(f"\n🕐 New candle: {latest_candle_time} - Close: ${current_price:.2f}")
                data = new_data
                last_processed_time = latest_candle_time
                
                image_path = f"temp_candle_{latest_candle_time.strftime('%Y%m%d_%H%M%S')}.png"
                if generate_candlestick_image(data, image_path, window_size=5):
                    signal, confidence = make_prediction(image_path)
                    if signal:
                        print(f"🎯 Signal: {signal} (confidence: {confidence:.3f})")
                        signal_coords.append(latest_candle_time)
                        signal_trends.append(signal)
                        
                        # Remove consecutive signals
                        if len(signal_trends) > 1 and signal_trends[-1] == signal_trends[-2]:
                            signal_coords.pop()
                            signal_trends.pop()
                            print("🚫 Removed consecutive signal")
                        else:
                            # Execute enhanced trade with stop loss and profit booking
                            execute_trade_with_enhanced_features(signal, current_price, latest_candle_time)
                    else:
                        print(f"🔄 No strong signal (prediction: {confidence:.3f})")
                    
                    try:
                        os.remove(image_path)
                    except:
                        pass
                
                # Update accuracy reports
                if len(signal_coords) > 1:
                    strength_results, accuracy_df, detailed_df, basic_accuracy, net_accuracy = calculate_improved_accuracy(signal_coords, signal_trends, data)
                    if not accuracy_df.empty:
                        update_accuracy_reports(accuracy_df, detailed_df, strength_results, basic_accuracy, net_accuracy)
                
                print_performance(current_price)
            else:
                # Even when no new candle, check stop loss and profit booking
                if long_position > 0 or short_position > 0:
                    print(f"⏳ Monitoring position... Price: ${current_price:.2f}", end='\r')
            
            time.sleep(30)
    
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping enhanced trading bot...")
        
        # Final position closure if needed
        final_price = data['Close'].iloc[-1] if len(data) > 0 else 0
        
        # Calculate final portfolio value with enhanced features
        if long_position > 0:
            unrealized_pnl = (final_price - long_entry_price) * long_position
            final_portfolio_value = (long_position * final_price / LEVERAGE) + current_amount_usdt
            print(f"📊 Final Long Position: {long_position:.6f} BTC @ ${long_entry_price:.2f}")
            print(f"   Unrealized P&L: ${unrealized_pnl / LEVERAGE:.2f}")
            
        elif short_position > 0:
            unrealized_pnl = (short_entry_price - final_price) * short_position
            final_portfolio_value = short_entry_value + (unrealized_pnl / LEVERAGE) + current_amount_usdt
            print(f"📊 Final Short Position: {short_position:.6f} BTC @ ${short_entry_price:.2f}")
            print(f"   Unrealized P&L: ${unrealized_pnl / LEVERAGE:.2f}")
            
        else:
            final_portfolio_value = current_amount_usdt
        
        # Final updates to CSV files
        if trade_data:
            update_trading_log()
            print(f"📄 Final trading log saved: {trade_log_path}")
        
        if len(signal_coords) > 1:
            strength_results, accuracy_df, detailed_df, basic_accuracy, net_accuracy = calculate_improved_accuracy(signal_coords, signal_trends, data)
            if not accuracy_df.empty:
                update_accuracy_reports(accuracy_df, detailed_df, strength_results, basic_accuracy, net_accuracy)
                print(f"📊 Final accuracy reports saved to: {reports_folder}")
        
        final_profit_loss = final_portfolio_value - initial_amount_usdt
        final_profit_percentage = (final_profit_loss / initial_amount_usdt) * 100
        
        print(f"\n📊 FINAL ENHANCED PERFORMANCE SUMMARY:")
        print(f"=" * 50)
        print(f"Initial Capital: ${initial_amount_usdt}")
        print(f"Final Portfolio Value: ${final_portfolio_value:.2f}")
        print(f"Total Profit/Loss: ${final_profit_loss:.2f}")
        print(f"Total Return: {final_profit_percentage:.2f}%")
        print(f"Total Trades Executed: {trade_count}")
        print(f"Leverage Used: {LEVERAGE}x")
        
        # Enhanced statistics
        if trade_data:
            trade_df = pd.DataFrame(trade_data)
            long_trades = trade_df[trade_df['Action'].str.contains('LONG', na=False)]
            short_trades = trade_df[trade_df['Action'].str.contains('SHORT', na=False)]
            stop_losses = trade_df[trade_df['Action'].str.contains('STOP_LOSS', na=False)]
            profit_books = trade_df[trade_df['Action'].str.contains('PROFIT_BOOK', na=False)]
            
            print(f"Long Trades: {len(long_trades)}")
            print(f"Short Trades: {len(short_trades)}")
            print(f"Stop Losses Hit: {len(stop_losses)}")
            print(f"Profit Bookings: {len(profit_books)}")
        
        print(f"📁 All enhanced data saved in folder: {reports_folder}")
        print("Thanks for using the Enhanced Trading Bot with Stop Loss & Profit Booking! 🚀💎")

if __name__ == "__main__":
    main()