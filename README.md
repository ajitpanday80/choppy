# Choppy - NIFTY 50 Options Auto-Trading System

An automated options trading system for NIFTY 50 based on the **Ajit Volatility Transition Index (AVTI)** indicator.

## Features

- **AVTI Indicator**: Novel volatility transition detection algorithm
- **Automated Entry**: Identifies high-probability options buying opportunities
- **Smart Call/Put Selection**: Market condition-based directional bias
- **Multiple Exit Strategies**: Target profit, stop loss, trailing stop, time-based, and indicator-based exits
- **Paper Trading Mode**: Risk-free testing with realistic simulation
- **Real Trading Mode**: Automated order execution via Zerodha Kite API
- **Risk Management**: Daily loss limits, position sizing, max concurrent positions
- **Comprehensive Logging**: All trades tracked with detailed P&L analysis

## What is AVTI?

The **Ajit Volatility Transition Index** detects when the market is about to transition from LOW volatility to HIGH volatility - the perfect moment for options buying.

**Formula:**
```
AVTI = (Volume_Acceleration × Compression_Coefficient) / Directional_Deviation × 100
```

**Components:**
- **Volume Acceleration**: Volume increasing while range is compressed
- **Compression Coefficient**: Measures price "coiling" (tight ATR + narrow Bollinger Bands)
- **Directional Deviation**: Filters sideways chop, prefers mean reversion setups

**Signal**: AVTI > 65 = Volatility breakout imminent

## Installation

### 1. Clone the repository
```bash
git clone <repository-url>
cd choppy
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure credentials
```bash
cp .env.example .env
# Edit .env and add your Zerodha API credentials
```

### 4. Get Zerodha API Credentials
1. Sign up at https://kite.trade/
2. Create an app to get API Key and API Secret
3. Generate access token (see Zerodha documentation)

## Configuration

Edit `.env` file:

```bash
# Switch between PAPER and REAL mode
TRADING_MODE=PAPER

# Risk parameters
MAX_DAILY_LOSS=5000        # Stop trading if daily loss exceeds this
MAX_POSITIONS=2             # Maximum concurrent positions
POSITION_SIZE=1             # Lot size per trade

# Strategy parameters
AVTI_THRESHOLD=65           # Entry signal threshold
TARGET_PROFIT_PERCENT=30    # Take profit at 30%
STOP_LOSS_PERCENT=20        # Stop loss at 20%
TRAILING_STOP_PERCENT=15    # Trailing stop activated after 15% profit

