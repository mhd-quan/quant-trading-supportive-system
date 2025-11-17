"""Configuration management for the trading platform."""

import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from dotenv import load_dotenv
from loguru import logger


@dataclass
class ExchangeConfig:
    """Exchange API configuration."""

    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    password: Optional[str] = None

    def mask_key(self, key: Optional[str]) -> str:
        """Mask API key for logging."""
        if not key:
            return "None"
        if len(key) < 8:
            return "***"
        return f"{key[:4]}...{key[-4:]}"

    def validate(self) -> bool:
        """Validate API key format."""
        if self.api_key:
            # Basic validation - keys should be alphanumeric and at least 16 chars
            if len(self.api_key) < 16:
                logger.warning("API key appears too short")
                return False
            if not self.api_key.replace("-", "").replace("_", "").isalnum():
                logger.warning("API key contains invalid characters")
                return False
        if self.api_secret:
            if len(self.api_secret) < 16:
                logger.warning("API secret appears too short")
                return False
        return True

    def log_safe(self) -> str:
        """Return a safe string for logging."""
        return f"api_key={self.mask_key(self.api_key)}, api_secret={self.mask_key(self.api_secret)}"


@dataclass
class DatabaseConfig:
    """Database configuration."""

    duckdb_path: str = "./data/crypto.duckdb"
    parquet_root: str = "./data/lake"

    def __post_init__(self):
        """Ensure directories exist."""
        Path(self.duckdb_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.parquet_root).mkdir(parents=True, exist_ok=True)


@dataclass
class LoggingConfig:
    """Logging configuration."""

    level: str = "INFO"
    log_file: Optional[str] = "./logs/platform.log"

    def __post_init__(self):
        """Ensure log directory exists."""
        if self.log_file:
            Path(self.log_file).parent.mkdir(parents=True, exist_ok=True)


@dataclass
class PerformanceConfig:
    """Performance and optimization settings."""

    chunk_size: int = 10000
    max_workers: int = 4
    cache_ttl_seconds: int = 300
    request_timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""

    requests_per_second: int = 10
    requests_per_minute: int = 1200
    weight_per_minute: Optional[int] = None


@dataclass
class Config:
    """Main configuration class."""

    binance: ExchangeConfig
    coinbase: ExchangeConfig
    kraken: ExchangeConfig
    okx: ExchangeConfig
    bybit: ExchangeConfig
    database: DatabaseConfig
    logging: LoggingConfig
    performance: PerformanceConfig

    # Additional settings
    prefect_api_url: str = "http://localhost:4200/api"
    streamlit_port: int = 8501
    initial_capital: float = 10000
    default_commission: float = 0.001
    default_slippage: float = 0.0005
    max_risk_per_trade: float = 0.02
    max_portfolio_risk: float = 0.06

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        # Load .env file
        load_dotenv()

        # Exchange configurations
        binance = ExchangeConfig(
            api_key=os.getenv("BINANCE_API_KEY"),
            api_secret=os.getenv("BINANCE_SECRET"),
        )

        coinbase = ExchangeConfig(
            api_key=os.getenv("COINBASE_API_KEY"),
            api_secret=os.getenv("COINBASE_SECRET"),
            password=os.getenv("COINBASE_PASSWORD"),
        )

        kraken = ExchangeConfig(
            api_key=os.getenv("KRAKEN_API_KEY"),
            api_secret=os.getenv("KRAKEN_SECRET"),
        )

        okx = ExchangeConfig(
            api_key=os.getenv("OKX_API_KEY"),
            api_secret=os.getenv("OKX_SECRET"),
            password=os.getenv("OKX_PASSPHRASE"),
        )

        bybit = ExchangeConfig(
            api_key=os.getenv("BYBIT_API_KEY"),
            api_secret=os.getenv("BYBIT_SECRET"),
        )

        # Database configuration
        database = DatabaseConfig(
            duckdb_path=os.getenv("DUCKDB_PATH", "./data/crypto.duckdb"),
            parquet_root=os.getenv("PARQUET_ROOT", "./data/lake"),
        )

        # Logging configuration
        logging_config = LoggingConfig(
            level=os.getenv("LOG_LEVEL", "INFO"),
            log_file=os.getenv("LOG_FILE", "./logs/platform.log"),
        )

        # Performance configuration
        performance = PerformanceConfig(
            chunk_size=int(os.getenv("CHUNK_SIZE", "10000")),
            max_workers=int(os.getenv("MAX_WORKERS", "4")),
            cache_ttl_seconds=int(os.getenv("CACHE_TTL_SECONDS", "300")),
            request_timeout=int(os.getenv("REQUEST_TIMEOUT", "30")),
            max_retries=int(os.getenv("MAX_RETRIES", "3")),
            retry_delay=float(os.getenv("RETRY_DELAY", "1.0")),
        )

        config = cls(
            binance=binance,
            coinbase=coinbase,
            kraken=kraken,
            okx=okx,
            bybit=bybit,
            database=database,
            logging=logging_config,
            performance=performance,
            prefect_api_url=os.getenv("PREFECT_API_URL", "http://localhost:4200/api"),
            streamlit_port=int(os.getenv("STREAMLIT_PORT", "8501")),
            initial_capital=float(os.getenv("INITIAL_CAPITAL", "10000")),
            default_commission=float(os.getenv("DEFAULT_COMMISSION", "0.001")),
            default_slippage=float(os.getenv("DEFAULT_SLIPPAGE", "0.0005")),
            max_risk_per_trade=float(os.getenv("MAX_RISK_PER_TRADE", "0.02")),
            max_portfolio_risk=float(os.getenv("MAX_PORTFOLIO_RISK", "0.06")),
        )

        # Validate exchange configurations
        for exchange_name in ["binance", "coinbase", "kraken", "okx", "bybit"]:
            exchange_config = getattr(config, exchange_name)
            if exchange_config.api_key:
                if not exchange_config.validate():
                    logger.warning(f"{exchange_name} configuration validation failed")

        logger.info("Configuration loaded successfully")
        return config

    def log_summary(self) -> None:
        """Log a summary of configuration (safe for logs)."""
        logger.info(f"Binance: {self.binance.log_safe()}")
        logger.info(f"Coinbase: {self.coinbase.log_safe()}")
        logger.info(f"Kraken: {self.kraken.log_safe()}")
        logger.info(f"OKX: {self.okx.log_safe()}")
        logger.info(f"Bybit: {self.bybit.log_safe()}")
        logger.info(f"Database: {self.database.duckdb_path}")
        logger.info(f"Parquet: {self.database.parquet_root}")
        logger.info(f"Log level: {self.logging.level}")


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get or create global configuration instance."""
    global _config
    if _config is None:
        _config = Config.from_env()
    return _config


def reload_config() -> Config:
    """Reload configuration from environment."""
    global _config
    _config = Config.from_env()
    return _config
