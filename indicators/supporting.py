"""
Supporting indicators for trading system
Includes VWAP, ATR, EMA, Volume analysis, etc.
"""
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger('choppy')


def calculate_vwap(df):
    """
    Calculate VWAP (Volume Weighted Average Price)

    Args:
        df: DataFrame with columns: high, low, close, volume

    Returns:
        DataFrame with VWAP column added
    """
    try:
        data = df.copy()

        # Typical Price
        data['typical_price'] = (data['high'] + data['low'] + data['close']) / 3

        # Cumulative TPV (Typical Price × Volume)
        data['tpv'] = data['typical_price'] * data['volume']
        data['cum_tpv'] = data['tpv'].cumsum()

        # Cumulative Volume
        data['cum_volume'] = data['volume'].cumsum()

        # VWAP
        data['VWAP'] = data['cum_tpv'] / data['cum_volume']

        # Clean up intermediate columns
        data = data.drop(columns=['typical_price', 'tpv', 'cum_tpv', 'cum_volume'])

        return data

    except Exception as e:
        logger.error(f"Error calculating VWAP: {e}")
        df['VWAP'] = df['close']
        return df


def calculate_ema(df, column='close', period=20):
    """
    Calculate Exponential Moving Average

    Args:
        df: DataFrame
        column: Column to calculate EMA on
        period: EMA period

    Returns:
        Series with EMA values
    """
    try:
        return df[column].ewm(span=period, adjust=False).mean()
    except Exception as e:
        logger.error(f"Error calculating EMA: {e}")
        return df[column]


def calculate_sma(df, column='close', period=20):
    """
    Calculate Simple Moving Average

    Args:
        df: DataFrame
        column: Column to calculate SMA on
        period: SMA period

    Returns:
        Series with SMA values
    """
    try:
        return df[column].rolling(window=period, min_periods=period).mean()
    except Exception as e:
        logger.error(f"Error calculating SMA: {e}")
        return df[column]


def calculate_atr(df, period=14):
    """
    Calculate Average True Range (ATR)

    Args:
        df: DataFrame with high, low, close
        period: ATR period

    Returns:
        Series with ATR values
    """
    try:
        data = df.copy()

        # True Range
        data['tr'] = np.maximum(
            data['high'] - data['low'],
            np.maximum(
                abs(data['high'] - data['close'].shift(1)),
                abs(data['low'] - data['close'].shift(1))
            )
        )

        # ATR
        atr = data['tr'].rolling(window=period, min_periods=period).mean()

        return atr

    except Exception as e:
        logger.error(f"Error calculating ATR: {e}")
        return pd.Series(0, index=df.index)


def is_bullish_candle(row):
    """Check if candle is bullish"""
    return row['close'] > row['open']


def is_bearish_candle(row):
    """Check if candle is bearish"""
    return row['close'] < row['open']


def get_recent_trend(df, periods=3):
    """
    Get recent trend direction

    Args:
        df: DataFrame with OHLC
        periods: Number of periods to check

    Returns:
        String: 'BULLISH', 'BEARISH', or 'NEUTRAL'
    """
    try:
        if df.empty or len(df) < periods:
            return 'NEUTRAL'

        recent = df.tail(periods)

        bullish_count = sum(1 for _, row in recent.iterrows() if is_bullish_candle(row))
        bearish_count = sum(1 for _, row in recent.iterrows() if is_bearish_candle(row))

        if bullish_count > bearish_count:
            return 'BULLISH'
        elif bearish_count > bullish_count:
            return 'BEARISH'
        else:
            return 'NEUTRAL'

    except Exception as e:
        logger.error(f"Error getting trend: {e}")
        return 'NEUTRAL'


def is_above_vwap(df, periods=3):
    """
    Check if price has been above VWAP for last N periods

    Args:
        df: DataFrame with close and VWAP
        periods: Number of periods to check

    Returns:
        bool: True if consistently above VWAP
    """
    try:
        if df.empty or 'VWAP' not in df.columns or len(df) < periods:
            return False

        recent = df.tail(periods)
        return all(recent['close'] > recent['VWAP'])

    except Exception as e:
        logger.error(f"Error checking VWAP position: {e}")
        return False


