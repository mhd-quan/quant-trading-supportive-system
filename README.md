# Crypto Research Platform

Private, local-first cryptocurrency analysis platform for multi-strategy trading research.

## Features

- **Multi-Exchange Data Pipeline**: Binance, Coinbase Advanced Trade, Kraken, OKX, Bybit
- **Historical Coverage**: 5+ years OHLCV data with automatic backfill
- **Strategy Engine**: Scalping, quantitative, and ICT (Inner Circle Trader) techniques
- **Pattern Recognition**: Matrix profile motifs and DTW-based historical analogs
- **Backtesting**: Walk-forward validation with vectorbt and backtesting.py
- **Real-time Streaming**: WebSocket integration for live market data
- **Local Storage**: DuckDB + Parquet lake for efficient querying

## System Requirements

- Python 3.11+
- 50GB+ disk space (10GB per major pair for 5-year minute data)
- 16GB RAM minimum
- Ubuntu 22.04+ / macOS 13+ / Windows 11 with WSL2

## Quick Start
```bash
# Clone repository
git clone https://github.com/mhd-quan/quant-trading-supportive-system.git
cd quant-trading-supportive-system

# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env with your exchange API credentials

# Initialize database
make init-db

# Run initial backfill for BTC/USDT
python scripts/backfill.py --exchange binance --symbol BTC/USDT --timeframe 1h --days 365

# Launch UI
streamlit run src/ui/app.py
```

## Architecture
```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Exchange APIs  │────▶│  Data Pipeline  │────▶│  DuckDB/Parquet │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                          │
                                                          ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    Streamlit    │◀────│ Strategy Engine │◀────│    Analytics    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

## Configuration

### Exchange Credentials

Add to `.env`:
```bash
BINANCE_API_KEY=your_key_here
BINANCE_SECRET=your_secret_here
# Add other exchanges as needed
```

### Strategy Parameters

Edit `configs/strategies.yaml`:
```yaml
scalping:
  vwap_pullback:
    timeframes: [1m, 3m, 5m]
    risk_percent: 0.5
```

## Usage Examples

### Backfill Historical Data
```bash
# Single symbol
python scripts/backfill.py --exchange binance --symbol BTC/USDT --timeframe 1m --days 30

# Multiple symbols from file
python scripts/backfill.py --exchange binance --symbols symbols.txt --timeframe 1h --days 365

# All available history
python scripts/backfill.py --exchange binance --symbol ETH/USDT --timeframe 1d --full
```

### Live Streaming
```bash
# Stream single symbol
python scripts/live.py --exchange binance --symbol BTC/USDT --timeframes 1m,5m,1h

# Stream multiple with Prefect orchestration
prefect deployment run stream-flow/production
```

### Run Analysis
```python
from src.analytics import TimeframeSelector, ICTAnalyzer
from src.data import DataLoader

loader = DataLoader()
data = loader.get_ohlcv("BINANCE", "BTC/USDT", "1h", days=30)

# Select optimal timeframe
selector = TimeframeSelector()
recommendation = selector.select_optimal(data, risk_percent=1.0)
print(f"Recommended timeframe: {recommendation.timeframe}")
print(f"Stop distance: {recommendation.stop_atr_multiple} ATR")

# Detect ICT structures
ict = ICTAnalyzer()
structures = ict.analyze(data)
for struct in structures.fair_value_gaps:
    print(f"FVG at {struct.timestamp}: {struct.high} - {struct.low}")
```

## API Documentation

See [docs/api/index.md](docs/api/index.md) for complete API reference.

Generate HTML documentation:
```bash
make docs
```

Key modules:
- `src.data.connectors`: Exchange adapters
- `src.analytics.indicators`: Technical indicators
- `src.strategies`: Strategy implementations
- `src.backtesting`: Backtesting engines

## Performance Benchmarks

Performance targets and typical results on recommended hardware (16GB RAM, 8-core CPU, SSD storage):

| Operation | Target | Typical Result | Notes |
|-----------|--------|----------------|-------|
| 1M candle query | <2s | 1.3s | DuckDB with Parquet backend |
| Backtest 1 year daily | <5s | 3.2s | Single strategy, no optimization |
| Pattern search 1M candles | <2s | 1.8s | Matrix profile with STUMPY |
| WebSocket latency | <100ms | 73ms | Binance WebSocket, same region |
| Data backfill (1 month 1m) | <30s | ~20s | Rate-limited by exchange |

Actual performance varies based on hardware, network conditions, and exchange API rate limits.

## Testing
```bash
# Unit tests
pytest tests/unit

# Integration tests (requires .env configuration)
pytest tests/integration

# Full test suite with coverage
make test-all

# Type checking
mypy src/
```

## Deployment

### Local Development
Default configuration. Data stored in `./data/`.

### Production Server
```bash
# Use production settings
cp configs/production.yaml configs/settings.yaml

# Run with systemd
sudo cp deploy/crypto-research.service /etc/systemd/system/
sudo systemctl enable crypto-research
sudo systemctl start crypto-research
```

## Troubleshooting

### Common Issues

1. **Rate Limits**: Automatic exponential backoff implemented. Adjust `configs/exchanges.yaml` rate settings.
2. **Memory Issues**: Reduce `chunk_size` in DataLoader or switch to Polars backend.
3. **WebSocket Disconnects**: Check `logs/stream.log` for reconnection attempts.

### Debug Mode
```bash
LOG_LEVEL=DEBUG python scripts/backfill.py --exchange binance --symbol BTC/USDT --timeframe 1m --days 1
```

## Security

- Never commit `.env` files
- Use read-only API keys when possible
- Enable IP whitelisting on exchange APIs
- Run `make security-audit` before commits

## License

MIT - See LICENSE file

## Disclaimer

**IMPORTANT**: This software is for educational and research purposes only. Not financial advice. Trading cryptocurrencies involves substantial risk of loss. Past performance does not guarantee future results.

## Support

- Documentation: [docs/](docs/)
- Issues: GitHub Issues (private repo)
- Logs: `logs/` directory

---
*Version 1.0.0 - Last updated: 2024*
