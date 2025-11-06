"""
Risk management for trading system
"""
import logging
from datetime import datetime

logger = logging.getLogger('choppy')


class RiskManager:
    """Manages trading risk and position sizing"""

    def __init__(self,
                 max_daily_loss=5000,
                 max_positions=2,
                 position_size=1,
                 max_position_risk_percent=5,
                 account_balance=100000):
        """
        Initialize risk manager

        Args:
            max_daily_loss: Maximum allowed daily loss
            max_positions: Maximum concurrent positions
            position_size: Default lot size per trade
            max_position_risk_percent: Max % of account to risk per trade
            account_balance: Current account balance
        """
        self.max_daily_loss = max_daily_loss
        self.max_positions = max_positions
        self.position_size = position_size
        self.max_position_risk_percent = max_position_risk_percent
        self.account_balance = account_balance

        # Tracking
        self.daily_pnl = 0
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.largest_win = 0
        self.largest_loss = 0
        self.current_positions = 0

        # Circuit breaker
        self.trading_halted = False
        self.halt_reason = None

        logger.info(f"RiskManager initialized: Max Loss=₹{max_daily_loss}, Max Positions={max_positions}")

    def can_take_trade(self):
        """
        Check if new trade can be taken

        Returns:
            Tuple: (allowed, reason)
        """
        # Check if trading is halted
        if self.trading_halted:
            return False, f"TRADING_HALTED: {self.halt_reason}"

        # Check max positions
        if self.current_positions >= self.max_positions:
            logger.warning(f"Max positions ({self.max_positions}) reached")
            return False, f"MAX_POSITIONS ({self.current_positions}/{self.max_positions})"

        # Check daily loss limit
        if self.daily_pnl <= -self.max_daily_loss:
            self.halt_trading(f"Daily loss limit exceeded: ₹{self.daily_pnl:.2f}")
            return False, f"DAILY_LOSS_LIMIT (₹{self.daily_pnl:.2f})"

        # All checks passed
        return True, "APPROVED"

    def get_position_size(self, entry_price, stop_loss_percent):
        """
        Calculate position size based on risk management

        Args:
            entry_price: Entry price of the option
            stop_loss_percent: Stop loss percentage

        Returns:
            Number of lots
        """
        try:
            # Calculate max loss per lot
            max_loss_per_lot = entry_price * (stop_loss_percent / 100)

            # Calculate max risk amount for this trade
            max_risk_amount = self.account_balance * (self.max_position_risk_percent / 100)

            # Calculate lots based on risk
            calculated_lots = int(max_risk_amount / max_loss_per_lot)

            # Use minimum of calculated and default position size
            lots = min(calculated_lots, self.position_size) if calculated_lots > 0 else self.position_size

            logger.debug(f"Position size: {lots} lot(s) (max risk: ₹{max_risk_amount:.2f})")

            return lots

        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return self.position_size

    def record_trade(self, pnl, is_winner):
        """
        Record a completed trade

        Args:
            pnl: Trade P&L
            is_winner: Whether trade was profitable
        """
        self.total_trades += 1
        self.daily_pnl += pnl

        if is_winner:
            self.winning_trades += 1
            if pnl > self.largest_win:
                self.largest_win = pnl
        else:
            self.losing_trades += 1
            if pnl < self.largest_loss:
                self.largest_loss = pnl

        logger.info(f"Trade recorded: P&L=₹{pnl:+.2f} | Daily P&L=₹{self.daily_pnl:+.2f}")

        # Check if we hit daily loss limit
        if self.daily_pnl <= -self.max_daily_loss:
            self.halt_trading(f"Daily loss limit reached: ₹{self.daily_pnl:.2f}")

    def position_opened(self):
        """Increment position counter"""
        self.current_positions += 1
        logger.debug(f"Position opened. Active positions: {self.current_positions}")

    def position_closed(self):
        """Decrement position counter"""
        self.current_positions = max(0, self.current_positions - 1)
        logger.debug(f"Position closed. Active positions: {self.current_positions}")

    def halt_trading(self, reason):
        """
        Halt all trading

        Args:
            reason: Reason for halt
        """
        self.trading_halted = True
        self.halt_reason = reason
        logger.critical(f"🛑 TRADING HALTED: {reason}")

    def resume_trading(self):
        """Resume trading after halt"""
        self.trading_halted = False
        self.halt_reason = None
        logger.info("✓ Trading resumed")

    def reset_daily(self):
        """Reset daily tracking (call at start of new trading day)"""
        self.daily_pnl = 0
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.largest_win = 0
        self.largest_loss = 0
        self.current_positions = 0
        self.trading_halted = False
        self.halt_reason = None

        logger.info("Daily risk metrics reset for new trading day")

    def get_statistics(self):
        """
        Get trading statistics

        Returns:
            Dict with stats
        """
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0

        avg_win = self.largest_win / self.winning_trades if self.winning_trades > 0 else 0
        avg_loss = self.largest_loss / self.losing_trades if self.losing_trades > 0 else 0

        return {
            'daily_pnl': self.daily_pnl,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': win_rate,
            'largest_win': self.largest_win,
            'largest_loss': self.largest_loss,
            'current_positions': self.current_positions,
            'trading_halted': self.trading_halted
        }

    def display_statistics(self):
        """Display formatted statistics"""
        stats = self.get_statistics()

        print("\n" + "="*60)
        print("                  RISK STATISTICS")
        print("="*60)
        print(f"Daily P&L:           ₹{stats['daily_pnl']:+,.2f}")
        print(f"Total Trades:        {stats['total_trades']}")
        print(f"Win Rate:            {stats['win_rate']:.1f}%")
        print(f"Winners/Losers:      {stats['winning_trades']}/{stats['losing_trades']}")
        print(f"Largest Win:         ₹{stats['largest_win']:+,.2f}")
        print(f"Largest Loss:        ₹{stats['largest_loss']:+,.2f}")
        print(f"Active Positions:    {stats['current_positions']}/{self.max_positions}")
        print(f"Trading Status:      {'🛑 HALTED' if stats['trading_halted'] else '✓ ACTIVE'}")

        if self.trading_halted:
            print(f"Halt Reason:         {self.halt_reason}")

        print("="*60 + "\n")

    def check_drawdown(self, peak_balance):
        """
        Check current drawdown from peak

        Args:
            peak_balance: Peak account balance

        Returns:
            Drawdown percentage
        """
        current_balance = self.account_balance + self.daily_pnl
        drawdown = ((peak_balance - current_balance) / peak_balance) * 100 if peak_balance > 0 else 0

        if drawdown > 10:  # 10% drawdown warning
            logger.warning(f"⚠ Drawdown alert: {drawdown:.2f}% from peak")

        return drawdown

    def update_account_balance(self, new_balance):
        """Update account balance"""
        self.account_balance = new_balance
        logger.info(f"Account balance updated: ₹{new_balance:,.2f}")

    def get_risk_summary(self):
        """Get risk summary for display"""
        return {
            'max_daily_loss': self.max_daily_loss,
            'current_daily_pnl': self.daily_pnl,
            'remaining_loss_buffer': self.max_daily_loss + self.daily_pnl,
            'max_positions': self.max_positions,
            'current_positions': self.current_positions,
            'available_position_slots': self.max_positions - self.current_positions,
            'trading_status': 'HALTED' if self.trading_halted else 'ACTIVE'
        }
