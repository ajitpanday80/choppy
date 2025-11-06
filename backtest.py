"""
Backtesting framework for AVTI strategy
"""
import argparse
import pandas as pd
import logging
from datetime import datetime, timedelta
from tabulate import tabulate

from config.settings import Config
from utils.logger import setup_logger
from data.zerodha_client import ZerodhaClient
from indicators.avti import calculate_avti
from indicators.supporting import add_all_indicators, has_volume_spike, is_above_vwap, is_below_vwap, get_recent_trend
from strategies.entry_logic import EntrySignalGenerator
from utils.helpers import calculate_pnl, calculate_costs


class Backtester:
    """Backtesting engine"""

    def __init__(self, from_date, to_date):
        """
        Initialize backtester

        Args:
            from_date: Start date for backtest
            to_date: End date for backtest
        """
        self.from_date = from_date
        self.to_date = to_date
        self.logger = setup_logger('backtest', 'INFO')

        # Initialize components
        self.zerodha_client = None
        self.entry_generator = EntrySignalGenerator(Config.AVTI_THRESHOLD, Config.VOLUME_SPIKE_MULTIPLIER)

        # Results
        self.trades = []
        self.signals = []

        self.logger.info(f"Backtester initialized: {from_date} to {to_date}")

    def initialize_client(self):
        """Initialize Zerodha client for historical data"""
        try:
            if not Config.KITE_API_KEY or not Config.KITE_ACCESS_TOKEN:
                self.logger.error("Zerodha credentials required for backtesting")
                return False

            self.zerodha_client = ZerodhaClient(
                api_key=Config.KITE_API_KEY,
                api_secret=Config.KITE_API_SECRET,
                access_token=Config.KITE_ACCESS_TOKEN
            )

            self.logger.info("✓ Zerodha client initialized")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize client: {e}")
            return False

    def fetch_historical_data(self):
        """Fetch historical data for backtest period"""
        try:
            self.logger.info("Fetching historical data...")

            df = self.zerodha_client.get_historical_data(
                instrument_token=Config.NIFTY_INSTRUMENT_TOKEN,
                from_date=self.from_date,
                to_date=self.to_date,
                interval=Config.TIMEFRAME
            )

            if df.empty:
                self.logger.error("No historical data received")
                return None

            self.logger.info(f"Fetched {len(df)} candles")

            # Add indicators
            df = add_all_indicators(df)
            df = calculate_avti(df)

            return df

        except Exception as e:
            self.logger.error(f"Error fetching historical data: {e}")
            return None

    def simulate_trade(self, entry_bar, exit_bar, signal_type, entry_price, exit_price):
        """
        Simulate a trade

        Args:
            entry_bar: Entry candle data
            exit_bar: Exit candle data
            signal_type: CALL or PUT
            entry_price: Option entry price (estimated)
            exit_price: Option exit price (estimated)

        Returns:
            Trade dict
        """
        # Calculate P&L
        pnl, pnl_percent = calculate_pnl(entry_price, exit_price, Config.POSITION_SIZE, Config.NIFTY_LOT_SIZE)

        # Calculate costs
        costs = calculate_costs(entry_price, exit_price, Config.POSITION_SIZE, Config.NIFTY_LOT_SIZE)

        # Net P&L
        net_pnl = pnl - costs

        # Holding time
        entry_time = entry_bar['date']
        exit_time = exit_bar['date']
        holding_time = (exit_time - entry_time).total_seconds() / 60

        trade = {
            'entry_date': entry_time,
            'exit_date': exit_time,
            'signal_type': signal_type,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'gross_pnl': pnl,
            'costs': costs,
            'net_pnl': net_pnl,
            'pnl_percent': pnl_percent,
            'holding_time_mins': holding_time,
            'entry_avti': entry_bar['AVTI'],
            'exit_avti': exit_bar['AVTI']
        }

        return trade

    def estimate_option_premium(self, spot_price, signal_type, avti_value):
        """
        Rough estimate of option premium based on spot movement

        Args:
            spot_price: NIFTY spot price
            signal_type: CALL or PUT
            avti_value: Current AVTI value

        Returns:
            Estimated premium
        """
        # Very rough approximation: ATM option is typically 0.5-2% of spot
        # Higher AVTI = higher volatility = higher premium
        volatility_factor = min(avti_value / 100, 1.0)  # 0 to 1
        base_premium_percent = 0.005 + (volatility_factor * 0.015)  # 0.5% to 2%

        estimated_premium = spot_price * base_premium_percent

        return estimated_premium

    def run_backtest(self):
        """Run the backtest"""
        try:
            # Fetch data
            df = self.fetch_historical_data()

            if df is None or df.empty:
                self.logger.error("No data for backtest")
                return

            self.logger.info(f"Running backtest on {len(df)} candles...")

            # Iterate through data
            in_position = False
            entry_bar = None
            entry_premium = None
            signal_type = None

            for idx in range(20, len(df)):  # Start after warmup period
                current_bar = df.iloc[idx]

                # Check for entry signal
                if not in_position:
                    # Create mini-df for signal check
                    mini_df = df.iloc[:idx+1].copy()

                    signal = self.entry_generator.check_entry_conditions(mini_df)

                    if signal:
                        # Entry signal detected
                        entry_bar = current_bar
                        signal_type = signal['signal_type']
                        entry_premium = self.estimate_option_premium(
                            current_bar['close'],
                            signal_type,
                            current_bar['AVTI']
                        )

                        in_position = True

                        self.signals.append({
                            'date': current_bar['date'],
                            'type': signal_type,
                            'avti': current_bar['AVTI'],
                            'spot': current_bar['close']
                        })

                        self.logger.info(f"ENTRY: {signal_type} @ {current_bar['date']} | AVTI: {current_bar['AVTI']:.2f}")

                # Check for exit conditions
                elif in_position:
                    # Exit conditions:
                    # 1. Target profit (30%)
                    # 2. Stop loss (20%)
                    # 3. AVTI reversal (<40)
                    # 4. Max holding time (simulated - exit after 10 bars)

                    exit_premium = self.estimate_option_premium(
                        current_bar['close'],
                        signal_type,
                        current_bar['AVTI']
                    )

                    # Estimate premium change based on spot movement
                    spot_change = ((current_bar['close'] - entry_bar['close']) / entry_bar['close']) * 100

                    # Options have leverage - roughly 5-7x spot movement
                    option_leverage = 6.0
                    estimated_premium_change = spot_change * option_leverage

                    if signal_type == 'PUT':
                        estimated_premium_change = -estimated_premium_change

                    exit_premium = entry_premium * (1 + estimated_premium_change / 100)
                    premium_pnl_percent = ((exit_premium - entry_premium) / entry_premium) * 100

                    # Check exit conditions
                    should_exit = False
                    exit_reason = None

                    if premium_pnl_percent >= Config.TARGET_PROFIT_PERCENT:
                        should_exit = True
                        exit_reason = 'TARGET_PROFIT'
                    elif premium_pnl_percent <= -Config.STOP_LOSS_PERCENT:
                        should_exit = True
                        exit_reason = 'STOP_LOSS'
                    elif current_bar['AVTI'] < Config.AVTI_EXIT_THRESHOLD:
                        should_exit = True
                        exit_reason = 'AVTI_REVERSAL'
                    elif (idx - df.index[df['date'] == entry_bar['date']][0]) >= 10:  # 10 bars = 50 mins
                        should_exit = True
                        exit_reason = 'TIME_EXIT'

                    if should_exit:
                        # Exit trade
                        trade = self.simulate_trade(
                            entry_bar,
                            current_bar,
                            signal_type,
                            entry_premium,
                            exit_premium
                        )
                        trade['exit_reason'] = exit_reason

                        self.trades.append(trade)

                        self.logger.info(f"EXIT: {exit_reason} @ {current_bar['date']} | P&L: ₹{trade['net_pnl']:+.2f} ({trade['pnl_percent']:+.2f}%)")

                        in_position = False
                        entry_bar = None
                        entry_premium = None
                        signal_type = None

            self.logger.info(f"\n✓ Backtest complete: {len(self.signals)} signals, {len(self.trades)} trades")

        except Exception as e:
            self.logger.error(f"Error running backtest: {e}", exc_info=True)

    def generate_report(self):
        """Generate backtest report"""
        if not self.trades:
            print("\n⚠️  No trades executed during backtest period")
            return

        # Convert to DataFrame
        trades_df = pd.DataFrame(self.trades)

        # Calculate statistics
        total_trades = len(trades_df)
        winning_trades = len(trades_df[trades_df['net_pnl'] > 0])
        losing_trades = len(trades_df[trades_df['net_pnl'] < 0])
        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0

        total_pnl = trades_df['net_pnl'].sum()
        avg_win = trades_df[trades_df['net_pnl'] > 0]['net_pnl'].mean() if winning_trades > 0 else 0
        avg_loss = trades_df[trades_df['net_pnl'] < 0]['net_pnl'].mean() if losing_trades > 0 else 0

        max_win = trades_df['net_pnl'].max()
        max_loss = trades_df['net_pnl'].min()

        avg_holding_time = trades_df['holding_time_mins'].mean()

        # Profit factor
        total_wins = trades_df[trades_df['net_pnl'] > 0]['net_pnl'].sum()
        total_losses = abs(trades_df[trades_df['net_pnl'] < 0]['net_pnl'].sum())
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')

        # Print report
        print("\n" + "="*70)
        print("                   BACKTEST REPORT")
        print("="*70)
        print(f"Period:              {self.from_date} to {self.to_date}")
        print(f"Total Signals:       {len(self.signals)}")
        print(f"Total Trades:        {total_trades}")
        print(f"Winning Trades:      {winning_trades} ({win_rate:.1f}%)")
        print(f"Losing Trades:       {losing_trades}")
        print(f"\nTotal P&L:           ₹{total_pnl:+,.2f}")
        print(f"Average Win:         ₹{avg_win:,.2f}")
        print(f"Average Loss:        ₹{avg_loss:,.2f}")
        print(f"Max Win:             ₹{max_win:,.2f}")
        print(f"Max Loss:            ₹{max_loss:,.2f}")
        print(f"\nProfit Factor:       {profit_factor:.2f}")
        print(f"Avg Holding Time:    {avg_holding_time:.1f} minutes")
        print("="*70)

        # Exit reasons breakdown
        print("\nExit Reasons:")
        exit_counts = trades_df['exit_reason'].value_counts()
        for reason, count in exit_counts.items():
            print(f"  {reason:20s}: {count} ({count/total_trades*100:.1f}%)")

        # Trade log (last 10 trades)
        print("\nLast 10 Trades:")
        recent_trades = trades_df.tail(10)[[
            'entry_date', 'signal_type', 'net_pnl', 'pnl_percent', 'exit_reason'
        ]]

        print(tabulate(recent_trades, headers='keys', tablefmt='simple', showindex=False))

        print("\n")

    def run(self):
        """Main run method"""
        if not self.initialize_client():
            return

        self.run_backtest()
        self.generate_report()


def main():
    """Entry point for backtesting"""
    parser = argparse.ArgumentParser(description='Backtest AVTI strategy')
    parser.add_argument('--from-date', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--to-date', required=True, help='End date (YYYY-MM-DD)')

    args = parser.parse_args()

    # Parse dates
    from_date = datetime.strptime(args.from_date, '%Y-%m-%d')
    to_date = datetime.strptime(args.to_date, '%Y-%m-%d')

    # Run backtest
    backtester = Backtester(from_date, to_date)
    backtester.run()


if __name__ == "__main__":
    main()
