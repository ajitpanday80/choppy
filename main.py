"""
Choppy - NIFTY 50 Options Auto-Trading System
Main entry point for the trading bot
"""
import logging
import sys
import time
from datetime import datetime
import signal

# Import configuration
from config.settings import Config

# Import utilities
from utils.logger import setup_logger, TradeLogger
from utils.helpers import is_trading_time, get_ist_time, PerformanceTracker

# Import data handlers
from data.zerodha_client import ZerodhaClient
from data.market_data import MarketDataHandler, OptionsDataHandler

# Import indicators
from indicators.avti import AVTIIndicator, calculate_avti
from indicators.supporting import add_all_indicators

# Import strategy
from strategies.entry_logic import EntrySignalGenerator, EntryFilter
from strategies.exit_logic import ExitStrategy, PositionManager

# Import risk management
from risk.risk_manager import RiskManager

# Import executors
from executors.paper_trader import PaperTrader
from executors.real_trader import RealTrader


class TradingBot:
    """Main trading bot orchestrator"""

    def __init__(self):
        """Initialize the trading bot"""

        # Setup logger
        self.logger = setup_logger('choppy', Config.LOG_LEVEL, Config.LOG_DIR)
        self.trade_logger = TradeLogger(Config.TRADE_DIR)

        self.logger.info("="*70)
        self.logger.info("           CHOPPY - NIFTY 50 OPTIONS TRADING SYSTEM")
        self.logger.info("="*70)

        # Validate configuration
        errors = Config.validate()
        if errors:
            self.logger.error("Configuration errors:")
            for error in errors:
                self.logger.error(f"  - {error}")
            sys.exit(1)

        # Display configuration
        print(Config.display_config())

        # Initialize components
        self.zerodha_client = None
        self.market_data = None
        self.options_data = None
        self.avti_indicator = AVTIIndicator(Config.AVTI_THRESHOLD, Config.AVTI_EXIT_THRESHOLD)
        self.entry_generator = EntrySignalGenerator(Config.AVTI_THRESHOLD, Config.VOLUME_SPIKE_MULTIPLIER)
        self.entry_filter = EntryFilter()
        self.exit_strategy = ExitStrategy(
            target_profit_percent=Config.TARGET_PROFIT_PERCENT,
            stop_loss_percent=Config.STOP_LOSS_PERCENT,
            trailing_stop_percent=Config.TRAILING_STOP_PERCENT,
            trailing_trigger_percent=Config.TRAILING_STOP_TRIGGER,
            avti_exit_threshold=Config.AVTI_EXIT_THRESHOLD,
            time_exit_hour=Config.TRADING_END_HOUR,
            time_exit_minute=Config.TRADING_END_MINUTE
        )
        self.position_manager = PositionManager(self.exit_strategy)
        self.risk_manager = RiskManager(
            max_daily_loss=Config.MAX_DAILY_LOSS,
            max_positions=Config.MAX_POSITIONS,
            position_size=Config.POSITION_SIZE
        )
        self.performance = PerformanceTracker()

        # Executor (Paper or Real)
        self.executor = None

        # Running flag
        self.running = False

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        self.logger.info("Trading bot initialized")

    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.warning("\n⚠️  Shutdown signal received. Closing positions and exiting...")
        self.shutdown()
        sys.exit(0)

    def initialize_zerodha(self):
        """Initialize Zerodha client"""
        try:
            if Config.is_paper_mode():
                self.logger.info("📄 PAPER TRADING MODE - No real orders will be placed")
                # Initialize paper trader
                self.executor = PaperTrader(
                    initial_balance=Config.PAPER_INITIAL_BALANCE,
                    slippage_percent=Config.PAPER_SLIPPAGE_PERCENT,
                    lot_size=Config.NIFTY_LOT_SIZE
                )

                # Still need Zerodha client for market data (even in paper mode)
                if Config.KITE_API_KEY:
                    self.zerodha_client = ZerodhaClient(
                        api_key=Config.KITE_API_KEY,
                        api_secret=Config.KITE_API_SECRET,
                        access_token=Config.KITE_ACCESS_TOKEN
                    )
                else:
                    self.logger.warning("No Zerodha credentials provided. Using mock data.")
                    return False

            else:
                self.logger.warning("⚠️  REAL TRADING MODE - Real orders will be placed!")
                self.zerodha_client = ZerodhaClient(
                    api_key=Config.KITE_API_KEY,
                    api_secret=Config.KITE_API_SECRET,
                    access_token=Config.KITE_ACCESS_TOKEN
                )

                # Verify connection
                profile = self.zerodha_client.get_profile()
                if not profile:
                    self.logger.error("Failed to connect to Zerodha")
                    return False

                # Initialize real trader
                self.executor = RealTrader(
                    zerodha_client=self.zerodha_client,
                    lot_size=Config.NIFTY_LOT_SIZE
                )

            # Initialize market data handler
            self.market_data = MarketDataHandler(
                zerodha_client=self.zerodha_client,
                instrument_token=Config.NIFTY_INSTRUMENT_TOKEN,
                timeframe=Config.TIMEFRAME
            )

            # Initialize options data handler
            self.options_data = OptionsDataHandler(self.zerodha_client)

            self.logger.info("✓ Zerodha client initialized")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize Zerodha: {e}")
            return False

    def load_initial_data(self):
        """Load initial historical data"""
        try:
            self.logger.info(f"Loading {Config.LOOKBACK_DAYS} days of historical data...")
            success = self.market_data.load_historical_data(days=Config.LOOKBACK_DAYS)

            if not success:
                self.logger.error("Failed to load historical data")
                return False

            self.logger.info("✓ Historical data loaded")
            return True

        except Exception as e:
            self.logger.error(f"Error loading initial data: {e}")
            return False

    def process_market_data(self):
        """Process current market data and calculate indicators"""
        try:
            # Get latest candle
            latest_candle = self.market_data.get_latest_candle()

            if latest_candle is None:
                # No new candle yet
                return None

            # Get current dataframe
            df = self.market_data.get_dataframe()

            if df.empty or len(df) < 20:
                self.logger.debug("Insufficient data for analysis")
                return None

            # Add all indicators
            df = add_all_indicators(df)

            # Calculate AVTI
            df = calculate_avti(df)

            # Store back
            self.market_data.candles = df

            return df

        except Exception as e:
            self.logger.error(f"Error processing market data: {e}")
            return None

    def check_entry_signal(self, df):
        """Check for entry signals"""
        try:
            # Check if we can take a trade
            can_trade, reason = self.risk_manager.can_take_trade()

            if not can_trade:
                self.logger.debug(f"Cannot take trade: {reason}")
                return None

            # Check trading hours
            if not self.entry_filter.check_time_filter(Config.get_trading_hours()):
                return None

            # Check entry conditions
            signal = self.entry_generator.check_entry_conditions(df)

            if signal is None:
                return None

            # Apply entry filters
            allowed, filter_reason = self.entry_filter.filter_signal(
                signal,
                self.position_manager.get_position_count(),
                self.risk_manager.daily_pnl,
                Config.MAX_POSITIONS,
                Config.MAX_DAILY_LOSS
            )

            if not allowed:
                self.logger.warning(f"Signal filtered: {filter_reason}")
                return None

            return signal

        except Exception as e:
            self.logger.error(f"Error checking entry signal: {e}")
            return None

    def execute_entry(self, signal):
        """Execute entry order"""
        try:
            spot_price = signal['close']
            option_type = self.entry_generator.get_option_type(signal['signal_type'])

            # Get ATM option details
            option_details = self.options_data.get_atm_option_details(
                spot_price=spot_price,
                option_type=option_type,
                underlying='NIFTY',
                strike_interval=50
            )

            if not option_details:
                self.logger.error("Could not get option details")
                return False

            symbol = option_details['symbol']
            strike = option_details['strike']
            ltp = option_details['ltp']

            self.logger.info(f"Executing {signal['signal_type']}: {symbol} @ ₹{ltp:.2f}")

            # Execute order via executor (paper or real)
            order = self.executor.place_buy_order(
                symbol=symbol,
                quantity=Config.POSITION_SIZE,
                option_type=option_type,
                strike=strike,
                current_price=ltp,
                signal_type=signal['signal_type']
            )

            if not order:
                self.logger.error("Failed to execute order")
                return False

            # Add position to manager
            self.position_manager.add_position(order)

            # Update risk manager
            self.risk_manager.position_opened()

            self.logger.info(f"✓ Position opened: {symbol}")

            return True

        except Exception as e:
            self.logger.error(f"Error executing entry: {e}")
            return False

    def check_exits(self, df):
        """Check and execute exits for open positions"""
        try:
            if self.position_manager.get_position_count() == 0:
                return

            # Market data provider for current prices
            def get_current_price(symbol):
                try:
                    ltp = self.options_data.get_option_ltp(symbol)
                    return ltp
                except:
                    return None

            # Check all positions
            positions_to_exit = self.position_manager.check_all_positions(get_current_price, df)

            # Execute exits
            for exit_info in positions_to_exit:
                self.execute_exit(exit_info['position'], exit_info['exit_price'], exit_info['exit_reason'])

        except Exception as e:
            self.logger.error(f"Error checking exits: {e}")

    def execute_exit(self, position, exit_price, exit_reason):
        """Execute exit order"""
        try:
            self.logger.info(f"Exiting position: {position['symbol']} @ ₹{exit_price:.2f} ({exit_reason})")

            # Execute sell order
            exit_record = self.executor.place_sell_order(position, exit_price, exit_reason)

            if not exit_record:
                self.logger.error("Failed to execute exit")
                return False

            # Remove position from manager
            self.position_manager.remove_position(position)

            # Update risk manager
            self.risk_manager.position_closed()
            self.risk_manager.record_trade(exit_record['net_pnl'], exit_record['net_pnl'] > 0)

            # Update performance tracker
            self.performance.add_trade(exit_record['net_pnl'])

            # Log trade
            trade_data = {
                'timestamp': exit_record['exit_time'].strftime("%Y-%m-%d %H:%M:%S"),
                'signal_type': position.get('signal_type', 'UNKNOWN'),
                'strike': position.get('strike', ''),
                'option_type': position.get('option_type', ''),
                'entry_price': exit_record['entry_price'],
                'exit_price': exit_record['exit_price'],
                'quantity': exit_record['quantity'],
                'pnl': exit_record['net_pnl'],
                'pnl_percent': exit_record['pnl_percent'],
                'exit_reason': exit_reason,
                'avti_entry': position.get('avti', 0),
                'avti_exit': 0,  # TODO: Get current AVTI
                'holding_time_mins': exit_record['holding_time_mins'],
                'slippage': exit_record.get('slippage', 0),
                'costs': exit_record.get('costs', 0)
            }

            self.trade_logger.log_trade(trade_data)

            self.logger.info(f"✓ Position exited | P&L: ₹{exit_record['net_pnl']:+.2f} ({exit_record['pnl_percent']:+.2f}%)")

            return True

        except Exception as e:
            self.logger.error(f"Error executing exit: {e}")
            return False

    def trading_loop(self):
        """Main trading loop"""
        self.logger.info("Starting trading loop...")
        self.running = True

        last_check_time = None
        check_interval = 60  # Check every 60 seconds

        while self.running:
            try:
                current_time = get_ist_time()

                # Check if it's trading time
                if not is_trading_time(Config.get_trading_hours()):
                    self.logger.debug("Outside trading hours. Waiting...")
                    time.sleep(30)
                    continue

                # Throttle checks
                if last_check_time and (current_time - last_check_time).total_seconds() < check_interval:
                    time.sleep(10)
                    continue

                last_check_time = current_time

                self.logger.info(f"\n{'='*60}")
                self.logger.info(f"Market Check - {current_time.strftime('%H:%M:%S')}")
                self.logger.info(f"{'='*60}")

                # Process market data
                df = self.process_market_data()

                if df is None or df.empty:
                    self.logger.debug("No new data to process")
                    continue

                # Display current AVTI
                current_avti = self.avti_indicator.get_current_value(df)
                latest_close = df['close'].iloc[-1]
                self.logger.info(f"AVTI: {current_avti:.2f} | NIFTY: {latest_close:.2f}")

                # Check exits first
                self.check_exits(df)

                # Check for entry signals
                signal = self.check_entry_signal(df)

                if signal:
                    self.execute_entry(signal)

                # Display status
                self.display_status()

                # Sleep before next iteration
                time.sleep(10)

            except KeyboardInterrupt:
                self.logger.warning("Keyboard interrupt received")
                break
            except Exception as e:
                self.logger.error(f"Error in trading loop: {e}", exc_info=True)
                time.sleep(30)

        self.logger.info("Trading loop stopped")

    def display_status(self):
        """Display current status"""
        risk_summary = self.risk_manager.get_risk_summary()

        self.logger.info(f"\n--- Status ---")
        self.logger.info(f"Daily P&L: ₹{risk_summary['current_daily_pnl']:+.2f}")
        self.logger.info(f"Active Positions: {risk_summary['current_positions']}/{risk_summary['max_positions']}")
        self.logger.info(f"Trading Status: {risk_summary['trading_status']}")

    def shutdown(self):
        """Graceful shutdown"""
        self.logger.info("Shutting down...")
        self.running = False

        # Close all open positions
        if self.position_manager.get_position_count() > 0:
            self.logger.warning("Closing all open positions...")

            def get_current_price(symbol):
                try:
                    return self.options_data.get_option_ltp(symbol)
                except:
                    return None

            positions_to_exit = self.position_manager.force_exit_all_positions(get_current_price, 'SHUTDOWN')

            for exit_info in positions_to_exit:
                self.execute_exit(exit_info['position'], exit_info['exit_price'], exit_info['exit_reason'])

        # Display final statistics
        self.logger.info("\n" + "="*60)
        self.logger.info("           END OF DAY SUMMARY")
        self.logger.info("="*60)

        self.risk_manager.display_statistics()
        self.performance.display_stats()

        if Config.is_paper_mode():
            self.executor.display_summary()

        self.logger.info("Shutdown complete")

    def run(self):
        """Main run method"""
        try:
            # Initialize Zerodha
            if not self.initialize_zerodha():
                self.logger.error("Failed to initialize Zerodha. Exiting.")
                return

            # Load initial data
            if not self.load_initial_data():
                self.logger.error("Failed to load initial data. Exiting.")
                return

            self.logger.info("\n✓ All systems initialized. Starting trading...")

            # Start trading loop
            self.trading_loop()

        except Exception as e:
            self.logger.error(f"Fatal error in main run: {e}", exc_info=True)
        finally:
            self.shutdown()


def main():
    """Entry point"""
    bot = TradingBot()
    bot.run()


if __name__ == "__main__":
    main()
