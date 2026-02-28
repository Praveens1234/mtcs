"""Trade history API routes."""

import logging
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.api.deps import app_state

logger = logging.getLogger("mtcs.api.history")
router = APIRouter(prefix="/api/v1/history", tags=["history"])


import time
import asyncio

@router.get("/trades")
async def get_trade_history(
    symbol: str = Query(None),
    account: int = Query(None),
    limit: int = Query(500, ge=1, le=1000),
    days: int = Query(30, ge=1, le=365),
):
    """Get real trade history deals from MT5 workers."""
    if not app_state.workers:
        return JSONResponse(content={"trades": [], "total": 0})

    all_trades = []
    # Fetch from target account or all active workers
    workers_to_query = []
    if account:
        w = app_state.workers.get_worker(account)
        if w and w.alive:
            workers_to_query.append(w)
    else:
        workers_to_query = [w for w in app_state.workers.get_all_workers() if w.alive]
        
    tasks = [app_state.workers.get_history_deals(w.login, days) for w in workers_to_query]
    
    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, deals in enumerate(results):
            if isinstance(deals, list):
                login = workers_to_query[i].login
                for d in deals:
                    d["account_login"] = login
                    # We might want to filter out non-TRADE deals if desired
                    # MT5 deal types: 0=Buy, 1=Sell, 2=Balance, 3=Credit, 4=Charge, 5=Correction, 6=Bonus
                    if d.get("type") in (0, 1): 
                        d["direction"] = "buy" if d["type"] == 0 else "sell"
                        d["timestamp"] = d.get("time", 0) * 1000  # JS frontend expects milliseconds
                        d["trade_type"] = "entry" if d.get("entry", 0) == 0 else "exit"
                        d["close_price"] = d.get("price", 0)
                        d["open_price"] = d.get("price", 0)
                        
                        # filter by symbol if requested
                        if symbol and d.get("symbol") != symbol:
                            continue
                            
                        all_trades.append(d)

    # Sort DESC by time
    all_trades.sort(key=lambda x: x.get("time", 0), reverse=True)
    all_trades = all_trades[:limit]

    return JSONResponse(content={
        "trades": all_trades,
        "total": len(all_trades),
        "limit": limit,
    })


@router.get("/mappings")
async def get_trade_mappings(
    status: str = Query(None),
    limit: int = Query(50, ge=1, le=500),
):
    """Get trade mappings (master -> slave)."""
    query = "SELECT * FROM trade_mappings WHERE 1=1"
    params = []

    if status:
        query += " AND status = ?"
        params.append(status)

    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    mappings = await app_state.db.fetch_all(query, tuple(params))
    return JSONResponse(content={"mappings": mappings})


@router.get("/audit")
async def get_audit_log(
    event_type: str = Query(None),
    limit: int = Query(100, ge=1, le=1000),
):
    """Get audit log entries."""
    query = "SELECT * FROM audit_log WHERE 1=1"
    params = []

    if event_type:
        query += " AND event_type = ?"
        params.append(event_type)

    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    entries = await app_state.db.fetch_all(query, tuple(params))
    return JSONResponse(content={"audit": entries})