# Trading hours (IST)
TRADING_START_HOUR=9
TRADING_START_MINUTE=20     # Start after market stabilizes
TRADING_END_HOUR=15
TRADING_END_MINUTE=20       # Exit all positions before close
```

## Usage

### Run Paper Trading (Recommended First)
```bash
python main.py
```

The system will:
1. Connect to Zerodha for live data
2. Calculate AVTI every 5 minutes
3. Generate entry signals (AVTI > 65 with filters)
4. Simulate order execution with realistic slippage
5. Log all trades to `trades/` folder

### Run Real Trading (After Paper Trading Validation)
```bash
# Change TRADING_MODE=REAL in .env
python main.py
```

**⚠️ WARNING**: Real mode places actual orders. Ensure you've tested thoroughly in paper mode first.

### Run Backtesting
```bash
python backtest.py --from-date 2024-09-01 --to-date 2024-11-06
```

## System Architecture

```
choppy/
├── config/          # Configuration and settings
├── data/            # Zerodha API integration & data streaming
├── indicators/      # AVTI and supporting indicators
├── strategies/      # Entry and exit logic
├── executors/       # Paper and real trading engines
├── risk/            # Risk management rules
├── utils/           # Logging and helpers
├── logs/            # System and trade logs
└── trades/          # Trade records (CSV)
```

## Entry Logic

A trade is triggered when **ALL** conditions are met:

1. **AVTI > 65** (volatility transition detected)
2. **Volume Spike**: Current volume > 1.5× average of last 10 bars
3. **Directional Bias**: Price on same side of VWAP for last 3 candles
4. **Time Filter**: Within trading hours (9:20 AM - 3:20 PM IST)
5. **Risk Check**: Daily loss limit not exceeded, max positions not reached

**Call vs Put Selection:**
- If price > VWAP AND recent bars bullish → Buy ATM Call
- If price < VWAP AND recent bars bearish → Buy ATM Put

## Exit Logic

Positions are automatically exited when **ANY** condition is met:

1. **Target Profit**: Premium increases by 30% (configurable)
2. **Stop Loss**: Premium decreases by 20% (configurable)
3. **Trailing Stop**: After 15% profit, exit if drops 10% from peak
4. **Time Exit**: 3:20 PM IST (before market close)
5. **AVTI Reversal**: AVTI drops below 40 (volatility exhausted)

## Monitoring

### Live Monitoring
The bot prints real-time updates:
```
[09:25:15] AVTI: 68.5 | Signal: LONG | Volume: 2.1x
[09:25:15] PAPER MODE: Bought NIFTY 19500 CE @ ₹125.50 (Lot: 50)
[09:32:20] Position Update: +18.5% (₹148.50)
[09:35:10] PAPER MODE: Exited at ₹162.75 | P&L: +₹1,862.50 (+29.7%)
```

### Trade Logs
All trades saved to `trades/trades_YYYYMMDD.csv`:
```csv
timestamp,signal_type,strike,option_type,entry_price,exit_price,pnl,pnl_percent,exit_reason
09:25:15,LONG,19500,CE,125.50,162.75,1862.50,29.7,TARGET_PROFIT
```

### Performance Summary
At end of day, view performance:
```bash
python -m utils.analyze_trades --date 2024-11-06
```

Output:
```
=== Daily Performance ===
Total Trades: 8
Winners: 5 (62.5%)
Losers: 3 (37.5%)
Gross P&L: ₹4,250.50
Net P&L (after costs): ₹3,890.20
Win Rate: 62.5%
Avg Win: ₹1,456.30
Avg Loss: ₹-820.10
Profit Factor: 2.23
Max Drawdown: ₹-1,640.20
```

## Risk Management

Built-in safeguards:

- **Daily Loss Circuit Breaker**: Stops trading if daily loss exceeds limit
- **Position Limits**: Max 2 concurrent positions (prevents over-exposure)
- **Position Sizing**: Fixed lot size per trade
- **Time-Based Exits**: Forces exit before market close (prevents overnight risk)
- **Slippage Modeling**: Paper mode includes realistic 2-3% slippage

## Paper vs Real Mode

| Feature | Paper Mode | Real Mode |
|---------|-----------|-----------|
| Order Execution | Simulated | Actual Zerodha orders |
| Slippage | 2-3% modeled | Real market slippage |
| Costs | Modeled (₹20 + 0.05% STT) | Actual brokerage charges |
| Risk | Zero | Real capital at risk |
| Use Case | Testing & validation | Live trading |

## Troubleshooting

### "Invalid API credentials"
- Check KITE_API_KEY and KITE_API_SECRET in .env
- Ensure access token is valid (regenerate if expired)

### "No data fetched"
- Verify market hours (9:15 AM - 3:30 PM IST, Mon-Fri)
- Check internet connection
- Ensure Zerodha API subscription is active

### "Order rejected"
- Verify sufficient margin in Zerodha account
- Check if options contract is tradable
- Ensure position limits not exceeded

### "AVTI always 0"
- Need at least 20 bars of data for calculation
- Wait 100 minutes (20 × 5min bars) after market open

## Backtesting

Validate strategy on historical data:

```bash
# Test specific date range
python backtest.py --from-date 2024-09-01 --to-date 2024-11-06

# Generate performance report
python backtest.py --from-date 2024-09-01 --to-date 2024-11-06 --report
```

## Disclaimer

**⚠️ IMPORTANT DISCLAIMERS:**

1. **Trading Risk**: Options trading involves substantial risk. You can lose all invested capital.
2. **No Guarantee**: Past performance (backtest or paper trading) does NOT guarantee future results.
3. **Use at Own Risk**: This software is provided "as-is" without warranties. The author is not responsible for any losses.
4. **Paper Trade First**: ALWAYS validate in paper mode for at least 1-2 months before going live.
5. **Not Financial Advice**: This is an educational project, not financial advice. Consult a financial advisor.
6. **Market Conditions Change**: Strategies that work in one regime may fail in another.
7. **Monitor Actively**: Even in auto-mode, monitor the system regularly.

## Development

### Running Tests
```bash
pytest tests/
```

### Adding Custom Indicators
Edit `indicators/supporting.py` and add your indicator function.

### Modifying Strategy
Edit `strategies/entry_logic.py` or `strategies/exit_logic.py`.

## Roadmap

- [ ] Multi-timeframe AVTI confirmation
- [ ] Machine learning-based position sizing
- [ ] Telegram/Email notifications
- [ ] Options Greeks-based filtering
- [ ] Support for BANKNIFTY
- [ ] Web dashboard for monitoring

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Test thoroughly in paper mode
4. Submit a pull request

## License

MIT License - see LICENSE file

## Support

For issues or questions:
- Open an issue on GitHub
- Review the troubleshooting section
- Check Zerodha KiteConnect documentation

---

**Built with Python 🐍 | Powered by Zerodha Kite API 📈**

**Remember**: The best trading system is one you understand completely. Study the code, validate the logic, and trade responsibly.
