"""Worker Manager — orchestrates MT5 worker subprocesses.

Responsibilities:
- Spawn/kill dedicated worker processes per account
- Route API commands to the correct worker via IPC queues
- Receive trade events from the master worker
- Broadcast events to all slave workers in PARALLEL
- Auto-restart crashed workers
"""

import asyncio
import multiprocessing as mp
import logging
import time
import uuid
from typing import Optional, Callable
from dataclasses import asdict

from app.config import settings
from app.core.mt5_worker import (
    _worker_process, WorkerMessage, WorkerResponse, WorkerCommand, TradeEvent,
)

logger = logging.getLogger("mtcs.worker_manager")


class WorkerHandle:
    """Handle to a running worker subprocess."""

    def __init__(
        self,
        login: int,
        server: str,
        role: str,
        process: mp.Process,
        input_queue: mp.Queue,
        output_queue: mp.Queue,
        event_queue: Optional[mp.Queue] = None,
    ):
        self.login = login
        self.server = server
        self.role = role
        self.process = process
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.event_queue = event_queue
        self.started_at = time.time()
        self.restart_count = 0
        self.last_response_time = time.time()
        self.init_data: dict = {}

    @property
    def alive(self) -> bool:
        return self.process.is_alive()

    @property
    def pid(self) -> int:
        return self.process.pid or 0


