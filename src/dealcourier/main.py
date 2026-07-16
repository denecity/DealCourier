"""DealCourier entry point -- starts scheduler and web server."""

import logging
import socket

import uvicorn

from dealcourier.config import load_config
from dealcourier.db.engine import init_db
from dealcourier.logging_setup import setup_logging
from dealcourier.ai.prompts import seed_default_prompts
from dealcourier.scheduler.runner import start_scheduler, stop_scheduler


def main():
    cfg = load_config()

    # Initialize database (creates tables if needed)
    init_db(cfg.database_path)

    # Set up logging (file + console + DB handler)
    setup_logging(cfg.log_file)

    logger = logging.getLogger("dealcourier")
    logger.info("DealCourier v2.0.0 starting up")

    # Seed default prompts
    seed_default_prompts()

    # Start the scheduler (logs the actual interval and its source)
    start_scheduler()

    # Start the web server (blocks)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as _s:
            _s.connect(("8.8.8.8", 80))
            lan_ip = _s.getsockname()[0]
    except Exception:
        lan_ip = cfg.host
    logger.info(f"Web dashboard: http://{lan_ip}:{cfg.port}")
    try:
        from dealcourier.web.app import app

        uvicorn.run(app, host=cfg.host, port=cfg.port, log_level="warning")
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        stop_scheduler()
        logger.info("DealCourier stopped")


if __name__ == "__main__":
    main()
