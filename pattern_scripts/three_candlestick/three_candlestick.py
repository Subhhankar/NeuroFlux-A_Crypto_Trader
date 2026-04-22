import pandas as pd
import numpy as np
from tqdm import tqdm

# === Configuration ===
SHORT_TERM_PERIOD = 20
LONG_TERM_PERIOD = 50
PRICE_TOLERANCE = 0.001  # For patterns like stick sandwich
DOJI_THRESHOLD = 0.1      # For doji detection
DOJI_BODY_FACTOR = 0.05  # For abandoned baby, evening/morning doji star
MIN_BODY_RATIO = 0.6     # For long candles (e.g., advance block, unique three river)
MIN_LOWER_SHADOW = 2     # For hammer in unique three river
MAX_BULLISH = 50
MAX_BEARISH = 50

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

# === Doji Detection ===
def is_doji(candle, threshold=DOJI_THRESHOLD, avg_candle_size=None):
    body = abs(candle['close'] - candle['open'])
    if avg_candle_size:
        return body < DOJI_BODY_FACTOR * avg_candle_size
    total_range = candle['high'] - candle['low']
    return total_range > 0 and body <= threshold * total_range

# === Consolidated Pattern Detection ===
def detect_three_candlestick_patterns(df):
    patterns = []
    trend_cache = {}
    avg_candle_size = np.mean(abs(df['close'] - df['open']))

    print("Scanning for all three-candlestick patterns...")
    for i in tqdm(range(max(SHORT_TERM_PERIOD, LONG_TERM_PERIOD) + 3, len(df))):
        c1 = df.iloc[i - 3]  # t-3
        c2 = df.iloc[i - 2]  # t-2
        c3 = df.iloc[i - 1]  # t-1
        trends = determine_trends(df, i - 1, trend_cache)
        avg_price = (c1['close'] + c2['close'] + c3['close']) / 3

        # Count patterns to enforce limits
        bullish_counts = {p: sum(1 for x in patterns if x['pattern'] == p) for p in [
            'bullish_abandoned_baby', 'bullish_doji_star', 'morning_doji_star',
            'bullish_side_by_side_white_lines', 'bullish_stick_sandwich',
            'bullish_tri_star_doji', 'unique_three_river', 'upside_tasuki_gap']}
        bearish_counts = {p: sum(1 for x in patterns if x['pattern'] == p) for p in [
            'bearish_abandoned_baby', 'advance_block', 'deliberation_pattern',
            'bearish_doji_star', 'evening_doji_star', 'bearish_side_by_side_white_lines',
            'bearish_stick_sandwich', 'three_black_crows', 'bearish_tri_star_doji',
            'upside_gap_two_crows', 'downside_tasuki_gap']}

        if all(count >= MAX_BULLISH for count in bullish_counts.values()) and \
           all(count >= MAX_BEARISH for count in bearish_counts.values()):
            break

        # === Bullish Abandoned Baby ===
        c1_body = abs(c1['close'] - c1['open'])
        c2_body = abs(c2['close'] - c2['open'])
        c3_body = abs(c3['close'] - c3['open'])
        if (
            trends['short_term'] == 'down' and trends['long_term'] == 'down' and
            c1['close'] < c1['open'] and
            is_doji(c2, avg_candle_size=avg_candle_size) and
            (c2['low'] > c1['high'] or c2['high'] < c1['low']) and
            c3['close'] > c3['open'] and
            (c3['low'] > c2['high'] or c3['high'] < c2['low']) and
            c3['close'] > c1['open'] and
            bullish_counts.get('bullish_abandoned_baby', 0) < MAX_BULLISH
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'bullish_abandoned_baby',
                'impact': 'Potential Bullish Reversal',
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': c3['close']
            })

        # === Bearish Abandoned Baby ===
        elif (
            trends['short_term'] == 'up' and trends['long_term'] == 'up' and
            c1['close'] > c1['open'] and
            is_doji(c2, avg_candle_size=avg_candle_size) and
            (c2['low'] > c1['high'] or c2['high'] < c1['low']) and
            c3['close'] < c3['open'] and
            (c3['low'] > c2['high'] or c3['high'] < c2['low']) and
            c3['close'] < c1['open'] and
            bearish_counts.get('bearish_abandoned_baby', 0) < MAX_BEARISH
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'bearish_abandoned_baby',
                'impact': 'Potential Bearish Reversal',
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': c3['close']
            })

        # === Advance Block ===
        if (
            trends['short_term'] == 'up' and
            c1['close'] > c1['open'] and c2['close'] > c2['open'] and c3['close'] > c3['open'] and
            c2['open'] > c1['open'] and c2['open'] < c1['close'] and
            c3['open'] > c2['open'] and c3['open'] < c2['close'] and
            (c1['close'] - c1['open']) > (c2['close'] - c2['open']) > (c3['close'] - c3['open']) and
            (c2['high'] - max(c2['open'], c2['close'])) > (c1['high'] - max(c1['open'], c1['close'])) and
            (c3['high'] - max(c3['open'], c3['close'])) > (c2['high'] - max(c2['open'], c2['close'])) and
            bearish_counts.get('advance_block', 0) < MAX_BEARISH
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'advance_block',
                'impact': 'Potential Bearish Reversal',
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': c3['close']
            })

        # === Deliberation Pattern ===
        c1_range = c1['high'] - c1['low']
        c2_range = c2['high'] - c2['low']
        c1_body = abs(c1['close'] - c1['open'])
        c2_body = abs(c2['close'] - c2['open'])
        c3_body = abs(c3['close'] - c3['open'])
        c3_upper_shadow = c3['high'] - max(c3['open'], c3['close'])
        if (
            trends['short_term'] == 'up' and trends['long_term'] == 'up' and
            c1['close'] > c1['open'] and c2['close'] > c2['open'] and c3['close'] > c3['open'] and
            c1_body >= 0.6 * c1_range and c2_body >= 0.6 * c2_range and
            c3_body < c1_body * 0.5 and c3_upper_shadow > c3_body and
            c2['open'] > c1['open'] and c2['close'] > c1['close'] and
            c3['open'] > c2['open'] and
            bearish_counts.get('deliberation_pattern', 0) < MAX_BEARISH
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'deliberation_pattern',
                'impact': 'Potential Bullish Exhaustion',
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': c3['close']
            })

        # === Bullish Doji Star ===
        if (
            trends['short_term'] == 'down' and trends['long_term'] == 'down' and
            c1['close'] < c1['open'] and
            c2_body <= 0.001 * ((c2['high'] + c2['low']) / 2) and
            c2['low'] < c1['close'] and
            c3['close'] > c3['open'] and
            c3['close'] > (c1['open'] + c1['close']) / 2 and
            c1_body > 0.005 * avg_price and c3_body > 0.005 * avg_price and
            bullish_counts.get('bullish_doji_star', 0) < MAX_BULLISH
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'bullish_doji_star',
                'impact': 'Potential Bullish Reversal',
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': c3['close']
            })

        # === Bearish Doji Star ===
        elif (
            trends['short_term'] == 'up' and trends['long_term'] == 'up' and
            c1['close'] > c1['open'] and
            c2_body <= 0.001 * ((c2['high'] + c2['low']) / 2) and
            c2['high'] > c1['close'] and
            c3['close'] < c3['open'] and
            c3['close'] < (c1['open'] + c1['close']) / 2 and
            c1_body > 0.005 * avg_price and c3_body > 0.005 * avg_price and
            bearish_counts.get('bearish_doji_star', 0) < MAX_BEARISH
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'bearish_doji_star',
                'impact': 'Potential Bearish Reversal',
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': c3['close']
            })

        # === Evening Doji Star ===
        if (
            trends['short_term'] == 'up' and trends['long_term'] == 'up' and
            c1['close'] > c1['open'] and
            c2_body < 0.05 * avg_candle_size and c2_body < 0.1 * c1_body and
            c2['open'] > c1['close'] and
            c3['close'] < c3['open'] and
            c3['open'] < c2['open'] and c3['close'] < c2['close'] and
            bearish_counts.get('evening_doji_star', 0) < MAX_BEARISH
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'evening_doji_star',
                'impact': 'Potential Bearish Reversal',
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': c3['close']
            })

        # === Morning Doji Star ===
        if (
            trends['short_term'] == 'down' and trends['long_term'] == 'down' and
            c1['close'] < c1['open'] and
            is_doji(c2) and c2['open'] < c1['close'] and
            c3['close'] > c3['open'] and
            c3['open'] > c2['open'] and c3['close'] > c1['open'] and
            bullish_counts.get('morning_doji_star', 0) < MAX_BULLISH
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'morning_doji_star',
                'impact': 'Potential Bullish Reversal',
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': c3['close']
            })

        # === Bullish Side-by-Side White Lines ===
        if (
            trends['short_term'] == 'up' and trends['long_term'] == 'up' and
            c1['close'] > c1['open'] and c2['close'] > c2['open'] and c3['close'] > c3['open'] and
            c2['open'] > c1['close'] and
            abs(c3['open'] - c2['open']) / c2['open'] < 0.01 and
            abs((c3['close'] - c3['open']) - (c2['close'] - c2['open'])) / c2['open'] < 0.2 and
            bullish_counts.get('bullish_side_by_side_white_lines', 0) < MAX_BULLISH
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'bullish_side_by_side_white_lines',
                'impact': 'Bullish Continuation',
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': c3['close']
            })

        # === Bearish Side-by-Side White Lines ===
        elif (
            trends['short_term'] == 'down' and trends['long_term'] == 'down' and
            c1['close'] < c1['open'] and c2['close'] > c2['open'] and c3['close'] > c3['open'] and
            c2['open'] < c1['close'] and
            abs(c3['open'] - c2['open']) / c2['open'] < 0.01 and
            abs((c3['close'] - c3['open']) - (c2['close'] - c2['open'])) / c2['open'] < 0.2 and
            bearish_counts.get('bearish_side_by_side_white_lines', 0) < MAX_BEARISH
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'bearish_side_by_side_white_lines',
                'impact': 'Bearish Continuation',
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': c3['close']
            })

        # === Bullish Stick Sandwich ===
        if (
            trends['short_term'] == 'down' and trends['long_term'] == 'down' and
            c1['close'] < c1['open'] and c2['close'] > c2['open'] and c3['close'] < c3['open'] and
            abs(c3['close'] - c1['close']) / c1['close'] < 0.002 and
            bullish_counts.get('bullish_stick_sandwich', 0) < MAX_BULLISH
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'bullish_stick_sandwich',
                'impact': 'Potential Bullish Reversal',
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': c3['close']
            })

        # === Bearish Stick Sandwich ===
        elif (
            trends['short_term'] == 'up' and trends['long_term'] == 'up' and
            c1['close'] > c1['open'] and c2['close'] < c2['open'] and c3['close'] > c3['open'] and
            abs(c3['close'] - c1['close']) / c1['close'] < 0.002 and
            bearish_counts.get('bearish_stick_sandwich', 0) < MAX_BEARISH
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'bearish_stick_sandwich',
                'impact': 'Potential Bearish Reversal',
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': c3['close']
            })

        # === Three Black Crows ===
        if (
            trends['short_term'] == 'up' and trends['long_term'] == 'up' and
            c1['close'] < c1['open'] and c2['close'] < c2['open'] and c3['close'] < c3['open'] and
            c2['open'] <= c1['open'] and c2['open'] >= c1['close'] and
            c3['open'] <= c2['open'] and c3['open'] >= c2['close'] and
            c2['close'] < c1['close'] and c3['close'] < c2['close'] and
            (c1['high'] - max(c1['open'], c1['close'])) < 0.25 * (c1['high'] - c1['low']) and
            (c2['high'] - max(c2['open'], c2['close'])) < 0.25 * (c2['high'] - c2['low']) and
            (c3['high'] - max(c3['open'], c3['close'])) < 0.25 * (c3['high'] - c3['low']) and
            bearish_counts.get('three_black_crows', 0) < MAX_BEARISH
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'three_black_crows',
                'impact': 'Bearish Reversal',
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': c3['close']
            })

        # === Bullish Tri-Star Doji ===
        if (
            trends['short_term'] == 'down' and trends['long_term'] == 'down' and
            is_doji(c1) and is_doji(c2) and is_doji(c3) and
            c2['high'] < c1['low'] and c3['low'] > c2['high'] and
            bullish_counts.get('bullish_tri_star_doji', 0) < MAX_BULLISH
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'bullish_tri_star_doji',
                'impact': 'Potential Bullish Reversal',
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': c3['close']
            })

        # === Bearish Tri-Star Doji ===
        elif (
            trends['short_term'] == 'up' and trends['long_term'] == 'up' and
            is_doji(c1) and is_doji(c2) and is_doji(c3) and
            c2['low'] > c1['high'] and c3['high'] < c2['low'] and
            bearish_counts.get('bearish_tri_star_doji', 0) < MAX_BEARISH
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'bearish_tri_star_doji',
                'impact': 'Potential Bearish Reversal',
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': c3['close']
            })

        # === Unique Three River ===
        c2_lower = min(c2['open'], c2['close']) - c2['low']
        if (
            trends['short_term'] == 'down' and trends['long_term'] == 'down' and
            c1['close'] < c1['open'] and c1_body > (c1['high'] - c1['low']) * 0.6 and
            c2_body < (c2['high'] - c2['low']) * 0.3 and c2_lower > c2_body * 2 and
            c3['close'] > c3['open'] and
            c3['close'] < max(c2['open'], c2['close']) and c3['open'] > c2['low'] and
            c3['high'] <= c2['high'] and c3['low'] >= c2['low'] and
            bullish_counts.get('unique_three_river', 0) < MAX_BULLISH
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'unique_three_river',
                'impact': 'Potential Bullish Reversal',
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': c3['close']
            })

        # === Upside Tasuki Gap ===
        if (
            trends['short_term'] == 'up' and trends['long_term'] == 'up' and
            c1['close'] > c1['open'] and
            c2['open'] > c1['close'] and c2['close'] > c2['open'] and
            c3['open'] > c2['close'] and c3['close'] < c3['open'] and
            c1['close'] < c3['close'] < c2['open'] and
            bullish_counts.get('upside_tasuki_gap', 0) < MAX_BULLISH
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'upside_tasuki_gap',
                'impact': 'Bullish Continuation',
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': c3['close']
            })

        # === Downside Tasuki Gap ===
        elif (
            trends['short_term'] == 'down' and trends['long_term'] == 'down' and
            c1['close'] < c1['open'] and
            c2['open'] < c1['close'] and c2['close'] < c2['open'] and
            c3['open'] < c2['close'] and c3['close'] > c3['open'] and
            c2['open'] < c3['close'] < c1['close'] and
            bearish_counts.get('downside_tasuki_gap', 0) < MAX_BEARISH
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'downside_tasuki_gap',
                'impact': 'Bearish Continuation',
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': c3['close']
            })

        # === Upside Gap Two Crows ===
        if (
            trends['short_term'] == 'up' and trends['long_term'] == 'up' and
            c1['close'] > c1['open'] and
            c2['open'] > c1['close'] and c2['close'] < c2['open'] and
            c3['open'] > c2['open'] and c3['close'] < c2['close'] and c3['close'] > c1['close'] and
            c3['close'] < c3['open'] and
            bearish_counts.get('upside_gap_two_crows', 0) < MAX_BEARISH
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'upside_gap_two_crows',
                'impact': 'Bearish Reversal',
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': c3['close']
            })

    return patterns

# === Main Analysis Function ===
def run_analysis(data_file):
    df = pd.read_csv(data_file, parse_dates=['datetime_utc']).sort_values('datetime_utc')
    patterns = detect_three_candlestick_patterns(df)

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