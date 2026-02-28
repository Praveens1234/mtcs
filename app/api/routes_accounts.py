"""Account management API routes.

Refactored for multi-process: adding an account spawns a dedicated worker subprocess.
"""

import json
import logging
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse

from app.api.deps import app_state

logger = logging.getLogger("mtcs.api.accounts")
router = APIRouter(prefix="/api/v1/accounts", tags=["accounts"])


@router.get("")
async def list_accounts():
    """List all accounts with current status (from workers)."""
    accounts = await app_state.db.fetch_all(
        "SELECT id, login, server, role, enabled, display_name, settings_json, "
        "created_at FROM accounts ORDER BY role DESC, login"
    )
    enriched = []
    for acc in accounts:
        acc_data = dict(acc)
        acc_data["mt5_connected"] = False
        acc_data["balance"] = 0
        acc_data["equity"] = 0
        acc_data["profit"] = 0
        acc_data["currency"] = "USD"
        acc_data["worker_alive"] = False
        acc_data["worker_pid"] = 0

        # Check if worker is alive for this account
        if app_state.workers:
            worker = app_state.workers.get_worker(acc["login"])
            if worker and worker.alive:
                acc_data["worker_alive"] = True
                acc_data["worker_pid"] = worker.pid
                # Get live account info from the worker
                try:
                    info = await app_state.workers.get_account_info(login=acc["login"])
                    if info:
                        acc_data["balance"] = info.get("balance", 0)
                        acc_data["equity"] = info.get("equity", 0)
                        acc_data["profit"] = info.get("profit", 0)
                        acc_data["currency"] = info.get("currency", "USD")
                        acc_data["mt5_connected"] = True
                except Exception:
                    pass

        enriched.append(acc_data)

    return JSONResponse(content={"accounts": enriched})


@router.post("/add")
async def add_account(
    login: int = Form(...),
    password: str = Form(...),
    server: str = Form(...),
    role: str = Form("slave"),
):
    """Add an account and spawn its worker subprocess."""
    password = password.strip()
    server = server.strip()
    
    if role not in ("master", "slave"):
        return JSONResponse(
            content={"success": False, "error": "Role must be 'master' or 'slave'"},
            status_code=400,
        )

    # If adding master, check if one already exists
    if role == "master":
        existing_master = await app_state.db.fetch_one(
            "SELECT login FROM accounts WHERE role = 'master'"
        )
        if existing_master:
            return JSONResponse(
                content={
                    "success": False,
                    "error": f"Master already exists (login: {existing_master['login']}). Remove it first.",
                },
                status_code=400,
            )

    # Spawn a dedicated worker subprocess for this account
    spawn_result = {"success": False, "error": "Worker manager not ready"}
    if app_state.workers and app_state.workers.available:
        spawn_result = await app_state.workers.spawn_worker(
            login=login, password=password, server=server, role=role,
        )

    # Save to database
    encrypted_pw = app_state.credentials.encrypt(password)
    existing = await app_state.db.fetch_one(
        "SELECT id FROM accounts WHERE login = ?", (login,)
    )
    if existing:
        await app_state.db.execute(
            "UPDATE accounts SET encrypted_password=?, server=?, role=?, "
            "enabled=?, updated_at=datetime('now') WHERE login=?",
            (encrypted_pw, server, role, 1 if spawn_result.get("success") else 0, login),
        )
    else:
        await app_state.db.execute(
            "INSERT INTO accounts (login, encrypted_password, server, role, enabled) "
            "VALUES (?, ?, ?, ?, ?)",
            (login, encrypted_pw, server, role, 1 if spawn_result.get("success") else 0),
        )

    # Save to credentials.json
    app_state.credentials.add_account(login, password, server, role)

    # Audit
    await app_state.db.audit_log(
        "account_added",
        json.dumps({
            "login": login, "server": server, "role": role,
            "worker_spawned": spawn_result.get("success", False),
            "pid": spawn_result.get("pid", 0),
        }),
    )

    # Start master monitor if master was added successfully
    if role == "master" and spawn_result.get("success"):
        await app_state.workers.start_master_monitor()
        app_state.copy_active = True

    return JSONResponse(content={
        "success": True,
        "mt5_validated": spawn_result.get("success", False),
        "mt5_message": spawn_result.get("error", "Worker spawned successfully"),
        "account": {
            "login": login,
            "server": server,
            "role": role,
            "balance": spawn_result.get("balance", 0),
            "equity": spawn_result.get("equity", 0),
            "pid": spawn_result.get("pid", 0),
        },
    })


@router.post("/remove/{login}")
async def remove_account(login: int):
    """Remove an account and kill its worker."""
    account = await app_state.db.fetch_one(
        "SELECT role FROM accounts WHERE login = ?", (login,)
    )
    if not account:
        return JSONResponse(
            content={"success": False, "error": "Account not found"},
            status_code=404,
        )

    # Kill the worker subprocess
    if app_state.workers:
        await app_state.workers.kill_worker(login)

    if account["role"] == "master":
        app_state.copy_active = False

    await app_state.db.execute("DELETE FROM accounts WHERE login = ?", (login,))
    app_state.credentials.remove_account(login)

    await app_state.db.audit_log(
        "account_removed", json.dumps({"login": login})
    )

    return JSONResponse(content={"success": True})


@router.post("/toggle/{login}")
async def toggle_account(login: int):
    """Toggle account enabled/disabled. Spawns/kills worker accordingly."""
    account = await app_state.db.fetch_one(
        "SELECT enabled, encrypted_password, server, role FROM accounts WHERE login = ?",
        (login,)
    )
    if not account:
        return JSONResponse(
            content={"success": False, "error": "Account not found"},
            status_code=404
        )

    new_state = 0 if account["enabled"] else 1
    await app_state.db.execute(
        "UPDATE accounts SET enabled = ?, updated_at = datetime('now') WHERE login = ?",
        (new_state, login),
    )

    # Spawn or kill worker
    if app_state.workers:
        if new_state == 1:
            # Re-spawn worker
            try:
                password = app_state.credentials.decrypt(account["encrypted_password"])
                await app_state.workers.spawn_worker(
                    login=login, password=password,
                    server=account["server"], role=account["role"],
                )
            except Exception as e:
                logger.error(f"Failed to respawn worker {login}: {e}")
        else:
            # Kill worker
            await app_state.workers.kill_worker(login)

    return JSONResponse(content={"success": True, "enabled": bool(new_state)})


@router.post("/settings/{login}")
async def update_account_settings(login: int, request: Request):
    """Update per-slave settings."""
    body = await request.json()
    settings_json = json.dumps(body)
    await app_state.db.execute(
        "UPDATE accounts SET settings_json = ?, updated_at = datetime('now') WHERE login = ?",
        (settings_json, login),
    )
    return JSONResponse(content={"success": True, "settings": body})


@router.get("/workers")
async def worker_health():
    """Get health status of all worker subprocesses."""
    if not app_state.workers:
        return JSONResponse(content={"workers": {}})
    health = await app_state.workers.health_check()
    return JSONResponse(content={"workers": health})
