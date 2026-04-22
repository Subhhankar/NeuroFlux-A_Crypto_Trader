import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import os
from tqdm import tqdm
import numpy as np

# === Configuration ===
SHORT_TERM = 20
LONG_TERM = 50
CANDLES_TO_SHOW = 60
OUTPUT_DIR = "unique_three_river"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# === Trend Determination ===
def determine_trends(df, idx, cache):
    if idx in cache:
        return cache[idx]
    trends = {'short_term': 'neutral', 'long_term': 'neutral'}
    if idx >= SHORT_TERM:
        change = (df.iloc[idx]['close'] - df.iloc[idx - SHORT_TERM]['close']) / df.iloc[idx - SHORT_TERM]['close']
        trends['short_term'] = 'down' if change < 0 else 'up'
    if idx >= LONG_TERM:
        change = (df.iloc[idx]['close'] - df.iloc[idx - LONG_TERM]['close']) / df.iloc[idx - LONG_TERM]['close']
        trends['long_term'] = 'down' if change < 0 else 'up'
    cache[idx] = trends
    return trends

# === Pattern Detection ===
def detect_unique_three_river(df):
    patterns = []
    trend_cache = {}

    for i in tqdm(range(max(SHORT_TERM, LONG_TERM) + 3, len(df))):
        t1 = df.iloc[i - 3]
        t2 = df.iloc[i - 2]
        t3 = df.iloc[i - 1]
        trends = determine_trends(df, i - 1, trend_cache)

        if trends['short_term'] != 'down' or trends['long_term'] != 'down':
            continue

        # --- Candle 1: Long bearish ---
        c1_body = abs(t1['open'] - t1['close'])
        if not (t1['close'] < t1['open'] and c1_body > (t1['high'] - t1['low']) * 0.6):
            continue

        # --- Candle 2: Hammer (small body, long lower shadow) ---
        c2_body = abs(t2['close'] - t2['open'])
        c2_lower = min(t2['open'], t2['close']) - t2['low']
        if not (c2_body < (t2['high'] - t2['low']) * 0.3 and c2_lower > c2_body * 2):
            continue

        # --- Candle 3: Small bullish within hammer range ---
        if not (t3['close'] > t3['open']):  # bullish
            continue
        if not (t3['close'] < max(t2['open'], t2['close']) and t3['open'] > t2['low']):
            continue
        if not (t3['high'] <= t2['high'] and t3['low'] >= t2['low']):
            continue

        patterns.append({
            'idx': i - 1,
            'pattern': 'unique_three_river',
            'impact': 'Potential Bullish Reversal',
            'short_term_trend': trends['short_term'],
            'long_term_trend': trends['long_term'],
            'key_price': t3['close']
        })

    return patterns

# === Chart Generator ===
def generate_chart(df, pattern_info, file_index):
    plt.style.use('seaborn-darkgrid')
    fig, ax = plt.subplots(figsize=(15, 8))

    pattern_idx = pattern_info['idx']
    start_idx = max(0, pattern_idx - CANDLES_TO_SHOW // 2)
    end_idx = min(len(df), pattern_idx + CANDLES_TO_SHOW // 2 + 1)
    subset = df.iloc[start_idx:end_idx].reset_index(drop=True)

    highlight_start = pattern_idx - start_idx - 2
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

    ax.add_patch(patches.Rectangle(
        (highlight_start - 0.5, subset['low'].min() * 0.995),
        3,
        subset['high'].max() * 1.005 - subset['low'].min() * 0.995,
        fill=False,
        edgecolor='black',
        linewidth=2,
        linestyle='--'
    ))

    ax.axhline(
        y=pattern_info['key_price'],
        color='black',
        linestyle=':',
        alpha=0.7,
        label='Key Price'
    )

    info_text = (
        f"Pattern: {pattern_info['pattern'].replace('_', ' ').title()}\n"
        f"Impact: {pattern_info['impact']}\n"
        f"20-period Trend: {pattern_info['short_term_trend'].upper()}\n"
        f"50-period Trend: {pattern_info['long_term_trend'].upper()}\n"
        f"Date: {df.iloc[pattern_info['idx']]['datetime_utc'].strftime('%Y-%m-%d')}\n"
        f"Key Price: {pattern_info['key_price']:.4f}"
    )

    ax.text(
        0.05, 0.95, info_text,
        transform=ax.transAxes,
        verticalalignment='top',
        bbox=dict(facecolor='white', edgecolor='gray', alpha=0.9),
        fontsize=10
    )

    xticks = np.linspace(0, len(subset) - 1, 10, dtype=int)
    xtick_labels = [subset.iloc[i]['datetime_utc'].strftime('%m-%d') for i in xticks]
    ax.set_xticks(xticks)
    ax.set_xticklabels(xtick_labels, rotation=45)
    ax.set_title("Unique Three River Pattern", fontsize=12)
    ax.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, f"{file_index:03d}_unique_three_river.png"))
    plt.close()

# === Runner ===
def run_analysis(file):
    df = pd.read_csv(file, parse_dates=['datetime_utc']).sort_values('datetime_utc')
    patterns = detect_unique_three_river(df)

    print(f"\nDetected {len(patterns)} Unique Three River patterns")

    max_charts = 50
    for i, pattern in enumerate(patterns[:max_charts]):
        generate_chart(df, pattern, i)

    print(f"\nSaved charts to: {os.path.abspath(OUTPUT_DIR)}")

if __name__ == "__main__":
    run_analysis("OHCLV.csv")
