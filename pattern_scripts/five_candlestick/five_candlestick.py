import pandas as pd
import numpy as np
from tqdm import tqdm

# === Configuration ===
SHORT_TERM_PERIOD = 20
LONG_TERM_PERIOD = 50
MAX_PATTERNS = 50

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

# === Helper Functions ===
def is_bullish(candle):
    return candle['close'] > candle['open']

def is_bearish(candle):
    return candle['close'] < candle['open']

# === Consolidated Pattern Detection ===
def detect_five_candlestick_patterns(df):
    patterns = []
    trend_cache = {}

    print("Scanning for all five-candlestick patterns...")
    for i in tqdm(range(max(SHORT_TERM_PERIOD, LONG_TERM_PERIOD) + 5, len(df))):
        t5 = df.iloc[i - 5]  # t-5
        t4 = df.iloc[i - 4]  # t-4
        t3 = df.iloc[i - 3]  # t-3
        t2 = df.iloc[i - 2]  # t-2
        t1 = df.iloc[i - 1]  # t-1
        trends = determine_trends(df, i - 1, trend_cache)

        # Count patterns to enforce limits
        pattern_counts = {
            'rising_three_methods': 0,
            'falling_three_methods': 0,
            'bullish_mat_hold': 0,
            'bearish_mat_hold': 0
        }
        for pattern in patterns:
            pattern_counts[pattern['pattern']] = pattern_counts.get(pattern['pattern'], 0) + 1

        if all(count >= MAX_PATTERNS for count in pattern_counts.values()):
            break

        # === Rising Three Methods ===
        if (
            is_bullish(t5) and is_bullish(t1) and
            all(is_bearish(c) for c in [t4, t3, t2]) and
            all(t5['low'] <= c['low'] <= t5['high'] and t5['low'] <= c['high'] <= t5['high'] for c in [t4, t3, t2]) and
            t1['close'] > t5['high'] and
            trends['short_term'] == 'up' and trends['long_term'] == 'up' and
            pattern_counts.get('rising_three_methods', 0) < MAX_PATTERNS
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'rising_three_methods',
                'impact': 'Bullish Continuation',
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': t1['close']
            })

        # === Falling Three Methods ===
        if (
            is_bearish(t5) and is_bearish(t1) and
            all(is_bullish(c) for c in [t4, t3, t2]) and
            all(t5['low'] <= c['low'] <= t5['high'] and t5['low'] <= c['high'] <= t5['high'] for c in [t4, t3, t2]) and
            t1['close'] < t5['low'] and
            trends['short_term'] == 'down' and trends['long_term'] == 'down' and
            pattern_counts.get('falling_three_methods', 0) < MAX_PATTERNS
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'falling_three_methods',
                'impact': 'Bearish Continuation',
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': t1['close']
            })

        # === Bullish Mat Hold ===
        if (
            is_bullish(t5) and is_bullish(t1) and
            is_bearish(t4) and is_bearish(t3) and is_bearish(t2) and
            t4['open'] < t5['close'] and
            all(c['low'] >= t5['low'] for c in [t4, t3, t2]) and
            all(c['high'] <= t5['high'] for c in [t4, t3, t2]) and
            t1['close'] > t5['high'] and
            trends['short_term'] == 'up' and trends['long_term'] == 'up' and
            pattern_counts.get('bullish_mat_hold', 0) < MAX_PATTERNS
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'bullish_mat_hold',
                'impact': 'Bullish Continuation',
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': t1['close']
            })

        # === Bearish Mat Hold ===
        if (
            is_bearish(t5) and is_bearish(t1) and
            is_bullish(t4) and is_bullish(t3) and is_bullish(t2) and
            t4['open'] > t5['close'] and
            all(c['high'] <= t5['high'] for c in [t4, t3, t2]) and
            all(c['low'] >= t5['low'] for c in [t4, t3, t2]) and
            t1['close'] < t5['low'] and
            trends['short_term'] == 'down' and trends['long_term'] == 'down' and
            pattern_counts.get('bearish_mat_hold', 0) < MAX_PATTERNS
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'bearish_mat_hold',
                'impact': 'Bearish Continuation',
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': t1['close']
            })

    return patterns

# === Main Analysis Function ===
def run_analysis(data_file):
    df = pd.read_csv(data_file, parse_dates=['datetime_utc']).sort_values('datetime_utc')
    patterns = detect_five_candlestick_patterns(df)

    # Count patterns by type
    pattern_counts = {}
    for pattern in patterns:
        ptype = pattern['pattern']
        pattern_counts[ptype] = pattern_counts.get(ptype, 0) + 1

    print("\nPattern Detection Summary:")
    for ptype, count in pattern_counts.items():
        print(f"{ptype.replace('_', ' ').title()}: {count}")

    return patterns

if __name__ == "__main__":
    patterns = run_analysis("OHCLV.csv")