"""
Utility helper functions
"""
from datetime import datetime, time
import pytz


def is_market_open(trading_hours=None):
    """
    Check if market is currently open

    Args:
        trading_hours: Tuple of ((start_hour, start_min), (end_hour, end_min))

    Returns:
        bool: True if market is open
    """
    if trading_hours is None:
        trading_hours = ((9, 15), (15, 30))  # Default NSE hours

    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)

    # Check if weekday (Monday=0, Sunday=6)
    if now.weekday() >= 5:  # Saturday or Sunday
        return False

    # Check trading hours
    start_time = time(trading_hours[0][0], trading_hours[0][1])
    end_time = time(trading_hours[1][0], trading_hours[1][1])
    current_time = now.time()

    return start_time <= current_time <= end_time


def is_trading_time(trading_hours):
    """
    Check if it's within configured trading time (may be different from market hours)

    Args:
        trading_hours: Tuple of ((start_hour, start_min), (end_hour, end_min))

    Returns:
        bool: True if within trading time
    """
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)

    # Check if weekday
    if now.weekday() >= 5:
        return False

    start_time = time(trading_hours[0][0], trading_hours[0][1])
    end_time = time(trading_hours[1][0], trading_hours[1][1])
    current_time = now.time()

    return start_time <= current_time <= end_time


def get_ist_time():
    """Get current IST time"""
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.now(ist)


def format_currency(amount):
    """Format amount as INR currency"""
    return f"₹{amount:,.2f}"


def calculate_pnl(entry_price, exit_price, quantity, lot_size):
    """
    Calculate P&L for options trade

    Args:
        entry_price: Entry premium price
        exit_price: Exit premium price
        quantity: Number of lots
        lot_size: Lot size (e.g., 50 for NIFTY)

    Returns:
        Tuple of (pnl_amount, pnl_percent)
    """
    total_entry = entry_price * quantity * lot_size
    total_exit = exit_price * quantity * lot_size

    pnl_amount = total_exit - total_entry
    pnl_percent = ((exit_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0

    return pnl_amount, pnl_percent


def calculate_costs(entry_price, exit_price, quantity, lot_size, brokerage=20, stt_percent=0.05, charges_percent=0.05):
    """
    Calculate transaction costs

    Args:
        entry_price: Entry premium
        exit_price: Exit premium
        quantity: Number of lots
        lot_size: Lot size
        brokerage: Brokerage per order
        stt_percent: STT percentage (on sell side)
        charges_percent: Other charges percentage

    Returns:
        Total costs
    """
    # Brokerage (both buy and sell)
    total_brokerage = brokerage * 2

    # STT (only on sell side)
    sell_value = exit_price * quantity * lot_size
    stt = (stt_percent / 100) * sell_value

    # Transaction charges
    total_value = (entry_price + exit_price) * quantity * lot_size
    transaction_charges = (charges_percent / 100) * total_value

    total_costs = total_brokerage + stt + transaction_charges
    return total_costs


def round_to_tick(price, tick_size=0.05):
    """
    Round price to nearest tick size

    Args:
        price: Price to round
        tick_size: Tick size (0.05 for options)

    Returns:
        Rounded price
    """
    return round(price / tick_size) * tick_size


def get_atm_strike(spot_price, strike_interval=50):
    """
    Get ATM (At The Money) strike price

    Args:
        spot_price: Current spot price
        strike_interval: Strike interval (50 for NIFTY, 100 for BANKNIFTY)

    Returns:
        ATM strike price
    """
    return round(spot_price / strike_interval) * strike_interval


def get_option_symbol(underlying, expiry, strike, option_type):
    """
    Construct option symbol for Zerodha

    Args:
        underlying: Underlying (e.g., 'NIFTY')
        expiry: Expiry date string (e.g., '24NOV06')
        strike: Strike price (e.g., 19500)
        option_type: 'CE' or 'PE'

    Returns:
        Option symbol string
    """
    return f"{underlying}{expiry}{strike}{option_type}"


def format_time_elapsed(seconds):
    """
    Format seconds into readable time

    Args:
        seconds: Number of seconds

    Returns:
        Formatted string (e.g., "2h 35m")
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"


class PerformanceTracker:
    """Track trading performance metrics"""

    def __init__(self):
        self.trades = []
        self.daily_pnl = 0
        self.peak_pnl = 0
        self.max_drawdown = 0

    def add_trade(self, pnl):
        """Add a completed trade"""
        self.trades.append(pnl)
        self.daily_pnl += pnl

        # Update peak and drawdown
        if self.daily_pnl > self.peak_pnl:
            self.peak_pnl = self.daily_pnl
        else:
            drawdown = self.peak_pnl - self.daily_pnl
            if drawdown > self.max_drawdown:
                self.max_drawdown = drawdown

    def get_stats(self):
        """Get performance statistics"""
        if not self.trades:
            return {
                'total_trades': 0,
                'winners': 0,
                'losers': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'profit_factor': 0,
                'max_drawdown': 0
            }

        winners = [t for t in self.trades if t > 0]
        losers = [t for t in self.trades if t < 0]

        total_wins = sum(winners)
        total_losses = abs(sum(losers))

        return {
            'total_trades': len(self.trades),
            'winners': len(winners),
            'losers': len(losers),
            'win_rate': (len(winners) / len(self.trades)) * 100 if self.trades else 0,
            'total_pnl': self.daily_pnl,
            'avg_win': total_wins / len(winners) if winners else 0,
            'avg_loss': total_losses / len(losers) if losers else 0,
            'profit_factor': total_wins / total_losses if total_losses > 0 else float('inf'),
            'max_drawdown': self.max_drawdown
        }

    def display_stats(self):
        """Display formatted statistics"""
        stats = self.get_stats()

        print("\n" + "="*60)
        print("              DAILY PERFORMANCE SUMMARY")
        print("="*60)
        print(f"Total Trades:        {stats['total_trades']}")
        print(f"Winners:             {stats['winners']} ({stats['win_rate']:.1f}%)")
        print(f"Losers:              {stats['losers']}")
        print(f"Total P&L:           {format_currency(stats['total_pnl'])}")
        print(f"Avg Win:             {format_currency(stats['avg_win'])}")
        print(f"Avg Loss:            {format_currency(stats['avg_loss'])}")
        print(f"Profit Factor:       {stats['profit_factor']:.2f}")
        print(f"Max Drawdown:        {format_currency(stats['max_drawdown'])}")
        print("="*60 + "\n")
