"""State recovery — reload state after crash/restart, reconcile trades."""

import json
import logging
from app.persistence.database import Database

logger = logging.getLogger("mtcs.recovery")


class StateRecovery:
    """Handle crash recovery and trade reconciliation."""

    def __init__(self, db: Database):
        self.db = db

    async def get_all_accounts(self) -> list[dict]:
        """Load all accounts from database."""
        return await self.db.fetch_all(
            "SELECT * FROM accounts ORDER BY role DESC, login"
        )

    async def get_master_account(self) -> dict | None:
        """Get the master account if one exists."""
        return await self.db.fetch_one(
            "SELECT * FROM accounts WHERE role = 'master' LIMIT 1"
        )

    async def get_slave_accounts(self) -> list[dict]:
        """Get all slave accounts."""
        return await self.db.fetch_all(
            "SELECT * FROM accounts WHERE role = 'slave' ORDER BY login"
        )

    async def get_active_mappings(self) -> list[dict]:
        """Get all non-closed trade mappings for reconciliation."""
        return await self.db.fetch_all(
            "SELECT * FROM trade_mappings WHERE status NOT IN ('closed', 'failed') "
            "ORDER BY created_at"
        )

    async def mark_mapping_orphaned(self, mapping_id: int) -> None:
        """Mark a trade mapping as orphaned (position no longer exists)."""
        await self.db.execute(
            "UPDATE trade_mappings SET status = 'orphaned', updated_at = datetime('now') "
            "WHERE id = ?",
            (mapping_id,),
        )
        logger.warning(f"Trade mapping {mapping_id} marked as orphaned")

    async def reconcile_trades(self, live_master_tickets: set[int],
                                live_slave_tickets: dict[int, set[int]]) -> dict:
        """
        Reconcile database mappings against live MT5 positions.
        
        Args:
            live_master_tickets: Set of currently open master position tickets
            live_slave_tickets: Dict of {slave_login: set of open ticket numbers}
            
        Returns:
            Dict with reconciliation results
        """
        results = {"orphaned": 0, "active": 0, "mismatched": 0}
        active_mappings = await self.get_active_mappings()

        for mapping in active_mappings:
            master_ticket = mapping["master_ticket"]
            slave_login = mapping["slave_login"]
            slave_ticket = mapping.get("slave_ticket")

            # Check if master position still exists
            if master_ticket not in live_master_tickets:
                await self.mark_mapping_orphaned(mapping["id"])
                results["orphaned"] += 1
                continue

            # Check if slave position still exists
            slave_tickets = live_slave_tickets.get(slave_login, set())
            if slave_ticket and slave_ticket not in slave_tickets:
                await self.mark_mapping_orphaned(mapping["id"])
                results["mismatched"] += 1
                continue

            results["active"] += 1

        logger.info(
            f"Trade reconciliation complete: {results['active']} active, "
            f"{results['orphaned']} orphaned, {results['mismatched']} mismatched"
        )
        await self.db.audit_log("reconciliation", json.dumps(results))
        return results

    async def save_system_state(self, key: str, value: str) -> None:
        """Save a system state value."""
        await self.db.execute(
            "INSERT OR REPLACE INTO system_config (key, value, updated_at) "
            "VALUES (?, ?, datetime('now'))",
            (key, value),
        )

    async def get_system_state(self, key: str) -> str | None:
        """Get a system state value."""
        row = await self.db.fetch_one(
            "SELECT value FROM system_config WHERE key = ?", (key,)
        )
        return row["value"] if row else None
