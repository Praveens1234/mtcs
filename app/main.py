"""FastAPI application — main entry point with lifespan management."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse

from app.config import settings
from app.utils.logging_config import setup_logging
from app.api.deps import app_state

# Route imports
from app.api.routes_accounts import router as accounts_router
from app.api.routes_trading import router as trading_router
from app.api.routes_dashboard import router as dashboard_router
from app.api.routes_history import router as history_router
from app.api.routes_settings import router as settings_router
from app.api.routes_sse import router as sse_router

logger = logging.getLogger("mtcs.main")

# Template and static paths
UI_DIR = Path(__file__).parent / "ui"
TEMPLATE_DIR = UI_DIR / "templates"
STATIC_DIR = UI_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown."""
    # Startup
    settings.ensure_dirs()
    setup_logging(settings.LOG_DIR, settings.DEBUG)
    logger.info("=" * 60)
    logger.info("MT5 Copy Trading System starting...")
    logger.info(f"Server: {settings.HOST}:{settings.PORT}")
    logger.info("=" * 60)

    await app_state.initialize()

    yield

    # Shutdown
    logger.info("Shutting down...")
    await app_state.shutdown()
    logger.info("Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="MT5 Copy Trading System",
    description="Production MT5 copy trading with mobile-first web UI",
    version="1.0.0",
    lifespan=lifespan,
)

# Mount static files
STATIC_DIR.mkdir(parents=True, exist_ok=True)
(STATIC_DIR / "css").mkdir(exist_ok=True)
(STATIC_DIR / "js").mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Templates
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

# Include API routers
app.include_router(accounts_router)
app.include_router(trading_router)
app.include_router(dashboard_router)
app.include_router(history_router)
app.include_router(settings_router)
app.include_router(sse_router)


# ---------- Page Routes ----------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Main page — redirect to dashboard or setup."""
    master = None
    if app_state.db:
        master = await app_state.recovery.get_master_account()

    if master:
        return templates.TemplateResponse("trade.html", {
            "request": request,
            "active_tab": "dashboard",
            "network": app_state.network_info,
        })
    else:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "active_tab": "setup",
            "network": app_state.network_info,
        })


@app.get("/quotes", response_class=HTMLResponse)
async def quotes_page(request: Request):
    return templates.TemplateResponse("quotes.html", {
        "request": request,
        "active_tab": "quotes",
        "network": app_state.network_info,
    })


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    return templates.TemplateResponse("trade.html", {
        "request": request,
        "active_tab": "dashboard",
        "network": app_state.network_info,
    })


@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    return templates.TemplateResponse("history.html", {
        "request": request,
        "active_tab": "history",
        "network": app_state.network_info,
    })


@app.get("/accounts", response_class=HTMLResponse)
async def accounts_page(request: Request):
    return templates.TemplateResponse("accounts.html", {
        "request": request,
        "active_tab": "accounts",
        "network": app_state.network_info,
    })


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "active_tab": "settings",
        "network": app_state.network_info,
    })
