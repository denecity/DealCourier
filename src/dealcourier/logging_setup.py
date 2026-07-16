"""Logging configuration with file rotation and console handler."""

import logging
import logging.handlers
from pathlib import Path


def setup_logging(log_file: str = "logs/dealcourier.log", level: int = logging.INFO) -> None:
    """Set up logging with file rotation and console handlers.

    The web dashboard reads live log lines directly from `log_file`
    (see ``dealcourier.web.routers.logs``), so no database handler is
    attached here. Writing one log row per record to SQLite caused
    lock contention with the SSE reader during long, low-frequency
    scrape phases (e.g. ricardo's 30s inter-request delay), which
    silently dropped log entries from the web UI while the console
    kept working.
    """
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(level)

    # Clear existing handlers
    root.handlers.clear()

    # File handler with daily rotation
    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_path,
        when="midnight",
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    # Quiet noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
