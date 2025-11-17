# API Documentation

## Overview

Complete API documentation for the Quant Trading Supportive System.

This documentation is auto-generated using `pdoc`. To regenerate:

```bash
make docs
```

To serve documentation locally:

```bash
make serve-docs
```

## Module Structure

### Data Layer (`src.data`)

#### Connectors (`src.data.connectors`)
- **BinanceConnector**: Binance exchange API integration
- **CoinbaseConnector**: Coinbase Advanced Trade API integration
- **KrakenConnector**: Kraken exchange API integration
- **OKXConnector**: OKX exchange API integration
- **BybitConnector**: Bybit exchange API integration

#### Warehouse (`src.data.warehouse`)
- **DuckDBManager**: DuckDB database operations for OHLCV data
- **ParquetManager**: Parquet data lake management with partitioning

#### Stream (`src.data.stream`)
- **WebSocketManager**: Base WebSocket manager with reconnection logic
- **BinanceStreamConnector**: Binance WebSocket streaming
- **CoinbaseStreamConnector**: Coinbase WebSocket streaming

### Analytics Layer (`src.analytics`)

#### Indicators (`src.analytics.indicators`)
- **TechnicalIndicators**: Technical analysis indicators (RSI, MACD, Bollinger Bands, etc.)
- **ICTIndicators**: Inner Circle Trader (ICT) concepts (Order Blocks, Fair Value Gaps, etc.)

#### Pattern Recognition (`src.analytics.patterns`)
- **MatrixProfileAnalyzer**: Matrix profile for motif discovery
- **DTWAnalyzer**: Dynamic Time Warping for historical analogs

#### Timeframe Analysis (`src.analytics.timeframe`)
- **TimeframeSelector**: Optimal timeframe selection for trading strategies
- **MultiTimeframeAnalyzer**: Multi-timeframe analysis and confluence

### Strategy Layer (`src.strategies`)

#### Base (`src.strategies.base`)
- **Strategy**: Base strategy class
- **SignalGenerator**: Signal generation framework

#### Implementations (`src.strategies.implementations`)
- **ScalpingStrategy**: High-frequency scalping strategies
- **ICTStrategy**: Inner Circle Trader methodology implementation
- **QuantStrategy**: Quantitative mean-reversion and momentum strategies

### Backtesting Layer (`src.backtesting`)

- **BacktestEngine**: Main backtesting engine
- **WalkForwardOptimizer**: Walk-forward optimization
- **PerformanceMetrics**: Performance metrics calculation

### UI Layer (`src.ui`)

- **app.py**: Main Streamlit application
- **pages/**: Individual page implementations

## Quick Examples

### Data Retrieval

```python
from src.data.warehouse.duckdb_manager import DuckDBManager

db = DuckDBManager()
data = db.query_ohlcv(
    symbol="BTC/USDT",
    timeframe="1h",
    exchange="binance",
    days=30
)
```

### Technical Analysis

```python
from src.analytics.indicators.technical import TechnicalIndicators

indicators = TechnicalIndicators()
df_with_indicators = indicators.add_all_indicators(df)
```

### Strategy Backtesting

```python
from src.strategies.implementations.scalping import ScalpingStrategy
from src.backtesting.engine import BacktestEngine

strategy = ScalpingStrategy()
engine = BacktestEngine(strategy)
results = engine.run(data, initial_capital=10000)
```

## Generating Full Documentation

To generate complete HTML documentation:

```bash
# Generate docs
make docs

# Serve locally on port 8080
make serve-docs
```

Then visit: http://localhost:8080/api

## API Reference

The full API reference is generated automatically from docstrings. See the generated HTML documentation for complete details on:

- All classes and their methods
- Function signatures and return types
- Parameter descriptions
- Usage examples
- Type hints

## Contributing

When adding new modules or functions:

1. Include comprehensive docstrings following Google style
2. Add type hints for all parameters and return values
3. Include usage examples in docstrings where applicable
4. Run `make docs` to verify documentation generates correctly

## Support

For questions about the API:
- Check the generated HTML documentation
- Review source code docstrings
- Check the main README.md for usage examples
