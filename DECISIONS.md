# Architecture Decision Records

## ADR-001: DuckDB + Parquet Lake Storage
**Date**: 2024-01-01  
**Status**: Accepted

### Context
Need efficient storage for billions of OHLCV records with fast analytical queries.

### Decision
DuckDB as primary database with Parquet files as cold storage.

### Rationale
- DuckDB: Columnar, OLAP-optimized, embedded (no server)
- Parquet: Compressed, partitioned, cloud-compatible
- Alternative rejected: TimescaleDB (requires PostgreSQL server)
- Alternative rejected: ClickHouse (overkill for single-user)

### Consequences
- Positive: Sub-second analytical queries, 10x compression
- Negative: Not suitable for high-frequency concurrent writes
- Mitigation: Batch writes every 1000 records

---

## ADR-002: Exchange Connectivity via CCXT + Native WebSockets
**Date**: 2024-01-02  
**Status**: Accepted

### Context
Need unified interface for multiple exchanges with real-time streaming.

### Decision
CCXT for REST API historical data, native WebSocket clients for streaming.

### Rationale
- CCXT: Battle-tested, 100+ exchange support
- Native WS: Lower latency, exchange-specific features
- Alternative rejected: CCXT Pro (paid, unnecessary for our use case)

### Implementation
```python
class ExchangeAdapter:
    def __init__(self):
        self.ccxt_client = ccxt.binance()
        self.ws_client = BinanceWebSocket()
```

---

## ADR-003: ICT Strategy Implementation
**Date**: 2024-01-03  
**Status**: Accepted

### Context
ICT (Inner Circle Trader) concepts lack standardized implementation.

### Decision
Custom implementation with configurable thresholds.

### Definitions
- **BOS (Break of Structure)**: Close beyond previous swing high/low
- **MSS (Market Structure Shift)**: Failed retest after BOS
- **FVG (Fair Value Gap)**: Gap between candles with no body overlap
- **Order Block**: Last opposing candle before impulsive move

### Algorithm
```python
def detect_fvg(candles: pd.DataFrame, min_gap_atr: float = 0.5):
    gaps = []
    for i in range(2, len(candles)):
        gap_high = min(candles.iloc[i-2].high, candles.iloc[i].high)
        gap_low = max(candles.iloc[i-2].low, candles.iloc[i].low)
        if gap_high < gap_low:  # Valid gap
            atr = calculate_atr(candles[:i])
            if (gap_low - gap_high) >= min_gap_atr * atr:
                gaps.append(FVG(gap_high, gap_low, candles.iloc[i].timestamp))
    return gaps
```

---

## ADR-004: Backtesting Framework Selection
**Date**: 2024-01-04  
**Status**: Accepted

### Context
Need fast, accurate backtesting with walk-forward validation.

### Decision
Dual-engine approach: vectorbt for parameter sweeps, backtesting.py for detailed reports.

### Rationale
- vectorbt: 100x faster for grid search via vectorization
- backtesting.py: Cleaner API, better reporting
- Alternative rejected: Zipline (abandoned project)
- Alternative rejected: Backtrader (slower, complex API)

### Usage Pattern
```python
# Quick parameter optimization
results = vbt.Portfolio.from_signals(
    close=prices,
    entries=signals.entry,
    exits=signals.exit
).optimize(sl_stop=np.arange(0.01, 0.05, 0.01))

# Detailed single run
bt = Backtest(prices, MyStrategy, cash=10000)
stats = bt.run(sl_percent=0.02)
```

---

## ADR-005: Pattern Matching via Matrix Profile
**Date**: 2024-01-05  
**Status**: Accepted

### Context
Need efficient method to find similar historical patterns.

### Decision
STUMPY library for matrix profile computation.

### Implementation
```python
def find_patterns(data: np.ndarray, window: int = 100):
    # Multi-dimensional matrix profile
    features = np.column_stack([
        data,  # Price
        calculate_returns(data),
        calculate_volume_profile(data),
        calculate_atr(data)
    ])
    mp = stumpy.mstump(features, m=window)
    motifs = stumpy.motifs(mp[0], mp[1], k=10)
    return motifs
```

### Performance
- 1M candles: 1.8 seconds
- Memory: O(n) where n = series length

---

## ADR-006: WebSocket Reconnection Strategy
**Date**: 2024-01-06  
**Status**: Accepted

### Context
WebSocket connections drop frequently (network, exchange maintenance).

### Decision
Exponential backoff with jitter, max 5 minute delay.

### Implementation
```python
async def reconnect_with_backoff(self):
    delay = 1  # Start with 1 second
    max_delay = 300  # Cap at 5 minutes
    
    while not self.connected:
        try:
            await self.connect()
            delay = 1  # Reset on success
        except Exception as e:
            jitter = random.uniform(0, delay * 0.1)
            await asyncio.sleep(delay + jitter)
            delay = min(delay * 2, max_delay)
```

---

## ADR-007: Position Sizing Algorithm
**Date**: 2024-01-07  
**Status**: Accepted

### Context
Need consistent risk management across strategies.

### Decision
Modified Kelly Criterion capped at user risk percentage.

### Formula
```
position_size = min(
    kelly_fraction * account_balance,
    (risk_percent * account_balance) / stop_distance
)
```

### Safety Constraints
- Maximum 2% risk per trade
- Maximum 20% account allocation per position
- Correlation adjustment for multiple positions

---

## ADR-008: Timeframe Selection Scoring
**Date**: 2024-01-08  
**Status**: Accepted

### Context
"Identify the timeframe" requirement needs formalization.

### Decision
Multi-factor scoring system.

### Formula
```
Score = 0.3 * trend_efficiency 
      + 0.3 * volume_score
      - 0.2 * slippage_penalty
      + 0.2 * liquidity_score
```

### Components
- **Trend Efficiency**: Kaufman Efficiency Ratio (direction/volatility)
- **Volume Score**: Z-score of recent volume vs 30-period mean
- **Slippage Penalty**: Estimated from bid-ask spread
- **Liquidity Score**: Order book depth at 1% from mid

---

## ADR-009: Data Validation Pipeline
**Date**: 2024-01-09  
**Status**: Accepted

### Context
Exchange data contains gaps, duplicates, and errors.

### Decision
Three-stage validation pipeline.

### Stages
1. **Immediate**: Timestamp monotonicity, OHLC relationship (H>=L, etc.)
2. **Batch**: Duplicate detection, gap identification
3. **Daily**: Statistical anomaly detection (>10 sigma moves)

### Recovery
- Gaps < 5 minutes: Linear interpolation
- Gaps > 5 minutes: Mark as missing, attempt re-fetch
- Anomalies: Flag for manual review

---

## ADR-010: UI Framework Selection
**Date**: 2024-01-10  
**Status**: Accepted

### Context
Need rapid prototyping with interactive charts.

### Decision
Streamlit with streamlit-lightweight-charts.

### Rationale
- Streamlit: Python-native, rapid development
- Lightweight Charts: TradingView library, professional appearance
- Alternative rejected: Dash (more complex)
- Alternative rejected: Django (overkill for single-user)

### Limitations
- Single-user only (Streamlit limitation)
- 1GB file upload limit
- WebSocket integration requires workarounds

---

## Future Decisions

- [ ] ADR-011: Cloud deployment strategy (AWS vs GCP vs local)
- [ ] ADR-012: Multi-user support architecture
- [ ] ADR-013: Machine learning integration
- [ ] ADR-014: Options data integration
