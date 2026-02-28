"""Risk Manager — global risk controls via WorkerManager.

Refactored for multi-process: close/emergency commands are broadcast
to all worker subprocesses in parallel.
"""

import asyncio
import json
import logging
from app.core.mt5_worker import WorkerCommand
from app.persistence.database import Database

logger = logging.getLogger("mtcs.risk")


class RiskManager:
    """Global and per-slave risk enforcement via WorkerManager."""

    def __init__(self, worker_manager, db: Database):
        self._wm = worker_manager
        self.db = db
        self._emergency_stop = False

    @property
    def is_emergency(self) -> bool:
        return self._emergency_stop

    async def emergency_stop(self) -> dict:
        """Immediately pause all copying and monitoring."""
        self._emergency_stop = True
        # Pause master monitor
        await self._wm.pause_master_monitor()
        logger.critical("EMERGENCY STOP activated")
        await self.db.audit_log("emergency_stop", '{"action": "activated"}')
        return {"success": True, "message": "Emergency stop activated"}

    async def emergency_resume(self) -> dict:
        """Resume after emergency stop."""
        self._emergency_stop = False
        await self._wm.resume_master_monitor()
        logger.info("Emergency stop deactivated")
        await self.db.audit_log("emergency_stop", '{"action": "deactivated"}')
        return {"success": True, "message": "Emergency stop deactivated"}

    async def close_all_positions(self) -> dict:
        """Close all positions on ALL accounts (master + slaves) in parallel."""
        results = {"closed": 0, "failed": 0, "total": 0}

        # Gather positions from all workers
        all_workers = self._wm.get_all_workers()
        close_tasks = []

        for worker in all_workers:
            if not worker.alive:
                continue
            positions = await self._wm.get_positions(login=worker.login)
            results["total"] += len(positions)
            for pos in positions:
                close_tasks.append(
                    self._wm.close_position(worker.login, pos["ticket"])
                )

        if close_tasks:
            task_results = await asyncio.gather(*close_tasks, return_exceptions=True)
            for r in task_results:
                if isinstance(r, dict) and r.get("success"):
                    results["closed"] += 1
                else:
                    results["failed"] += 1

        logger.info(f"Close all: {results['closed']}/{results['total']}")
        await self.db.audit_log("close_all", json.dumps(results))
        return results

    async def close_winners(self) -> dict:
        """Close only profitable positions on all accounts."""
        results = {"closed": 0, "failed": 0, "total": 0}

        for worker in self._wm.get_all_workers():
            if not worker.alive:
                continue
            positions = await self._wm.get_positions(login=worker.login)
            winners = [p for p in positions if p.get("profit", 0) > 0]
            results["total"] += len(winners)

            tasks = [self._wm.close_position(worker.login, p["ticket"]) for p in winners]
            if tasks:
                task_results = await asyncio.gather(*tasks, return_exceptions=True)
                for r in task_results:
                    if isinstance(r, dict) and r.get("success"):
                        results["closed"] += 1
                    else:
                        results["failed"] += 1

        logger.info(f"Close winners: {results['closed']}/{results['total']}")
        await self.db.audit_log("close_winners", json.dumps(results))
        return results

    async def close_losers(self) -> dict:
        """Close only losing positions on all accounts."""
        results = {"closed": 0, "failed": 0, "total": 0}

        for worker in self._wm.get_all_workers():
            if not worker.alive:
                continue
            positions = await self._wm.get_positions(login=worker.login)
            losers = [p for p in positions if p.get("profit", 0) < 0]
            results["total"] += len(losers)

            tasks = [self._wm.close_position(worker.login, p["ticket"]) for p in losers]
            if tasks:
                task_results = await asyncio.gather(*tasks, return_exceptions=True)
                for r in task_results:
                    if isinstance(r, dict) and r.get("success"):
                        results["closed"] += 1
                    else:
                        results["failed"] += 1

        logger.info(f"Close losers: {results['closed']}/{results['total']}")
        await self.db.audit_log("close_losers", json.dumps(results))
        return results

    async def close_by_direction(self, direction: str) -> dict:
        """Close all buy or sell positions on all accounts."""
        results = {"closed": 0, "failed": 0, "total": 0}

        for worker in self._wm.get_all_workers():
            if not worker.alive:
                continue
            positions = await self._wm.get_positions(login=worker.login)
            filtered = [p for p in positions if p.get("type") == direction]
            results["total"] += len(filtered)

            tasks = [self._wm.close_position(worker.login, p["ticket"]) for p in filtered]
            if tasks:
                task_results = await asyncio.gather(*tasks, return_exceptions=True)
                for r in task_results:
                    if isinstance(r, dict) and r.get("success"):
                        results["closed"] += 1
                    else:
                        results["failed"] += 1

        logger.info(f"Close {direction}: {results['closed']}/{results['total']}")
        await self.db.audit_log(f"close_{direction}", json.dumps(results))
        return results

    async def check_equity_threshold(self, login: int, threshold: float) -> bool:
        info = await self._wm.get_account_info(login=login)
        if info and info.get("equity", 0) < threshold:
            logger.warning(f"Equity {info['equity']} below {threshold} for {login}")
            return False
        return True

    def validate_order(self, spread: float, max_spread: int,
                       slippage: float = 0, max_slippage: int = 50) -> dict:
        if self._emergency_stop:
            return {"valid": False, "reason": "Emergency stop active"}
        if max_spread and spread > max_spread:
            return {"valid": False, "reason": f"Spread {spread} > {max_spread}"}
        if max_slippage and slippage > max_slippage:
            return {"valid": False, "reason": f"Slippage {slippage} > {max_slippage}"}
        return {"valid": True}