class WorkerManager:
    """Manages all MT5 worker subprocesses."""

    def __init__(self, terminal_path: str = ""):
        self._terminal_path = terminal_path
        self._workers: dict[int, WorkerHandle] = {}  # login -> handle
        self._master_login: Optional[int] = None
        self._event_queue: mp.Queue = mp.Queue(maxsize=1000)
        self._shutdown_event: mp.Event = mp.Event()
        self._event_listeners: list[Callable] = []
        self._event_task: Optional[asyncio.Task] = None
        self._monitor_interval = settings.MONITOR_INTERVAL_MS / 1000.0

    @property
    def master_login(self) -> Optional[int]:
        return self._master_login

    @property
    def available(self) -> bool:
        """MT5 package is available (at least one worker could start)."""
        try:
            import MetaTrader5
            return True
        except ImportError:
            return False

    @property
    def connected(self) -> bool:
        """Master worker is alive and connected."""
        if self._master_login and self._master_login in self._workers:
            return self._workers[self._master_login].alive
        return False

    def get_worker(self, login: int) -> Optional[WorkerHandle]:
        return self._workers.get(login)

    def get_all_workers(self) -> list[WorkerHandle]:
        return list(self._workers.values())

    def get_slave_workers(self) -> list[WorkerHandle]:
        return [w for w in self._workers.values() if w.role == "slave"]

    def on_trade_event(self, callback: Callable) -> None:
        """Register a listener for master trade events."""
        self._event_listeners.append(callback)

    async def spawn_worker(
        self, login: int, password: str, server: str, role: str
    ) -> dict:
        """Spawn a new worker subprocess for an account."""
        if login in self._workers:
            old = self._workers[login]
            if old.alive:
                logger.info(f"Worker {login} already running (pid={old.pid}), killing first")
                await self.kill_worker(login)

        input_q = mp.Queue(maxsize=100)
        output_q = mp.Queue(maxsize=100)
        event_q = self._event_queue if role == "master" else None

        process = mp.Process(
            target=_worker_process,
            args=(
                login, password, server, self._terminal_path, role,
                input_q, output_q, event_q,
                self._monitor_interval, self._shutdown_event,
            ),
            name=f"MT5-{role}-{login}",
            daemon=True,
        )
        process.start()
        logger.info(f"Spawned {role} worker: {login}@{server} (pid={process.pid})")

        handle = WorkerHandle(
            login=login, server=server, role=role,
            process=process, input_queue=input_q,
            output_queue=output_q, event_queue=event_q,
        )

        # Wait for init response (with timeout)
        init_resp = await self._wait_response(handle, timeout=15.0)
        if init_resp and init_resp.success:
            handle.init_data = init_resp.data
            self._workers[login] = handle
            if role == "master":
                self._master_login = login
            logger.info(f"Worker {login} initialized: {init_resp.data.get('balance', '?')}")
            return {
                "success": True,
                "pid": process.pid,
                **init_resp.data,
            }
        else:
            error = init_resp.error if init_resp else "Timeout waiting for worker init"
            logger.error(f"Worker {login} init failed: {error}")
            if process.is_alive():
                process.terminate()
            return {"success": False, "error": error}

    async def kill_worker(self, login: int) -> None:
        """Terminate a worker subprocess."""
        handle = self._workers.pop(login, None)
        if not handle:
            return

        try:
            handle.input_queue.put(WorkerMessage(command=WorkerCommand.SHUTDOWN))
            await asyncio.sleep(0.5)
        except Exception:
            pass

        if handle.process.is_alive():
            handle.process.terminate()
            handle.process.join(timeout=3)
            if handle.process.is_alive():
                handle.process.kill()

        if login == self._master_login:
            self._master_login = None

        logger.info(f"Worker {login} terminated")

    async def send_command(
        self, login: int, command: str, data: dict = None, timeout: float = 10.0
    ) -> WorkerResponse:
        """Send a command to a specific worker and wait for response."""
        handle = self._workers.get(login)
        if not handle:
            return WorkerResponse(success=False, error=f"No worker for login {login}")
        if not handle.alive:
            return WorkerResponse(success=False, error=f"Worker {login} is dead")

        request_id = str(uuid.uuid4())[:8]
        msg = WorkerMessage(
            command=command, request_id=request_id,
            data=data or {},
        )

        try:
            handle.input_queue.put(msg)
        except Exception as e:
            return WorkerResponse(success=False, error=f"Queue error: {e}")

        resp = await self._wait_response(handle, timeout=timeout, request_id=request_id)
        if resp:
            handle.last_response_time = time.time()
            return resp
        return WorkerResponse(success=False, error="Timeout")

    async def broadcast_to_slaves(
        self, command: str, data: dict = None, timeout: float = 10.0
    ) -> list[WorkerResponse]:
        """Send a command to ALL slave workers in parallel."""
        slaves = self.get_slave_workers()
        if not slaves:
            return []

        tasks = [
            self.send_command(w.login, command, data, timeout)
            for w in slaves if w.alive
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        responses = []
        for r in results:
            if isinstance(r, Exception):
                responses.append(WorkerResponse(success=False, error=str(r)))
            else:
                responses.append(r)
        return responses

    async def send_to_master(
        self, command: str, data: dict = None, timeout: float = 10.0
    ) -> WorkerResponse:
        """Send a command to the master worker."""
        if not self._master_login:
            return WorkerResponse(success=False, error="No master worker")
        return await self.send_command(self._master_login, command, data, timeout)

    # ---------- Convenience methods (used by API routes) ----------

    async def get_positions(self, login: int = None) -> list[dict]:
        """Get positions from a worker (defaults to master)."""
        target = login or self._master_login
        if not target:
            return []
        resp = await self.send_command(target, WorkerCommand.GET_POSITIONS)
        return resp.data.get("positions", []) if resp.success else []

    async def get_orders(self, login: int = None) -> list[dict]:
        target = login or self._master_login
        if not target:
            return []
        resp = await self.send_command(target, WorkerCommand.GET_ORDERS)
        return resp.data.get("orders", []) if resp.success else []

    async def get_history_deals(self, login: int, days: int) -> list[dict]:
        """Get history deals from a specific worker."""
        resp = await self.send_command(login, WorkerCommand.GET_HISTORY_DEALS, {
            "days": days,
        })
        return resp.data.get("deals", []) if resp.success else []

    async def get_account_info(self, login: int = None) -> Optional[dict]:
        target = login or self._master_login
        if not target:
            return None
        resp = await self.send_command(target, WorkerCommand.GET_ACCOUNT_INFO)
        return resp.data if resp.success else None

    async def get_symbol_tick(self, symbol: str, login: int = None) -> Optional[dict]:
        target = login or self._master_login
        if not target:
            return None
        resp = await self.send_command(target, WorkerCommand.GET_SYMBOL_TICK, {"symbol": symbol})
        return resp.data if resp.success else None

    async def get_symbol_info(self, symbol: str, login: int = None) -> Optional[dict]:
        target = login or self._master_login
        if not target:
            return None
        resp = await self.send_command(target, WorkerCommand.GET_SYMBOL_INFO, {"symbol": symbol})
        return resp.data if resp.success else None

    async def send_order(self, login: int, request: dict) -> dict:
        resp = await self.send_command(login, WorkerCommand.SEND_ORDER, {"request": request})
        if resp.success:
            return {"success": True, **resp.data}
        return {"success": False, "error": resp.error, **resp.data}

    async def close_position(self, login: int, ticket: int, volume: float = None) -> dict:
        data = {"ticket": ticket}
        if volume:
            data["volume"] = volume
        resp = await self.send_command(login, WorkerCommand.CLOSE_POSITION, data)
        if resp.success:
            return {"success": True, **resp.data}
        return {"success": False, "error": resp.error}

    async def start_master_monitor(self) -> bool:
        if not self._master_login:
            return False
        resp = await self.send_to_master(WorkerCommand.START_MONITOR)
        if resp.success:
            # Start event listener loop
            if not self._event_task or self._event_task.done():
                self._event_task = asyncio.create_task(self._event_listener_loop())
        return resp.success

    async def stop_master_monitor(self) -> bool:
        if not self._master_login:
            return False
        resp = await self.send_to_master(WorkerCommand.STOP_MONITOR)
        return resp.success

    async def pause_master_monitor(self) -> bool:
        if not self._master_login:
            return False
        resp = await self.send_to_master(WorkerCommand.PAUSE_MONITOR)
        return resp.success

    async def resume_master_monitor(self) -> bool:
        if not self._master_login:
            return False
        resp = await self.send_to_master(WorkerCommand.RESUME_MONITOR)
        return resp.success

    # ---------- Event listener ----------

    async def _event_listener_loop(self):
        """Poll the event queue from the master worker and dispatch."""
        logger.info("Event listener started")
        while not self._shutdown_event.is_set():
            try:
                # Poll queue in thread to avoid blocking
                event = await asyncio.to_thread(self._event_queue.get, True, 1.0)
                if isinstance(event, TradeEvent):
                    logger.info(
                        f"Trade event from master: {event.event_type} "
                        f"{event.data.get('symbol', '?')}"
                    )
                    # Notify all listeners
                    for listener in self._event_listeners:
                        try:
                            if asyncio.iscoroutinefunction(listener):
                                await listener(event)
                            else:
                                listener(event)
                        except Exception as e:
                            logger.error(f"Event listener error: {e}")
            except Exception:
                # Queue.get timeout — normal
                pass
        logger.info("Event listener stopped")

    # ---------- Internal ----------

    async def _wait_response(
        self, handle: WorkerHandle, timeout: float = 10.0,
        request_id: str = None,
    ) -> Optional[WorkerResponse]:
        """Wait for a response from a worker with timeout."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                resp = await asyncio.to_thread(
                    handle.output_queue.get, True, min(0.5, deadline - time.time())
                )
                if isinstance(resp, WorkerResponse):
                    if request_id is None or resp.request_id == request_id or resp.request_id == "init":
                        return resp
            except Exception:
                if not handle.process.is_alive():
                    return WorkerResponse(success=False, error="Worker process died")
        return None

    async def shutdown(self):
        """Shutdown all workers."""
        self._shutdown_event.set()

        if self._event_task and not self._event_task.done():
            self._event_task.cancel()
            try:
                await self._event_task
            except asyncio.CancelledError:
                pass

        for login in list(self._workers.keys()):
            await self.kill_worker(login)

        logger.info("All workers shut down")

    async def health_check(self) -> dict:
        """Get health status of all workers."""
        status = {}
        for login, handle in self._workers.items():
            info = {
                "login": login,
                "server": handle.server,
                "role": handle.role,
                "alive": handle.alive,
                "pid": handle.pid,
                "uptime_s": round(time.time() - handle.started_at, 1),
                "restarts": handle.restart_count,
            }
            if handle.alive:
                resp = await self.send_command(login, WorkerCommand.PING, timeout=3.0)
                info["responsive"] = resp.success
            else:
                info["responsive"] = False
            status[login] = info
        return status
