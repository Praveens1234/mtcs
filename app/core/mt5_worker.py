"""MT5 Worker — dedicated subprocess per MT5 account.

Each worker:
- Runs mt5.initialize() + mt5.login() ONCE on startup
- Stays permanently logged in (no login switching)
- Listens for commands on input_queue, responds on output_queue
- Master workers additionally run the trade monitor loop
  and push trade events to event_queue
"""

import multiprocessing as mp
import time
import logging
import traceback
from typing import Optional
from dataclasses import dataclass, field, asdict
from enum import Enum

# Configure logging for subprocess
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("mtcs.worker")


class WorkerCommand(str, Enum):
    """Commands from main process → worker."""
    PING = "ping"
    SHUTDOWN = "shutdown"
    GET_POSITIONS = "get_positions"
    GET_ORDERS = "get_orders"
    GET_ACCOUNT_INFO = "get_account_info"
    GET_SYMBOL_TICK = "get_symbol_tick"
    GET_SYMBOL_INFO = "get_symbol_info"
    GET_SYMBOLS = "get_symbols"
    SEND_ORDER = "send_order"
    CLOSE_POSITION = "close_position"
    START_MONITOR = "start_monitor"
    STOP_MONITOR = "stop_monitor"
    PAUSE_MONITOR = "pause_monitor"
    RESUME_MONITOR = "resume_monitor"
    GET_HISTORY_DEALS = "get_history_deals"


@dataclass
class WorkerMessage:
    """Message sent to a worker subprocess."""
    command: str
    request_id: str = ""
    data: dict = field(default_factory=dict)


@dataclass
class WorkerResponse:
    """Response from a worker subprocess."""
    request_id: str = ""
    success: bool = True
    data: dict = field(default_factory=dict)
    error: str = ""


@dataclass
class TradeEvent:
    """Trade event emitted by master worker."""
    event_type: str = ""  # open, close, modify, partial_close
    data: dict = field(default_factory=dict)
    timestamp: float = 0.0


