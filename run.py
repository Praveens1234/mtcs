"""Entry point — run the application."""

import multiprocessing
import uvicorn
from app.config import settings


def main():
    """Launch the MTCS server."""
    print("=" * 60)
    print("  MT5 Copy Trading System v2.0")
    print(f"  Starting on http://{settings.HOST}:{settings.PORT}")
    print("  Architecture: Multi-Process (1 worker per account)")
    print("=" * 60)

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info",
    )


if __name__ == "__main__":
    # Required for Windows multiprocessing
    multiprocessing.freeze_support()
    try:
        multiprocessing.set_start_method("spawn")
    except RuntimeError:
        pass  # Already set
    main()
