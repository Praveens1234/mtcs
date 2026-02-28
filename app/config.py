"""Application configuration via pydantic-settings."""

import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central configuration for the MTCS application."""

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 9600
    DEBUG: bool = False

    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    DB_PATH: Path = DATA_DIR / "mtcs.db"
    CREDENTIALS_FILE: Path = DATA_DIR / "credentials.json"
    ENCRYPTION_KEY_FILE: Path = DATA_DIR / ".key"
    LOG_DIR: Path = DATA_DIR / "logs"

    # MT5
    MT5_TERMINAL_PATH: str = r"C:\Program Files\MetaTrader 5\terminal64.exe"

    # Trading
    MONITOR_INTERVAL_MS: int = 500
    MAX_SLIPPAGE_POINTS: int = 50
    MAX_SPREAD_POINTS: int = 100
    DEFAULT_LOT_SIZE: float = 0.01

    # Watchlist
    MAX_WATCHLIST_SYMBOLS: int = 10
    DEFAULT_SYMBOLS: list[str] = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "BTCUSD"]

    # SSE
    SSE_RETRY_MS: int = 3000
    SSE_KEEPALIVE_S: int = 15

    # Security
    PIN_ENABLED: bool = False
    PIN_HASH: str = ""

    # UI
    THEME: str = "dark"  # dark | light | auto
    ONE_CLICK_TRADING: bool = False

    model_config = {"env_prefix": "MTCS_", "env_file": ".env", "extra": "ignore"}

    def ensure_dirs(self) -> None:
        """Create all required data directories."""
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.LOG_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
