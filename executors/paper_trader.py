"""
Paper trading executor (simulated trades)
"""
import logging
import random
from datetime import datetime

logger = logging.getLogger('choppy')


class PaperTrader:
    """Simulates order execution without real money"""

    def __init__(self, initial_balance=100000, slippage_percent=2.5, lot_size=50):
        """
        Initialize paper trader

        Args:
            initial_balance: Starting capital
            slippage_percent: Realistic slippage to apply
            lot_size: Lot size for contracts (50 for NIFTY)
        """
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.slippage_percent = slippage_percent
        self.lot_size = lot_size

        # Order tracking
        self.next_order_id = 1000
        self.orders = {}
        self.filled_orders = []

        logger.info(f"Paper Trader initialized with balance: ₹{initial_balance:,.2f}")
        logger.info(f"Slippage model: {slippage_percent}% | Lot size: {lot_size}")

    def place_buy_order(self, symbol, quantity, option_type, strike, current_price, signal_type):
        """
        Simulate buying an option

        Args:
            symbol: Option symbol
            quantity: Number of lots
            option_type: CE or PE
            strike: Strike price
            current_price: Current market price (LTP)
            signal_type: CALL or PUT

        Returns:
            Order dict
        """
        try:
            # Apply realistic slippage (buying means paying higher)
            slippage = self._calculate_slippage(current_price, is_buy=True)
            execution_price = current_price + slippage

            # Round to tick size (0.05)
            execution_price = round(execution_price / 0.05) * 0.05

            # Calculate total cost
            total_cost = execution_price * quantity * self.lot_size

            # Check if sufficient balance
            if total_cost > self.current_balance:
                logger.error(f"Insufficient balance. Required: ₹{total_cost:.2f}, Available: ₹{self.current_balance:.2f}")
                return None

            # Create order
            order_id = self._generate_order_id()
            order = {
                'order_id': order_id,
                'symbol': symbol,
                'option_type': option_type,
                'strike': strike,
                'signal_type': signal_type,
                'quantity': quantity,
                'entry_price': execution_price,
                'market_price': current_price,
                'slippage': slippage,
                'slippage_percent': (slippage / current_price) * 100,
                'total_cost': total_cost,
                'timestamp': datetime.now(),
                'status': 'FILLED'
            }

            # Deduct balance
            self.current_balance -= total_cost

            # Record order
            self.orders[order_id] = order
            self.filled_orders.append(order)

            logger.info(f"📈 PAPER BUY: {quantity} lot(s) {symbol} @ ₹{execution_price:.2f}")
            logger.info(f"   Market: ₹{current_price:.2f} | Slippage: ₹{slippage:.2f} ({(slippage/current_price)*100:.2f}%)")
            logger.info(f"   Total Cost: ₹{total_cost:.2f} | Balance: ₹{self.current_balance:.2f}")

            return order

        except Exception as e:
            logger.error(f"Error in paper buy order: {e}")
            return None

    def place_sell_order(self, position, current_price, exit_reason):
        """
        Simulate selling an option

        Args:
            position: Position dict from buy order
            current_price: Current market price
            exit_reason: Reason for exit

        Returns:
            Dict with exit details
        """
        try:
            # Apply realistic slippage (selling means receiving lower)
            slippage = self._calculate_slippage(current_price, is_buy=False)
            execution_price = current_price - slippage

            # Round to tick size
            execution_price = round(execution_price / 0.05) * 0.05

            # Calculate proceeds
            total_proceeds = execution_price * position['quantity'] * self.lot_size

            # Calculate costs (brokerage + STT + charges)
            costs = self._calculate_costs(position['entry_price'], execution_price, position['quantity'])

            # Net proceeds after costs
            net_proceeds = total_proceeds - costs

            # Calculate P&L
            gross_pnl = (execution_price - position['entry_price']) * position['quantity'] * self.lot_size
            net_pnl = gross_pnl - costs
            pnl_percent = ((execution_price - position['entry_price']) / position['entry_price']) * 100

            # Update balance
            self.current_balance += net_proceeds

            # Create exit record
            exit_record = {
                'order_id': position['order_id'],
                'symbol': position['symbol'],
                'quantity': position['quantity'],
                'entry_price': position['entry_price'],
                'exit_price': execution_price,
                'market_price': current_price,
                'slippage': slippage,
                'exit_reason': exit_reason,
                'gross_pnl': gross_pnl,
                'costs': costs,
                'net_pnl': net_pnl,
                'pnl_percent': pnl_percent,
                'proceeds': total_proceeds,
                'net_proceeds': net_proceeds,
                'entry_time': position['timestamp'],
                'exit_time': datetime.now(),
                'holding_time_mins': (datetime.now() - position['timestamp']).total_seconds() / 60
            }

            logger.info(f"📉 PAPER SELL: {position['quantity']} lot(s) {position['symbol']} @ ₹{execution_price:.2f}")
            logger.info(f"   Entry: ₹{position['entry_price']:.2f} | Exit: ₹{execution_price:.2f}")
            logger.info(f"   P&L: ₹{net_pnl:+.2f} ({pnl_percent:+.2f}%) | Costs: ₹{costs:.2f}")
            logger.info(f"   Exit Reason: {exit_reason} | Balance: ₹{self.current_balance:.2f}")

            return exit_record

        except Exception as e:
            logger.error(f"Error in paper sell order: {e}")
            return None

    def _calculate_slippage(self, price, is_buy=True):
        """
        Calculate realistic slippage

        Args:
            price: Base price
            is_buy: True for buy (positive slippage), False for sell (negative slippage)

        Returns:
            Slippage amount
        """
        # Add randomness to slippage (1.5% to 3.5% range)
        slippage_range = self.slippage_percent * 0.4  # ±40% variation
        actual_slippage_percent = self.slippage_percent + random.uniform(-slippage_range, slippage_range)

        slippage = price * (actual_slippage_percent / 100)

        # Buy slippage is positive (pay more), sell is negative (receive less)
        return abs(slippage)

    def _calculate_costs(self, entry_price, exit_price, quantity):
        """
        Calculate transaction costs

        Args:
            entry_price: Entry price
            exit_price: Exit price
            quantity: Number of lots

        Returns:
            Total costs
        """
        # Brokerage (flat ₹20 per order, both sides)
        brokerage = 20 * 2

        # STT (0.05% on sell side only)
        sell_value = exit_price * quantity * self.lot_size
        stt = (0.05 / 100) * sell_value

        # Transaction charges (CTT, stamp duty, etc - approx 0.05% on both sides)
        total_value = (entry_price + exit_price) * quantity * self.lot_size
        transaction_charges = (0.05 / 100) * total_value

        total_costs = brokerage + stt + transaction_charges

        return round(total_costs, 2)

    def _generate_order_id(self):
        """Generate unique order ID"""
        order_id = self.next_order_id
        self.next_order_id += 1
        return order_id

    def get_balance(self):
        """Get current balance"""
        return self.current_balance

    def get_pnl(self):
        """Get total P&L"""
        return self.current_balance - self.initial_balance

    def get_statistics(self):
        """Get trading statistics"""
        if not self.filled_orders:
            return {
                'total_trades': 0,
                'total_pnl': 0,
                'total_costs': 0,
                'avg_slippage_percent': 0
            }

        # Calculate from filled orders (need to match with exits)
        total_pnl = self.get_pnl()
        avg_slippage = sum(order.get('slippage_percent', 0) for order in self.filled_orders) / len(self.filled_orders)

        return {
            'total_trades': len(self.filled_orders),
            'total_pnl': total_pnl,
            'current_balance': self.current_balance,
            'avg_slippage_percent': avg_slippage
        }

    def reset(self):
        """Reset paper trader"""
        self.current_balance = self.initial_balance
        self.orders = {}
        self.filled_orders = []
        self.next_order_id = 1000
        logger.info("Paper trader reset")

    def display_summary(self):
        """Display trading summary"""
        stats = self.get_statistics()
        pnl = self.get_pnl()
        pnl_percent = (pnl / self.initial_balance) * 100 if self.initial_balance > 0 else 0

        print("\n" + "="*60)
        print("              PAPER TRADING SUMMARY")
        print("="*60)
        print(f"Initial Balance:     ₹{self.initial_balance:,.2f}")
        print(f"Current Balance:     ₹{self.current_balance:,.2f}")
        print(f"Total P&L:           ₹{pnl:+,.2f} ({pnl_percent:+.2f}%)")
        print(f"Total Trades:        {stats['total_trades']}")
        print(f"Avg Slippage:        {stats['avg_slippage_percent']:.2f}%")
        print("="*60 + "\n")
