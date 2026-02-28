"""SQLite WAL database layer with aiosqlite."""

import logging
import aiosqlite
from pathlib import Path

logger = logging.getLogger("mtcs.database")

SCHEMA_SQL = """
-- Accounts table
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    login INTEGER NOT NULL UNIQUE,
    encrypted_password TEXT NOT NULL,
    server TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('master', 'slave')),
    enabled INTEGER NOT NULL DEFAULT 1,
    display_name TEXT DEFAULT '',
    settings_json TEXT DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Trade mappings (Master UUID -> Slave tickets)
CREATE TABLE IF NOT EXISTS trade_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    master_uuid TEXT NOT NULL,
    master_ticket INTEGER NOT NULL,
    master_login INTEGER NOT NULL,
    slave_ticket INTEGER,
    slave_login INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    master_lot REAL NOT NULL,
    slave_lot REAL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK(status IN ('pending', 'filled', 'partial', 'closed', 'failed', 'orphaned')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_mappings_uuid ON trade_mappings(master_uuid);
CREATE INDEX IF NOT EXISTS idx_mappings_master_ticket ON trade_mappings(master_ticket);
CREATE INDEX IF NOT EXISTS idx_mappings_slave ON trade_mappings(slave_login, status);

-- Trade history (full lifecycle)
CREATE TABLE IF NOT EXISTS trade_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    master_uuid TEXT,
    account_login INTEGER NOT NULL,
    ticket INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    trade_type TEXT NOT NULL,
    direction TEXT NOT NULL,
    volume REAL NOT NULL,
    open_price REAL,
    close_price REAL,
    sl REAL,
    tp REAL,
    profit REAL,
    commission REAL DEFAULT 0,
    swap REAL DEFAULT 0,
    event TEXT NOT NULL,
    timestamp TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_history_account ON trade_history(account_login);
CREATE INDEX IF NOT EXISTS idx_history_symbol ON trade_history(symbol);
CREATE INDEX IF NOT EXISTS idx_history_timestamp ON trade_history(timestamp);

-- System configuration
CREATE TABLE IF NOT EXISTS system_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Audit log
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    details TEXT NOT NULL DEFAULT '{}',
    timestamp TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);

-- Watchlist
CREATE TABLE IF NOT EXISTS watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL UNIQUE,
    sort_order INTEGER NOT NULL DEFAULT 0
);
"""


class Database:
    """Async SQLite database manager with WAL mode."""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self._db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Open connection and enable WAL mode."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self.db_path))
        self._db.row_factory = aiosqlite.Row

        # Enable WAL mode for crash safety
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA synchronous=NORMAL")
        await self._db.execute("PRAGMA foreign_keys=ON")
        await self._db.execute("PRAGMA busy_timeout=5000")

        logger.info(f"Database connected: {self.db_path} (WAL mode)")

    async def init_schema(self) -> None:
        """Create all tables if not exist."""
        await self._db.executescript(SCHEMA_SQL)
        await self._db.commit()
        logger.info("Database schema initialized")

    async def close(self) -> None:
        """Close the database connection."""
        if self._db:
            await self._db.close()
            self._db = None
            logger.info("Database connection closed")

    @property
    def conn(self) -> aiosqlite.Connection:
        """Get the active connection."""
        if not self._db:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._db

    async def execute(self, sql: str, params: tuple = ()) -> aiosqlite.Cursor:
        """Execute a single SQL statement."""
        cursor = await self._db.execute(sql, params)
        await self._db.commit()
        return cursor

    async def fetch_one(self, sql: str, params: tuple = ()) -> dict | None:
        """Fetch a single row as dict."""
        cursor = await self._db.execute(sql, params)
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def fetch_all(self, sql: str, params: tuple = ()) -> list[dict]:
        """Fetch all rows as list of dicts."""
        cursor = await self._db.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def verify_wal(self) -> bool:
        """Verify WAL mode is active."""
        row = await self.fetch_one("PRAGMA journal_mode")
        mode = row.get("journal_mode", "unknown") if row else "unknown"
        is_wal = mode.lower() == "wal"
        logger.info(f"Journal mode: {mode} (WAL verified: {is_wal})")
        return is_wal

    async def audit_log(self, event_type: str, details: str = "{}") -> None:
        """Insert an audit log entry."""
        await self.execute(
            "INSERT INTO audit_log (event_type, details) VALUES (?, ?)",
            (event_type, details),
        )
