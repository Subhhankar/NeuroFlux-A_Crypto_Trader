import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import os
import numpy as np
from tqdm import tqdm

# === Configuration ===
SHORT_TERM_PERIOD = 20
LONG_TERM_PERIOD = 50
CANDLES_TO_SHOW = 40
MAX_PATTERNS = 50
OUTPUT_DIR = "belt_hold_patterns"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# === Load and preprocess ===
def load_data(filepath):
    df = pd.read_csv(filepath, parse_dates=['datetime_utc'])
    df.sort_values('datetime_utc', inplace=True)
    df.reset_index(drop=True, inplace=True)

    df['short_term_trend'] = df['close'].shift(1).rolling(SHORT_TERM_PERIOD).apply(lambda x: 1 if x.iloc[-1] > x.iloc[0] else -1)
    df['long_term_trend'] = df['close'].shift(1).rolling(LONG_TERM_PERIOD).apply(lambda x: 1 if x.iloc[-1] > x.iloc[0] else -1)

    return df

# === Pattern Detection ===
def detect_belt_hold_patterns(df):
    patterns = []

    for i in tqdm(range(max(SHORT_TERM_PERIOD, LONG_TERM_PERIOD) + 2, len(df)), desc="Detecting Belt Hold Patterns"):
        c0 = df.iloc[i]      # Current candle
        c1 = df.iloc[i - 1]  # Previous
        c2 = df.iloc[i - 2]  # Before previous

        short_trend = df.iloc[i - 1]['short_term_trend']
        long_trend = df.iloc[i - 1]['long_term_trend']

        # === Bullish Belt Hold ===
        if (
            c0['close'] > c0['open'] and  # Bullish
            c0['open'] < c1['low'] and  # Gap down
            abs(c0['open'] - c0['low']) <= 0.01 * c0['open'] and  # No/very small lower shadow
            abs(c0['close'] - c0['high']) <= 0.01 * c0['close'] and  # No/very small upper shadow
            short_trend == -1 and long_trend == -1  # Must come after a downtrend
        ):
            patterns.append({
                'idx': i,
                'pattern': 'bullish_belt_hold',
                'short_term_trend': 'down',
                'long_term_trend': 'down',
                'key_price': c0['close']
            })

        # === Bearish Belt Hold ===
        if (
            c0['close'] < c0['open'] and  # Bearish
            c0['open'] > c1['high'] and  # Gap up
            abs(c0['open'] - c0['high']) <= 0.01 * c0['open'] and  # No/very small upper shadow
            abs(c0['close'] - c0['low']) <= 0.01 * c0['close'] and  # No/very small lower shadow
            short_trend == 1 and long_trend == 1  # Must come after an uptrend
        ):
            patterns.append({
                'idx': i,
                'pattern': 'bearish_belt_hold',
                'short_term_trend': 'up',
                'long_term_trend': 'up',
                'key_price': c0['close']
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

    # Calculate pattern box index relative to subset
    subset_indices = df.index[start_idx:end_idx].tolist()
    box_idx = subset_indices.index(pattern_idx)

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

    # Bounding box around the belt hold candle
    box_candle = subset.iloc[box_idx]
    ax.add_patch(patches.Rectangle(
        (box_idx - 0.5, box_candle['low']),
        1,
        box_candle['high'] - box_candle['low'],
        linewidth=2,
        edgecolor='blue',
        facecolor='none',
        linestyle='--',
        zorder=5
    ))

    # Horizontal key price line
    ax.axhline(y=pattern_info['key_price'], color='black', linestyle=':', alpha=0.7, label='Key Price')

    info_text = (
        f"Pattern: {pattern_info['pattern'].replace('_', ' ').title()}\n"
        f"Short-Term Trend: {pattern_info['short_term_trend'].upper()}\n"
        f"Long-Term Trend: {pattern_info['long_term_trend'].upper()}\n"
        f"Date: {df.iloc[pattern_info['idx']]['datetime_utc'].strftime('%Y-%m-%d')}\n"
        f"Key Price: {pattern_info['key_price']:.2f}"
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
    patterns = detect_belt_hold_patterns(df)

    print(f"\nDetected {len(patterns)} Belt Hold patterns")

    bullish_count = 0
    bearish_count = 0
    i = 0
    for pattern in tqdm(patterns, desc="Generating charts"):
        if pattern['pattern'] == 'bullish_belt_hold' and bullish_count < MAX_PATTERNS:
            generate_chart(df, pattern, i)
            bullish_count += 1
            i += 1
        elif pattern['pattern'] == 'bearish_belt_hold' and bearish_count < MAX_PATTERNS:
            generate_chart(df, pattern, i)
            bearish_count += 1
            i += 1
        if bullish_count >= MAX_PATTERNS and bearish_count >= MAX_PATTERNS:
            break

    print(f"\nSaved charts to: {os.path.abspath(OUTPUT_DIR)}")

if __name__ == "__main__":
    run_analysis("OHCLV.csv")
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
OUTPUT_DIR = "mat_hold_patterns"
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
def detect_mat_hold_patterns(df):
    patterns = []
    for i in tqdm(range(5 + max(SHORT_TERM_PERIOD, LONG_TERM_PERIOD), len(df)), desc="Detecting patterns"):
        c1, c2, c3, c4, c5 = [df.iloc[j] for j in range(i - 5, i)]

        short_trend = df.iloc[i - 1]['short_term_trend']
        long_trend = df.iloc[i - 1]['long_term_trend']

        # === Bullish Mat Hold ===
        if (
            c1['close'] > c1['open'] and  # First is bullish
            c2['close'] < c2['open'] and  # Next 3 are bearish
            c3['close'] < c3['open'] and
            c4['close'] < c4['open'] and
            c2['open'] < c1['close'] and  # Gap down on second candle
            all(c['low'] >= c1['low'] for c in [c2, c3, c4]) and
            all(c['high'] <= c1['high'] for c in [c2, c3, c4]) and
            c5['close'] > c5['open'] and  # Fifth is bullish
            c5['close'] > c1['high'] and  # Closes above first candle’s high
            short_trend == 1 and long_trend == 1
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'bullish_mat_hold',
                'short_term_trend': 'up',
                'long_term_trend': 'up',
                'key_price': c5['close']
            })

        # === Bearish Mat Hold ===
        if (
            c1['close'] < c1['open'] and  # First is bearish
            c2['close'] > c2['open'] and  # Next 3 are bullish
            c3['close'] > c3['open'] and
            c4['close'] > c4['open'] and
            c2['open'] > c1['close'] and  # Gap up on second candle
            all(c['high'] <= c1['high'] for c in [c2, c3, c4]) and
            all(c['low'] >= c1['low'] for c in [c2, c3, c4]) and
            c5['close'] < c5['open'] and  # Fifth is bearish
            c5['close'] < c1['low'] and   # Closes below first candle’s low
            short_trend == -1 and long_trend == -1
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'bearish_mat_hold',
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

    # Determine index range of pattern inside the subset
    pattern_start = pattern_idx - 4
    pattern_end = pattern_idx
    subset_indices = list(df.index[start_idx:end_idx])
    box_start = subset_indices.index(pattern_start)
    box_end = subset_indices.index(pattern_end)

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

    # === Bounding Box around pattern ===
    lows = subset.iloc[box_start:box_end + 1]['low']
    highs = subset.iloc[box_start:box_end + 1]['high']
    box_low = lows.min()
    box_high = highs.max()

    ax.add_patch(patches.Rectangle(
        (box_start - 0.5, box_low),
        box_end - box_start + 1,
        box_high - box_low,
        linewidth=2,
        edgecolor='blue',
        facecolor='none',
        linestyle='--',
        zorder=5
    ))

    # Horizontal line
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
    patterns = detect_mat_hold_patterns(df)

    print(f"\nDetected {len(patterns)} Mat Hold patterns")

    bullish_count = 0
    bearish_count = 0
    i = 0
    for pattern in tqdm(patterns, desc="Generating charts"):
        if pattern['pattern'] == 'bullish_mat_hold' and bullish_count < MAX_PATTERNS:
            generate_chart(df, pattern, i)
            bullish_count += 1
            i += 1
        elif pattern['pattern'] == 'bearish_mat_hold' and bearish_count < MAX_PATTERNS:
            generate_chart(df, pattern, i)
            bearish_count += 1
            i += 1
        if bullish_count >= MAX_PATTERNS and bearish_count >= MAX_PATTERNS:
            break

    print(f"\nSaved charts to: {os.path.abspath(OUTPUT_DIR)}")

if __name__ == "__main__":
    run_analysis("OHCLV.csv") 