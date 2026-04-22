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
MAX_PATTERNS = 50
OUTPUT_DIR = "rising_falling_three_methods"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# === Load and preprocess ===
def load_data(filepath):
    df = pd.read_csv(filepath, parse_dates=['datetime_utc'])
    df.sort_values('datetime_utc', inplace=True)
    df.reset_index(drop=True, inplace=True)
    df['short_term_trend'] = df['close'].rolling(SHORT_TERM_PERIOD).apply(lambda x: 1 if x.iloc[-1] > x.iloc[0] else -1)
    df['long_term_trend'] = df['close'].rolling(LONG_TERM_PERIOD).apply(lambda x: 1 if x.iloc[-1] > x.iloc[0] else -1)
    return df

# === Pattern Detection ===
def detect_three_methods_patterns(df):
    patterns = []
    for i in tqdm(range(5 + max(SHORT_TERM_PERIOD, LONG_TERM_PERIOD), len(df)), desc="Detecting patterns"):
        c1 = df.iloc[i - 5]
        c2 = df.iloc[i - 4]
        c3 = df.iloc[i - 3]
        c4 = df.iloc[i - 2]
        c5 = df.iloc[i - 1]

        short_trend = df.iloc[i - 1]['short_term_trend']
        long_trend = df.iloc[i - 1]['long_term_trend']

        # === Rising Three Methods ===
        if c1['close'] > c1['open'] and c5['close'] > c5['open']:
            if all(c1['low'] <= c['low'] <= c1['high'] and c1['low'] <= c['high'] <= c1['high'] for c in [c2, c3, c4]):
                if all(c['close'] < c['open'] for c in [c2, c3, c4]):
                    if c5['close'] > c1['high'] and short_trend == 1 and long_trend == 1:
                        patterns.append({
                            'idx': i - 1,
                            'pattern': 'rising_three_methods',
                            'short_term_trend': 'up',
                            'long_term_trend': 'up',
                            'key_price': c5['close']
                        })

        # === Falling Three Methods ===
        if c1['close'] < c1['open'] and c5['close'] < c5['open']:
            if all(c1['low'] <= c['low'] <= c1['high'] and c1['low'] <= c['high'] <= c1['high'] for c in [c2, c3, c4]):
                if all(c['close'] > c['open'] for c in [c2, c3, c4]):
                    if c5['close'] < c1['low'] and short_trend == -1 and long_trend == -1:
                        patterns.append({
                            'idx': i - 1,
                            'pattern': 'falling_three_methods',
                            'short_term_trend': 'down',
                            'long_term_trend': 'down',
                            'key_price': c5['close']
                        })

        if len(patterns) >= 2 * MAX_PATTERNS:
            break
    return patterns

# === Chart Plot ===
def generate_chart(df, pattern_info, file_index):
    plt.style.use('seaborn-darkgrid')
    fig, ax = plt.subplots(figsize=(15, 8))

    pattern_idx = pattern_info['idx']
    start_idx = max(0, pattern_idx - CANDLES_TO_SHOW // 2)
    end_idx = min(len(df), pattern_idx + CANDLES_TO_SHOW // 2 + 1)
    subset = df.iloc[start_idx:end_idx].reset_index(drop=True)

    pattern_start = pattern_idx - 4
    pattern_end = pattern_idx

    local_start = pattern_start - start_idx
    local_end = pattern_end - start_idx

    highs = []
    lows = []

    for i, row in subset.iterrows():
        color = 'green' if row['close'] >= row['open'] else 'red'
        ax.plot([i, i], [row['low'], row['high']], color=color, linewidth=1)
        height = abs(row['close'] - row['open'])
        if height > 0:
            ax.add_patch(patches.Rectangle(
                (i - 0.3, min(row['open'], row['close'])),
                0.6,
                height,
                facecolor=color,
                edgecolor='black',
                linewidth=0.5,
                zorder=10
            ))
        if local_start <= i <= local_end:
            highs.append(row['high'])
            lows.append(row['low'])

    if highs and lows:
        x = local_start - 0.5
        width = (local_end - local_start) + 1
        y = min(lows)
        height = max(highs) - y
        ax.add_patch(patches.Rectangle(
            (x, y),
            width,
            height,
            linewidth=1.5,
            edgecolor='blue',
            facecolor='blue',
            alpha=0.15,
            zorder=5
        ))

    ax.axhline(y=pattern_info['key_price'], color='black', linestyle=':', alpha=0.7, label='Key Price')

    info_text = (
        f"Pattern: {pattern_info['pattern'].replace('_', ' ').title()}\n"
        f"Short-Term Trend: {pattern_info['short_term_trend'].upper()}\n"
        f"Long-Term Trend: {pattern_info['long_term_trend'].upper()}\n"
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
    ax.set_title(f"{pattern_info['pattern'].replace('_', ' ').title()} Pattern", fontsize=12)
    plt.tight_layout()
    filename = f"{file_index:03d}_{pattern_info['pattern']}.png"
    plt.savefig(os.path.join(OUTPUT_DIR, filename), bbox_inches='tight', pad_inches=0.2)
    plt.close()

# === Run Script ===
def run_analysis(filepath):
    df = load_data(filepath)
    patterns = detect_three_methods_patterns(df)

    print(f"\nDetected {len(patterns)} Rising/Falling Three Methods patterns")

    rising_count = 0
    falling_count = 0
    i = 0
    for pattern in tqdm(patterns, desc="Generating charts"):
        if pattern['pattern'] == 'rising_three_methods' and rising_count < MAX_PATTERNS:
            generate_chart(df, pattern, i)
            rising_count += 1
            i += 1
        elif pattern['pattern'] == 'falling_three_methods' and falling_count < MAX_PATTERNS:
            generate_chart(df, pattern, i)
            falling_count += 1
            i += 1
        if rising_count >= MAX_PATTERNS and falling_count >= MAX_PATTERNS:
            break

    print(f"\nSaved charts to: {os.path.abspath(OUTPUT_DIR)}")

if __name__ == "__main__":
    run_analysis("OHCLV.csv")
