# MTCS v2 (MetaTrader Copy System)
# 50-Phase Deep Debugging and Audit Plan

## Part 1: Architecture and Environment (Phases 1-10)
1. **Phase 1: Project Initialization & Structure Audit:** Review overall directory structure and basic setup (`app/main.py`, `app/config.py`, `run.py`).
2. **Phase 2: Dependency & Environment Audit:** Verify `requirements.txt` for outdated, insecure, or conflicting packages. Check for Python version compatibility.
3. **Phase 3: Core Multiprocessing Engine (WorkerManager):** Deep audit of `app/core/worker_manager.py` for IPC queue robustness, deadlock prevention, and zombie process handling.
4. **Phase 4: Worker Lifecycle Management:** Audit `app/core/mt5_worker.py` for correct start, stop, restart, and health check mechanics to ensure MT5 terminals don't hang.
5. **Phase 5: MT5 Integration Bridge (Master):** Audit `app/core/mt5_bridge.py` for correct initialization, error handling, and robust data fetching on the Master node.
6. **Phase 6: MT5 Integration Bridge (Slave):** Deep review of MT5 signal ingestion, execution commands, and order placement reliability.
7. **Phase 7: Process Synchronization:** Audit concurrency locks and parallel state synchronization to ensure data consistency across multiple spawned `mp.Process` workers.
8. **Phase 8: Parallel Execution Synchronization:** Audit `asyncio.gather` usage and concurrency limits to ensure no race conditions during trade broadcast.
9. **Phase 9: Threading vs Asyncio Assessment:** Verify synchronous MT5 library calls are strictly wrapped in `asyncio.to_thread` to prevent event loop blocking.
10. **Phase 10: Graceful Shutdowns:** Verify `lifespan` event handlers terminate all child OS processes efficiently without memory leaks.

## Part 2: Trade Execution and Core Logic (Phases 11-20)
11. **Phase 11: Trade Copier Logic (Core Execution):** Audit `app/core/trade_copier.py` for precise trade replication, error handling during execution, and slippage checks.
12. **Phase 12: Risk Management Core (Lot Sizing):** Audit `app/core/risk_manager.py` for accurate multiplier, fixed lot, and equity percentage calculations.
13. **Phase 13: Risk Management Core (Safety Rails):** Validate maximum slippage constraints, max spread allowance filters, and hard overrides.
14. **Phase 14: Emergency Protocols:** Audit `RiskManager.emergency_stop()` and related mechanisms ensuring instant disconnection of copying under duress.
15. **Phase 15: Real-time Trade Monitoring:** Audit `app/core/trade_monitor.py` for latency, accuracy of floating PnL, and open positions tracking.
16. **Phase 16: Position Reconciliation:** Deep verify that MT5 state continuously reconciles with SQLite DB `trade_mappings`.
17. **Phase 17: Partial Fill Handling:** Test scenarios where broker rejects a portion of the FOK/IOC trade volume.
18. **Phase 18: Order De-duplication:** Ensure network retry loops don't accidentally execute the same master signal twice on the slave.
19. **Phase 19: Timezone Normalization:** Deep verify that the system accurately normalizes timestamps across different broker server timezones natively to UNIX epochs.
20. **Phase 20: Event Emitting Latency Test:** Profile `TradeEvent` travel time from master queue to slave execution layer.

