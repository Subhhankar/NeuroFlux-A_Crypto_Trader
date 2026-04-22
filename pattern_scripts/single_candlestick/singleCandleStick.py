import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import os
from tqdm import tqdm

# Configurations
IMAGE_WIDTH = 640
IMAGE_HEIGHT = 640
OUTPUT_DIR = "single_candle_patterns"
os.makedirs(OUTPUT_DIR, exist_ok=True)

CANDLES_TO_SHOW = 33
TREND_LOOKBACK = 5

WICK_DOMINANCE_FACTOR = 2.0
SPINNING_BODY_MIN = 0.2
SPINNING_BODY_MAX = 0.4
MARUBOZU_BODY_MIN = 0.9
DOJI_THRESHOLD = 0.1

BOX_STYLE = {
    'linewidth': 2.0,
    'edgecolor': '#FF00FF',
    'facecolor': 'none',
    'linestyle': '-',
    'alpha': 0.9,
    'zorder': 10
}

IMPACT_MAP = {
    "hammer": "Bullish Reversal",
    "inverted_hammer": "Potential Bullish",
    "hanging_man": "Bearish Warning",
    "shooting_star": "Bearish Reversal",
    "spinning_top_bullish": "Indecision After Downtrend",
    "spinning_top_bearish": "Indecision After Uptrend",
    "bullish_marubozu": "Strong Bullish Continuation",
    "bearish_marubozu": "Strong Bearish Continuation",
    'standard': {'uptrend': 'Possible Top', 'downtrend': 'Possible Bottom'},
    'long_legged': {'uptrend': 'Exhaustion Risk', 'downtrend': 'Potential Reversal'},
    'dragonfly': {'uptrend': 'Weak Continuation', 'downtrend': 'Bullish Reversal'},
    'gravestone': {'uptrend': 'Bearish Reversal', 'downtrend': 'Likely Continuation'}
}

def determine_trend(df, idx):
    start = max(0, idx - TREND_LOOKBACK)
    end = idx
    if end <= start:
        return "unknown"
    return "uptrend" if df.iloc[end]['close'] > df.iloc[start]['close'] else "downtrend"

def determine_doji_type(row):
    body = abs(row['close'] - row['open'])
    rng = row['high'] - row['low']
    if rng == 0 or body / rng > DOJI_THRESHOLD:
        return None
    upper = row['high'] - max(row['open'], row['close'])
    lower = min(row['open'], row['close']) - row['low']
    if lower > 2 * upper and lower > 2 * body:
        return "dragonfly"
    elif upper > 2 * lower and upper > 2 * body:
        return "gravestone"
    elif upper > body and lower > body:
        return "long_legged"
    return "standard"

def determine_pattern_type(row, trend):
    body = abs(row['close'] - row['open'])
    rng = row['high'] - row['low']
    if rng == 0:
        return None
    body_ratio = body / rng
    upper = row['high'] - max(row['close'], row['open'])
    lower = min(row['close'], row['open']) - row['low']

    if body_ratio >= MARUBOZU_BODY_MIN:
        return "bullish_marubozu" if row['close'] > row['open'] else "bearish_marubozu"
    if lower > WICK_DOMINANCE_FACTOR * body and upper < body:
        return "hammer" if trend == "downtrend" else "hanging_man"
    if upper > WICK_DOMINANCE_FACTOR * body and lower < body:
        return "shooting_star" if trend == "uptrend" else "inverted_hammer"
    wick_balance = abs(upper - lower) < 0.25 * rng
    wick_ratio = (upper + lower) / rng
    if SPINNING_BODY_MIN < body_ratio < SPINNING_BODY_MAX and wick_ratio > 0.5 and wick_balance:
        return "spinning_top_bullish" if row['close'] > row['open'] else "spinning_top_bearish"
    return None

