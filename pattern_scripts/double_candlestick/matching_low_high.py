import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import os
import numpy as np
from tqdm import tqdm

# === Configuration ===
IMAGE_WIDTH = 1500
IMAGE_HEIGHT = 800
OUTPUT_DIR = "matching_patterns"
os.makedirs(OUTPUT_DIR, exist_ok=True)

SHORT_TERM_PERIOD = 20
LONG_TERM_PERIOD = 50
CANDLES_TO_SHOW = 60
PRICE_TOLERANCE = 0.001  # 0.1% tolerance
MAX_PATTERNS = 100

# === Trend Determination with Lookback ===
def determine_trends(df, idx):
    trends = {'short_term': 'neutral', 'long_term': 'neutral'}

    if idx >= SHORT_TERM_PERIOD:
        short_change = (df.iloc[idx]['close'] - df.iloc[idx - SHORT_TERM_PERIOD]['close']) / df.iloc[idx - SHORT_TERM_PERIOD]['close']
        trends['short_term'] = 'up' if short_change > 0 else 'down'

    if idx >= LONG_TERM_PERIOD:
        long_change = (df.iloc[idx]['close'] - df.iloc[idx - LONG_TERM_PERIOD]['close']) / df.iloc[idx - LONG_TERM_PERIOD]['close']
        trends['long_term'] = 'up' if long_change > 0 else 'down'

    return trends

# === Matching High/Low Pattern Detection ===
def detect_matching_patterns(df):
    patterns = []
    print("Scanning for Matching Low and Matching High patterns...")
    
    for i in tqdm(range(max(SHORT_TERM_PERIOD, LONG_TERM_PERIOD) + 1, len(df))):
        if len(patterns) >= MAX_PATTERNS:
            break

        candle1 = df.iloc[i - 2]
        candle2 = df.iloc[i - 1]
        trends = determine_trends(df, i - 1)

        # Matching Low (potential bullish reversal)
        if (
            trends['short_term'] == 'down' and
            trends['long_term'] == 'down' and
            candle1['close'] < candle1['open'] and  # bearish
            candle2['close'] < candle2['open'] and  # bearish
            candle2['open'] > candle1['close'] and
            abs(candle2['close'] - candle1['close']) <= candle1['close'] * PRICE_TOLERANCE
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'matching_low',
                'impact': 'Potential Bullish Reversal',
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': candle1['close']
            })

        # Matching High (potential bearish reversal)
        elif (
            trends['short_term'] == 'up' and
            trends['long_term'] == 'up' and
            candle1['close'] > candle1['open'] and  # bullish
            candle2['close'] > candle2['open'] and  # bullish
            candle2['open'] < candle1['close'] and
            abs(candle2['close'] - candle1['close']) <= candle1['close'] * PRICE_TOLERANCE
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'matching_high',
                'impact': 'Potential Bearish Reversal',
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': candle1['close']
            })

    return patterns

# === Chart Generator ===
def generate_chart(df, pattern_info, file_index):
    plt.style.use('seaborn')
    fig, ax = plt.subplots(figsize=(IMAGE_WIDTH / 100, IMAGE_HEIGHT / 100), dpi=100)

    pattern_idx = pattern_info['idx']
    start_idx = max(0, pattern_idx - CANDLES_TO_SHOW // 2)
    end_idx = min(len(df), pattern_idx + CANDLES_TO_SHOW // 2 + 1)
    subset = df.iloc[start_idx:end_idx].reset_index(drop=True)

    t1_pos = pattern_idx - start_idx - 1
    t2_pos = t1_pos + 1

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

    box_color = 'darkgreen' if pattern_info['pattern'] == 'matching_low' else 'darkred'
    ax.add_patch(patches.Rectangle(
        (t1_pos - 0.5, subset['low'].min() * 0.995),
        2,
        subset['high'].max() * 1.005 - subset['low'].min() * 0.995,
        fill=False,
        edgecolor=box_color,
        linewidth=2,
        linestyle='--'
    ))

    ax.axhline(
        y=pattern_info['key_price'],
        color='green' if pattern_info['pattern'] == 'matching_low' else 'red',
        linestyle=':',
        alpha=0.7,
        label='Support' if pattern_info['pattern'] == 'matching_low' else 'Resistance'
    )

    info_text = (
        f"Pattern: {pattern_info['pattern'].replace('_', ' ').title()}\n"
        f"Impact: {pattern_info['impact']}\n"
        f"20-period Trend: {pattern_info['short_term_trend'].upper()}\n"
        f"50-period Trend: {pattern_info['long_term_trend'].upper()}\n"
        f"Date: {df.iloc[pattern_idx]['datetime_utc'].strftime('%Y-%m-%d')}\n"
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

    xtick_positions = np.linspace(0, len(subset) - 1, 10, dtype=int)
    xtick_labels = [subset.iloc[i]['datetime_utc'].strftime('%m-%d') for i in xtick_positions]
    ax.set_xticks(xtick_positions)
    ax.set_xticklabels(xtick_labels, rotation=45)

    ax.legend(loc='upper left')
    ax.set_title(f"{pattern_info['pattern'].replace('_', ' ').title()} Pattern", fontsize=12)
    plt.tight_layout()

    filename = f"{file_index:03d}_{pattern_info['pattern']}.png"
    plt.savefig(os.path.join(OUTPUT_DIR, filename), bbox_inches='tight', pad_inches=0.2)
    plt.close()

# === Main ===
def run_analysis(data_file):
    df = pd.read_csv(data_file, parse_dates=['datetime_utc']).sort_values('datetime_utc')
    patterns = detect_matching_patterns(df)

    print(f"\nGenerated {len(patterns)} total matching patterns")
    for i, pattern in enumerate(tqdm(patterns)):
        generate_chart(df, pattern, i)

    print(f"\nSaved to: {os.path.abspath(OUTPUT_DIR)}")

if __name__ == "__main__":
    run_analysis("OHCLV.csv")
