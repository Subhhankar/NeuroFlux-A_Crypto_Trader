import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import mplfinance as mpf
import talib
import os
from datetime import datetime, timedelta
import pickle
import xgboost as xgb
from tensorflow.keras.utils import load_img, img_to_array
from keras.models import load_model
import warnings
warnings.filterwarnings('ignore')

# Configuration for fast processing
plt.ioff()

class MLTradingBacktester:
    def __init__(self, initial_capital=100000, data_file=None):
        # Trading configuration
        self.initial_capital = initial_capital
        self.portfolio_value = initial_capital
        self.current_position = "CASH"  # CASH, LONG, SHORT, PENDING_LONG, PENDING_SHORT
        self.position_size = 0
        self.entry_price = 0
        self.current_target_price = 0
        self.current_stop_loss = 0
        self.target_active = False
        self.stop_loss_active = False
        self.avoid_weak_signals = True
        
        # NEW: Pending trade tracking
        self.pending_signal = None
        self.pending_confidence = 0
        self.pending_target_price = 0
        self.pending_stop_price = 0
        self.pending_entry_threshold = 0  # 60-70% of target price movement
        self.pending_signal_price = 0
        self.pending_timestamp = None
        self.pending_predicted_high = 0
        self.pending_predicted_low = 0
        
        # NEW: Maximum movement tracking
        self.max_favorable_movement = 0
        self.max_adverse_movement = 0
        
        # Statistics tracking
        self.trade_count = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.gross_winning_amount = 0
        self.gross_losing_amount = 0
        self.max_drawdown = 0
        self.peak_portfolio_value = initial_capital
        
        # Target achievement tracking
        self.target_hits = 0
        self.stop_hits = 0
        self.signal_reversal_exits = 0
        self.target_achievement_distances = []  # Distance from target when achieved
        
        # Consecutive wins/losses tracking
        self.consecutive_wins = 0
        self.consecutive_losses = 0
        self.max_consecutive_wins = 0
        self.max_consecutive_losses = 0
        self.current_streak = 0  # Positive for wins, negative for losses
        self.win_loss_sequence = []  # Track sequence of wins/losses
        
        # Data storage
        self.trade_data = []
        self.ml_predictions_data = []
        self.portfolio_history = []
        
        # Previous trend tracking
        self.previous_trend_duration = 0
        self.previous_trend_high = 0
        self.previous_trend_low = 0
        self.last_trend_start_index = None
        self.last_trend_type = None
        
        # Signal tracking
        self.signal_coords = []
        self.signal_trends = []
        
        # Current trade tracking
        self.current_trade_record = None
        
        # NEW: Statistics for avoided trades
        self.avoided_trades = 0
        self.avoided_uptrend_lower_target = 0
        self.avoided_downtrend_higher_target = 0
        
        # Load historical data
        self.data = None
        if data_file:
            self.load_data(data_file)
        
        # Model placeholders
        self.xgb_model = None
        self.cnn_model = None
    
    def load_data(self, file_path):
        """Load historical OHLCV data"""
        try:
            if file_path.endswith('.csv'):
                self.data = pd.read_csv(file_path)
            else:
                raise ValueError("Currently supports only CSV files")
            
            # Ensure proper column names and data types
            required_cols = ['Time', 'Open', 'High', 'Low', 'Close', 'Volume']
            if not all(col in self.data.columns for col in required_cols):
                # Try alternative column names
                col_mapping = {
                    'timestamp': 'Time', 'datetime': 'Time', 'date': 'Time',
                    'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'
                }
                self.data = self.data.rename(columns=col_mapping)
            
            # Convert timestamp to datetime
            self.data['Time'] = pd.to_datetime(self.data['Time'])
            
            # Ensure numeric columns
            numeric_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
            for col in numeric_cols:
                self.data[col] = pd.to_numeric(self.data[col], errors='coerce')
            
            # Sort by time
            self.data = self.data.sort_values('Time').reset_index(drop=True)
            
            print(f"✅ Loaded {len(self.data)} historical candles")
            print(f"Data range: {self.data['Time'].min()} to {self.data['Time'].max()}")
            
        except Exception as e:
            print(f"❌ Error loading data: {e}")
            self.data = None
    
    def load_models(self):
        """Load XGBoost and CNN models"""
        # Load XGBoost model
        try:
            if os.path.exists("optimized_xgb_tp_sl_predictor.pkl"):
                with open("optimized_xgb_tp_sl_predictor.pkl", 'rb') as f:
                    self.xgb_model = pickle.load(f)
                print("✅ XGBoost model loaded")
            else:
                print("⚠️ XGBoost model not found, will use default targets")
        except Exception as e:
            print(f"⚠️ Error loading XGBoost model: {e}")
        
        # Load CNN model
        try:
            if os.path.exists("trend_classification_model.h5"):
                self.cnn_model = load_model("trend_classification_model.h5")
                print("✅ CNN model loaded")
            else:
                print("❌ CNN model not found - required for signal generation")
                return False
        except Exception as e:
            print(f"❌ Error loading CNN model: {e}")
            return False
        
        return True
    
    def calculate_hurst_volatility(self, prices, window_size):
        """Calculate Hurst exponent for volatility measure"""
        try:
            if len(prices) < window_size or window_size < 10:
                return 0.5
            
            price_window = prices[-window_size:]
            returns = np.diff(np.log(price_window))
            volatility = np.std(returns)
            normalized_vol = min(volatility * 100, 1.0)
            return normalized_vol
        except:
            return 0.5
    
    def calculate_obv(self, closes, volumes):
        """Calculate On-Balance Volume"""
        try:
            if len(closes) < 2:
                return 0
            
            obv = [0]
            for i in range(1, len(closes)):
                if closes[i] > closes[i-1]:
                    obv.append(obv[-1] + volumes[i])
                elif closes[i] < closes[i-1]:
                    obv.append(obv[-1] - volumes[i])
                else:
                    obv.append(obv[-1])
            
            return obv[-1]
        except:
            return 0
    
    def prepare_ml_features(self, signal_direction, signal_confidence, entry_price, window_data, window_size):
        """Prepare features for XGBoost model prediction"""
        try:
            if len(window_data) < window_size:
                return None
            
            closes = window_data['Close'].values
            highs = window_data['High'].values
            lows = window_data['Low'].values
            volumes = window_data['Volume'].values
            
            # Calculate technical indicators
            rsi_period = min(window_size, len(closes) - 1)
            atr_period = min(window_size, len(closes) - 1)
            
            rsi = talib.RSI(closes, timeperiod=max(2, rsi_period))[-1] if rsi_period > 1 else 50
            sma = talib.SMA(closes, timeperiod=window_size)[-1]
            ema = talib.EMA(closes, timeperiod=window_size)[-1]
            volume_ma = np.mean(volumes)
            atr = talib.ATR(highs, lows, closes, timeperiod=max(2, atr_period))[-1] if atr_period > 1 else np.std(closes)
            std_dev = np.std(closes)
            hurst_volatility = self.calculate_hurst_volatility(closes, window_size)
            obv = self.calculate_obv(closes, volumes)
            
            # Distance calculations
            distance_to_prev_high_abs = abs(entry_price - self.previous_trend_high) if self.previous_trend_high > 0 else 0
            distance_to_prev_low_abs = abs(entry_price - self.previous_trend_low) if self.previous_trend_low > 0 else 0
            
            features = {
                'signal_direction': 1 if signal_direction in ['STRONG_U', 'WEAK_U'] else 0,
                'signal_confidence': signal_confidence,
                'entry_price': entry_price,
                'rsi': rsi if not np.isnan(rsi) else 50,
                'sma': sma if not np.isnan(sma) else entry_price,
                'ema': ema if not np.isnan(ema) else entry_price,
                'volume_ma': volume_ma if not np.isnan(volume_ma) else np.mean(volumes),
                'atr': atr if not np.isnan(atr) else std_dev,
                'std_dev': std_dev if not np.isnan(std_dev) else 0,
                'hurst_volatility': hurst_volatility,
                'window_size_used': window_size,
                'previous_trend_high': self.previous_trend_high,
                'previous_trend_low': self.previous_trend_low,
                'distance_to_prev_high_abs': distance_to_prev_high_abs,
                'distance_to_prev_low_abs': distance_to_prev_low_abs,
                'OBV': obv if not np.isnan(obv) else 0,
                'Volume': volumes[-1] if len(volumes) > 0 else 0
            }
            
            return features
        except Exception as e:
            print(f"Error preparing ML features: {e}")
            return None
    
    def predict_target_and_stoploss(self, features):
        """Use XGBoost model to predict target price and stop loss"""
        try:
            if self.xgb_model is None or features is None:
                return None, None
            
            feature_df = pd.DataFrame([features])
            prediction = self.xgb_model.predict(feature_df)
            
            if hasattr(prediction, 'shape'):
                if len(prediction.shape) > 1 and prediction.shape[1] >= 2:
                    highest_price = float(prediction[0][0])
                    lowest_price = float(prediction[0][1])
                elif len(prediction.shape) == 1 and len(prediction) >= 2:
                    highest_price = float(prediction[0])
                    lowest_price = float(prediction[1])
                else:
                    val = float(prediction[0])
                    highest_price = val
                    lowest_price = val
            else:
                val = float(prediction)
                highest_price = val
                lowest_price = val
            
            return highest_price, lowest_price
        except Exception as e:
            print(f"Error making XGBoost prediction: {e}")
            return None, None
    
    def generate_candlestick_image(self, window_data, output_path):
        """Generate candlestick chart image"""
        try:
            if len(window_data) < 5:
                return False
            
            window = window_data.copy()
            window = window.set_index('Time')
            
            if len(window_data) >= 20:
                sma_data = talib.SMA(window_data['Close'].values, timeperiod=20)
                if len(sma_data) >= len(window):
                    window['SMA'] = sma_data[-len(window):]
                    ap = [mpf.make_addplot(window['SMA'], color='blue', secondary_y=False)]
                else:
                    ap = []
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
    
    def make_prediction(self, image_path):
        """Make prediction using CNN model"""
        try:
            if self.cnn_model is None:
                return None, None
            
            image = load_img(image_path, color_mode='rgb', interpolation="bilinear", target_size=(150, 150))
            image = img_to_array(image) / 255.0
            X = np.array([image])
            prediction = self.cnn_model.predict(X, verbose=0)[0][0]
            
            # Enhanced thresholds for Long/Short strategy
            strong_confidence_threshold = 0.85
            weak_confidence_threshold = 0.65
            
            if prediction >= strong_confidence_threshold:
                return "STRONG_U", prediction
            elif prediction <= (1 - strong_confidence_threshold):
                return "STRONG_D", 1 - prediction
            elif prediction >= weak_confidence_threshold:
                return "WEAK_U", prediction
            elif prediction <= (1 - weak_confidence_threshold):
                return "WEAK_D", 1 - prediction
            else:
                return None, prediction
                
        except Exception as e:
            print(f"Error making prediction: {e}")
            return None, None
    
    def update_previous_trend_info(self, signal_type, current_index):
        """Update previous trend information"""
        if self.last_trend_start_index is not None and self.last_trend_type is not None:
            # Calculate duration of previous trend in candles
            self.previous_trend_duration = max(1, current_index - self.last_trend_start_index)
            
            # Update previous trend high/low
            if current_index > self.previous_trend_duration:
                trend_start = max(0, current_index - self.previous_trend_duration)
                trend_data = self.data.iloc[trend_start:current_index]
                self.previous_trend_high = trend_data['High'].max()
                self.previous_trend_low = trend_data['Low'].min()
        
        self.last_trend_start_index = current_index
        self.last_trend_type = signal_type
    
    def validate_target_direction(self, signal, predicted_high, predicted_low, entry_price):
        """NEW: Validate that predicted target aligns with signal direction"""
        if signal in ['STRONG_U', 'WEAK_U']:
            # Uptrend: target should be higher than entry price
            target_price = predicted_high
            if target_price <= entry_price:
                self.avoided_trades += 1
                self.avoided_uptrend_lower_target += 1
                print(f"  → AVOIDED: Uptrend signal but target ${target_price:.2f} <= entry ${entry_price:.2f}")
                return False, 0
            return True, target_price
        else:
            # Downtrend: target should be lower than entry price
            target_price = predicted_low
            if target_price >= entry_price:
                self.avoided_trades += 1
                self.avoided_downtrend_higher_target += 1
                print(f"  → AVOIDED: Downtrend signal but target ${target_price:.2f} >= entry ${entry_price:.2f}")
                return False, 0
            return True, target_price
    
    def calculate_entry_threshold(self, signal, entry_price, target_price):
        """NEW: Calculate the 60-70% threshold price for trade execution"""
        # Use 65% as the middle point between 60-70%
        threshold_percentage = 0.65
        
        if signal in ['STRONG_U', 'WEAK_U']:
            # For uptrend, we want price to move 65% towards target before entering
            price_diff = target_price - entry_price
            threshold_price = entry_price + (price_diff * threshold_percentage)
        else:
            # For downtrend, we want price to move 65% towards target before entering
            price_diff = entry_price - target_price
            threshold_price = entry_price - (price_diff * threshold_percentage)
        
        return threshold_price
    
    def calculate_target_stop_percentages(self, entry_price, target_price, stop_price, signal_direction):
        """Calculate target and stop loss percentages and trigger prices - FIXED VERSION"""
        
        # FIXED: Set target and stop prices based on signal direction and ML predictions
        if signal_direction in ['STRONG_U', 'WEAK_U']:  # LONG position
            # For LONG: target should be higher than entry, stop should be lower
            final_target_price = max(target_price, entry_price * 1.005)  # Ensure target is above entry
            final_stop_price = min(stop_price, entry_price * 0.995)      # Ensure stop is below entry
            
            target_percentage = ((final_target_price - entry_price) / entry_price) * 100
            stop_percentage = ((entry_price - final_stop_price) / entry_price) * 100
            
        else:  # SHORT position (STRONG_D, WEAK_D)
            # For SHORT: target should be lower than entry, stop should be higher  
            final_target_price = min(target_price, entry_price * 0.995)  # Ensure target is below entry
            final_stop_price = max(stop_price, entry_price * 1.005)      # Ensure stop is above entry
            
            target_percentage = ((entry_price - final_target_price) / entry_price) * 100
            stop_percentage = ((final_stop_price - entry_price) / entry_price) * 100
        
        return final_target_price, final_stop_price, target_percentage, stop_percentage
    
    def update_consecutive_stats(self, is_win):
        """Update consecutive wins/losses statistics"""
        self.win_loss_sequence.append('W' if is_win else 'L')
        
        if is_win:
            if self.current_streak >= 0:
                self.current_streak += 1
            else:
                self.current_streak = 1
            self.consecutive_wins = self.current_streak
            self.max_consecutive_wins = max(self.max_consecutive_wins, self.consecutive_wins)
        else:
            if self.current_streak <= 0:
                self.current_streak -= 1
            else:
                self.current_streak = -1
            self.consecutive_losses = abs(self.current_streak)
            self.max_consecutive_losses = max(self.max_consecutive_losses, self.consecutive_losses)
    
    def update_max_movements(self, current_price):
        """NEW: Update maximum favorable and adverse movements during a trade"""
        if self.current_position == "CASH" or not self.entry_price:
            return
        
        if self.current_position == "LONG":
            # For LONG: favorable is upward, adverse is downward
            current_favorable = current_price - self.entry_price
            current_adverse = self.entry_price - current_price
        else:  # SHORT
            # For SHORT: favorable is downward, adverse is upward
            current_favorable = self.entry_price - current_price
            current_adverse = current_price - self.entry_price
        
        # Update maximums
        if current_favorable > self.max_favorable_movement:
            self.max_favorable_movement = current_favorable
        
        if current_adverse > self.max_adverse_movement:
            self.max_adverse_movement = current_adverse
    
    def check_pending_entry(self, current_row):
        """NEW: Check if pending trade should be executed"""
        if self.current_position not in ["PENDING_LONG", "PENDING_SHORT"]:
            return False
        
        current_price = current_row['Close']
        high_price = current_row['High']
        low_price = current_row['Low']
        
        if self.current_position == "PENDING_LONG":
            # For pending LONG, check if price reached the entry threshold (moving towards target)
            if high_price >= self.pending_entry_threshold:
                return True
        elif self.current_position == "PENDING_SHORT":
            # For pending SHORT, check if price reached the entry threshold (moving towards target)
            if low_price <= self.pending_entry_threshold:
                return True
        
        return False
    
    def check_exit_conditions(self, current_row):
        """Check if current candle triggers any exit conditions - FIXED VERSION"""
        if self.current_position == "CASH" or self.current_position.startswith("PENDING"):
            return None, None, 0
        
        high_price = current_row['High']
        low_price = current_row['Low']
        close_price = current_row['Close']
        
        if self.current_position == "LONG":
            # Check if target was hit (using high of the candle)
            if self.target_active and high_price >= self.current_target_price:
                distance_to_target = abs(self.current_target_price - high_price)
                return "TARGET", self.current_target_price, distance_to_target
            
            # Check if stop loss was hit (using low of the candle)
            if self.stop_loss_active and low_price <= self.current_stop_loss:
                return "STOP_LOSS", self.current_stop_loss, 0
        
        elif self.current_position == "SHORT":
            # Check if target was hit (using low of the candle)
            if self.target_active and low_price <= self.current_target_price:
                distance_to_target = abs(self.current_target_price - low_price)
                return "TARGET", self.current_target_price, distance_to_target
            
            # Check if stop loss was hit (using high of the candle)
            if self.stop_loss_active and high_price >= self.current_stop_loss:
                return "STOP_LOSS", self.current_stop_loss, 0
        
        return None, None, 0
    
    def execute_backtest(self):
        """Execute the full backtest"""
        if self.data is None:
            print("❌ No data loaded for backtesting")
            return
        
        if not self.load_models():
            print("❌ Required models not loaded")
            return
        
        print(f"\n🚀 Starting Enhanced ML Trading Backtest")
        print(f"Data points: {len(self.data)}")
        print(f"Initial capital: ${self.initial_capital:,}")
        print("New Features: Target validation + Delayed entry at 60-70% target movement")
        print("=" * 80)
        
        # Process each candle
        for i in range(5, len(self.data)):
            current_row = self.data.iloc[i]
            current_time = current_row['Time']
            current_price = current_row['Close']
            
            # Update maximum movements if in a trade
            if self.current_position in ["LONG", "SHORT"]:
                self.update_max_movements(current_price)
            
            # Check pending trade execution
            if self.current_position.startswith("PENDING"):
                if self.check_pending_entry(current_row):
                    # Execute the pending trade
                    actual_entry_price = self.pending_entry_threshold
                    self.execute_pending_trade(actual_entry_price, current_time)
            
            # Check exit conditions for active positions
            if self.current_position in ["LONG", "SHORT"]:
                exit_type, exit_price, distance_to_target = self.check_exit_conditions(current_row)
                if exit_type:
                    self.close_position(exit_price, current_time, exit_type, distance_to_target)
            
            # Update portfolio history
            if self.current_position == "LONG":
                current_value = self.position_size * current_price
            elif self.current_position == "SHORT":
                # FIXED: Correct calculation for SHORT position value
                unrealized_pnl = self.position_size * (self.entry_price - current_price)
                current_value = self.portfolio_value + unrealized_pnl
            else:
                current_value = self.portfolio_value
            
            self.portfolio_history.append({
                'timestamp': current_time,
                'portfolio_value': current_value,
                'position': self.current_position,
                'price': current_price
            })
            
            # Only generate new signals if we're not in any position or pending
            if self.current_position == "CASH":
                # Generate signal
                window_data = self.data.iloc[i-4:i+1]  # 5 candles window
                temp_image = f"temp_backtest_{i}.png"
                
                if self.generate_candlestick_image(window_data, temp_image):
                    signal, confidence = self.make_prediction(temp_image)
                    
                    # Clean up temp image
                    try:
                        os.remove(temp_image)
                    except:
                        pass
                    
                    if signal:
                        # Check if this is a new signal (not consecutive)
                        if self.avoid_weak_signals and signal in ['WEAK_U', 'WEAK_D']:
                            print(f"  → SKIPPED: Weak signal {signal} at ${current_price:.2f} (confidence: {confidence:.3f})")
                            continue
                        if len(self.signal_trends) == 0 or self.signal_trends[-1] != signal:
                            self.signal_coords.append(i)
                            self.signal_trends.append(signal)
                            
                            # Process trade setup with validation
                            self.process_trade_signal(signal, confidence, current_price, current_time, i)
        
        # Final cleanup
        self.finalize_backtest()
    
    def process_trade_signal(self, signal, confidence, price, timestamp, data_index):
        """NEW: Process trade signal with target validation and pending entry setup"""        
        # Update previous trend info
        self.update_previous_trend_info(signal, data_index)
        
        # Determine window size
        window_size = max(6, self.previous_trend_duration) if self.previous_trend_duration > 0 else 6
        
        # Use ML predictions if we have previous trend data
        use_ml_predictions = len(self.signal_coords) > 1
        
        if use_ml_predictions:
            window_data = self.data.iloc[max(0, data_index-window_size):data_index+1]
            features = self.prepare_ml_features(signal, confidence, price, window_data, window_size)
            
            if features is not None:
                predicted_high, predicted_low = self.predict_target_and_stoploss(features)
                
                if predicted_high is not None and predicted_low is not None:
                    # NEW: Validate target direction
                    is_valid, target_price = self.validate_target_direction(signal, predicted_high, predicted_low, price)
                    
                    if not is_valid:
                        return  # Skip this trade
                    
                    # Store ML prediction
                    ml_record = {
                        'timestamp': timestamp,
                        'signal': signal,
                        'confidence': confidence,
                        'entry_price': price,
                        'predicted_high': predicted_high,
                        'predicted_low': predicted_low,
                        'window_size': window_size,
                        'target_valid': True,
                        **features
                    }
                    self.ml_predictions_data.append(ml_record)
                else:
                    predicted_high, predicted_low = price * 1.03, price * 0.97
                    target_price = predicted_high if signal in ['STRONG_U', 'WEAK_U'] else predicted_low
            else:
                predicted_high, predicted_low = price * 1.03, price * 0.97
                target_price = predicted_high if signal in ['STRONG_U', 'WEAK_U'] else predicted_low
        else:
            predicted_high, predicted_low = price * 1.02, price * 0.98
            target_price = predicted_high if signal in ['STRONG_U', 'WEAK_U'] else predicted_low
        
        # NEW: Calculate entry threshold (60-70% of target movement)
        entry_threshold = self.calculate_entry_threshold(signal, price, target_price)
        
        # Setup pending trade
        self.setup_pending_trade(signal, confidence, price, timestamp, predicted_high, predicted_low, entry_threshold)
    
    def setup_pending_trade(self, signal, confidence, signal_price, timestamp, predicted_high, predicted_low, entry_threshold):
        """NEW: Setup a pending trade that waits for 60-70% target movement"""
        
        if signal in ['STRONG_U', 'WEAK_U']:
            self.current_position = "PENDING_LONG"
        else:
            self.current_position = "PENDING_SHORT"
        
        # Store pending trade information
        self.pending_signal = signal
        self.pending_confidence = confidence
        self.pending_signal_price = signal_price
        self.pending_target_price = predicted_high if signal in ['STRONG_U', 'WEAK_U'] else predicted_low
        self.pending_stop_price = predicted_low if signal in ['STRONG_U', 'WEAK_U'] else predicted_high
        self.pending_entry_threshold = entry_threshold
        self.pending_timestamp = timestamp
        self.pending_predicted_high = predicted_high
        self.pending_predicted_low = predicted_low
        
        print(f"PENDING {self.current_position.split('_')[1]}: Signal @ ${signal_price:.2f} | Entry when price hits ${entry_threshold:.2f}")