"""
Exit strategy logic for options positions
"""
import logging
from datetime import datetime
from indicators.avti import is_avti_reversing

logger = logging.getLogger('choppy')


class ExitStrategy:
    """Manages exit conditions for positions"""

    def __init__(self,
                 target_profit_percent=30,
                 stop_loss_percent=20,
                 trailing_stop_percent=15,
                 trailing_trigger_percent=15,
                 avti_exit_threshold=40,
                 time_exit_hour=15,
                 time_exit_minute=20):
        """
        Initialize exit strategy

        Args:
            target_profit_percent: Take profit at this % gain
            stop_loss_percent: Stop loss at this % loss
            trailing_stop_percent: Trailing stop distance from peak
            trailing_trigger_percent: Activate trailing stop after this % profit
            avti_exit_threshold: Exit if AVTI drops below this
            time_exit_hour: Hour to force exit (IST)
            time_exit_minute: Minute to force exit (IST)
        """
        self.target_profit_percent = target_profit_percent
        self.stop_loss_percent = stop_loss_percent
        self.trailing_stop_percent = trailing_stop_percent
        self.trailing_trigger_percent = trailing_trigger_percent
        self.avti_exit_threshold = avti_exit_threshold
        self.time_exit_hour = time_exit_hour
        self.time_exit_minute = time_exit_minute

    def check_exit(self, position, current_price, df=None):
        """
        Check if position should be exited

        Args:
            position: Position object with entry details
            current_price: Current market price
            df: DataFrame with indicators (for AVTI check)

        Returns:
            Tuple: (should_exit, exit_reason, exit_price)
        """
        try:
            # Calculate current P&L %
            pnl_percent = ((current_price - position['entry_price']) / position['entry_price']) * 100

            # Update peak price for trailing stop
            if current_price > position.get('peak_price', position['entry_price']):
                position['peak_price'] = current_price

            # Check 1: Target profit
            if pnl_percent >= self.target_profit_percent:
                logger.info(f"✓ Target profit reached: {pnl_percent:.2f}% >= {self.target_profit_percent}%")
                return True, 'TARGET_PROFIT', current_price

            # Check 2: Stop loss
            if pnl_percent <= -self.stop_loss_percent:
                logger.info(f"✗ Stop loss hit: {pnl_percent:.2f}% <= -{self.stop_loss_percent}%")
                return True, 'STOP_LOSS', current_price

            # Check 3: Trailing stop (if triggered)
            if pnl_percent >= self.trailing_trigger_percent:
                peak_price = position.get('peak_price', position['entry_price'])
                drop_from_peak_percent = ((peak_price - current_price) / peak_price) * 100

                if drop_from_peak_percent >= self.trailing_stop_percent:
                    logger.info(f"↘ Trailing stop triggered: Dropped {drop_from_peak_percent:.2f}% from peak")
                    return True, 'TRAILING_STOP', current_price

            # Check 4: AVTI reversal (if dataframe provided)
            if df is not None and not df.empty:
                if is_avti_reversing(df, self.avti_exit_threshold):
                    logger.info(f"⚠ AVTI reversal detected (< {self.avti_exit_threshold})")
                    return True, 'AVTI_REVERSAL', current_price

            # Check 5: Time-based exit
            if self._is_time_to_exit():
                logger.info(f"⏰ Time-based exit: {self.time_exit_hour:02d}:{self.time_exit_minute:02d} reached")
                return True, 'TIME_EXIT', current_price

            # No exit condition met
            return False, None, current_price

        except Exception as e:
            logger.error(f"Error checking exit conditions: {e}")
            return False, None, current_price

    def _is_time_to_exit(self):
        """
        Check if it's time to exit (based on configured time)

        Returns:
            bool: True if past exit time
        """
        try:
            import pytz
            from datetime import time

            ist = pytz.timezone('Asia/Kolkata')
            now = datetime.now(ist)

            exit_time = time(self.time_exit_hour, self.time_exit_minute)
            current_time = now.time()

            return current_time >= exit_time

        except Exception as e:
            logger.error(f"Error checking exit time: {e}")
            return False

    def force_exit_all(self, reason='MARKET_CLOSE'):
        """
        Signal to force exit all positions

        Args:
            reason: Reason for force exit

        Returns:
            Tuple: (True, reason)
        """
        logger.warning(f"⚠ FORCE EXIT ALL: {reason}")
        return True, reason

    def calculate_exit_pnl(self, position, exit_price, lot_size, include_costs=True, costs=0):
        """
        Calculate P&L for position exit

        Args:
            position: Position dict
            exit_price: Exit price
            lot_size: Lot size
            include_costs: Whether to include transaction costs
            costs: Transaction costs

        Returns:
            Dict with P&L details
        """
        try:
            entry_price = position['entry_price']
            quantity = position['quantity']

            # Gross P&L
            gross_pnl = (exit_price - entry_price) * quantity * lot_size
            pnl_percent = ((exit_price - entry_price) / entry_price) * 100

            # Net P&L (after costs)
            net_pnl = gross_pnl - costs if include_costs else gross_pnl

            # Holding time
            entry_time = position.get('entry_time', datetime.now())
            exit_time = datetime.now()
            holding_time_mins = (exit_time - entry_time).total_seconds() / 60

            return {
                'gross_pnl': gross_pnl,
                'net_pnl': net_pnl,
                'pnl_percent': pnl_percent,
                'costs': costs,
                'holding_time_mins': holding_time_mins,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'quantity': quantity
            }

        except Exception as e:
            logger.error(f"Error calculating exit P&L: {e}")
            return {
                'gross_pnl': 0,
                'net_pnl': 0,
                'pnl_percent': 0,
                'costs': 0,
                'holding_time_mins': 0
            }


