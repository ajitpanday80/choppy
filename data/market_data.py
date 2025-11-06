"""
Market data handler for live and historical data
"""
import pandas as pd
import logging
from datetime import datetime, timedelta
from collections import deque

logger = logging.getLogger('choppy')


class MarketDataHandler:
    """Manages market data - both historical and live"""

    def __init__(self, zerodha_client, instrument_token, timeframe='5minute', buffer_size=100):
        """
        Initialize market data handler

        Args:
            zerodha_client: ZerodhaClient instance
            instrument_token: Instrument token to track
            timeframe: Candle timeframe
            buffer_size: Number of candles to keep in memory
        """
        self.client = zerodha_client
        self.instrument_token = instrument_token
        self.timeframe = timeframe
        self.buffer_size = buffer_size

        # Data buffer (stores recent candles)
        self.candles = pd.DataFrame()

        # Current live candle being formed
        self.current_candle = None

        logger.info(f"MarketDataHandler initialized for token {instrument_token}, timeframe {timeframe}")

    def load_historical_data(self, days=5):
        """
        Load historical data to seed the buffer

        Args:
            days: Number of days to fetch

        Returns:
            bool: Success status
        """
        try:
            to_date = datetime.now()
            from_date = to_date - timedelta(days=days)

            logger.info(f"Fetching historical data from {from_date.date()} to {to_date.date()}")

            df = self.client.get_historical_data(
                instrument_token=self.instrument_token,
                from_date=from_date,
                to_date=to_date,
                interval=self.timeframe
            )

            if df.empty:
                logger.error("No historical data received")
                return False

            # Keep only required columns
            self.candles = df[['date', 'open', 'high', 'low', 'close', 'volume']].copy()

            # Keep last buffer_size candles
            if len(self.candles) > self.buffer_size:
                self.candles = self.candles.tail(self.buffer_size)

            logger.info(f"Loaded {len(self.candles)} historical candles")
            return True

        except Exception as e:
            logger.error(f"Failed to load historical data: {e}")
            return False

    def update_live_tick(self, tick_data):
        """
        Update current candle with live tick data

        Args:
            tick_data: Tick data from WebSocket
        """
        # This would be called from WebSocket handler
        # For now, we'll use polling approach (get_latest_candle)
        pass

    def get_latest_candle(self):
        """
        Fetch the latest completed candle and update buffer

        Returns:
            Latest candle as Series
        """
        try:
            # Fetch last 2 candles to get the most recent completed one
            to_date = datetime.now()
            from_date = to_date - timedelta(hours=2)

            df = self.client.get_historical_data(
                instrument_token=self.instrument_token,
                from_date=from_date,
                to_date=to_date,
                interval=self.timeframe
            )

            if df.empty or len(df) == 0:
                logger.warning("No new candle data available")
                return None

            # Get the latest candle
            latest_candle = df.iloc[-1]

            # Check if this is a new candle (not already in buffer)
            if not self.candles.empty:
                last_buffered_date = self.candles.iloc[-1]['date']
                if latest_candle['date'] <= last_buffered_date:
                    # Same candle, no update needed
                    return None

            # Add to buffer
            new_row = latest_candle[['date', 'open', 'high', 'low', 'close', 'volume']].to_frame().T
            self.candles = pd.concat([self.candles, new_row], ignore_index=True)

            # Keep buffer size limited
            if len(self.candles) > self.buffer_size:
                self.candles = self.candles.tail(self.buffer_size)

            logger.info(f"New candle added: {latest_candle['date']} | Close: {latest_candle['close']}")
            return latest_candle

        except Exception as e:
            logger.error(f"Failed to get latest candle: {e}")
            return None

    def get_dataframe(self):
        """
        Get current dataframe with all candles

        Returns:
            DataFrame
        """
        return self.candles.copy()

    def get_latest_close(self):
        """Get latest close price"""
        if self.candles.empty:
            return None
        return self.candles.iloc[-1]['close']

    def get_latest_data(self, periods=20):
        """
        Get latest N periods of data

        Args:
            periods: Number of periods to return

        Returns:
            DataFrame
        """
        if self.candles.empty:
            return pd.DataFrame()

        return self.candles.tail(periods).copy()

    def has_sufficient_data(self, required_periods=20):
        """
        Check if we have enough data for indicator calculation

        Args:
            required_periods: Minimum periods required

        Returns:
            bool
        """
        return len(self.candles) >= required_periods

    def reset(self):
        """Reset the data buffer"""
        self.candles = pd.DataFrame()
        logger.info("Market data buffer reset")


