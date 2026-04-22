import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import os
import numpy as np
from tqdm import tqdm

# === Configuration ===
IMAGE_WIDTH = 1500
IMAGE_HEIGHT = 800
OUTPUT_DIR = "doji_star_patterns"
os.makedirs(OUTPUT_DIR, exist_ok=True)

SHORT_TERM_PERIOD = 20
LONG_TERM_PERIOD = 50
CANDLES_TO_SHOW = 60
MAX_PATTERNS = 50

# === Trend Determination ===
def determine_trends(df, idx):
    trends = {'short_term': 'neutral', 'long_term': 'neutral'}

    if idx >= SHORT_TERM_PERIOD:
        short_change = (df.iloc[idx]['close'] - df.iloc[idx - SHORT_TERM_PERIOD]['close']) / df.iloc[idx - SHORT_TERM_PERIOD]['close']
        trends['short_term'] = 'up' if short_change > 0 else 'down'

    if idx >= LONG_TERM_PERIOD:
        long_change = (df.iloc[idx]['close'] - df.iloc[idx - LONG_TERM_PERIOD]['close']) / df.iloc[idx - LONG_TERM_PERIOD]['close']
        trends['long_term'] = 'up' if long_change > 0 else 'down'

    return trends

# === Doji Star Pattern Detection ===
def detect_doji_star_patterns(df):
    patterns = []
    print("Detecting Bullish and Bearish Doji Star patterns...")

    for i in tqdm(range(2 + max(SHORT_TERM_PERIOD, LONG_TERM_PERIOD), len(df))):
        c1, c2, c3 = df.iloc[i-2], df.iloc[i-1], df.iloc[i]
        body1 = abs(c1['close'] - c1['open'])
        body2 = abs(c2['close'] - c2['open'])
        body3 = abs(c3['close'] - c3['open'])
        avg_price = (c1['close'] + c3['close']) / 2

        is_doji = body2 <= 0.001 * ((c2['high'] + c2['low']) / 2)
        trends = determine_trends(df, i)

        # === Bullish Doji Star ===
        if (
            trends['short_term'] == 'down' and trends['long_term'] == 'down' and
            c1['close'] < c1['open'] and  # bearish candle
            is_doji and
            c2['low'] < c1['close'] and  # gap down
            c3['close'] > c3['open'] and  # bullish candle
            c3['close'] > (c1['open'] + c1['close']) / 2 and  # close above midpoint of c1
            body1 > 0.005 * avg_price and body3 > 0.005 * avg_price
        ):
            patterns.append({
                'idx': i,
                'pattern': 'bullish_doji_star',
                'key_price': c3['close'],
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term']
            })

        # === Bearish Doji Star ===
        elif (
            trends['short_term'] == 'up' and trends['long_term'] == 'up' and
            c1['close'] > c1['open'] and  # bullish candle
            is_doji and
            c2['high'] > c1['close'] and  # gap up
            c3['close'] < c3['open'] and  # bearish candle
            c3['close'] < (c1['open'] + c1['close']) / 2 and  # close below midpoint of c1
            body1 > 0.005 * avg_price and body3 > 0.005 * avg_price
        ):
            patterns.append({
                'idx': i,
                'pattern': 'bearish_doji_star',
                'key_price': c3['close'],
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term']
            })

    return patterns

# === Visualization ===
def generate_chart(df, pattern_info, file_index):
    plt.style.use('seaborn')
    fig, ax = plt.subplots(figsize=(IMAGE_WIDTH/100, IMAGE_HEIGHT/100), dpi=100)

    pattern_idx = pattern_info['idx']
    start_idx = max(0, pattern_idx - CANDLES_TO_SHOW//2)
    end_idx = min(len(df), pattern_idx + CANDLES_TO_SHOW//2 + 1)
    subset = df.iloc[start_idx:end_idx].reset_index(drop=True)

    # Pattern candle position
    pos = pattern_idx - start_idx

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

    # Highlight the pattern area
    ax.add_patch(patches.Rectangle(
        (pos - 2 - 0.5, subset['low'].min()*0.995),
        3,
        subset['high'].max()*1.005 - subset['low'].min()*0.995,
        fill=False,
        edgecolor='blue',
        linewidth=2,
        linestyle='--'
    ))

    ax.axhline(y=pattern_info['key_price'], color='black', linestyle=':', alpha=0.7)

    info_text = (
        f"Pattern: {pattern_info['pattern'].replace('_', ' ').title()}\n"
        f"Short-Term Trend: {pattern_info['short_term_trend'].upper()}\n"
        f"Long-Term Trend: {pattern_info['long_term_trend'].upper()}\n"
        f"Key Price: {pattern_info['key_price']:.4f}"
    )

    ax.text(0.05, 0.95, info_text, transform=ax.transAxes, verticalalignment='top',
            bbox=dict(facecolor='white', alpha=0.9, edgecolor='gray'), fontsize=10)

    xticks = np.linspace(0, len(subset)-1, 10, dtype=int)
    xticklabels = [subset.iloc[i]['datetime_utc'].strftime('%m-%d') for i in xticks]
    ax.set_xticks(xticks)
    ax.set_xticklabels(xticklabels, rotation=45)

    ax.set_title(f"{pattern_info['pattern'].replace('_', ' ').title()} Pattern")
    plt.tight_layout()
    filename = f"{file_index:03d}_{pattern_info['pattern']}.png"
    plt.savefig(os.path.join(OUTPUT_DIR, filename), bbox_inches='tight')
    plt.close()

# === Main Analysis ===
def run_analysis(data_file):
    df = pd.read_csv(data_file, parse_dates=['datetime_utc']).sort_values('datetime_utc')
    df = df.reset_index(drop=True)

    patterns = detect_doji_star_patterns(df)

    bullish = [p for p in patterns if p['pattern'] == 'bullish_doji_star'][:MAX_PATTERNS]
    bearish = [p for p in patterns if p['pattern'] == 'bearish_doji_star'][:MAX_PATTERNS]

    print(f"\nDetected {len(bullish)} Bullish Doji Star and {len(bearish)} Bearish Doji Star patterns")

    for i, pattern in enumerate(bullish + bearish):
        generate_chart(df, pattern, i)

    print(f"\nCharts saved to: {os.path.abspath(OUTPUT_DIR)}")

if __name__ == "__main__":
    run_analysis("OHCLV.csv")