class PositionManager:
    """Manages open positions"""

    def __init__(self, exit_strategy):
        """
        Initialize position manager

        Args:
            exit_strategy: ExitStrategy instance
        """
        self.exit_strategy = exit_strategy
        self.open_positions = []

    def add_position(self, position):
        """
        Add a new position

        Args:
            position: Position dict with entry details
        """
        # Initialize tracking fields
        position['peak_price'] = position['entry_price']
        position['entry_time'] = datetime.now()

        self.open_positions.append(position)
        logger.info(f"Position added: {position['symbol']} @ ₹{position['entry_price']}")

    def remove_position(self, position):
        """Remove a position from tracking"""
        if position in self.open_positions:
            self.open_positions.remove(position)
            logger.info(f"Position removed: {position['symbol']}")

    def get_open_positions(self):
        """Get all open positions"""
        return self.open_positions.copy()

    def get_position_count(self):
        """Get number of open positions"""
        return len(self.open_positions)

    def check_all_positions(self, market_data_provider, df=None):
        """
        Check all open positions for exit conditions

        Args:
            market_data_provider: Function to get current price for a symbol
            df: DataFrame with indicators

        Returns:
            List of positions to exit with reasons
        """
        positions_to_exit = []

        for position in self.open_positions:
            try:
                # Get current price for this position
                current_price = market_data_provider(position['symbol'])

                if current_price is None:
                    logger.warning(f"Could not get price for {position['symbol']}")
                    continue

                # Check exit conditions
                should_exit, exit_reason, exit_price = self.exit_strategy.check_exit(
                    position, current_price, df
                )

                if should_exit:
                    positions_to_exit.append({
                        'position': position,
                        'exit_reason': exit_reason,
                        'exit_price': exit_price
                    })

                    logger.info(f"Exit signal for {position['symbol']}: {exit_reason} @ ₹{exit_price}")
                else:
                    # Update position status
                    pnl_percent = ((current_price - position['entry_price']) / position['entry_price']) * 100
                    logger.debug(f"{position['symbol']}: {pnl_percent:+.2f}% | Price: ₹{current_price}")

            except Exception as e:
                logger.error(f"Error checking position {position.get('symbol', 'UNKNOWN')}: {e}")

        return positions_to_exit

    def force_exit_all_positions(self, market_data_provider, reason='FORCE_EXIT'):
        """
        Force exit all positions

        Args:
            market_data_provider: Function to get current prices
            reason: Reason for force exit

        Returns:
            List of all positions to exit
        """
        positions_to_exit = []

        for position in self.open_positions:
            try:
                current_price = market_data_provider(position['symbol'])

                if current_price is None:
                    current_price = position['entry_price']  # Use entry price if can't get current

                positions_to_exit.append({
                    'position': position,
                    'exit_reason': reason,
                    'exit_price': current_price
                })

            except Exception as e:
                logger.error(f"Error in force exit for {position.get('symbol', 'UNKNOWN')}: {e}")

        return positions_to_exit

    def get_position_summary(self):
        """Get summary of all open positions"""
        summary = []

        for pos in self.open_positions:
            summary.append({
                'symbol': pos['symbol'],
                'type': pos['option_type'],
                'entry': pos['entry_price'],
                'quantity': pos['quantity'],
                'entry_time': pos.get('entry_time', 'Unknown')
            })

        return summary
