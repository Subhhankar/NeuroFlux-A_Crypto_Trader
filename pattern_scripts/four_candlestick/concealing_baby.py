import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from tqdm import tqdm
import os

# Config
SHORT_TERM_PERIOD = 20
LONG_TERM_PERIOD = 50
OUTPUT_DIR = "concealing_baby_swallow"
MAX_IMAGES = 50
CANDLES_TO_SHOW = 60
os.makedirs(OUTPUT_DIR, exist_ok=True)

# === Trend Detection ===
def get_trend(df, idx):
    trends = {'short_term': 'neutral', 'long_term': 'neutral'}
    if idx >= SHORT_TERM_PERIOD:
        short_return = (df.iloc[idx]['close'] - df.iloc[idx - SHORT_TERM_PERIOD]['close']) / df.iloc[idx - SHORT_TERM_PERIOD]['close']
        trends['short_term'] = 'down' if short_return < 0 else 'up'
    if idx >= LONG_TERM_PERIOD:
        long_return = (df.iloc[idx]['close'] - df.iloc[idx - LONG_TERM_PERIOD]['close']) / df.iloc[idx - LONG_TERM_PERIOD]['close']
        trends['long_term'] = 'down' if long_return < 0 else 'up'
    return trends

# === Candle Type Helpers ===
def is_bearish(c): return c['close'] < c['open']
def is_bullish(c): return c['close'] > c['open']

def is_marubozu(c, avg_size):
    body = abs(c['close'] - c['open'])
    shadows = abs(c['high'] - max(c['close'], c['open'])) + abs(min(c['close'], c['open']) - c['low'])
    return is_bearish(c) and shadows < 0.1 * body and body > 0.8 * avg_size

def engulfing(c_big, c_small):
    return c_big['high'] >= c_small['high'] and c_big['low'] <= c_small['low']

# === Pattern Detection ===
def detect_concealing_baby_swallow(df):
    patterns = []
    avg_candle_size = df['high'] - df['low']
    avg_size = avg_candle_size.rolling(10).mean()

    for i in tqdm(range(max(SHORT_TERM_PERIOD, LONG_TERM_PERIOD) + 4, len(df))):
        t4, t3, t2, t1 = df.iloc[i - 4], df.iloc[i - 3], df.iloc[i - 2], df.iloc[i - 1]
        trend = get_trend(df, i - 1)

        if trend['short_term'] != 'down' or trend['long_term'] != 'down':
            continue

        marubozu1 = is_marubozu(t4, avg_size[i - 4])
        marubozu2 = is_marubozu(t3, avg_size[i - 3]) and t3['open'] < t4['close']

        gap_down = t2['open'] < t3['close']
        upper_shadow = t2['high'] > t3['open'] and is_bearish(t2)

        engulf = engulfing(t1, t2) and is_bearish(t1)

        if marubozu1 and marubozu2 and gap_down and upper_shadow and engulf:
            patterns.append({
                'idx': i - 1,
                'pattern': 'Bullish Concealing Baby Swallow',
                'short_term_trend': trend['short_term'],
                'long_term_trend': trend['long_term'],
                'key_price': t1['close']
            })

        if len(patterns) >= MAX_IMAGES:
            break

    return patterns

# === Chart Plotting ===
def generate_chart(df, pattern_info, file_index):
    plt.style.use('seaborn-darkgrid')
    fig, ax = plt.subplots(figsize=(15, 8))

    pattern_idx = pattern_info['idx']
    start_idx = max(0, pattern_idx - CANDLES_TO_SHOW // 2)
    end_idx = min(len(df), pattern_idx + CANDLES_TO_SHOW // 2 + 1)
    subset = df.iloc[start_idx:end_idx].reset_index(drop=True)

    for i, row in subset.iterrows():
        color = 'green' if row['close'] >= row['open'] else 'red'
        ax.plot([i, i], [row['low'], row['high']], color=color, linewidth=1)
        ax.add_patch(patches.Rectangle(
            (i - 0.3, min(row['open'], row['close'])),
            0.6,
            abs(row['close'] - row['open']),
            facecolor=color,
            edgecolor=color
        ))

    ax.axhline(y=pattern_info['key_price'], color='black', linestyle=':', alpha=0.7)

    info_text = (
        f"Pattern: {pattern_info['pattern']}\n"
        f"Impact: Potential Bullish Reversal\n"
        f"Short-Term Trend: {pattern_info['short_term_trend'].upper()}\n"
        f"Long-Term Trend: {pattern_info['long_term_trend'].upper()}\n"
        f"Key Price: {pattern_info['key_price']:.4f}"
    )

    ax.text(
        0.05, 0.95,
        info_text,
        transform=ax.transAxes,
        verticalalignment='top',
        horizontalalignment='left',
        bbox=dict(facecolor='white', alpha=0.9, edgecolor='gray', boxstyle='round'),
        fontsize=10
    )

    ax.set_title("Bullish Concealing Baby Swallow Pattern", fontsize=12)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, f"{file_index:03d}_concealing_baby_swallow.png"), bbox_inches='tight')
    plt.close()

# === Run ===
def run_analysis(file):
    df = pd.read_csv(file, parse_dates=['datetime_utc']).sort_values('datetime_utc')
    patterns = detect_concealing_baby_swallow(df)

    print(f"\nDetected {len(patterns)} valid Concealing Baby Swallow patterns")
    for i, pattern in enumerate(patterns):
        generate_chart(df, pattern, i)
    print(f"\nSaved to {os.path.abspath(OUTPUT_DIR)}")

if __name__ == "__main__":
    run_analysis("OHCLV.csv")