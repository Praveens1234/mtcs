"""Trading control API routes."""

import json
import logging
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.api.deps import app_state

logger = logging.getLogger("mtcs.api.trading")
router = APIRouter(prefix="/api/v1/trading", tags=["trading"])


@router.post("/order")
async def send_manual_order(request: Request):
    """Send a manual order (defaults to master, triggers auto-copy)."""
    import MetaTrader5 as mt5
    body = await request.json()
    login = body.get("login")
    if not login:
        master = await app_state.recovery.get_master_account()
        if not master:
            return JSONResponse(content={"success": False, "error": "No master account"})
        login = master["login"]
    
    symbol = body.get("symbol")
    direction = body.get("type", "buy").lower()  # buy, sell, buy limit, sell stop, etc.
    volume = float(body.get("volume", 0.01))
    sl = float(body.get("sl", 0.0))
    tp = float(body.get("tp", 0.0))
    price_open = float(body.get("price_open", 0.0))
    
    tick = await app_state.workers.get_symbol_tick(symbol, login=login)
    if not tick:
        return JSONResponse(content={"success": False, "error": f"No tick data for {symbol}"})
        
    # Map direction string to MT5 order type
    order_type_map = {
        "buy": mt5.ORDER_TYPE_BUY,
        "sell": mt5.ORDER_TYPE_SELL,
        "buy limit": mt5.ORDER_TYPE_BUY_LIMIT,
        "sell limit": mt5.ORDER_TYPE_SELL_LIMIT,
        "buy stop": mt5.ORDER_TYPE_BUY_STOP,
        "sell stop": mt5.ORDER_TYPE_SELL_STOP,
    }
    
    mt5_type = order_type_map.get(direction, mt5.ORDER_TYPE_BUY)
    
    # Determine execution price: 
    # For market orders, use current ask/bid. For pending, use provided price.
    is_pending = "limit" in direction or "stop" in direction
    if is_pending:
        if price_open <= 0:
             return JSONResponse(content={"success": False, "error": f"price_open is required for pending orders"})
        exec_price = price_open
        action = mt5.TRADE_ACTION_PENDING
    else:
        exec_price = tick["ask"] if mt5_type == mt5.ORDER_TYPE_BUY else tick["bid"]
        action = mt5.TRADE_ACTION_DEAL
    
    req = {
        "action": action,
        "symbol": symbol,
        "volume": volume,
        "type": mt5_type,
        "price": exec_price,
        "sl": sl,
        "tp": tp,
        "deviation": 50,
        "magic": 999999,
        "comment": "MTCS Manual",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC if not is_pending else mt5.ORDER_FILLING_RETURN,
    }
    
    result = await app_state.workers.send_order(login, req)
    return JSONResponse(content=result)


@router.post("/copy/start")
async def start_copying():
    """Start copy trading."""
    if not app_state.monitor:
        return JSONResponse(content={"success": False, "error": "System not ready"})

    master = await app_state.recovery.get_master_account()
    if not master:
        return JSONResponse(content={"success": False, "error": "No master account configured"})

    await app_state.monitor.start()
    app_state.copier.resume()
    app_state.copy_active = True

    await app_state.db.audit_log("copy_started", "{}")
    return JSONResponse(content={"success": True, "message": "Copy trading started"})


@router.post("/copy/stop")
async def stop_copying():
    """Stop copy trading (preserves state)."""
    if app_state.monitor:
        app_state.monitor.pause()
    if app_state.copier:
        app_state.copier.pause()
    app_state.copy_active = False

    await app_state.db.audit_log("copy_stopped", "{}")
    return JSONResponse(content={"success": True, "message": "Copy trading stopped"})


@router.post("/emergency-stop")
async def emergency_stop():
    """Emergency stop — pause all immediately."""
    result = await app_state.risk.emergency_stop()
    if app_state.monitor:
        app_state.monitor.pause()
    if app_state.copier:
        app_state.copier.pause()
    app_state.copy_active = False
    return JSONResponse(content=result)


@router.post("/emergency-resume")
async def emergency_resume():
    """Resume after emergency stop."""
    result = await app_state.risk.emergency_resume()
    return JSONResponse(content=result)


