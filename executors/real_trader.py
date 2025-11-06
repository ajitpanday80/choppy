"""
Real trading executor (actual orders via Zerodha)
"""
import logging
from datetime import datetime
import time

logger = logging.getLogger('choppy')


class RealTrader:
    """Executes real orders via Zerodha Kite API"""

    def __init__(self, zerodha_client, lot_size=50, exchange='NFO', product='MIS'):
        """
        Initialize real trader

        Args:
            zerodha_client: ZerodhaClient instance
            lot_size: Lot size for contracts
            exchange: Exchange (NFO for F&O)
            product: Product type (MIS for intraday, NRML for overnight)
        """
        self.client = zerodha_client
        self.lot_size = lot_size
        self.exchange = exchange
        self.product = product

        # Order tracking
        self.active_orders = {}
        self.filled_orders = {}

        logger.info(f"Real Trader initialized | Exchange: {exchange} | Product: {product}")
        logger.warning("⚠️  REAL TRADING MODE - Real orders will be placed!")

    def place_buy_order(self, symbol, quantity, option_type, strike, current_price=None, signal_type=None, order_type='MARKET'):
        """
        Place a real buy order

        Args:
            symbol: Trading symbol (e.g., 'NIFTY24NOV19500CE')
            quantity: Number of lots
            option_type: CE or PE
            strike: Strike price
            current_price: Current market price (for logging)
            signal_type: CALL or PUT (for logging)
            order_type: MARKET or LIMIT

        Returns:
            Order dict if successful, None otherwise
        """
        try:
            # Calculate total quantity
            total_quantity = quantity * self.lot_size

            logger.info(f"Placing REAL BUY order: {total_quantity} units of {symbol}")

            # Place order via Zerodha
            order_id = self.client.place_order(
                tradingsymbol=symbol,
                exchange=self.exchange,
                transaction_type='BUY',
                quantity=total_quantity,
                order_type=order_type,
                product=self.product
            )

            if not order_id:
                logger.error("Failed to place buy order - no order ID returned")
                return None

            logger.info(f"✓ Order placed successfully | Order ID: {order_id}")

            # Wait briefly for order to fill
            time.sleep(2)

            # Get order status
            order_details = self._get_order_status(order_id)

            if not order_details:
                logger.error(f"Could not retrieve order status for {order_id}")
                return None

            # Create order record
            order = {
                'order_id': order_id,
                'symbol': symbol,
                'option_type': option_type,
                'strike': strike,
                'signal_type': signal_type,
                'quantity': quantity,
                'total_quantity': total_quantity,
                'entry_price': order_details.get('average_price', current_price),
                'market_price': current_price,
                'status': order_details.get('status', 'UNKNOWN'),
                'timestamp': datetime.now(),
                'order_details': order_details
            }

            # Track order
            if order['status'] == 'COMPLETE':
                self.filled_orders[order_id] = order
                logger.info(f"📈 REAL BUY FILLED: {quantity} lot(s) {symbol} @ ₹{order['entry_price']:.2f}")
            else:
                self.active_orders[order_id] = order
                logger.warning(f"Order {order_id} status: {order['status']}")

            return order

        except Exception as e:
            logger.error(f"Error placing real buy order: {e}")
            return None

    def place_sell_order(self, position, current_price=None, exit_reason=None, order_type='MARKET'):
        """
        Place a real sell order

        Args:
            position: Position dict from buy order
            current_price: Current market price (for logging)
            exit_reason: Reason for exit
            order_type: MARKET or LIMIT

        Returns:
            Exit record dict if successful, None otherwise
        """
        try:
            total_quantity = position['total_quantity']
            symbol = position['symbol']

            logger.info(f"Placing REAL SELL order: {total_quantity} units of {symbol}")

            # Place sell order
            order_id = self.client.place_order(
                tradingsymbol=symbol,
                exchange=self.exchange,
                transaction_type='SELL',
                quantity=total_quantity,
                order_type=order_type,
                product=self.product
            )

            if not order_id:
                logger.error("Failed to place sell order - no order ID returned")
                return None

            logger.info(f"✓ Sell order placed | Order ID: {order_id}")

            # Wait for fill
            time.sleep(2)

            # Get order status
            order_details = self._get_order_status(order_id)

            if not order_details:
                logger.error(f"Could not retrieve sell order status for {order_id}")
                return None

            # Get execution price
            execution_price = order_details.get('average_price', current_price)

            # Calculate P&L
            entry_price = position['entry_price']
            quantity = position['quantity']

            gross_pnl = (execution_price - entry_price) * quantity * self.lot_size
            pnl_percent = ((execution_price - entry_price) / entry_price) * 100

            # Costs will be debited separately by broker
            costs = 0  # Broker handles this

            net_pnl = gross_pnl  # Approximate (actual costs settled by broker)

            # Create exit record
            exit_record = {
                'order_id': order_id,
                'entry_order_id': position['order_id'],
                'symbol': symbol,
                'quantity': quantity,
                'entry_price': entry_price,
                'exit_price': execution_price,
                'market_price': current_price,
                'exit_reason': exit_reason,
                'gross_pnl': gross_pnl,
                'costs': costs,
                'net_pnl': net_pnl,
                'pnl_percent': pnl_percent,
                'entry_time': position['timestamp'],
                'exit_time': datetime.now(),
                'holding_time_mins': (datetime.now() - position['timestamp']).total_seconds() / 60,
                'status': order_details.get('status', 'UNKNOWN'),
                'order_details': order_details
            }

            logger.info(f"📉 REAL SELL FILLED: {quantity} lot(s) {symbol} @ ₹{execution_price:.2f}")
            logger.info(f"   Entry: ₹{entry_price:.2f} | Exit: ₹{execution_price:.2f}")
            logger.info(f"   P&L: ₹{net_pnl:+.2f} ({pnl_percent:+.2f}%)")
            logger.info(f"   Exit Reason: {exit_reason}")

            return exit_record

        except Exception as e:
            logger.error(f"Error placing real sell order: {e}")
            return None

    def _get_order_status(self, order_id):
        """
        Get order status from Zerodha

        Args:
            order_id: Order ID to check

        Returns:
            Order details dict
        """
        try:
            orders = self.client.get_orders()

            for order in orders:
                if order['order_id'] == order_id:
                    return order

            logger.warning(f"Order {order_id} not found in orders list")
            return None

        except Exception as e:
            logger.error(f"Error getting order status: {e}")
            return None

    def cancel_order(self, order_id):
        """
        Cancel a pending order

        Args:
            order_id: Order ID to cancel

        Returns:
            bool: Success status
        """
        try:
            self.client.cancel_order(order_id)
            logger.info(f"Order {order_id} cancelled")

            # Remove from active orders
            if order_id in self.active_orders:
                del self.active_orders[order_id]

            return True

        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return False

    def get_positions(self):
        """Get current positions from Zerodha"""
        try:
            positions = self.client.get_positions()
            return positions
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return {}

    def check_order_status(self, order_id):
        """
        Check if order is filled

        Args:
            order_id: Order ID

        Returns:
            Tuple: (is_filled, details)
        """
        try:
            order_details = self._get_order_status(order_id)

            if not order_details:
                return False, None

            is_filled = order_details.get('status') == 'COMPLETE'

            return is_filled, order_details

        except Exception as e:
            logger.error(f"Error checking order status: {e}")
            return False, None

    def get_active_orders(self):
        """Get all active orders"""
        return self.active_orders.copy()

    def get_filled_orders(self):
        """Get all filled orders"""
        return self.filled_orders.copy()

    def update_order_status(self, order_id):
        """
        Update status of an active order

        Args:
            order_id: Order ID to update

        Returns:
            Updated status
        """
        try:
            is_filled, details = self.check_order_status(order_id)

            if is_filled and order_id in self.active_orders:
                # Move to filled orders
                self.filled_orders[order_id] = self.active_orders[order_id]
                del self.active_orders[order_id]
                logger.info(f"Order {order_id} filled and moved to filled orders")

            return details.get('status', 'UNKNOWN') if details else 'UNKNOWN'

        except Exception as e:
            logger.error(f"Error updating order status: {e}")
            return 'ERROR'

    def close_all_positions(self, reason='FORCE_EXIT'):
        """
        Close all open positions (emergency)

        Args:
            reason: Reason for closing

        Returns:
            List of exit records
        """
        try:
            logger.warning(f"⚠️  Closing all positions: {reason}")

            positions = self.get_positions()
            exit_records = []

            # Close net positions
            if 'net' in positions:
                for pos in positions['net']:
                    if pos['quantity'] != 0:
                        symbol = pos['tradingsymbol']
                        quantity = abs(pos['quantity'])

                        logger.info(f"Closing position: {symbol} ({quantity} units)")

                        # Determine transaction type (opposite of current position)
                        transaction_type = 'SELL' if pos['quantity'] > 0 else 'BUY'

                        try:
                            order_id = self.client.place_order(
                                tradingsymbol=symbol,
                                exchange=self.exchange,
                                transaction_type=transaction_type,
                                quantity=quantity,
                                order_type='MARKET',
                                product=self.product
                            )

                            logger.info(f"Position close order placed: {order_id}")

                            exit_records.append({
                                'symbol': symbol,
                                'order_id': order_id,
                                'reason': reason
                            })

                        except Exception as e:
                            logger.error(f"Error closing position {symbol}: {e}")

            return exit_records

        except Exception as e:
            logger.error(f"Error in close_all_positions: {e}")
            return []

    def display_summary(self):
        """Display trading summary"""
        print("\n" + "="*60)
        print("              REAL TRADING SUMMARY")
        print("="*60)
        print(f"Active Orders:       {len(self.active_orders)}")
        print(f"Filled Orders:       {len(self.filled_orders)}")
        print("="*60 + "\n")

        if self.filled_orders:
            print("Filled Orders:")
            for order_id, order in self.filled_orders.items():
                print(f"  {order_id}: {order['symbol']} @ ₹{order['entry_price']:.2f}")
