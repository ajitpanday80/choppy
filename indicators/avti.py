"""
Ajit Volatility Transition Index (AVTI)
A novel indicator for detecting low-to-high volatility transitions
"""
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger('choppy')


def calculate_avti(df, vol_period=20, atr_short=5, atr_long=20, bb_period=20):
    """
    Calculate Ajit Volatility Transition Index (AVTI)

    The AVTI detects when the market is about to transition from LOW volatility
    to HIGH volatility - the perfect moment for options buying.

    Formula:
        AVTI = (Volume_Acceleration × Compression_Coefficient) / Directional_Deviation × 100

    Components:
        1. Volume Acceleration: Volume increasing while range is compressed
        2. Compression Coefficient: Measures price "coiling" (tight ATR + narrow BB)
        3. Directional Deviation: Filters sideways chop

    Args:
        df: DataFrame with columns: open, high, low, close, volume
        vol_period: Period for volume EMA
        atr_short: Short ATR period
        atr_long: Long ATR period
        bb_period: Bollinger Band period

    Returns:
        DataFrame with AVTI column added
    """
    try:
        # Make a copy to avoid modifying original
        data = df.copy()

        # Ensure we have required data
        if len(data) < max(vol_period, atr_long, bb_period):
            logger.warning(f"Insufficient data for AVTI calculation. Need {max(vol_period, atr_long, bb_period)} candles.")
            data['AVTI'] = 0
            return data

        # Calculate ATR (Average True Range)
        data['tr'] = np.maximum(
            data['high'] - data['low'],
            np.maximum(
                abs(data['high'] - data['close'].shift(1)),
                abs(data['low'] - data['close'].shift(1))
            )
        )

        data['atr_5'] = data['tr'].rolling(window=atr_short, min_periods=atr_short).mean()
        data['atr_20'] = data['tr'].rolling(window=atr_long, min_periods=atr_long).mean()

        # Calculate Volume EMA
        data['vol_ema'] = data['volume'].ewm(span=vol_period, adjust=False).mean()

        # Calculate Bollinger Band Width
        data['sma_20'] = data['close'].rolling(window=bb_period, min_periods=bb_period).mean()
        data['std_20'] = data['close'].rolling(window=bb_period, min_periods=bb_period).std()
        data['bbw'] = (data['std_20'] * 2) / data['sma_20'] * 100  # BB Width as %
        data['bbw_avg'] = data['bbw'].rolling(window=bb_period, min_periods=bb_period).mean()

        # Component 1: Volume Acceleration
        # High when volume is increasing but ATR is compressed
        vol_ratio = data['volume'] / data['vol_ema']
        atr_ratio = data['atr_5'] / data['atr_20']

        # Avoid division by zero
        atr_ratio = atr_ratio.replace(0, 0.01)

        v_accel = vol_ratio / atr_ratio

        # Component 2: Compression Coefficient
        # Approaches 1.0 when range is very tight vs recent history
        atr_comp = data['atr_5'] / data['atr_20']
        bb_comp = data['bbw'] / data['bbw_avg']

        # Handle edge cases
        atr_comp = atr_comp.fillna(0).replace([np.inf, -np.inf], 0)
        bb_comp = bb_comp.fillna(0).replace([np.inf, -np.inf], 0)

        c_comp = 1 - (atr_comp * bb_comp)
        c_comp = c_comp.clip(0, 2)  # Constrain to reasonable range

        # Component 3: Directional Deviation
        # Low values when price is far from mean (trending)
        # High values when price is near mean (ranging/coiling)
        price_dev = abs((data['close'] - data['sma_20']) / data['atr_20'])
        price_dev = price_dev.fillna(0).replace([np.inf, -np.inf], 0)

        # Add small constant to avoid division by zero
        d_dev = 1 + (1 / (price_dev + 0.01))
        d_dev = d_dev.clip(1, 10)  # Constrain to reasonable range

        # Calculate AVTI
        avti_raw = (v_accel * c_comp) / d_dev

        # Scale to 0-100 range and clip extremes
        data['AVTI'] = (avti_raw * 100).clip(0, 100)

        # Handle NaN values
        data['AVTI'] = data['AVTI'].fillna(0)

        logger.debug(f"AVTI calculated. Latest value: {data['AVTI'].iloc[-1]:.2f}")

        # Clean up intermediate columns (optional)
        columns_to_keep = ['date', 'open', 'high', 'low', 'close', 'volume', 'AVTI',
                          'atr_5', 'atr_20', 'sma_20', 'vol_ema', 'bbw']
        data = data[[col for col in columns_to_keep if col in data.columns]]

        return data

    except Exception as e:
        logger.error(f"Error calculating AVTI: {e}")
        df['AVTI'] = 0
        return df


def get_avti_signal(df, threshold=65):
    """
    Get AVTI signal (entry or not)

    Args:
        df: DataFrame with AVTI column
        threshold: AVTI threshold for signal

    Returns:
        Tuple: (signal_active, current_avti)
    """
    if df.empty or 'AVTI' not in df.columns:
        return False, 0

    current_avti = df['AVTI'].iloc[-1]
    signal_active = current_avti >= threshold

    return signal_active, current_avti


def is_avti_reversing(df, exit_threshold=40):
    """
    Check if AVTI is reversing (volatility exhausted)

    Args:
        df: DataFrame with AVTI
        exit_threshold: Threshold below which to consider reversal

    Returns:
        bool: True if AVTI dropped below exit threshold
    """
    if df.empty or 'AVTI' not in df.columns or len(df) < 2:
        return False

    current_avti = df['AVTI'].iloc[-1]
    return current_avti < exit_threshold


def get_avti_components(df):
    """
    Get individual AVTI components for debugging/analysis

    Args:
        df: DataFrame with AVTI calculation

    Returns:
        Dict with component values
    """
    if df.empty or len(df) < 20:
        return None

    latest = df.iloc[-1]

    try:
        vol_ratio = latest['volume'] / latest['vol_ema'] if 'vol_ema' in df.columns else 0
        atr_ratio = latest['atr_5'] / latest['atr_20'] if 'atr_5' in df.columns and 'atr_20' in df.columns else 0
        bb_compression = latest['bbw'] / latest.get('bbw_avg', 1) if 'bbw' in df.columns else 0

        return {
            'avti': latest.get('AVTI', 0),
            'volume_ratio': vol_ratio,
            'atr_ratio': atr_ratio,
            'bb_compression': bb_compression,
            'close': latest['close']
        }
    except Exception as e:
        logger.error(f"Error getting AVTI components: {e}")
        return None


class AVTIIndicator:
    """AVTI Indicator class for easier usage"""

    def __init__(self, threshold=65, exit_threshold=40):
        """
        Initialize AVTI indicator

        Args:
            threshold: Entry signal threshold
            exit_threshold: Exit signal threshold
        """
        self.threshold = threshold
        self.exit_threshold = exit_threshold
        self.last_avti = 0
        self.last_signal_time = None

    def calculate(self, df):
        """Calculate AVTI on dataframe"""
        return calculate_avti(df)

    def get_signal(self, df):
        """Get entry signal"""
        signal, avti = get_avti_signal(df, self.threshold)
        self.last_avti = avti
        return signal

    def is_exit_signal(self, df):
        """Get exit signal"""
        return is_avti_reversing(df, self.exit_threshold)

    def get_current_value(self, df):
        """Get current AVTI value"""
        if df.empty or 'AVTI' not in df.columns:
            return 0
        return df['AVTI'].iloc[-1]

    def get_components(self, df):
        """Get AVTI components"""
        return get_avti_components(df)