def find_patterns(df):
    all_patterns = []
    for i in range(TREND_LOOKBACK + 1, len(df) - CANDLES_TO_SHOW):
        idx = i - 1  # Use only past candles
        row = df.iloc[idx]
        trend = determine_trend(df, idx)

        # Doji logic
        doji_type = determine_doji_type(row)
        if doji_type:
            impact = IMPACT_MAP[doji_type][trend]
            all_patterns.append({
                'idx': idx,
                'type': 'doji',
                'pattern': doji_type,
                'trend': trend,
                'impact': impact
            })
            continue

        # Other patterns
        pattern = determine_pattern_type(row, trend)
        if pattern:
            impact = IMPACT_MAP.get(pattern, "Unknown")
            all_patterns.append({
                'idx': idx,
                'type': 'candle',
                'pattern': pattern,
                'trend': trend,
                'impact': impact
            })
    return all_patterns

def plot_candlestick(ax, x, open_p, high_p, low_p, close_p, width=0.4):
    color = '#2e7d32' if close_p >= open_p else '#c62828'
    body_bottom, body_top = sorted([open_p, close_p])
    ax.plot([x, x], [high_p, low_p], color=color, linewidth=1.0)
    ax.add_patch(patches.Rectangle((x - width / 2, body_bottom), width, body_top - body_bottom,
                                   linewidth=0.8, edgecolor=color, facecolor=color, zorder=5))

def generate_image(df, candle_info, index):
    window = 16
    start_idx = candle_info['idx'] - window
    end_idx = candle_info['idx'] + window + 1
    if start_idx < 0 or end_idx > len(df):
        return
    subset = df.iloc[start_idx:end_idx].reset_index(drop=True)
    if subset['low'].isna().any() or subset['high'].isna().any():
        return
    fig, ax = plt.subplots(figsize=(IMAGE_WIDTH / 100, IMAGE_HEIGHT / 100), dpi=100)
    min_p = subset['low'].min()
    max_p = subset['high'].max()
    padding = (max_p - min_p) * 0.1
    ax.set_ylim(min_p - padding, max_p + padding)
    ax.set_xlim(-0.5, len(subset) - 0.5)

    for i, (_, row) in enumerate(subset.iterrows()):
        plot_candlestick(ax, i, row['open'], row['high'], row['low'], row['close'])

    rel_idx = window
    x_left = rel_idx - 0.5
    x_right = rel_idx + 0.5
    y_bottom = subset.iloc[rel_idx]['low'] - padding * 0.05
    y_top = subset.iloc[rel_idx]['high'] + padding * 0.05

    ax.add_patch(patches.Rectangle((x_left, y_bottom), x_right - x_left, y_top - y_bottom, **BOX_STYLE))

    pattern_name = candle_info['pattern'].replace('_', ' ').title()
    impact_label = candle_info['impact']
    ax.text(x_left, y_top + padding * 0.05,
            f"{pattern_name} ({candle_info['trend'].capitalize()}): {impact_label}",
            fontsize=8, color='black', verticalalignment='bottom',
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.6))

    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(f"{pattern_name} in {candle_info['trend']}", fontsize=10)
    plt.tight_layout()
    filename = f"{OUTPUT_DIR}/{pattern_name.replace(' ', '_')}_{index + 1}.png"
    fig.savefig(filename)
    plt.close()

def load_data(file):
    df = pd.read_csv(file, parse_dates=['datetime_utc'], dayfirst=True)
    df = df.sort_values('datetime_utc').reset_index(drop=True)
    cutoff = df['datetime_utc'].max() - pd.DateOffset(months=6)
    return df[df['datetime_utc'] >= cutoff].reset_index(drop=True)

def process(file, max_images=500):
    df = load_data(file)
    all_patterns = find_patterns(df)
    print(f"Total Patterns Found: {len(all_patterns)}")
    selected = all_patterns[:max_images]
    for i, pattern in enumerate(tqdm(selected, desc="Generating Images")):
        generate_image(df, pattern, i)

if __name__ == "__main__":
    process("OHCLV.csv", max_images=500)