def _worker_process(
    login: int,
    password: str,
    server: str,
    terminal_path: str,
    role: str,
    input_queue: mp.Queue,
    output_queue: mp.Queue,
    event_queue: Optional[mp.Queue],
    monitor_interval: float,
    shutdown_event: mp.Event,
):
    """
    Entry point for the worker subprocess.
    Runs in a completely separate process with its own MT5 connection.
    """
    import uuid as uuid_mod

    proc_name = f"MT5Worker-{role}-{login}"
    logger = logging.getLogger(proc_name)
    logger.info(f"Worker starting: {login}@{server} (role={role}, pid={mp.current_process().pid})")

    # Import MT5 inside the subprocess
    try:
        import MetaTrader5 as mt5
    except ImportError:
        logger.error("MetaTrader5 package not available in worker")
        output_queue.put(WorkerResponse(
            request_id="init", success=False,
            error="MetaTrader5 not installed"
        ))
        return

    # Initialize MT5 with credentials to prevent stale terminal auto-login failures (-6)
    init_kwargs = {
        "login": login,
        "password": password,
        "server": server,
    }
    if terminal_path:
        init_ok = mt5.initialize(terminal_path, **init_kwargs)
    else:
        init_ok = mt5.initialize(**init_kwargs)

    if not init_ok:
        err = mt5.last_error()
        logger.error(f"MT5 init failed: {err}")
        
        # If the terminal is completely stuck on an old invalid account, 
        # initialize() might still fail. We will return the error.
        output_queue.put(WorkerResponse(
            request_id="init", success=False,
            error=f"MT5 init failed: {err} — Check terminal state or credentials"
        ))
        return

    # Login
    login_ok = mt5.login(login, password=password, server=server)
    if not login_ok:
        err = mt5.last_error()
        logger.error(f"Login failed: {err}")
        mt5.shutdown()
        output_queue.put(WorkerResponse(
            request_id="init", success=False,
            error=f"Login failed: {err}"
        ))
        return

    # Get account info to confirm
    acc_info = mt5.account_info()
    if acc_info:
        logger.info(
            f"Login OK: {acc_info.login}@{acc_info.server} "
            f"balance={acc_info.balance} equity={acc_info.equity}"
        )
        output_queue.put(WorkerResponse(
            request_id="init", success=True,
            data={
                "login": acc_info.login,
                "server": acc_info.server,
                "balance": acc_info.balance,
                "equity": acc_info.equity,
                "profit": acc_info.profit,
                "margin": acc_info.margin,
                "margin_free": acc_info.margin_free,
                "currency": acc_info.currency,
                "leverage": acc_info.leverage,
                "name": acc_info.name,
            }
        ))
    else:
        output_queue.put(WorkerResponse(request_id="init", success=True))

    # ---------- Build Symbol Map ----------
    # Map base symbols (e.g. EURUSD) to broker-specific symbols (e.g. EURUSDm, EURUSDc)
    broker_symbols = mt5.symbols_get()
    symbol_map = {}
    if broker_symbols:
        for bs in broker_symbols:
            name = bs.name
            # If it's a forex pair, it's usually 6 chars + optional suffix.
            if len(name) >= 6:
                base = name[:6].upper()
                if base not in symbol_map:
                    symbol_map[base] = name
                else:
                    # Prefer suffixes like 'm' or 'c' over others if multiple exist
                    if name.endswith('m') or name.endswith('c'):
                        symbol_map[base] = name
    
    def resolve_symbol(sym: str) -> str:
        s = sym.upper()
        # If the exact symbol exists, return it
        if mt5.symbol_info(sym):
            return sym
        # Try mapped base
        if s in symbol_map:
            return symbol_map[s]
        # Return original and let MT5 fail naturally
        return sym

    # ---------- Monitor state (master only) ----------
    monitor_running = False
    monitor_paused = False
    last_positions: dict = {}  # ticket -> position dict
    trade_uuids: dict = {}  # ticket -> UUID string

    def _get_positions_list():
        positions = mt5.positions_get()
        if positions is None:
            return []
        return [
            {
                "ticket": p.ticket,
                "symbol": p.symbol,
                "type": "buy" if p.type == 0 else "sell",
                "volume": p.volume,
                "price_open": p.price_open,
                "price_current": p.price_current,
                "sl": p.sl,
                "tp": p.tp,
                "profit": p.profit,
                "swap": p.swap,
                "commission": getattr(p, "commission", 0.0),
                "magic": p.magic,
                "comment": p.comment,
                "time": p.time,
                "identifier": p.identifier,
            }
            for p in positions
        ]

    def _get_orders_list():
        orders = mt5.orders_get()
        if orders is None:
            return []
        type_map = {
            0: "buy_limit", 1: "sell_limit",
            2: "buy_stop", 3: "sell_stop",
            4: "buy_stop_limit", 5: "sell_stop_limit",
        }
        return [
            {
                "ticket": o.ticket,
                "symbol": o.symbol,
                "type": type_map.get(o.type, str(o.type)),
                "volume_initial": o.volume_initial,
                "volume_current": o.volume_current,
                "price_open": o.price_open,
                "sl": o.sl,
                "tp": o.tp,
                "price_current": o.price_current,
                "price_stoplimit": o.price_stoplimit,
                "magic": o.magic,
                "comment": o.comment,
                "time_setup": o.time_setup,
            }
            for o in orders
        ]

    def _get_uuid(ticket: int) -> str:
        if ticket not in trade_uuids:
            trade_uuids[ticket] = str(uuid_mod.uuid4())
        return trade_uuids[ticket]

    def _check_trades():
        """Snapshot comparison for master monitor."""
        nonlocal last_positions
        new_pos_list = _get_positions_list()
        new_positions = {p["ticket"]: p for p in new_pos_list}

        old_keys = set(last_positions.keys())
        new_keys = set(new_positions.keys())

        # New positions (opened)
        for ticket in new_keys - old_keys:
            pos = new_positions[ticket]
            event = TradeEvent(
                event_type="open",
                data={
                    "uuid": _get_uuid(ticket),
                    "ticket": ticket,
                    "symbol": pos["symbol"],
                    "direction": pos["type"],
                    "volume": pos["volume"],
                    "price": pos["price_open"],
                    "sl": pos["sl"],
                    "tp": pos["tp"],
                    "comment": pos.get("comment", ""),
                    "magic": pos.get("magic", 0),
                },
                timestamp=time.time(),
            )
            logger.info(f"TRADE OPEN: {pos['symbol']} {pos['type']} {pos['volume']} @ {pos['price_open']}")
            if event_queue:
                event_queue.put(event)

        # Closed positions
        for ticket in old_keys - new_keys:
            pos = last_positions[ticket]
            uid = trade_uuids.pop(ticket, str(uuid_mod.uuid4()))
            event = TradeEvent(
                event_type="close",
                data={
                    "uuid": uid,
                    "ticket": ticket,
                    "symbol": pos["symbol"],
                    "direction": pos["type"],
                    "volume": pos["volume"],
                    "price": pos.get("price_current", 0),
                    "sl": pos["sl"],
                    "tp": pos["tp"],
                },
                timestamp=time.time(),
            )
            logger.info(f"TRADE CLOSE: {pos['symbol']} [ticket={ticket}]")
            if event_queue:
                event_queue.put(event)

        # Modified positions
        for ticket in old_keys & new_keys:
            old_p = last_positions[ticket]
            new_p = new_positions[ticket]

            # Partial close
            if new_p["volume"] < old_p["volume"]:
                event = TradeEvent(
                    event_type="partial_close",
                    data={
                        "uuid": _get_uuid(ticket),
                        "ticket": ticket,
                        "symbol": new_p["symbol"],
                        "direction": new_p["type"],
                        "volume": round(old_p["volume"] - new_p["volume"], 4),
                        "remaining_volume": new_p["volume"],
                        "price": new_p.get("price_current", 0),
                        "sl": new_p["sl"],
                        "tp": new_p["tp"],
                    },
                    timestamp=time.time(),
                )
                logger.info(f"PARTIAL CLOSE: {new_p['symbol']} vol {old_p['volume']}->{new_p['volume']}")
                if event_queue:
                    event_queue.put(event)

            # SL/TP modification
            elif old_p["sl"] != new_p["sl"] or old_p["tp"] != new_p["tp"]:
                event = TradeEvent(
                    event_type="modify",
                    data={
                        "uuid": _get_uuid(ticket),
                        "ticket": ticket,
                        "symbol": new_p["symbol"],
                        "direction": new_p["type"],
                        "volume": new_p["volume"],
                        "price": new_p.get("price_current", 0),
                        "sl": new_p["sl"],
                        "tp": new_p["tp"],
                    },
                    timestamp=time.time(),
                )
                logger.info(f"SL/TP MODIFY: {new_p['symbol']} SL={new_p['sl']} TP={new_p['tp']}")
                if event_queue:
                    event_queue.put(event)

        last_positions = new_positions

    # ---------- Main command loop ----------
    last_monitor_check = 0.0

    while not shutdown_event.is_set():
        # Process commands (non-blocking with timeout)
        try:
            msg = input_queue.get(timeout=monitor_interval if monitor_running else 1.0)
        except Exception:
            msg = None

        if msg and isinstance(msg, WorkerMessage):
            cmd = msg.command
            resp = WorkerResponse(request_id=msg.request_id)

            try:
                if cmd == WorkerCommand.PING:
                    resp.data = {"alive": True, "login": login, "role": role}

                elif cmd == WorkerCommand.SHUTDOWN:
                    logger.info("Shutdown command received")
                    break

                elif cmd == WorkerCommand.GET_POSITIONS:
                    resp.data = {"positions": _get_positions_list()}

                elif cmd == WorkerCommand.GET_ORDERS:
                    resp.data = {"orders": _get_orders_list()}

                elif cmd == WorkerCommand.GET_ACCOUNT_INFO:
                    info = mt5.account_info()
                    term = mt5.terminal_info()
                    if info and term:
                        resp.data = {
                            "login": info.login, "server": info.server,
                            "balance": info.balance, "equity": info.equity,
                            "profit": info.profit, "margin": info.margin,
                            "margin_free": info.margin_free,
                            "currency": info.currency, "leverage": info.leverage,
                            "name": info.name,
                            "trade_allowed": term.trade_allowed,
                        }
                    else:
                        resp.success = False
                        resp.error = "No account info or terminal info"

                elif cmd == WorkerCommand.GET_SYMBOL_TICK:
                    base_symbol = msg.data.get("symbol", "")
                    symbol = resolve_symbol(base_symbol)
                    mt5.symbol_select(symbol, True)
                    tick = mt5.symbol_info_tick(symbol)
                    if tick:
                        resp.data = {
                            "symbol": base_symbol,  # Return the base symbol requested by UI
                            "broker_symbol": symbol,
                            "bid": tick.bid, "ask": tick.ask,
                            "last": tick.last, "volume": tick.volume,
                            "time": tick.time,
                            "spread": round(tick.ask - tick.bid, 6),
                        }
                    else:
                        resp.success = False
                        resp.error = f"No tick for {symbol} (base={base_symbol})"

                elif cmd == WorkerCommand.GET_SYMBOL_INFO:
                    base_symbol = msg.data.get("symbol", "")
                    symbol = resolve_symbol(base_symbol)
                    mt5.symbol_select(symbol, True)
                    info = mt5.symbol_info(symbol)
                    if info:
                        resp.data = {
                            "symbol": base_symbol, 
                            "broker_symbol": info.name,
                            "point": info.point,
                            "digits": info.digits, "volume_min": info.volume_min,
                            "volume_max": info.volume_max, "volume_step": info.volume_step,
                            "trade_contract_size": info.trade_contract_size,
                            "spread": info.spread, "ask": info.ask, "bid": info.bid,
                        }
                    else:
                        resp.success = False
                        resp.error = f"No info for {symbol}"

                elif cmd == WorkerCommand.GET_SYMBOLS:
                    symbols = mt5.symbols_get()
                    resp.data = {"symbols": [s.name for s in symbols if s.visible] if symbols else []}

                elif cmd == WorkerCommand.SEND_ORDER:
                    request = msg.data.get("request", {})
                    # Map symbol
                    if "symbol" in request:
                        request["symbol"] = resolve_symbol(request["symbol"])
                    
                    # Check order first (skip for SLTP mods as MT5 often fails the check but allows the send)
                    if request.get("action") == mt5.TRADE_ACTION_SLTP:
                        check = None
                        skip_check = True
                    else:
                        check = mt5.order_check(request)
                        skip_check = False

                    if not skip_check and check is None:
                        err = mt5.last_error()
                        resp.success = False
                        resp.error = f"Order check failed: {err}"
                    elif not skip_check and check.retcode != 0:
                        resp.success = False
                        resp.error = f"Check rejected: {check.comment}"
                        resp.data = {"retcode": check.retcode}
                    else:
                        result = mt5.order_send(request)
                        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                            resp.data = {
                                "order": result.order, "deal": result.deal,
                                "volume": result.volume, "price": result.price,
                                "retcode": result.retcode, "comment": result.comment,
                            }
                            logger.info(
                                f"ORDER OK: {request.get('symbol')} "
                                f"vol={result.volume} price={result.price} ticket={result.order}"
                            )
                        else:
                            resp.success = False
                            resp.error = result.comment if result else "Unknown"
                            resp.data = {"retcode": result.retcode if result else -1}

                elif cmd == WorkerCommand.CLOSE_POSITION:
                    ticket = msg.data.get("ticket")
                    volume = msg.data.get("volume")
                    positions = mt5.positions_get(ticket=ticket)
                    if not positions:
                        resp.success = False
                        resp.error = f"Position {ticket} not found"
                    else:
                        pos = positions[0]
                        close_vol = volume or pos.volume
                        close_type = mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY
                        tick = mt5.symbol_info_tick(pos.symbol)
                        if not tick:
                            resp.success = False
                            resp.error = f"No tick for {pos.symbol}"
                        else:
                            price = tick.bid if pos.type == 0 else tick.ask
                            req = {
                                "action": mt5.TRADE_ACTION_DEAL,
                                "symbol": pos.symbol,
                                "volume": close_vol,
                                "type": close_type,
                                "position": ticket,
                                "price": price,
                                "deviation": 50,
                                "magic": pos.magic,
                                "comment": "MTCS close",
                                "type_time": mt5.ORDER_TIME_GTC,
                                "type_filling": mt5.ORDER_FILLING_IOC,
                            }
                            result = mt5.order_send(req)
                            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                                resp.data = {"order": result.order, "deal": result.deal}
                                logger.info(f"CLOSE OK: ticket={ticket} vol={close_vol}")
                            else:
                                resp.success = False
                                resp.error = result.comment if result else "Unknown"

                elif cmd == WorkerCommand.START_MONITOR:
                    monitor_running = True
                    monitor_paused = False
                    last_positions = {p["ticket"]: p for p in _get_positions_list()}
                    logger.info("Trade monitor STARTED")
                    resp.data = {"monitoring": True}

                elif cmd == WorkerCommand.STOP_MONITOR:
                    monitor_running = False
                    logger.info("Trade monitor STOPPED")
                    resp.data = {"monitoring": False}

                elif cmd == WorkerCommand.PAUSE_MONITOR:
                    monitor_paused = True
                    logger.info("Trade monitor PAUSED")
                    resp.data = {"paused": True}

                elif cmd == WorkerCommand.RESUME_MONITOR:
                    monitor_paused = False
                    logger.info("Trade monitor RESUMED")
                    resp.data = {"paused": False}

                elif cmd == WorkerCommand.GET_HISTORY_DEALS:
                    from datetime import datetime, timedelta
                    days = msg.data.get("days", 30)
                    to_dt = datetime.now() + timedelta(days=1)
                    from_dt = to_dt - timedelta(days=days)
                    deals = mt5.history_deals_get(from_dt, to_dt)
                    if deals:
                        resp.data = {"deals": [
                            {
                                "ticket": d.ticket, "order": d.order,
                                "symbol": d.symbol, "type": d.type,
                                "volume": d.volume, "price": d.price,
                                "profit": d.profit, "commission": d.commission,
                                "swap": d.swap, "time": d.time,
                                "comment": d.comment,
                                "position_id": d.position_id,
                            }
                            for d in deals
                        ]}
                    else:
                        resp.data = {"deals": []}

                else:
                    resp.success = False
                    resp.error = f"Unknown command: {cmd}"

            except Exception as e:
                resp.success = False
                resp.error = f"{e}\n{traceback.format_exc()}"
                logger.error(f"Command {cmd} error: {e}")

            output_queue.put(resp)

        # Master monitor: check for trade changes
        if monitor_running and not monitor_paused and role == "master":
            now = time.time()
            if now - last_monitor_check >= monitor_interval:
                try:
                    _check_trades()
                except Exception as e:
                    logger.error(f"Monitor check error: {e}")
                last_monitor_check = now

    # Cleanup
    logger.info(f"Worker {login} shutting down MT5...")
    mt5.shutdown()
    logger.info(f"Worker {login} exited cleanly")
