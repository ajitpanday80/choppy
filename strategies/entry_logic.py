"""
Entry signal logic for options trading
"""
import logging
from indicators.avti import get_avti_signal
from indicators.supporting import (
    is_above_vwap,
    is_below_vwap,
    has_volume_spike,
    get_recent_trend,
    get_market_bias
)

logger = logging.getLogger('choppy')


class EntrySignalGenerator:
    """Generate entry signals for options trading"""

    def __init__(self, avti_threshold=65, volume_spike_multiplier=1.5, vwap_periods=3):
        """
        Initialize entry signal generator

        Args:
            avti_threshold: AVTI value above which to consider entry
            volume_spike_multiplier: Volume spike threshold
            vwap_periods: Number of periods to check VWAP consistency
        """
        self.avti_threshold = avti_threshold
        self.volume_spike_multiplier = volume_spike_multiplier
        self.vwap_periods = vwap_periods

    def check_entry_conditions(self, df):
        """
        Check all entry conditions

        Args:
            df: DataFrame with price data and indicators

        Returns:
            Dict with entry signal details or None
        """
        try:
            if df.empty or len(df) < 20:
                logger.debug("Insufficient data for entry check")
                return None

            # Condition 1: AVTI above threshold
            avti_signal, current_avti = get_avti_signal(df, self.avti_threshold)

            if not avti_signal:
                logger.debug(f"AVTI {current_avti:.2f} below threshold {self.avti_threshold}")
                return None

            logger.info(f"✓ AVTI signal active: {current_avti:.2f}")

            # Condition 2: Volume spike
            volume_spike = has_volume_spike(df, self.volume_spike_multiplier)

            if not volume_spike:
                logger.debug("No volume spike detected")
                return None

            logger.info(f"✓ Volume spike detected")

            # Condition 3: Directional bias
            signal_type, bias_strength = self._determine_direction(df)

            if signal_type == 'NEUTRAL':
                logger.debug("No clear directional bias")
                return None

            logger.info(f"✓ Directional bias: {signal_type} (strength: {bias_strength})")

            # All conditions met - generate signal
            latest = df.iloc[-1]

            signal = {
                'signal_type': signal_type,  # CALL or PUT
                'avti': current_avti,
                'close': latest['close'],
                'vwap': latest.get('VWAP', latest['close']),
                'volume': latest['volume'],
                'bias_strength': bias_strength,
                'timestamp': latest.get('date', None)
            }

            logger.info(f"🎯 ENTRY SIGNAL: {signal_type} | AVTI: {current_avti:.2f} | Price: {latest['close']:.2f}")

            return signal

        except Exception as e:
            logger.error(f"Error checking entry conditions: {e}")
            return None

    def _determine_direction(self, df):
        """
        Determine trade direction (CALL or PUT)

        Args:
            df: DataFrame with indicators

        Returns:
            Tuple: (signal_type, bias_strength)
                signal_type: 'CALL', 'PUT', or 'NEUTRAL'
                bias_strength: 0-100 (confidence in signal)
        """
        try:
            signals = []

            # Check VWAP position (strong signal)
            if is_above_vwap(df, self.vwap_periods):
                signals.append(('CALL', 30))
                logger.debug("Price above VWAP for 3+ periods → CALL bias")

            if is_below_vwap(df, self.vwap_periods):
                signals.append(('PUT', 30))
                logger.debug("Price below VWAP for 3+ periods → PUT bias")

            # Check recent trend
            trend = get_recent_trend(df, periods=3)
            if trend == 'BULLISH':
                signals.append(('CALL', 20))
                logger.debug("Recent trend bullish → CALL bias")
            elif trend == 'BEARISH':
                signals.append(('PUT', 20))
                logger.debug("Recent trend bearish → PUT bias")

            # Check overall market bias
            market_bias = get_market_bias(df)
            if market_bias == 'BULLISH':
                signals.append(('CALL', 15))
                logger.debug("Market bias bullish → CALL bias")
            elif market_bias == 'BEARISH':
                signals.append(('PUT', 15))
                logger.debug("Market bias bearish → PUT bias")

            # Check price vs EMAs (if available)
            if 'EMA_20' in df.columns:
                latest = df.iloc[-1]
                if latest['close'] > latest['EMA_20']:
                    signals.append(('CALL', 10))
                else:
                    signals.append(('PUT', 10))

            # Aggregate signals
            call_score = sum(strength for signal_type, strength in signals if signal_type == 'CALL')
            put_score = sum(strength for signal_type, strength in signals if signal_type == 'PUT')

            logger.debug(f"Direction scores - CALL: {call_score}, PUT: {put_score}")

            # Need at least 40 points to generate signal
            if call_score >= 40:
                return 'CALL', call_score
            elif put_score >= 40:
                return 'PUT', put_score
            else:
                return 'NEUTRAL', 0

        except Exception as e:
            logger.error(f"Error determining direction: {e}")
            return 'NEUTRAL', 0

    def get_option_type(self, signal_type):
        """
        Convert signal type to option type

        Args:
            signal_type: 'CALL' or 'PUT'

        Returns:
            'CE' or 'PE'
        """
        return 'CE' if signal_type == 'CALL' else 'PE'

    def validate_signal(self, signal, market_data):
        """
        Additional validation for generated signal

        Args:
            signal: Entry signal dict
            market_data: Current market data

        Returns:
            bool: True if signal is valid
        """
        try:
            # Check if price hasn't moved too much since signal
            if abs(market_data['close'] - signal['close']) / signal['close'] > 0.02:  # 2% move
                logger.warning("Price moved >2% since signal generation - signal may be stale")
                return False

            # Check AVTI is still active
            if market_data.get('avti', 0) < self.avti_threshold * 0.9:  # Allow 10% drop
                logger.warning("AVTI dropped significantly - signal weakened")
                return False

            return True

        except Exception as e:
            logger.error(f"Error validating signal: {e}")
            return False