class OptionsDataHandler:
    """Handler for options-specific data"""

    def __init__(self, zerodha_client):
        """
        Initialize options data handler

        Args:
            zerodha_client: ZerodhaClient instance
        """
        self.client = zerodha_client
        self.options_cache = {}  # Cache for options chain

    def get_atm_strike(self, spot_price, strike_interval=50):
        """
        Get ATM strike price

        Args:
            spot_price: Current spot price
            strike_interval: Strike interval

        Returns:
            ATM strike
        """
        return round(spot_price / strike_interval) * strike_interval

    def get_option_symbol(self, underlying, strike, option_type, expiry_date):
        """
        Construct option trading symbol

        Args:
            underlying: Underlying name (NIFTY, BANKNIFTY)
            strike: Strike price
            option_type: CE or PE
            expiry_date: Expiry date string (e.g., '24NOV07')

        Returns:
            Trading symbol
        """
        return f"{underlying}{expiry_date}{int(strike)}{option_type}"

    def get_option_ltp(self, trading_symbol, exchange='NFO'):
        """
        Get LTP for an option contract

        Args:
            trading_symbol: Option trading symbol
            exchange: Exchange

        Returns:
            LTP or None
        """
        try:
            instrument_id = f"{exchange}:{trading_symbol}"
            ltp_data = self.client.get_ltp([instrument_id])

            if instrument_id in ltp_data:
                ltp = ltp_data[instrument_id]['last_price']
                logger.debug(f"LTP for {trading_symbol}: {ltp}")
                return ltp
            else:
                logger.warning(f"No LTP data for {trading_symbol}")
                return None

        except Exception as e:
            logger.error(f"Failed to get option LTP: {e}")
            return None

    def find_current_expiry(self, underlying='NIFTY'):
        """
        Find the nearest weekly expiry

        Args:
            underlying: Underlying name

        Returns:
            Expiry date string (e.g., '24NOV07') or None
        """
        try:
            # Get options chain
            options = self.client.get_option_chain(underlying)

            if options.empty:
                logger.error("No options data available")
                return None

            # Get unique expiry dates
            options['expiry'] = pd.to_datetime(options['expiry'])
            expiries = sorted(options['expiry'].unique())

            # Find nearest expiry after today
            today = datetime.now()
            future_expiries = [exp for exp in expiries if exp > today]

            if not future_expiries:
                logger.error("No future expiries found")
                return None

            nearest_expiry = future_expiries[0]

            # Format as required (e.g., '24NOV07')
            expiry_str = nearest_expiry.strftime('%y%b%d').upper()
            logger.info(f"Current expiry: {expiry_str} ({nearest_expiry.date()})")

            return expiry_str

        except Exception as e:
            logger.error(f"Failed to find current expiry: {e}")
            return None

    def get_atm_option_details(self, spot_price, option_type='CE', underlying='NIFTY', strike_interval=50):
        """
        Get ATM option details (symbol, LTP)

        Args:
            spot_price: Current spot price
            option_type: CE or PE
            underlying: Underlying name
            strike_interval: Strike interval

        Returns:
            Dict with symbol and ltp
        """
        try:
            # Get ATM strike
            atm_strike = self.get_atm_strike(spot_price, strike_interval)

            # Get current expiry
            expiry = self.find_current_expiry(underlying)
            if not expiry:
                logger.error("Could not determine expiry")
                return None

            # Construct symbol
            symbol = self.get_option_symbol(underlying, atm_strike, option_type, expiry)

            # Get LTP
            ltp = self.get_option_ltp(symbol)

            if ltp is None:
                logger.error(f"Could not get LTP for {symbol}")
                return None

            return {
                'symbol': symbol,
                'strike': atm_strike,
                'option_type': option_type,
                'ltp': ltp,
                'expiry': expiry
            }

        except Exception as e:
            logger.error(f"Failed to get ATM option details: {e}")
            return None
