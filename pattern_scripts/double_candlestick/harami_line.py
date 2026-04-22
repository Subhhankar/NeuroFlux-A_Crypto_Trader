import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import os
import numpy as np
from tqdm import tqdm

# === Configuration ===
IMAGE_WIDTH = 1500
IMAGE_HEIGHT = 800
OUTPUT_DIR = "harami_patterns"
os.makedirs(OUTPUT_DIR, exist_ok=True)

SHORT_TERM_PERIOD = 20
LONG_TERM_PERIOD = 50
CANDLES_TO_SHOW = 60
MAX_BULLISH = 50
MAX_BEARISH = 50
STRICT_ENGULFING = True  # << Toggle for strict wick/body engulfing

# === Trend Determination with Caching ===
def determine_trends(df, idx, cache=None):
    if cache is None:
        cache = {}
    if idx in cache:
        return cache[idx]

    trends = {'short_term': 'neutral', 'long_term': 'neutral'}

    if idx >= SHORT_TERM_PERIOD:
        short_change = (df.iloc[idx]['close'] - df.iloc[idx - SHORT_TERM_PERIOD]['close']) / df.iloc[idx - SHORT_TERM_PERIOD]['close']
        trends['short_term'] = 'up' if short_change > 0 else 'down'

    if idx >= LONG_TERM_PERIOD:
        long_change = (df.iloc[idx]['close'] - df.iloc[idx - LONG_TERM_PERIOD]['close']) / df.iloc[idx - LONG_TERM_PERIOD]['close']
        trends['long_term'] = 'up' if long_change > 0 else 'down'

    cache[idx] = trends
    return trends

# === Harami Pattern Detection (Strict/Relaxed Mode) ===
def detect_harami_patterns(df):
    patterns = []
    trend_cache = {}

    print("Scanning for Harami patterns...")
    for i in tqdm(range(max(SHORT_TERM_PERIOD, LONG_TERM_PERIOD)+2, len(df))):
        prev = df.iloc[i-2]  # t-2
        curr = df.iloc[i-1]  # t-1
        trends = determine_trends(df, i-1, trend_cache)

        # === Bullish Harami ===
        if (
            trends['short_term'] == 'down' and trends['long_term'] == 'down' and
            prev['close'] < prev['open'] and  # bearish
            curr['close'] > curr['open']      # bullish
        ):
            if STRICT_ENGULFING:
                valid = curr['high'] <= prev['open'] and curr['low'] >= prev['close']
            else:
                valid = curr['open'] > prev['close'] and curr['close'] < prev['open']
            
            if valid and len([p for p in patterns if p['pattern'] == 'bullish_harami']) < MAX_BULLISH:
                patterns.append({
                    'idx': i-1,
                    'pattern': 'bullish_harami',
                    'impact': 'Potential Bullish Reversal',
                    'short_term_trend': trends['short_term'],
                    'long_term_trend': trends['long_term'],
                    'key_price': curr['close']
                })

        # === Bearish Harami ===
        elif (
            trends['short_term'] == 'up' and trends['long_term'] == 'up' and
            prev['close'] > prev['open'] and  # bullish
            curr['close'] < curr['open']      # bearish
        ):
            if STRICT_ENGULFING:
                valid = curr['high'] <= prev['close'] and curr['low'] >= prev['open']
            else:
                valid = curr['open'] < prev['close'] and curr['close'] > prev['open']
            
            if valid and len([p for p in patterns if p['pattern'] == 'bearish_harami']) < MAX_BEARISH:
                patterns.append({
                    'idx': i-1,
                    'pattern': 'bearish_harami',
                    'impact': 'Potential Bearish Reversal',
                    'short_term_trend': trends['short_term'],
                    'long_term_trend': trends['long_term'],
                    'key_price': curr['close']
                })

    return patterns

# === Professional Visualization ===
def generate_chart(df, pattern_info, file_index):
    plt.style.use('seaborn')
    fig, ax = plt.subplots(figsize=(IMAGE_WIDTH/100, IMAGE_HEIGHT/100), dpi=100)

    pattern_idx = pattern_info['idx']
    start_idx = max(0, pattern_idx - CANDLES_TO_SHOW//2)
    end_idx = min(len(df), pattern_idx + CANDLES_TO_SHOW//2 + 1)
    subset = df.iloc[start_idx:end_idx].reset_index(drop=True)

    t1_pos = pattern_idx - start_idx - 1
    t2_pos = t1_pos + 1

    for i, row in subset.iterrows():
        color = 'green' if row['close'] >= row['open'] else 'red'
        ax.plot([i, i], [row['low'], row['high']], color=color, linewidth=1)
        ax.add_patch(patches.Rectangle(
            (i-0.3, min(row['open'], row['close'])),
            0.6,
            abs(row['close']-row['open']),
            facecolor=color,
            edgecolor=color
        ))

    box_color = 'darkred' if pattern_info['pattern'] == 'bearish_harami' else 'darkgreen'
    ax.add_patch(patches.Rectangle(
        (t1_pos-0.5, subset['low'].min()*0.995),
        2,
        subset['high'].max()*1.005 - subset['low'].min()*0.995,
        fill=False,
        edgecolor=box_color,
        linewidth=2,
        linestyle='--'
    ))

    ax.axhline(
        y=pattern_info['key_price'],
        color='red' if pattern_info['pattern'] == 'bearish_harami' else 'green',
        linestyle=':',
        alpha=0.7,
        label='Resistance' if pattern_info['pattern'] == 'bearish_harami' else 'Support'
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

    xtick_positions = np.linspace(0, len(subset)-1, 10, dtype=int)
    xtick_labels = [subset.iloc[i]['datetime_utc'].strftime('%m-%d') for i in xtick_positions]
    ax.set_xticks(xtick_positions)
    ax.set_xticklabels(xtick_labels, rotation=45)

    ax.legend(loc='upper left')
    ax.set_title(f"{pattern_info['pattern'].replace('_', ' ').title()} Pattern", fontsize=12)
    plt.tight_layout()

    filename = f"{file_index:03d}_{pattern_info['pattern']}.png"
    plt.savefig(os.path.join(OUTPUT_DIR, filename), bbox_inches='tight', pad_inches=0.2)
    plt.close()

# === Main Analysis Function ===
def run_analysis(data_file):
    df = pd.read_csv(data_file, parse_dates=['datetime_utc']).sort_values('datetime_utc')
    patterns = detect_harami_patterns(df)

    bullish = [p for p in patterns if p['pattern'] == 'bullish_harami'][:MAX_BULLISH]
    bearish = [p for p in patterns if p['pattern'] == 'bearish_harami'][:MAX_BEARISH]

    print(f"\nGenerated {len(bullish)} bullish and {len(bearish)} bearish patterns")

    print("\nGenerating pattern charts...")
    for i, pattern in enumerate(tqdm(bullish, desc="Bullish Patterns")):
        generate_chart(df, pattern, i)

    for i, pattern in enumerate(tqdm(bearish, desc="Bearish Patterns")):
        generate_chart(df, pattern, i + MAX_BULLISH)

    print(f"\nSaved to: {os.path.abspath(OUTPUT_DIR)}")

if __name__ == "__main__":
    run_analysis("OHCLV.csv")
