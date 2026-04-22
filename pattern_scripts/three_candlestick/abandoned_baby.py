import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import os
from tqdm import tqdm

# === Configuration ===
SHORT_TERM_PERIOD = 20
LONG_TERM_PERIOD = 50
CANDLES_TO_SHOW = 60
MAX_IMAGES = 50
OUTPUT_DIR = "abandoned_baby"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# === Trend Detection ===
def determine_trend(df, idx, cache):
    if idx in cache:
        return cache[idx]
    trends = {'short_term': 'neutral', 'long_term': 'neutral'}
    if idx >= SHORT_TERM_PERIOD:
        change = (df.iloc[idx]['close'] - df.iloc[idx - SHORT_TERM_PERIOD]['close']) / df.iloc[idx - SHORT_TERM_PERIOD]['close']
        trends['short_term'] = 'up' if change > 0 else 'down'
    if idx >= LONG_TERM_PERIOD:
        change = (df.iloc[idx]['close'] - df.iloc[idx - LONG_TERM_PERIOD]['close']) / df.iloc[idx - LONG_TERM_PERIOD]['close']
        trends['long_term'] = 'up' if change > 0 else 'down'
    cache[idx] = trends
    return trends

# === Pattern Detection ===
def detect_abandoned_baby(df):
    patterns = []
    trend_cache = {}
    avg_candle_size = np.mean(abs(df['close'] - df['open']))

    for i in tqdm(range(max(SHORT_TERM_PERIOD, LONG_TERM_PERIOD) + 3, len(df))):
        c1 = df.iloc[i - 3]
        c2 = df.iloc[i - 2]
        c3 = df.iloc[i - 1]
        trends = determine_trend(df, i - 1, trend_cache)

        c1_body = abs(c1['close'] - c1['open'])
        c2_body = abs(c2['close'] - c2['open'])
        c3_body = abs(c3['close'] - c3['open'])

        is_doji = c2_body < 0.05 * avg_candle_size

        # Gaps (strict: no overlap of shadows)
        no_overlap_1_2 = c2['low'] > c1['high'] or c2['high'] < c1['low']
        no_overlap_2_3 = c3['low'] > c2['high'] or c3['high'] < c2['low']

        # === Bullish Abandoned Baby ===
        if (
            trends['short_term'] == 'down' and trends['long_term'] == 'down' and
            c1['close'] < c1['open'] and  # First: bearish
            is_doji and
            no_overlap_1_2 and
            c3['close'] > c3['open'] and  # Third: bullish
            no_overlap_2_3 and
            c3['close'] > c1['open']  # Close above first candle
        ):
            patterns.append({
                'idx': i - 1,
                'type': 'bullish',
                'key_price': c3['close'],
                'short_term': trends['short_term'],
                'long_term': trends['long_term']
            })

        # === Bearish Abandoned Baby ===
        if (
            trends['short_term'] == 'up' and trends['long_term'] == 'up' and
            c1['close'] > c1['open'] and  # First: bullish
            is_doji and
            no_overlap_1_2 and
            c3['close'] < c3['open'] and  # Third: bearish
            no_overlap_2_3 and
            c3['close'] < c1['open']  # Close below first candle
        ):
            patterns.append({
                'idx': i - 1,
                'type': 'bearish',
                'key_price': c3['close'],
                'short_term': trends['short_term'],
                'long_term': trends['long_term']
            })

    return patterns

# === Chart Plotting ===
def generate_chart(df, pattern_info, file_index):
    plt.style.use('seaborn-darkgrid')
    fig, ax = plt.subplots(figsize=(15, 8))

    pattern_idx = pattern_info['idx']
    start_idx = max(0, pattern_idx - CANDLES_TO_SHOW // 2)
    end_idx = min(len(df), pattern_idx + CANDLES_TO_SHOW // 2 + 1)
    subset = df.iloc[start_idx:end_idx].reset_index(drop=True)

    t1_pos = pattern_idx - start_idx - 2
    t3_pos = t1_pos + 2

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

    # Highlight pattern
    ax.add_patch(patches.Rectangle(
        (t1_pos - 0.5, subset['low'].min() * 0.995),
        3,
        subset['high'].max() * 1.005 - subset['low'].min() * 0.995,
        fill=False,
        edgecolor='black',
        linewidth=2,
        linestyle='--'
    ))

    ax.axhline(y=pattern_info['key_price'], color='black', linestyle=':', alpha=0.7, label='Key Price')

    info_text = (
        f"Pattern: {pattern_info['type'].capitalize()} Abandoned Baby\n"
        f"Impact: Potential {'Bullish' if pattern_info['type']=='bullish' else 'Bearish'} Reversal\n"
        f"20-period Trend: {pattern_info['short_term'].upper()}\n"
        f"50-period Trend: {pattern_info['long_term'].upper()}\n"
        f"Date: {df.iloc[pattern_info['idx']]['datetime_utc'].strftime('%Y-%m-%d')}\n"
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
    ax.set_title(f"{pattern_info['type'].capitalize()} Abandoned Baby Pattern", fontsize=12)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, f"{file_index:03d}_{pattern_info['type']}_abandoned_baby.png"), bbox_inches='tight', pad_inches=0.2)
    plt.close()

# === Runner ===
def run_analysis(file):
    df = pd.read_csv(file, parse_dates=['datetime_utc']).sort_values('datetime_utc')
    patterns = detect_abandoned_baby(df)
    print(f"\nDetected {len(patterns)} Abandoned Baby patterns")

    for i, pattern in enumerate(patterns[:MAX_IMAGES]):
        generate_chart(df, pattern, i)

    print(f"\nSaved charts to: {os.path.abspath(OUTPUT_DIR)}")

if __name__ == "__main__":
    run_analysis("OHCLV.csv")
