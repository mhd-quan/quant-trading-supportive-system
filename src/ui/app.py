"""Main Streamlit application."""

import streamlit as st
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

st.set_page_config(
    page_title="Crypto Research Platform",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🔐 Private Cryptocurrency Research Platform")
st.markdown("---")

# Disclaimer
st.warning(
    """
    **⚠️ DISCLAIMER: Educational purposes only. Not financial advice.**

    This platform is for research and educational purposes. All trading involves risk.
    Past performance does not guarantee future results. Always do your own research.
    """
)

st.markdown(
    """
    ## Welcome to Your Private Crypto Research Platform

    This platform provides:
    - **Historical Data Analysis**: 5+ years of OHLCV data
    - **Real-time Streaming**: Live WebSocket data from exchanges
    - **Technical Analysis**: 50+ indicators and ICT patterns
    - **Strategy Backtesting**: Test your strategies with realistic simulation
    - **Pattern Recognition**: Find similar historical patterns

    ### Quick Start

    1. **Configure API Keys**: Add your exchange API keys in `.env` file
    2. **Backfill Data**: Run `make backfill-btc` to download historical data
    3. **Analyze**: Use the sidebar to navigate to different analysis tools
    4. **Backtest**: Test your strategies before going live

    ### Navigation

    Use the sidebar to access:
    - 📊 **Market Analysis**: View charts and indicators
    - 🎯 **Strategy Testing**: Backtest trading strategies
    - 🔍 **Pattern Search**: Find similar historical patterns
    - ⚙️ **Data Management**: Download and manage data

    ### System Status
    """
)

# Status indicators
col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Database", "🟢 Online", "DuckDB")
with col2:
    st.metric("Data Lake", "🟢 Ready", "Parquet")
with col3:
    st.metric("Exchanges", "🟡 Configure", "API Keys")

st.markdown("---")

# Quick links
st.markdown("### Quick Links")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("**Documentation**")
    st.markdown("- [README](../README.md)")
    st.markdown("- [DECISIONS](../DECISIONS.md)")
    st.markdown("- [CONTRIBUTING](../CONTRIBUTING.md)")

with col2:
    st.markdown("**Configuration**")
    st.markdown("- [Exchanges](../configs/exchanges.yaml)")
    st.markdown("- [Strategies](../configs/strategies.yaml)")
    st.markdown("- [Indicators](../configs/indicators.yaml)")

with col3:
    st.markdown("**Tools**")
    st.code("make backfill-btc", language="bash")
    st.code("make ui", language="bash")
    st.code("make test", language="bash")

st.markdown("---")
st.info(
    """
    💡 **Tip**: Start by downloading some historical data using the backfill script.
    Then explore the Market Analysis page to visualize your data.
    """
)
