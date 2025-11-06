"""
Logging setup for the trading system
"""
import logging
import os
from datetime import datetime
from pathlib import Path
import colorlog

def setup_logger(name='choppy', log_level='INFO', log_dir='logs'):
    """
    Setup colored logger with file and console handlers

    Args:
        name: Logger name
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_dir: Directory to store log files

    Returns:
        Logger instance
    """
    # Create logs directory if it doesn't exist
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper()))

    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    # Create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(module)s:%(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    console_formatter = colorlog.ColoredFormatter(
        '%(log_color)s%(asctime)s | %(levelname)-8s | %(message)s%(reset)s',
        datefmt='%H:%M:%S',
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        }
    )

    # File handler (daily rotating)
    log_filename = os.path.join(log_dir, f'choppy_{datetime.now().strftime("%Y%m%d")}.log')
    file_handler = logging.FileHandler(log_filename)
    file_handler.setLevel(logging.DEBUG)  # Log everything to file
    file_handler.setFormatter(file_formatter)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_handler.setFormatter(console_formatter)

    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


class TradeLogger:
    """Specialized logger for trade records"""

    def __init__(self, trade_dir='trades'):
        self.trade_dir = Path(trade_dir)
        self.trade_dir.mkdir(parents=True, exist_ok=True)
        self.current_date = datetime.now().strftime("%Y%m%d")
        self.trade_file = self.trade_dir / f'trades_{self.current_date}.csv'

        # Create CSV file with headers if it doesn't exist
        if not self.trade_file.exists():
            self._create_trade_file()

    def _create_trade_file(self):
        """Create trade CSV file with headers"""
        headers = [
            'timestamp',
            'signal_type',
            'strike',
            'option_type',
            'entry_price',
            'exit_price',
            'quantity',
            'pnl',
            'pnl_percent',
            'exit_reason',
            'avti_entry',
            'avti_exit',
            'holding_time_mins',
            'slippage',
            'costs'
        ]

        with open(self.trade_file, 'w') as f:
            f.write(','.join(headers) + '\n')

    def log_trade(self, trade_data):
        """
        Log a completed trade

        Args:
            trade_data: Dict with trade details
        """
        # Check if date changed (new day, new file)
        current_date = datetime.now().strftime("%Y%m%d")
        if current_date != self.current_date:
            self.current_date = current_date
            self.trade_file = self.trade_dir / f'trades_{self.current_date}.csv'
            if not self.trade_file.exists():
                self._create_trade_file()

        # Format trade data
        row = [
            trade_data.get('timestamp', datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            trade_data.get('signal_type', ''),
            trade_data.get('strike', ''),
            trade_data.get('option_type', ''),
            trade_data.get('entry_price', 0),
            trade_data.get('exit_price', 0),
            trade_data.get('quantity', 0),
            trade_data.get('pnl', 0),
            trade_data.get('pnl_percent', 0),
            trade_data.get('exit_reason', ''),
            trade_data.get('avti_entry', 0),
            trade_data.get('avti_exit', 0),
            trade_data.get('holding_time_mins', 0),
            trade_data.get('slippage', 0),
            trade_data.get('costs', 0)
        ]

        # Write to CSV
        with open(self.trade_file, 'a') as f:
            f.write(','.join(str(x) for x in row) + '\n')

    def get_todays_trades(self):
        """Read today's trades from CSV"""
        import pandas as pd

        if not self.trade_file.exists():
            return pd.DataFrame()

        try:
            return pd.read_csv(self.trade_file)
        except Exception as e:
            logging.error(f"Error reading trade file: {e}")
            return pd.DataFrame()