def is_below_vwap(df, periods=3):
    """
    Check if price has been below VWAP for last N periods

    Args:
        df: DataFrame with close and VWAP
        periods: Number of periods to check

    Returns:
        bool: True if consistently below VWAP
    """
    try:
        if df.empty or 'VWAP' not in df.columns or len(df) < periods:
            return False

        recent = df.tail(periods)
        return all(recent['close'] < recent['VWAP'])

    except Exception as e:
        logger.error(f"Error checking VWAP position: {e}")
        return False


def has_volume_spike(df, multiplier=1.5, lookback=10):
    """
    Check if current volume is a spike compared to recent average

    Args:
        df: DataFrame with volume
        multiplier: Volume multiplier threshold
        lookback: Periods for average calculation

    Returns:
        bool: True if volume spike detected
    """
    try:
        if df.empty or len(df) < lookback + 1:
            return False

        current_volume = df['volume'].iloc[-1]
        avg_volume = df['volume'].iloc[-(lookback+1):-1].mean()

        return current_volume > (avg_volume * multiplier)

    except Exception as e:
        logger.error(f"Error checking volume spike: {e}")
        return False


def calculate_rsi(df, column='close', period=14):
    """
    Calculate RSI (Relative Strength Index)

    Args:
        df: DataFrame
        column: Column to calculate RSI on
        period: RSI period

    Returns:
        Series with RSI values
    """
    try:
        delta = df[column].diff()

        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)

        avg_gain = gain.rolling(window=period, min_periods=period).mean()
        avg_loss = loss.rolling(window=period, min_periods=period).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    except Exception as e:
        logger.error(f"Error calculating RSI: {e}")
        return pd.Series(50, index=df.index)


def add_all_indicators(df):
    """
    Add all indicators to dataframe

    Args:
        df: DataFrame with OHLCV

    Returns:
        DataFrame with all indicators
    """
    try:
        data = df.copy()

        # VWAP
        data = calculate_vwap(data)

        # ATR
        data['ATR'] = calculate_atr(data, period=14)
        data['ATR_5'] = calculate_atr(data, period=5)
        data['ATR_20'] = calculate_atr(data, period=20)

        # EMAs
        data['EMA_9'] = calculate_ema(data, 'close', 9)
        data['EMA_20'] = calculate_ema(data, 'close', 20)
        data['EMA_50'] = calculate_ema(data, 'close', 50)

        # SMAs
        data['SMA_20'] = calculate_sma(data, 'close', 20)

        # RSI
        data['RSI'] = calculate_rsi(data, 'close', 14)

        # Volume MA
        data['Volume_MA'] = data['volume'].rolling(window=20, min_periods=20).mean()

        logger.debug("All indicators calculated successfully")

        return data

    except Exception as e:
        logger.error(f"Error adding indicators: {e}")
        return df


def get_market_bias(df):
    """
    Get overall market bias based on multiple indicators

    Args:
        df: DataFrame with indicators

    Returns:
        String: 'BULLISH', 'BEARISH', or 'NEUTRAL'
    """
    try:
        if df.empty or len(df) < 20:
            return 'NEUTRAL'

        latest = df.iloc[-1]
        signals = []

        # VWAP position
        if 'VWAP' in df.columns:
            if latest['close'] > latest['VWAP']:
                signals.append(1)
            else:
                signals.append(-1)

        # EMA alignment
        if 'EMA_9' in df.columns and 'EMA_20' in df.columns:
            if latest['EMA_9'] > latest['EMA_20']:
                signals.append(1)
            else:
                signals.append(-1)

        # Price vs EMA
        if 'EMA_20' in df.columns:
            if latest['close'] > latest['EMA_20']:
                signals.append(1)
            else:
                signals.append(-1)

        # RSI
        if 'RSI' in df.columns:
            if latest['RSI'] > 55:
                signals.append(1)
            elif latest['RSI'] < 45:
                signals.append(-1)

        # Trend
        trend = get_recent_trend(df, 3)
        if trend == 'BULLISH':
            signals.append(1)
        elif trend == 'BEARISH':
            signals.append(-1)

        # Aggregate signals
        total_signal = sum(signals)

        if total_signal >= 2:
            return 'BULLISH'
        elif total_signal <= -2:
            return 'BEARISH'
        else:
            return 'NEUTRAL'

    except Exception as e:
        logger.error(f"Error getting market bias: {e}")
        return 'NEUTRAL'
