# Contributing Guidelines

## Development Setup

### Prerequisites
- Python 3.11+
- Git with signed commits
- GitHub account with 2FA

### Environment Setup
```bash
# Fork and clone
git clone https://github.com/YOUR_USERNAME/crypto-research-platform.git
cd crypto-research-platform

# Install development dependencies
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Configure git
git config user.name "Your Name"
git config user.email "your.email@example.com"
git config commit.gpgsign true
```

## Code Standards

### Python Style
- Formatter: Black (line length 100)
- Linter: Ruff (see pyproject.toml for rules)
- Type hints: Required for all public functions
- Docstrings: Google style

### Example Function
```python
from typing import Optional, List
import pandas as pd

def calculate_atr(
    data: pd.DataFrame,
    period: int = 14,
    method: str = "rma"
) -> pd.Series:
    """Calculate Average True Range.
    
    Args:
        data: OHLC dataframe with columns [high, low, close]
        period: ATR period (default: 14)
        method: Smoothing method - "rma", "ema", or "sma"
        
    Returns:
        Series with ATR values
        
    Raises:
        ValueError: If required columns missing
    """
    if not all(col in data.columns for col in ["high", "low", "close"]):
        raise ValueError("Required columns: high, low, close")
        
    # Implementation
    return atr_series
```

### Commit Messages
Format: `type(scope): description`

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `refactor`: Code restructuring
- `test`: Test additions/fixes
- `perf`: Performance improvements
- `chore`: Maintenance tasks

Examples:
```
feat(data): add Kraken WebSocket connector
fix(backtest): handle zero division in Sharpe ratio
docs(readme): update installation instructions
perf(analytics): optimize matrix profile computation
```

## Testing Requirements

### Test Structure
```
tests/
├── unit/           # No external dependencies
├── integration/    # Exchange/database tests
└── fixtures/       # Test data
```

### Writing Tests
```python
import pytest
from src.analytics import TimeframeSelector

class TestTimeframeSelector:
    @pytest.fixture
    def sample_data(self):
        """Generate sample OHLCV data."""
        return pd.DataFrame({
            "open": [100, 101, 99],
            "high": [102, 103, 101],
            "low": [99, 100, 98],
            "close": [101, 99, 100],
            "volume": [1000, 1200, 900]
        })
    
    def test_optimal_selection(self, sample_data):
        """Test timeframe selection with default parameters."""
        selector = TimeframeSelector()
        result = selector.select_optimal(sample_data)
        
        assert result.timeframe in ["1m", "5m", "15m", "1h", "4h", "1d"]
        assert 0.5 <= result.stop_atr_multiple <= 3.0
        assert result.score > 0
```

### Coverage Requirements
- Minimum 80% coverage for new code
- 100% coverage for critical paths (risk management, order execution)

## Pull Request Process

### Before Opening PR
1. Run tests: `make test-all`
2. Type check: `mypy src/`
3. Format: `black src/ tests/`
4. Lint: `ruff check src/ tests/`
5. Update documentation if needed

### PR Template
```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No credentials in code
```

### Review Process
1. Automated checks must pass
2. One maintainer approval required
3. No merge until 24-hour review period

## Adding Exchange Connectors

### Connector Interface
```python
from abc import ABC, abstractmethod
import pandas as pd

class ExchangeConnector(ABC):
    @abstractmethod
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        since: Optional[int] = None,
        limit: int = 1000
    ) -> pd.DataFrame:
        """Fetch historical OHLCV data."""
        pass
    
    @abstractmethod
    async def stream_klines(
        self,
        symbol: str,
        timeframe: str,
        callback: Callable
    ) -> None:
        """Stream live klines via WebSocket."""
        pass
```

### Implementation Checklist
- [ ] Implement ExchangeConnector interface
- [ ] Add rate limiting
- [ ] Handle authentication
- [ ] Add reconnection logic
- [ ] Write unit tests (mock responses)
- [ ] Write integration tests (real API)
- [ ] Update configs/exchanges.yaml
- [ ] Document API quirks in connector docstring

## Adding Strategies

### Strategy Interface
```python
from src.strategies.base import BaseStrategy

class MyStrategy(BaseStrategy):
    def __init__(self, params: dict):
        super().__init__(params)
        
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate entry/exit signals.
        
        Returns DataFrame with columns:
        - entry: bool
        - exit: bool
        - stop_loss: float
        - take_profit: float
        - position_size: float
        """
        pass
```

### Strategy Checklist
- [ ] Inherit from BaseStrategy
- [ ] Implement generate_signals
- [ ] Add parameter validation
- [ ] Include position sizing
- [ ] Write backtests
- [ ] Document parameters in docstring
- [ ] Add to configs/strategies.yaml

## Security Guidelines

### Never Commit
- API keys/secrets
- Personal data
- Production database URLs
- Wallet private keys

### Use Instead
- Environment variables
- GitHub Secrets for CI
- `.env.example` with dummy values

### Reporting Security Issues
Email security@[domain] with:
- Description of vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

## Documentation

### Required Documentation
- Docstrings for all public functions/classes
- README update for new features
- API documentation for new modules
- Architecture decisions in DECISIONS.md

### Documentation Style
```python
def complex_function(param1: str, param2: int) -> dict:
    """Brief description.
    
    Longer description explaining the purpose,
    algorithm, or important details.
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Dictionary containing:
        - key1: Description
        - key2: Description
        
    Raises:
        ValueError: When param1 is empty
        TypeError: When param2 is not integer
        
    Example:
        >>> result = complex_function("test", 42)
        >>> print(result["key1"])
        "expected_value"
    """
```

## Release Process

### Version Numbering
Semantic versioning: MAJOR.MINOR.PATCH

- MAJOR: Breaking changes
- MINOR: New features, backward compatible
- PATCH: Bug fixes

### Release Checklist
1. Update version in pyproject.toml
2. Update CHANGELOG.md
3. Run full test suite
4. Create git tag: `git tag v1.2.3`
5. Push tag: `git push origin v1.2.3`

## Getting Help

- Documentation: docs/
- GitHub Issues for bugs/features
- Discussions for questions

## Code of Conduct

### Our Standards
- Professional and respectful communication
- Constructive criticism
- Focus on what's best for the project
- No harassment or discrimination

### Enforcement
Violations may result in:
1. Warning
2. Temporary ban
3. Permanent ban

Report issues to conduct@[domain]
