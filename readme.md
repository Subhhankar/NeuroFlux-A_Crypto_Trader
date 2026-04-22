# 🤖 Enhanced Real-time Crypto Trading Bot

An advanced cryptocurrency trading bot with AI-powered trend prediction, risk management, and automated trading on Binance.

## 🚀 Features

### Core Trading Features
- ✅ **AI-Powered Predictions**: Uses trained neural network model for trend analysis
- ✅ **15-Minute Timeframe**: Stable signals with reduced noise
- ✅ **2x Leverage Trading**: Amplified position sizing for better capital efficiency
- ✅ **Long & Short Positions**: Full bidirectional trading capability
- ✅ **Real-time Monitoring**: Live price tracking every 30 seconds

### Risk Management
- 🛑 **Stop Loss Protection**: Automatic 100-point stop loss from entry
- 💎 **Smart Profit Booking**: 25% profit taking on reverse candle signals
- 📊 **Position Tracking**: Detailed monitoring of open positions
- ⚡ **Live Calculations**: No lag in stop loss and profit booking checks

### Advanced Features
- 📈 **Trend Following**: Automatically follows model signals
- 🔄 **Position Management**: Seamless transition between long/short
- 📝 **Comprehensive Logging**: All trades saved to CSV files
- 📊 **Accuracy Reports**: Detailed performance analytics
- 💰 **Portfolio Tracking**: Real-time P&L calculations

---

## 📋 Requirements

### System Requirements
- Python 3.8+
- GPU (optional but recommended for faster processing)
- Internet connection for live data

### Required Libraries
```bash
pip install pandas matplotlib mplfinance TA-Lib tensorflow keras binance-python numpy requests --break-system-packages
```

### Required Files
- `trend_classification_model.h5` - Trained neural network model (must be in same directory)

---

## ⚙️ Configuration

### Trading Parameters
```python
symbol = "BTCUSDT"                          # Trading pair
interval = Client.KLINE_INTERVAL_15MINUTE   # 15-minute candles
initial_amount_usdt = 1000                  # Starting capital
LEVERAGE = 2                                # 2x leverage
```

### Risk Management Settings
```python
STOP_LOSS_POINTS = 100          # Stop loss distance from entry
PROFIT_BOOKING_POINTS = 100     # Minimum move before profit booking
PROFIT_BOOKING_PERCENTAGE = 0.25 # 25% of position
confidence_threshold = 0.8       # 80% minimum confidence for signals
```

---

## 🎯 How It Works

### 1. **Signal Generation**
- Fetches latest 15-minute candlestick data from Binance
- Generates candlestick chart image with technical indicators
- AI model analyzes the image and predicts trend direction
- Only trades when confidence ≥ 80%

### 2. **Trade Execution**

#### **UP Signal (Bullish)**
1. Closes any existing SHORT position
2. Opens LONG position with 2x leverage
3. Sets stop loss 100 points below entry
4. Monitors for profit booking opportunities

#### **DOWN Signal (Bearish)**
1. Closes any existing LONG position
2. Opens SHORT position with 2x leverage
3. Sets stop loss 100 points above entry
4. Monitors for profit booking opportunities

### 3. **Risk Management**

#### **Stop Loss (Automatic)**
- **LONG**: Triggered if price drops 100 points below entry
- **SHORT**: Triggered if price rises 100 points above entry
- Checked every 30 seconds in real-time

#### **Profit Booking (Smart)**
- **LONG Position**: Books 25% profit when RED candle forms after 100+ point move UP
- **SHORT Position**: Books 25% profit when GREEN candle forms after 100+ point move DOWN
- Remaining 75% continues in the trade

### 4. **Position Monitoring**
```
Every 30 seconds:
├── Check stop loss conditions
├── Check profit booking conditions
└── Update portfolio value

Every 15 minutes (new candle):
├── Generate new prediction
├── Execute trades if high confidence
└── Update all reports
```

---

## 🎮 Usage

### Basic Usage
```bash
python enhanced_trading_bot.py
```

### During Operation
- Bot will display live updates every 30 seconds
- New candle notifications every 15 minutes
- Trade executions shown with full details
- Portfolio status updated continuously

### Stopping the Bot
- Press `Ctrl+C` to stop gracefully
- Final reports will be generated automatically
- All data saved to session folder

---

## 📊 Output Files

Each trading session creates a timestamped folder with:

### Trading Logs
- `BTC_USDT_trading_log.csv` - Complete trade history with timestamps

### Accuracy Reports
- `BTC_USDT_accuracy_data.csv` - Signal accuracy statistics
- `BTC_USDT_detailed_analysis.csv` - Detailed price movement analysis
- `BTC_USDT_strength_analysis.csv` - Performance by signal strength

### Folder Structure
```
realtime_trading_session_20250808_114136/
├── BTC_USDT_trading_log.csv
├── BTC_USDT_accuracy_data.csv
├── BTC_USDT_detailed_analysis.csv
└── BTC_USDT_strength_analysis.csv
```

