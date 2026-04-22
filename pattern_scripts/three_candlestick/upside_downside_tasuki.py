import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import os
import numpy as np
from tqdm import tqdm

# === Configuration ===
SHORT_TERM_PERIOD = 20
LONG_TERM_PERIOD = 50
CANDLES_TO_SHOW = 60
OUTPUT_DIR = "tasuki_gap_patterns"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# === Trend Calculation ===
def determine_trends(df, idx, cache):
    if idx in cache:
        return cache[idx]
    
    trends = {'short_term': 'neutral', 'long_term': 'neutral'}
    if idx >= SHORT_TERM_PERIOD:
        st_change = (df.iloc[idx]['close'] - df.iloc[idx - SHORT_TERM_PERIOD]['close']) / df.iloc[idx - SHORT_TERM_PERIOD]['close']
        trends['short_term'] = 'up' if st_change > 0 else 'down'
    if idx >= LONG_TERM_PERIOD:
        lt_change = (df.iloc[idx]['close'] - df.iloc[idx - LONG_TERM_PERIOD]['close']) / df.iloc[idx - LONG_TERM_PERIOD]['close']
        trends['long_term'] = 'up' if lt_change > 0 else 'down'
    
    cache[idx] = trends
    return trends

# === Pattern Detection ===
def detect_tasuki_gap_patterns(df):
    patterns = []
    trend_cache = {}

    for i in tqdm(range(max(SHORT_TERM_PERIOD, LONG_TERM_PERIOD) + 3, len(df))):
        c1 = df.iloc[i - 3]  # T-3
        c2 = df.iloc[i - 2]  # T-2
        c3 = df.iloc[i - 1]  # T-1

        trends = determine_trends(df, i - 1, trend_cache)

        # === Upside Tasuki Gap ===
        if (trends['short_term'] == 'up' and trends['long_term'] == 'up' and
            c1['close'] > c1['open'] and  # Bullish
            c2['open'] > c1['close'] and c2['close'] > c2['open'] and  # Gap up + bullish
            c3['open'] > c2['close'] and c3['close'] < c3['open']  # Bearish
        ):
            # Check if c3 closes within the gap but not fills it
            gap_bottom = c1['close']
            gap_top = c2['open']
            if gap_bottom < c3['close'] < gap_top:
                patterns.append({
                    'idx': i - 1,
                    'pattern': 'upside_tasuki_gap',
                    'impact': 'Bullish Continuation',
                    'short_term_trend': trends['short_term'],
                    'long_term_trend': trends['long_term'],
                    'key_price': c3['close']
                })

        # === Downside Tasuki Gap ===
        if (trends['short_term'] == 'down' and trends['long_term'] == 'down' and
            c1['close'] < c1['open'] and  # Bearish
            c2['open'] < c1['close'] and c2['close'] < c2['open'] and  # Gap down + bearish
            c3['open'] < c2['close'] and c3['close'] > c3['open']  # Bullish
        ):
            # Check if c3 closes within the gap but not fills it
            gap_top = c1['close']
            gap_bottom = c2['open']
            if gap_bottom < c3['close'] < gap_top:
                patterns.append({
                    'idx': i - 1,
                    'pattern': 'downside_tasuki_gap',
                    'impact': 'Bearish Continuation',
                    'short_term_trend': trends['short_term'],
                    'long_term_trend': trends['long_term'],
                    'key_price': c3['close']
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

    t1_pos = pattern_idx - start_idx - 2

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

    box_color = 'purple'
    ax.add_patch(patches.Rectangle(
        (t1_pos - 0.5, subset['low'].min() * 0.995),
        3,
        subset['high'].max() * 1.005 - subset['low'].min() * 0.995,
        fill=False,
        edgecolor=box_color,
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
    ax.set_title(pattern_info['pattern'].replace('_', ' ').title(), fontsize=12)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, f"{file_index:03d}_{pattern_info['pattern']}.png"), bbox_inches='tight', pad_inches=0.2)
    plt.close()

# === Run the Analysis ===
def run_analysis(file):
    df = pd.read_csv(file, parse_dates=['datetime_utc']).sort_values('datetime_utc')
    patterns = detect_tasuki_gap_patterns(df)

    print(f"\nDetected {len(patterns)} Tasuki Gap patterns")

    for idx, pattern in enumerate(patterns[:50]):  # Limit to 50 charts
        generate_chart(df, pattern, idx)

    print(f"\nSaved charts to: {os.path.abspath(OUTPUT_DIR)}")

if __name__ == "__main__":
    run_analysis("OHCLV.csv")
