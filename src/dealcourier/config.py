"""Configuration loading and validation."""

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv


@dataclass
class Config:
    # ─── Secrets ──────────────────────────────────────
    # A single API key + base URL for any OpenAI-compatible backend.
    # Examples:
    #   OpenAI:      base_url = "https://api.openai.com/v1"
    #   OpenRouter:  base_url = "https://openrouter.ai/api/v1"
    #   DeepSeek:    base_url = "https://api.deepseek.com/v1"
    api_key: str = ""
    base_url: str = "https://openrouter.ai/api/v1"
    discord_webhook_url: str = ""

    # ─── Server ──────────────────────────────────────
    host: str = "127.0.0.1"
    port: int = 8000
    database_path: str = "data/dealcourier.db"
    log_file: str = "logs/dealcourier.log"
    log_level: str = "INFO"

    # ─── Scheduler ──────────────────────────────────────
    scrape_interval_minutes: int = 60
    term_regeneration_interval_hours: int = 24
    run_scrape_on_start: bool = False

    # ─── AI / Evaluation ──────────────────────────────────────
    # All calls go to the same OpenAI-compatible backend (api_key / base_url).
    # `default_model` is used for the high-volume listing-evaluation pass.
    # `terms_model` optionally routes the low-frequency search-term generation
    # to a different (e.g. smarter) model on the same backend. Leave empty to
    # fall back to `default_model`.
    default_model: str = "deepseek-v4-flash"
    terms_model: str = "z-ai/glm-5.2"

    ai_max_tokens: int = 4096
    ai_request_timeout_seconds: int = 60
    batch_poll_interval_seconds: int = 10
    batch_max_wait_seconds: int = 3600

    # ─── Scraper: Global ──────────────────────────────────────
    request_timeout_seconds: int = 30
    request_delay_seconds: float = 1.0

    # ─── Scraper: Tutti ──────────────────────────────────────
    tutti_delay_seconds: float = 2.0
    tutti_max_terms: int = 0        # 0 = no limit
    tutti_results_per_page: int = 30

    # ─── Scraper: Ricardo ──────────────────────────────────────
    ricardo_delay_seconds: float = 30.0
    ricardo_max_terms: int = 0      # 0 = no limit
    ricardo_auction_max_hours: float = 3.0   # skip auctions ending later than this
    ricardo_include_auctions: bool = True     # set False to skip ALL auctions
    ricardo_include_buy_now: bool = True

    # ─── Scraper: Anibis ──────────────────────────────────────
    anibis_delay_seconds: float = 2.0
    anibis_max_terms: int = 0       # 0 = no limit

    # ─── Notifications ──────────────────────────────────────
    discord_enabled: bool = True
    discord_min_value_factor: float = 0.0   # only notify if value_factor >= this
    discord_min_profit: int = 0             # only notify if profit >= this (CHF)
    discord_max_distance_km: float = 0.0    # 0 = no limit

    # ─── Filters ──────────────────────────────────────
    global_min_price: int = 0
    global_max_price: int = 0       # 0 = no limit
    skip_free_listings: bool = True


_config: Config | None = None


def _resolve_env_vars(value: str) -> str:
    """Resolve ${ENV_VAR} references in config values."""
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        env_var = value[2:-1]
        return os.environ.get(env_var, "")
    return value


def load_config(config_path: str | None = None) -> Config:
    """Load configuration from YAML file and environment variables."""
    global _config

    load_dotenv()

    cfg = Config()

    # Try loading YAML config
    if config_path is None:
        config_path = os.environ.get("DEALCOURIER_CONFIG", "config.yaml")

    path = Path(config_path)
    if path.exists():
        with open(path) as f:
            data = yaml.safe_load(f) or {}

        for key, value in data.items():
            if hasattr(cfg, key):
                resolved = _resolve_env_vars(value) if isinstance(value, str) else value
                # Cast to the correct type based on the default
                default = getattr(cfg, key)
                try:
                    if isinstance(default, bool):
                        setattr(cfg, key, bool(resolved))
                    elif isinstance(default, int):
                        setattr(cfg, key, int(resolved))
                    elif isinstance(default, float):
                        setattr(cfg, key, float(resolved))
                    else:
                        setattr(cfg, key, resolved)
                except (ValueError, TypeError):
                    setattr(cfg, key, resolved)

    # Environment variables always take precedence
    env_overrides = {
        "API_KEY": "api_key",
        "BASE_URL": "base_url",
        "DISCORD_WEBHOOK_URL": "discord_webhook_url",
        "DEALCOURIER_HOST": "host",
        "DEALCOURIER_PORT": "port",
        "DEALCOURIER_DB": "database_path",
    }
    for env_var, attr in env_overrides.items():
        env_val = os.environ.get(env_var)
        if env_val:
            current = getattr(cfg, attr)
            if isinstance(current, int):
                setattr(cfg, attr, int(env_val))
            else:
                setattr(cfg, attr, env_val)

    _config = cfg
    return cfg


def get_config() -> Config:
    """Get the current config, loading if needed."""
    if _config is None:
        return load_config()
    return _config