## Part 3: Database and Persistence (Phases 21-30)
21. **Phase 21: Data Types & Schemas:** Review `app/core/trade_types.py` for strict typing, Pydantic validation, and data consistency.
22. **Phase 22: Database Models & Migrations:** Audit `app/persistence/models.py` for optimal SQLite schema design, indexing, and foreign key constraints.
23. **Phase 23: Database Connection & Query Optimization:** Review `app/persistence/database.py` for connection pooling, transaction management, and query efficiency.
24. **Phase 24: WAL Mode Efficacy:** Verify `PRAGMA journal_mode=WAL` is active and handles multiple async writes effectively without locking.
25. **Phase 25: State Recovery & Persistence:** Audit `app/persistence/state_recovery.py` for flawless system restarts without data loss or duplicate trades.
26. **Phase 26: Orphaned Trade Handling:** Validate that trades closed externally on MT5 mobile apps are correctly marked 'orphaned' by the system.
27. **Phase 27: Credential Security:** Review `app/persistence/credentials.py` for secure storage, symmetric encryption (Fernet), and access control of MT5 credentials.
28. **Phase 28: Settings Storage:** Ensure dynamic config updates persist across daemon reboots safely.
29. **Phase 29: File Permissions Audit:** Verify `credentials.json` and `.key` logic restrict read/write access successfully on OS layer.
30. **Phase 30: History Pagination Audit:** Validate large trade histories load efficiently from SQLite using limits and offsets.

## Part 4: API and Network Comm (Phases 31-40)
31. **Phase 31: API Routing - Accounts Management:** Audit `app/api/routes_accounts.py` for robust CRUD operations, input validation, and proper error responses.
32. **Phase 32: API Routing - Trading Operations:** Audit `app/api/routes_trading.py` for secure execution endpoints, rate limiting, and parameter validation.
33. **Phase 33: API Routing - Dashboard Data:** Review `app/api/routes_dashboard.py` for efficient data aggregation and caching mechanisms.
34. **Phase 34: API Routing - History & Reporting:** Audit `app/api/routes_history.py` for accurate historical data fetching, pagination, and timezone handling.
35. **Phase 35: Server-Sent Events (SSE) Stream:** Audit `app/api/routes_sse.py` for memory leaks, connection handling, and broadcasting efficiency.
36. **Phase 36: FastAPI Dependency Injection:** Review `app/api/deps.py` for correct dependency resolution, lifespan state management (`app_state`), and singleton usage.
37. **Phase 37: Networking Utilities:** Audit `app/utils/networking.py` for secure internal comms, LAN IP exposure, and potential vulnerabilities.
38. **Phase 38: Firewall Check Tooling:** Verify Windows `netsh` logic executes correctly without hanging the async event loop.
39. **Phase 39: Websocket/SSE Connection Resiliency:** Review frontend/backend reconnection logic for dropped SSE streams or temporary network failures.
40. **Phase 40: Logging & Auditing Framework:** Review `app/utils/logging_config.py` for adequate log levels, rotation, formatting, and sensitive data masking.

## Part 5: Frontend and UX Resiliency (Phases 41-50)
41. **Phase 41: Frontend Reactivity (Alpine.js):** Audit Alpine.js components in `app/ui/templates` for state consistency, performance, and memory management.
42. **Phase 42: Frontend Styling (Tailwind CSS):** Review Tailwind implementation for responsive design consistency, accessibility, and optimal asset bundling.
43. **Phase 43: HTML5 Semantics & Structure:** Audit Jinja2 templates for correct HTML5 structure, SEO (if applicable), and layout robustness.
44. **Phase 44: HTMX Integration:** Review dynamic HTML fragment loading for performance and seamless user experience without full page reloads.
45. **Phase 45: UI Data Grid & Live Quotes:** Audit the quotes grid for rendering performance under high-frequency updates and rapid spread changes.
46. **Phase 46: Manual Intervention Flows:** Test and audit the Trading Widget for manual order placement, limit orders, and instant execution reliability.
47. **Phase 47: Keyboard Shortcuts Integration:** Verify `Shift+B` and `Shift+S` implementation for focus handling, debouncing, and accidental trigger prevention.
48. **Phase 48: Error Handling & User Feedback:** Audit toast notifications, error modals, and loading states for clarity and responsiveness.
49. **Phase 49: Cross-Browser Mobile View:** Ensure layout gracefully scales down to iOS/Android dimensions without breaking tables.
50. **Phase 50: Final Audit Report & Submission:** Compile all bug findings into a comprehensive patch and submit the final, deeply debugged codebase.