class EntryFilter:
    """Additional filters for entry signals"""

    def __init__(self):
        """Initialize entry filter"""
        pass

    def filter_signal(self, signal, current_positions, daily_pnl, max_positions=2, max_daily_loss=5000):
        """
        Filter signal based on risk management rules

        Args:
            signal: Entry signal
            current_positions: Number of current open positions
            daily_pnl: Current daily P&L
            max_positions: Maximum allowed positions
            max_daily_loss: Maximum daily loss threshold

        Returns:
            Tuple: (allowed, reason)
        """
        try:
            # Check max positions
            if current_positions >= max_positions:
                logger.warning(f"Max positions ({max_positions}) reached. Signal rejected.")
                return False, f"MAX_POSITIONS_REACHED ({current_positions}/{max_positions})"

            # Check daily loss limit
            if daily_pnl < -max_daily_loss:
                logger.warning(f"Daily loss limit exceeded (₹{daily_pnl:.2f}). Trading halted.")
                return False, f"DAILY_LOSS_LIMIT_EXCEEDED ({daily_pnl:.2f})"

            # All filters passed
            return True, "PASSED"

        except Exception as e:
            logger.error(f"Error in entry filter: {e}")
            return False, "FILTER_ERROR"

    def check_time_filter(self, trading_hours):
        """
        Check if current time is within trading hours

        Args:
            trading_hours: Tuple of ((start_h, start_m), (end_h, end_m))

        Returns:
            bool: True if within trading hours
        """
        from datetime import datetime
        import pytz

        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)

        # Check if weekday
        if now.weekday() >= 5:
            logger.debug("Weekend - no trading")
            return False

        from datetime import time
        start_time = time(trading_hours[0][0], trading_hours[0][1])
        end_time = time(trading_hours[1][0], trading_hours[1][1])
        current_time = now.time()

        in_hours = start_time <= current_time <= end_time

        if not in_hours:
            logger.debug(f"Outside trading hours ({start_time} - {end_time})")

        return in_hours
