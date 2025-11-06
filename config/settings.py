"""
Configuration settings for the trading system
Loads from environment variables
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Main configuration class"""

    # Zerodha API Credentials
    KITE_API_KEY = os.getenv('KITE_API_KEY', '')
    KITE_API_SECRET = os.getenv('KITE_API_SECRET', '')
    KITE_ACCESS_TOKEN = os.getenv('KITE_ACCESS_TOKEN', '')

    # Trading Mode
    TRADING_MODE = os.getenv('TRADING_MODE', 'PAPER')  # PAPER or REAL

    # Risk Management
    MAX_DAILY_LOSS = float(os.getenv('MAX_DAILY_LOSS', '5000'))
    MAX_POSITIONS = int(os.getenv('MAX_POSITIONS', '2'))
    POSITION_SIZE = int(os.getenv('POSITION_SIZE', '1'))  # Number of lots

    # Strategy Parameters
    AVTI_THRESHOLD = float(os.getenv('AVTI_THRESHOLD', '65'))
    TARGET_PROFIT_PERCENT = float(os.getenv('TARGET_PROFIT_PERCENT', '30'))
    STOP_LOSS_PERCENT = float(os.getenv('STOP_LOSS_PERCENT', '20'))
    TRAILING_STOP_PERCENT = float(os.getenv('TRAILING_STOP_PERCENT', '15'))
    TRAILING_STOP_TRIGGER = float(os.getenv('TRAILING_STOP_TRIGGER', '15'))  # Activate trailing after this % profit

    # Volume confirmation
    VOLUME_SPIKE_MULTIPLIER = float(os.getenv('VOLUME_SPIKE_MULTIPLIER', '1.5'))

    # AVTI exit threshold
    AVTI_EXIT_THRESHOLD = float(os.getenv('AVTI_EXIT_THRESHOLD', '40'))

    # Trading Hours (IST - 24hr format)
    TRADING_START_HOUR = int(os.getenv('TRADING_START_HOUR', '9'))
    TRADING_START_MINUTE = int(os.getenv('TRADING_START_MINUTE', '20'))
    TRADING_END_HOUR = int(os.getenv('TRADING_END_HOUR', '15'))
    TRADING_END_MINUTE = int(os.getenv('TRADING_END_MINUTE', '20'))

    # Data settings
    TIMEFRAME = os.getenv('TIMEFRAME', '5minute')  # 1minute, 3minute, 5minute, 15minute
    LOOKBACK_DAYS = int(os.getenv('LOOKBACK_DAYS', '5'))  # Days of historical data to fetch

    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_DIR = 'logs'
    TRADE_DIR = 'trades'

    # NIFTY 50 settings
    NIFTY_SYMBOL = 'NIFTY 50'
    NIFTY_INSTRUMENT_TOKEN = 256265  # NSE:NIFTY 50 token (verify this)
    NIFTY_LOT_SIZE = 50  # NIFTY lot size

    # Paper trading settings
    PAPER_SLIPPAGE_PERCENT = float(os.getenv('PAPER_SLIPPAGE_PERCENT', '2.5'))  # Realistic slippage
    PAPER_INITIAL_BALANCE = float(os.getenv('PAPER_INITIAL_BALANCE', '100000'))

    # Order costs (for paper mode simulation)
    BROKERAGE_PER_ORDER = 20  # Zerodha flat fee
    STT_PERCENT = 0.05  # STT on options sell side
    TRANSACTION_CHARGES_PERCENT = 0.05  # CTT, stamp duty, etc.

    @classmethod
    def validate(cls):
        """Validate critical configuration"""
        errors = []

        if cls.TRADING_MODE not in ['PAPER', 'REAL']:
            errors.append("TRADING_MODE must be 'PAPER' or 'REAL'")

        if cls.TRADING_MODE == 'REAL':
            if not cls.KITE_API_KEY:
                errors.append("KITE_API_KEY is required for REAL mode")
            if not cls.KITE_API_SECRET:
                errors.append("KITE_API_SECRET is required for REAL mode")
            if not cls.KITE_ACCESS_TOKEN:
                errors.append("KITE_ACCESS_TOKEN is required for REAL mode")

        if cls.MAX_DAILY_LOSS <= 0:
            errors.append("MAX_DAILY_LOSS must be positive")

        if cls.MAX_POSITIONS <= 0:
            errors.append("MAX_POSITIONS must be positive")

        if cls.AVTI_THRESHOLD < 0 or cls.AVTI_THRESHOLD > 100:
            errors.append("AVTI_THRESHOLD must be between 0 and 100")

        return errors

    @classmethod
    def is_paper_mode(cls):
        """Check if running in paper trading mode"""
        return cls.TRADING_MODE == 'PAPER'

    @classmethod
    def is_real_mode(cls):
        """Check if running in real trading mode"""
        return cls.TRADING_MODE == 'REAL'

    @classmethod
    def get_trading_hours(cls):
        """Get trading hours as tuple"""
        return (
            (cls.TRADING_START_HOUR, cls.TRADING_START_MINUTE),
            (cls.TRADING_END_HOUR, cls.TRADING_END_MINUTE)
        )

    @classmethod
    def display_config(cls):
        """Display current configuration (hide sensitive data)"""
        config_str = f"""
╔══════════════════════════════════════════════════════════════╗
║              CHOPPY TRADING SYSTEM CONFIG                    ║
╠══════════════════════════════════════════════════════════════╣
║ Mode:                {cls.TRADING_MODE:<40} ║
║ Max Daily Loss:      ₹{cls.MAX_DAILY_LOSS:<38.2f} ║
║ Max Positions:       {cls.MAX_POSITIONS:<40} ║
║ Position Size:       {cls.POSITION_SIZE} lot(s){' '*32} ║
║                                                              ║
║ AVTI Threshold:      {cls.AVTI_THRESHOLD:<40.1f} ║
║ Target Profit:       {cls.TARGET_PROFIT_PERCENT}%{' '*38} ║
║ Stop Loss:           {cls.STOP_LOSS_PERCENT}%{' '*38} ║
║ Trailing Stop:       {cls.TRAILING_STOP_PERCENT}%{' '*38} ║
║                                                              ║
║ Trading Hours:       {cls.TRADING_START_HOUR:02d}:{cls.TRADING_START_MINUTE:02d} - {cls.TRADING_END_HOUR:02d}:{cls.TRADING_END_MINUTE:02d} IST{' '*24} ║
║ Timeframe:           {cls.TIMEFRAME:<40} ║
╚══════════════════════════════════════════════════════════════╝
        """
        return config_str
