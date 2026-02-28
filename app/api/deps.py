"""Shared API dependencies and application state.

Refactored for multi-process architecture:
- WorkerManager replaces single MT5Bridge
- Each account gets its own subprocess with permanent login
- Trade events flow: master worker → event_queue → copier → slave workers (parallel)
"""

import asyncio
import json
import logging
from typing import Optional

from app.config import settings
from app.core.worker_manager import WorkerManager
from app.core.trade_copier import TradeCopier
from app.core.risk_manager import RiskManager
from app.persistence.database import Database
from app.persistence.credentials import CredentialManager
from app.persistence.state_recovery import StateRecovery
from app.utils.networking import get_network_info

logger = logging.getLogger("mtcs.state")


class AppState:
    """Singleton application state — shared across all routes."""

    def __init__(self):
        self.db: Optional[Database] = None
        self.workers: Optional[WorkerManager] = None
        self.copier: Optional[TradeCopier] = None
        self.risk: Optional[RiskManager] = None
        self.credentials: Optional[CredentialManager] = None
        self.recovery: Optional[StateRecovery] = None
        self.network_info: dict = {}
        self.mt5_status: str = "disconnected"
        self.system_status: str = "starting"
        self.copy_active: bool = False

        # SSE event queues for broadcasting
        self._sse_subscribers: list[asyncio.Queue] = []

    # ---- Compatibility shims for route code that references bridge ----
    @property
    def bridge(self):
        """Shim so routes can still call app_state.bridge.connected etc."""
        return self.workers

    @property
    def monitor(self):
        """Shim — monitor is now inside the master worker subprocess."""
        return self._MonitorShim(self)

    class _MonitorShim:
        """Thin wrapper so routes can call monitor.start/stop/pause/resume."""
        def __init__(self, state):
            self._state = state
        @property
        def is_running(self):
            return self._state.copy_active
        @property
        def is_paused(self):
            return not self._state.copy_active
        async def start(self):
            await self._state.workers.start_master_monitor()
            self._state.copy_active = True
        async def stop(self):
            await self._state.workers.stop_master_monitor()
            self._state.copy_active = False
        def pause(self):
            asyncio.create_task(self._state.workers.pause_master_monitor())
            self._state.copy_active = False
        def resume(self):
            asyncio.create_task(self._state.workers.resume_master_monitor())
            self._state.copy_active = True

    async def initialize(self) -> None:
        """Boot the entire system."""
        settings.ensure_dirs()

        # Database
        self.db = Database(settings.DB_PATH)
        await self.db.connect()
        await self.db.init_schema()

        # Credentials
        self.credentials = CredentialManager(settings.DATA_DIR)
        self.credentials.initialize()

        # Worker Manager (replaces single MT5Bridge)
        self.workers = WorkerManager(terminal_path=settings.MT5_TERMINAL_PATH)

        # Trading components — wired to WorkerManager
        self.copier = TradeCopier(self.workers, self.db, self.credentials)
        self.risk = RiskManager(self.workers, self.db)
        self.recovery = StateRecovery(self.db)

        # Wire up: master worker trade events → copier
        self.workers.on_trade_event(self.copier.handle_trade_event)

        # Network info
        self.network_info = get_network_info(settings.PORT)

        # Seed default watchlist
        await self._seed_watchlist()

        # Spawn workers for saved accounts
        await self._spawn_saved_account_workers()

        self.system_status = "ready"
        logger.info("Application state initialized (multi-process)")
        logger.info(f"Access from mobile: {self.network_info.get('access_url', 'unknown')}")

        if not self.network_info.get("firewall", {}).get("allowed", False):
            fw_msg = self.network_info.get("firewall", {}).get("message", "")
            if fw_msg:
                logger.warning(f"Firewall: {fw_msg}")

    async def _seed_watchlist(self) -> None:
        existing = await self.db.fetch_all("SELECT * FROM watchlist")
        if not existing:
            for i, symbol in enumerate(settings.DEFAULT_SYMBOLS):
                await self.db.execute(
                    "INSERT OR IGNORE INTO watchlist (symbol, sort_order) VALUES (?, ?)",
                    (symbol, i),
                )

    async def _spawn_saved_account_workers(self) -> None:
        """Spawn a worker for each saved account."""
        try:
            # Sync credentials.json → DB
            file_accounts = self.credentials.load_credentials()
            for acc in file_accounts:
                existing = await self.db.fetch_one(
                    "SELECT * FROM accounts WHERE login = ?", (acc["login"],)
                )
                if not existing:
                    await self.db.execute(
                        "INSERT INTO accounts (login, encrypted_password, server, role) "
                        "VALUES (?, ?, ?, ?)",
                        (acc["login"], acc["encrypted_password"],
                         acc["server"], acc.get("role", "slave")),
                    )

            # Spawn workers for all enabled accounts
            accounts = await self.recovery.get_all_accounts()
            for acc in accounts:
                if not acc.get("enabled", True):
                    continue
                try:
                    password = self.credentials.decrypt(acc["encrypted_password"])
                    result = await self.workers.spawn_worker(
                        login=acc["login"],
                        password=password,
                        server=acc["server"],
                        role=acc["role"],
                    )
                    if result.get("success"):
                        self.mt5_status = "connected"
                        logger.info(
                            f"Worker spawned: {acc['login']}@{acc['server']} "
                            f"(role={acc['role']}, pid={result.get('pid')})"
                        )
                        await self.db.audit_log(
                            "worker_spawned",
                            json.dumps({
                                "login": acc["login"],
                                "role": acc["role"],
                                "pid": result.get("pid"),
                            }),
                        )
                    else:
                        logger.warning(
                            f"Worker spawn failed for {acc['login']}: {result.get('error')}"
                        )
                        await self.db.execute(
                            "UPDATE accounts SET enabled = 0 WHERE login = ?",
                            (acc["login"],),
                        )
                except Exception as e:
                    logger.error(f"Failed to spawn worker for {acc['login']}: {e}")
        except Exception as e:
            logger.error(f"Error spawning saved workers: {e}")

    async def shutdown(self) -> None:
        """Clean shutdown."""
        self.system_status = "shutting_down"
        if self.workers:
            await self.workers.shutdown()
        if self.db:
            await self.db.close()
        logger.info("Application state shutdown complete")

    # SSE broadcasting
    def sse_subscribe(self) -> asyncio.Queue:
        queue = asyncio.Queue(maxsize=100)
        self._sse_subscribers.append(queue)
        return queue

    def sse_unsubscribe(self, queue: asyncio.Queue) -> None:
        if queue in self._sse_subscribers:
            self._sse_subscribers.remove(queue)

    async def broadcast_sse(self, event: str, data: dict) -> None:
        message = {"event": event, "data": data}
        dead_queues = []
        for queue in self._sse_subscribers:
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                dead_queues.append(queue)
        for q in dead_queues:
            self._sse_subscribers.remove(q)


# Global singleton
app_state = AppState()
