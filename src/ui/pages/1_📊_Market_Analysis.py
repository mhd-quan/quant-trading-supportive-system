"""Market analysis page with charts and indicators."""

import streamlit as st
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.data.warehouse.duckdb_manager import DuckDBManager
from src.analytics.indicators.technical import TechnicalIndicators
from src.analytics.patterns.ict import ICTPatterns
import plotly.graph_objects as go

st.set_page_config(page_title="Market Analysis", page_icon="📊", layout="wide")

st.title("📊 Market Analysis")
st.markdown("Analyze cryptocurrency markets with technical indicators and ICT patterns.")

# Sidebar configuration
st.sidebar.header("Configuration")

exchange = st.sidebar.selectbox("Exchange", ["binance", "coinbase"])
symbol = st.sidebar.selectbox(
    "Symbol",
    ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"],
)
timeframe = st.sidebar.selectbox(
    "Timeframe",
    ["1m", "5m", "15m", "1h", "4h", "1d"],
)

days_back = st.sidebar.slider("Days to load", 1, 365, 30)

# Load data
@st.cache_data(ttl=300)
def load_data(exchange, symbol, timeframe, days_back):
    """Load data from DuckDB."""
    try:
        db = DuckDBManager()
        end_date = pd.Timestamp.now()
        start_date = end_date - pd.Timedelta(days=days_back)
        df = db.query_ohlcv(symbol, timeframe, start_date, end_date, exchange)
        db.close()
        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame()

df = load_data(exchange, symbol, timeframe, days_back)

if df.empty:
    st.warning(
        f"""
        No data available for {symbol} on {exchange}.

        Run the backfill script to download data:
        ```bash
        python scripts/backfill.py --exchange {exchange} --symbol {symbol} --timeframe {timeframe} --days 30
        ```
        """
    )
    st.stop()

# Add indicators
with st.spinner("Calculating indicators..."):
    df = TechnicalIndicators.add_all_indicators(df)

# Display metrics
col1, col2, col3, col4 = st.columns(4)

with col1:
    last_price = df.iloc[-1]["close"]
    st.metric("Last Price", f"${last_price:,.2f}")

with col2:
    change_24h = ((df.iloc[-1]["close"] - df.iloc[-24]["close"]) / df.iloc[-24]["close"] * 100) if len(df) >= 24 else 0
    st.metric("24h Change", f"{change_24h:.2f}%", delta=change_24h)

with col3:
    volume_24h = df.iloc[-24:]["volume"].sum() if len(df) >= 24 else df["volume"].sum()
    st.metric("24h Volume", f"{volume_24h:,.0f}")

with col4:
    atr = df.iloc[-1].get("atr_14", 0)
    st.metric("ATR(14)", f"${atr:.2f}")

# Chart
st.subheader("Price Chart")

chart_type = st.radio(
    "Chart Type",
    ["Candlestick", "Line"],
    horizontal=True,
)

# Create Plotly chart
fig = go.Figure()

if chart_type == "Candlestick":
    fig.add_trace(
        go.Candlestick(
            x=df["timestamp"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="OHLC",
        )
    )
else:
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["close"],
            mode="lines",
            name="Close",
            line=dict(color="#2962FF", width=2),
        )
    )

# Add indicators
show_indicators = st.sidebar.multiselect(
    "Indicators to Display",
    ["SMA 20", "SMA 50", "SMA 200", "EMA 9", "EMA 20", "VWAP", "BB Bands"],
    default=["SMA 20", "EMA 9", "VWAP"],
)

if "SMA 20" in show_indicators and "sma_20" in df.columns:
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["sma_20"],
            mode="lines",
            name="SMA 20",
            line=dict(color="#FF6D00", width=1),
        )
    )

if "EMA 9" in show_indicators and "ema_9" in df.columns:
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["ema_9"],
            mode="lines",
            name="EMA 9",
            line=dict(color="#00E676", width=1),
        )
    )

if "VWAP" in show_indicators and "vwap" in df.columns:
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["vwap"],
            mode="lines",
            name="VWAP",
            line=dict(color="#FFD600", width=1, dash="dash"),
        )
    )

if "BB Bands" in show_indicators and "bb_upper" in df.columns:
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["bb_upper"],
            mode="lines",
            name="BB Upper",
            line=dict(color="gray", width=1, dash="dot"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["bb_lower"],
            mode="lines",
            name="BB Lower",
            line=dict(color="gray", width=1, dash="dot"),
            fill="tonexty",
        )
    )

fig.update_layout(
    title=f"{symbol} {timeframe} Chart",
    xaxis_title="Time",
    yaxis_title="Price (USD)",
    height=600,
    template="plotly_dark",
    hovermode="x unified",
    xaxis_rangeslider_visible=False,
)

st.plotly_chart(fig, use_container_width=True)

# ICT Patterns
if st.sidebar.checkbox("Show ICT Patterns"):
    st.subheader("ICT Pattern Detection")

    with st.spinner("Detecting patterns..."):
        fvgs = ICTPatterns.detect_fair_value_gaps(df)
        order_blocks = ICTPatterns.detect_order_blocks(df)
        structure_points = ICTPatterns.detect_market_structure(df)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Fair Value Gaps", len(fvgs))
    with col2:
        st.metric("Order Blocks", len(order_blocks))
    with col3:
        st.metric("Structure Points", len(structure_points))

    # Show recent patterns
    if fvgs:
        st.write("**Recent Fair Value Gaps:**")
        recent_fvgs = sorted(fvgs, key=lambda x: x.timestamp, reverse=True)[:5]
        for fvg in recent_fvgs:
            st.write(
                f"- {fvg.direction.upper()} @ ${fvg.gap_low:.2f}-${fvg.gap_high:.2f} "
                f"(size: ${fvg.gap_size:.2f})"
            )

# Technical indicators table
st.subheader("Current Indicators")

indicator_data = {
    "Indicator": [],
    "Value": [],
}

latest = df.iloc[-1]

if "rsi_14" in df.columns:
    indicator_data["Indicator"].append("RSI(14)")
    indicator_data["Value"].append(f"{latest['rsi_14']:.2f}")

if "macd" in df.columns:
    indicator_data["Indicator"].append("MACD")
    indicator_data["Value"].append(f"{latest['macd']:.4f}")

if "adx_14" in df.columns:
    indicator_data["Indicator"].append("ADX(14)")
    indicator_data["Value"].append(f"{latest['adx_14']:.2f}")

st.table(pd.DataFrame(indicator_data))
