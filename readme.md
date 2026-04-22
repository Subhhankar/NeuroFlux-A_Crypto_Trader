# ⚡ Neuroflux — A Crypto Trader

> A deep learning–powered algorithmic trading system that reads candlestick chart images to predict market trends and execute real-time or backtested trades on crypto pairs.

---

## 📌 Overview

Neuroflux combines **computer vision** and **machine learning** to trade cryptocurrency. Instead of relying solely on raw price indicators, the system renders candlestick charts as images and feeds them into a Convolutional Neural Network (CNN) to classify market trends. An XGBoost model then predicts optimal take-profit and stop-loss levels. The result is a fully automated pipeline — from raw OHLCV data to live Binance trade execution.

---

## 🧠 How It Works

```
Raw OHLCV Data
      │
      ▼
Candlestick Pattern Detection (TA-Lib)
      │
      ▼
Chart Image Generation (mplfinance)
      │
      ▼
CNN Trend Classification (uptrend / downtrend)
      │
      ▼
XGBoost Target & Stop-Loss Prediction
      │
      ▼
Trade Execution (Live via Binance API / Backtester)
```

---

## 🗂️ Project Structure

```
neuroflux/
│
├── patter_genaration.py      # Generates labeled candlestick chart images for training
├── model.py                  # Trains the CNN image classification model
├── transformer.ipynb         # Trains the XGBoost TP/SL predictor (Jupyter notebook)
├── main.py                   # Live trading bot (connects to Binance real-time)
└── backtest.py               # Full historical backtesting engine
```

---

## 🔧 Key Components

### 1. `patter_genaration.py` — Training Data Generator
- Reads 15-minute EURUSD OHLCV data from a CSV file.
- Applies a 20-period SMA and slides a **5-candle window** across the dataset.
- Detects any of **61 TA-Lib candlestick patterns** within each window.
- Labels each detected pattern as `uptrend` or `downtrend` based on the close price relative to the SMA.
- Saves rendered candlestick chart images (with SMA overlay) into class-labelled folders.

### 2. `model.py` — CNN Trend Classifier
- Splits the image dataset into **Train / Val / Test** (70% / 10% / 20%).
- Trains a Sequential CNN on 150×150 RGB chart images:
  - 3× Conv2D + MaxPooling blocks
  - Dense (512) + Dropout (0.5)
  - Sigmoid output for binary classification
- Optimizer: Adam (lr = 0.0003), Loss: Binary Cross-Entropy
- Outputs training curves, confusion matrix, classification report, and ROC-AUC plot.
- Saves the trained model as `chart_classification_model.h5`.

### 3. `transformer.ipynb` — XGBoost TP/SL Predictor
- Trains an XGBoost regressor to predict **Take-Profit (high)** and **Stop-Loss (low)** price targets.
- Uses technical features from historical windows (Hurst exponent, OBV, ATR, trend duration, etc.).
- Saved as `optimized_xgb_tp_sl_predictor.pkl`.

### 4. `main.py` — Live Trading Bot
- Connects to the **Binance API** and polls BTC/USDT 15-minute klines every 30 seconds.
- On each new candle, generates a candlestick chart image and runs CNN inference.
- Executes **Long or Short** trades with **2× leverage** when confidence ≥ 80%.
- Features:
  - Automatic **stop-loss** (100 points from entry)
  - **Profit booking** (25% position reduction on reverse candle after 100+ point move)
  - Consecutive signal filtering (avoids duplicate signals)
  - Session-based CSV reports (accuracy, detailed analysis, trade log)

### 5. `backtest.py` — Historical Backtester
- Replays historical OHLCV data, generating signals using the same CNN + XGBoost pipeline.
- Implements a **pending entry** mechanism: enters at 60–70% of the predicted target movement rather than at the signal candle.
- Tracks full statistics: win rate, max drawdown, consecutive wins/losses, target hits, stop hits, and avoided trades.
- Outputs detailed trade records and portfolio history.

---

## ⚙️ Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/neuroflux.git
cd neuroflux

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install tensorflow keras xgboost scikit-learn pandas numpy matplotlib mplfinance TA-Lib python-binance splitfolders
```

> **Note:** TA-Lib requires a pre-built binary. On Windows, download the appropriate `.whl` from [here](https://www.lfd.uci.edu/~gohlke/pythonlibs/#ta-lib). On Linux/macOS, install via `brew install ta-lib` or the system package manager first.

---

## 🚀 Usage

### Step 1 — Generate Training Images
```bash
python patter_genaration.py
```
Set `dd` to your OHLCV CSV path and configure `window_size` / `shift_size` as needed.

### Step 2 — Train the CNN Model
```bash
python model.py
```
Set `input_folder` to the directory of generated images. The model is saved as `chart_classification_model.h5`.

### Step 3 — Train the XGBoost TP/SL Model
Open and run all cells in `transformer.ipynb`. The model is saved as `optimized_xgb_tp_sl_predictor.pkl`.

### Step 4a — Run the Live Bot
```bash
python main.py
```
Ensure both model files are in the same directory. The bot will begin monitoring BTC/USDT and printing real-time status. Press `Ctrl+C` to stop and save session reports.

### Step 4b — Run a Backtest
```bash
python backtest.py
```
Configure the `data_file` path and `initial_capital` inside the script, then run.

---

## 📊 Model Performance Outputs

| Output | Description |
|---|---|
| Training / Validation Accuracy Curves | Plotted after CNN training |
| Confusion Matrix | Per-class prediction breakdown |
| Classification Report | Precision, Recall, F1-score |
| ROC-AUC Curve | Model discrimination ability |
| Backtest Trade Log | Win rate, drawdown, streak stats |

---

## ⚠️ Disclaimer

> **This project is for educational and research purposes only.** Cryptocurrency trading carries significant financial risk. Past backtest performance does not guarantee future results. Never trade with capital you cannot afford to lose. The authors are not responsible for any financial losses incurred through the use of this software.

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
