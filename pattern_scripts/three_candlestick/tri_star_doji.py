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
OUTPUT_DIR = "tri_star_doji"
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
def is_doji(candle, threshold=0.1):
    body = abs(candle['close'] - candle['open'])
    range_ = candle['high'] - candle['low']
    return body < threshold * range_

def detect_tri_star_doji(df):
    patterns = []
    trend_cache = {}

    for i in tqdm(range(max(SHORT_TERM, LONG_TERM) + 3, len(df))):
        t1 = df.iloc[i - 3]
        t2 = df.iloc[i - 2]
        t3 = df.iloc[i - 1]
        trends = determine_trends(df, i - 1, trend_cache)

        if not (is_doji(t1) and is_doji(t2) and is_doji(t3)):
            continue

        # Bullish Tri-Star Doji
        if trends['short_term'] == 'down' and trends['long_term'] == 'down':
            if t2['high'] < t1['low'] and t3['low'] > t2['high']:
                patterns.append({
                    'idx': i - 1,
                    'pattern': 'bullish_tri_star_doji',
                    'impact': 'Potential Bullish Reversal',
                    'short_term_trend': trends['short_term'],
                    'long_term_trend': trends['long_term'],
                    'key_price': t3['close']
                })

        # Bearish Tri-Star Doji
        if trends['short_term'] == 'up' and trends['long_term'] == 'up':
            if t2['low'] > t1['high'] and t3['high'] < t2['low']:
                patterns.append({
                    'idx': i - 1,
                    'pattern': 'bearish_tri_star_doji',
                    'impact': 'Potential Bearish Reversal',
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
    ax.set_title("Tri-Star Doji Pattern", fontsize=12)
    ax.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, f"{file_index:03d}_tri_star_doji.png"))
    plt.close()

# === Runner ===
def run_analysis(file):
    df = pd.read_csv(file, parse_dates=['datetime_utc']).sort_values('datetime_utc')
    patterns = detect_tri_star_doji(df)

    print(f"\nDetected {len(patterns)} Tri-Star Doji patterns")

    max_charts = 50
    for i, pattern in enumerate(patterns[:max_charts]):
        generate_chart(df, pattern, i)

    print(f"\nSaved charts to: {os.path.abspath(OUTPUT_DIR)}")

if __name__ == "__main__":
    run_analysis("OHCLV.csv")