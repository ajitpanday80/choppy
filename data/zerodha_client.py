"""
Zerodha KiteConnect API wrapper
"""
from kiteconnect import KiteConnect
import logging
from datetime import datetime, timedelta
import pandas as pd

logger = logging.getLogger('choppy')


class ZerodhaClient:
    """Wrapper for Zerodha KiteConnect API"""

    def __init__(self, api_key, api_secret, access_token=None):
        """
        Initialize Zerodha client

        Args:
            api_key: Zerodha API key
            api_secret: Zerodha API secret
            access_token: Access token (if already generated)
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.access_token = access_token

        self.kite = KiteConnect(api_key=api_key)

        if access_token:
            self.kite.set_access_token(access_token)
            logger.info("Zerodha client initialized with access token")
        else:
            logger.warning("No access token provided. You'll need to generate one.")

    def generate_session(self, request_token):
        """
        Generate session using request token

        Args:
            request_token: Request token from login callback

        Returns:
            Access token
        """
        try:
            data = self.kite.generate_session(request_token, api_secret=self.api_secret)
            self.access_token = data["access_token"]
            self.kite.set_access_token(self.access_token)
            logger.info("Session generated successfully")
            return self.access_token
        except Exception as e:
            logger.error(f"Failed to generate session: {e}")
            raise

    def get_profile(self):
        """Get user profile"""
        try:
            profile = self.kite.profile()
            logger.info(f"Logged in as: {profile['user_name']}")
            return profile
        except Exception as e:
            logger.error(f"Failed to get profile: {e}")
            return None

    def get_margins(self):
        """Get account margins"""
        try:
            margins = self.kite.margins()
            return margins
        except Exception as e:
            logger.error(f"Failed to get margins: {e}")
            return None

    def get_historical_data(self, instrument_token, from_date, to_date, interval='5minute'):
        """
        Get historical data

        Args:
            instrument_token: Instrument token
            from_date: Start date (datetime or string)
            to_date: End date (datetime or string)
            interval: Timeframe (minute, 3minute, 5minute, 15minute, day)

        Returns:
            DataFrame with OHLCV data
        """
        try:
            data = self.kite.historical_data(
                instrument_token=instrument_token,
                from_date=from_date,
                to_date=to_date,
                interval=interval
            )

            if not data:
                logger.warning(f"No historical data returned for token {instrument_token}")
                return pd.DataFrame()

            df = pd.DataFrame(data)
            logger.info(f"Fetched {len(df)} candles for instrument {instrument_token}")
            return df

        except Exception as e:
            logger.error(f"Failed to fetch historical data: {e}")
            return pd.DataFrame()

    def get_ltp(self, instruments):
        """
        Get Last Traded Price for instruments

        Args:
            instruments: List of instrument identifiers (e.g., ['NSE:NIFTY 50'])

        Returns:
            Dict with LTP data
        """
        try:
            ltp_data = self.kite.ltp(instruments)
            return ltp_data
        except Exception as e:
            logger.error(f"Failed to get LTP: {e}")
            return {}

    def get_quote(self, instruments):
        """
        Get full quote for instruments

        Args:
            instruments: List of instrument identifiers

        Returns:
            Dict with quote data
        """
        try:
            quote_data = self.kite.quote(instruments)
            return quote_data
        except Exception as e:
            logger.error(f"Failed to get quote: {e}")
            return {}

    def get_instruments(self, exchange=None):
        """
        Get instruments list

        Args:
            exchange: Exchange name (NSE, NFO, etc.)

        Returns:
            List of instruments
        """
        try:
            instruments = self.kite.instruments(exchange)
            logger.info(f"Fetched {len(instruments)} instruments for {exchange}")
            return instruments
        except Exception as e:
            logger.error(f"Failed to get instruments: {e}")
            return []

    def search_instruments(self, query, exchange='NFO'):
        """
        Search for instruments by name

        Args:
            query: Search query (e.g., 'NIFTY24NOV')
            exchange: Exchange to search in

        Returns:
            List of matching instruments
        """
        try:
            instruments = self.get_instruments(exchange)
            matches = [inst for inst in instruments if query.upper() in inst['tradingsymbol'].upper()]
            logger.info(f"Found {len(matches)} instruments matching '{query}'")
            return matches
        except Exception as e:
            logger.error(f"Failed to search instruments: {e}")
            return []

    def place_order(self, tradingsymbol, exchange, transaction_type, quantity, order_type='MARKET', product='MIS', price=None):
        """
        Place an order

        Args:
            tradingsymbol: Trading symbol (e.g., 'NIFTY24NOV19500CE')
            exchange: Exchange (NFO for F&O)
            transaction_type: BUY or SELL
            quantity: Order quantity
            order_type: MARKET or LIMIT
            product: MIS (intraday) or NRML (normal)
            price: Limit price (for LIMIT orders)

        Returns:
            Order ID
        """
        try:
            order_params = {
                'tradingsymbol': tradingsymbol,
                'exchange': exchange,
                'transaction_type': transaction_type,
                'quantity': quantity,
                'order_type': order_type,
                'product': product
            }

            if order_type == 'LIMIT' and price:
                order_params['price'] = price

            order_id = self.kite.place_order(**order_params)
            logger.info(f"Order placed: {transaction_type} {quantity} {tradingsymbol} | Order ID: {order_id}")
            return order_id

        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            raise

    def get_orders(self):
        """Get all orders for the day"""
        try:
            orders = self.kite.orders()
            return orders
        except Exception as e:
            logger.error(f"Failed to get orders: {e}")
            return []

    def get_positions(self):
        """Get current positions"""
        try:
            positions = self.kite.positions()
            return positions
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return {}

    def cancel_order(self, order_id, variety='regular'):
        """
        Cancel an order

        Args:
            order_id: Order ID to cancel
            variety: Order variety

        Returns:
            Order ID
        """
        try:
            cancelled_order_id = self.kite.cancel_order(variety=variety, order_id=order_id)
            logger.info(f"Order cancelled: {order_id}")
            return cancelled_order_id
        except Exception as e:
            logger.error(f"Failed to cancel order: {e}")
            raise

    def modify_order(self, order_id, quantity=None, price=None, order_type=None, variety='regular'):
        """
        Modify an existing order

        Args:
            order_id: Order ID to modify
            quantity: New quantity
            price: New price
            order_type: New order type
            variety: Order variety

        Returns:
            Order ID
        """
        try:
            params = {}
            if quantity:
                params['quantity'] = quantity
            if price:
                params['price'] = price
            if order_type:
                params['order_type'] = order_type

            modified_order_id = self.kite.modify_order(variety=variety, order_id=order_id, **params)
            logger.info(f"Order modified: {order_id}")
            return modified_order_id
        except Exception as e:
            logger.error(f"Failed to modify order: {e}")
            raise

    def get_option_chain(self, underlying='NIFTY', expiry_date=None):
        """
        Get options chain for an underlying

        Args:
            underlying: Underlying symbol (NIFTY, BANKNIFTY, etc.)
            expiry_date: Expiry date string (e.g., '24NOV07')

        Returns:
            DataFrame with options chain
        """
        try:
            # Get all NFO instruments
            instruments = self.get_instruments('NFO')

            # Filter for the underlying
            options = [inst for inst in instruments if inst['name'] == underlying and inst['instrument_type'] in ['CE', 'PE']]

            # Filter by expiry if provided
            if expiry_date:
                options = [opt for opt in options if expiry_date in opt['tradingsymbol']]

            df = pd.DataFrame(options)
            logger.info(f"Retrieved {len(df)} options for {underlying}")
            return df

        except Exception as e:
            logger.error(f"Failed to get option chain: {e}")
            return pd.DataFrame()