---

## 📈 Understanding Confidence

### Model Prediction
The neural network outputs a probability between 0.0 and 1.0:
- **0.0 to 0.2** = Strong DOWN signal
- **0.2 to 0.8** = Uncertain (no trade)
- **0.8 to 1.0** = Strong UP signal

### Confidence Calculation
```python
# UP Signal
prediction = 0.85
confidence = 0.85  # 85% confident it's UP

# DOWN Signal  
prediction = 0.15
confidence = 1 - 0.15 = 0.85  # 85% confident it's DOWN
```

Both UP and DOWN signals require **≥80% confidence** to trade.

---

## 💡 Trading Strategy Example

### Scenario: LONG Position
```
1. Signal: UP (confidence: 85%)
   Entry Price: $95,000
   Position Size: 0.0211 BTC (2x leveraged from $1000)
   Stop Loss: $94,900

2. Market moves up to $95,300 (300 points)
   RED candle forms → Book 25% profit
   Remaining: 0.0158 BTC in position

3. Market continues to $95,500
   Another RED candle → Book another 25%
   Remaining: 0.0119 BTC in position

4. Market reverses to $94,900
   Stop loss triggered → Close remaining position
```

---

## 🔧 Customization

### Change Timeframe
```python
# Options available:
interval = Client.KLINE_INTERVAL_1MINUTE   # 1-minute
interval = Client.KLINE_INTERVAL_5MINUTE   # 5-minute
interval = Client.KLINE_INTERVAL_15MINUTE  # 15-minute (current)
interval = Client.KLINE_INTERVAL_1HOUR     # 1-hour
```

### Adjust Leverage
```python
LEVERAGE = 2   # Change to 1 (no leverage) or 3, 5, 10 (higher risk)
```

### Modify Stop Loss
```python
long_stop_loss = price - 100   # Change 100 to desired points
short_stop_loss = price + 100  # Change 100 to desired points
```

### Adjust Confidence Threshold
```python
confidence_threshold = 0.8  # Lower for more signals (0.7)
                           # Higher for fewer signals (0.9)
```

---

## ⚠️ Important Notes

### Risk Warnings
- **Paper Trading**: This bot executes simulated trades (no real money)
- **Leverage Risk**: 2x leverage amplifies both gains and losses
- **Market Risk**: Crypto markets are highly volatile
- **Model Risk**: AI predictions are not guaranteed to be accurate

### Best Practices
- ✅ Start with small capital to test
- ✅ Monitor the bot regularly
- ✅ Review trading logs and accuracy reports
- ✅ Adjust parameters based on performance
- ✅ Use proper risk management

### Limitations
- Requires `trend_classification_model.h5` file
- No API keys needed (uses public Binance data)
- Simulated trading only (not connected to real trading)
- Stop loss based on price points, not percentage

---

## 📞 Support & Troubleshooting

### Common Issues

**Model file not found:**
```
⚠️ Model file 'trend_classification_model.h5' not found!
```
→ Ensure the model file is in the same directory as the script

**GPU configuration warning:**
```
GPU configuration warning: ...
```
→ This is normal, bot will use CPU if GPU unavailable

**Failed to fetch data:**
```
⚠️ Failed to fetch data, retrying...
```
→ Check internet connection, Binance may be temporarily unavailable

---

## 📜 License

This project is for educational purposes only. Use at your own risk.

---

## 🎯 Performance Metrics

The bot tracks and reports:
- ✅ Total trades executed
- ✅ Long vs Short trade count
- ✅ Stop losses hit
- ✅ Profit bookings executed
- ✅ Total P&L and ROI percentage
- ✅ Signal accuracy statistics
- ✅ Average confidence levels

---

## 🚀 Quick Start Guide

1. **Install dependencies**
```bash
pip install pandas matplotlib mplfinance TA-Lib tensorflow keras binance-python numpy requests --break-system-packages
```

2. **Place model file**
```bash
# Ensure trend_classification_model.h5 is in the same directory
```

3. **Run the bot**
```bash
python enhanced_trading_bot.py
```

4. **Monitor output**
```
🤖 ENHANCED Real-time Crypto Trading Bot Starting...
💱 Trading Pair: BTC/USDT
⏱️ Interval: 15 minutes
💰 Initial Capital: $1000
🔄 Strategy: Long + Short with 2x Leverage
```

5. **Stop gracefully**
```
Press Ctrl+C to stop and see final report
```

---

## 📚 Additional Resources

- [Binance API Documentation](https://binance-docs.github.io/apidocs/)
- [TA-Lib Documentation](https://mrjbq7.github.io/ta-lib/)
- [TensorFlow/Keras Documentation](https://www.tensorflow.org/)

---

**Happy Trading! 🚀💰**

*Remember: Past performance does not guarantee future results. Always trade responsibly.*