@router.post("/close-all")
async def close_all():
    """Close all positions."""
    result = await app_state.risk.close_all_positions()
    return JSONResponse(content=result)


@router.post("/close-winners")
async def close_winners():
    """Close profitable positions only."""
    result = await app_state.risk.close_winners()
    return JSONResponse(content=result)


@router.post("/close-losers")
async def close_losers():
    """Close losing positions only."""
    result = await app_state.risk.close_losers()
    return JSONResponse(content=result)


@router.post("/close-buy")
async def close_buy():
    """Close all buy positions."""
    result = await app_state.risk.close_by_direction("buy")
    return JSONResponse(content=result)


@router.post("/close-sell")
async def close_sell():
    """Close all sell positions."""
    result = await app_state.risk.close_by_direction("sell")
    return JSONResponse(content=result)


@router.post("/position/close")
async def close_single_position(request: Request):
    """Close or partially close a specific position."""
    body = await request.json()
    login = int(body.get("login", 0))
    ticket = int(body.get("ticket", 0))
    volume = body.get("volume")
    if volume is not None:
        volume = float(volume)

    if not login or not ticket:
        return JSONResponse(content={"success": False, "error": "login and ticket required"})

    result = await app_state.workers.close_position(login, ticket, volume)
    return JSONResponse(content=result)


@router.post("/position/modify")
async def modify_position(request: Request):
    """Modify SL/TP of a specific position."""
    import MetaTrader5 as mt5
    body = await request.json()
    login = int(body.get("login", 0))
    ticket = int(body.get("ticket", 0))
    symbol = body.get("symbol", "")
    sl = float(body.get("sl", 0.0))
    tp = float(body.get("tp", 0.0))

    if not login or not ticket or not symbol:
        return JSONResponse(content={"success": False, "error": "login, ticket, and symbol required"})

    req = {
        "action": mt5.TRADE_ACTION_SLTP,
        "symbol": symbol,
        "position": ticket,
        "sl": sl,
        "tp": tp,
    }
    result = await app_state.workers.send_order(login, req)
    return JSONResponse(content=result)


@router.post("/order/cancel")
async def cancel_order(request: Request):
    """Cancel a pending order."""
    import MetaTrader5 as mt5
    body = await request.json()
    login = int(body.get("login", 0))
    ticket = int(body.get("ticket", 0))

    if not login or not ticket:
        return JSONResponse(content={"success": False, "error": "login and ticket required"})

    req = {
        "action": mt5.TRADE_ACTION_REMOVE,
        "order": ticket,
    }
    result = await app_state.workers.send_order(login, req)
    return JSONResponse(content=result)


@router.get("/positions")
async def get_positions():
    """Get current open positions from all workers."""
    all_positions = []
    if app_state.workers:
        for worker in app_state.workers.get_all_workers():
            if worker.alive:
                positions = await app_state.workers.get_positions(login=worker.login)
                for p in positions:
                    p["account"] = worker.login
                    p["role"] = worker.role
                all_positions.extend(positions)
    return JSONResponse(content={"positions": all_positions})


@router.get("/orders")
async def get_orders():
    """Get pending orders from all workers."""
    all_orders = []
    if app_state.workers:
        for worker in app_state.workers.get_all_workers():
            if worker.alive:
                orders = await app_state.workers.get_orders(login=worker.login)
                for o in orders:
                    o["account"] = worker.login
                    o["role"] = worker.role
                all_orders.extend(orders)
    return JSONResponse(content={"orders": all_orders})


@router.get("/status")
async def trading_status():
    """Get current copy trading status."""
    return JSONResponse(content={
        "copy_active": app_state.copy_active,
        "monitor_running": app_state.monitor.is_running if app_state.monitor else False,
        "monitor_paused": app_state.monitor.is_paused if app_state.monitor else False,
        "copier_paused": app_state.copier.is_paused if app_state.copier else False,
        "emergency_stop": app_state.risk.is_emergency if app_state.risk else False,
        "mt5_connected": app_state.bridge.connected if app_state.bridge else False,
        "mt5_available": app_state.bridge.available if app_state.bridge else False,
    })
