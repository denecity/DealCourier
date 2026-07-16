"""Search configuration CRUD API."""

import json
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from dealcourier.db.engine import get_session
from dealcourier.db.models import SearchItem, Setting
from dealcourier.ai.evaluator import generate_search_terms

ALL_PLATFORMS = ["tutti", "ricardo", "anibis"]

router = APIRouter(tags=["config"])


class SearchItemCreate(BaseModel):
    name: str
    enabled: bool = True
    platforms: list[str] = ["tutti"]
    search_terms_specific_prompt: str | None = None
    search_terms_general_prompt: str | None = None
    search_terms_specific_count: int = 50
    search_terms_general_count: int = 50
    min_price: int | None = None
    max_price: int | None = None
    min_profit: int | None = None
    min_value_factor: float | None = None
    eval_hint: str | None = None
    knowledge_base: str | None = None
    custom_filters: list[str] | None = None


class SearchItemUpdate(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    platforms: list[str] | None = None
    search_terms_specific_prompt: str | None = None
    search_terms_general_prompt: str | None = None
    search_terms_specific_count: int | None = None
    search_terms_general_count: int | None = None
    min_price: int | None = None
    max_price: int | None = None
    min_profit: int | None = None
    min_value_factor: float | None = None
    eval_hint: str | None = None
    knowledge_base: str | None = None
    custom_filters: list[str] | None = None


@router.get("/search-items")
def list_search_items():
    session = get_session()
    try:
        items = session.execute(
            select(SearchItem).order_by(SearchItem.id)
        ).scalars().all()
        return [_item_to_dict(item) for item in items]
    finally:
        session.close()


@router.post("/search-items")
def create_search_item(data: SearchItemCreate):
    session = get_session()
    try:
        item = SearchItem(
            name=data.name,
            enabled=data.enabled,
            platforms=data.platforms,
            search_terms_specific_prompt=data.search_terms_specific_prompt,
            search_terms_general_prompt=data.search_terms_general_prompt,
            search_terms_specific_count=data.search_terms_specific_count,
            search_terms_general_count=data.search_terms_general_count,
            min_price=data.min_price,
            max_price=data.max_price,
            min_profit=data.min_profit,
            min_value_factor=data.min_value_factor,
            eval_hint=data.eval_hint,
            knowledge_base=data.knowledge_base,
            custom_filters=data.custom_filters,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(item)
        session.commit()
        session.refresh(item)
        return _item_to_dict(item)
    except Exception as e:
        session.rollback()
        return {"error": str(e)}
    finally:
        session.close()


@router.put("/search-items/{item_id}")
def update_search_item(item_id: int, data: SearchItemUpdate):
    session = get_session()
    try:
        item = session.get(SearchItem, item_id)
        if item is None:
            return {"error": "Not found"}

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(item, field, value)
        item.updated_at = datetime.utcnow()

        session.commit()
        session.refresh(item)
        return _item_to_dict(item)
    except Exception as e:
        session.rollback()
        return {"error": str(e)}
    finally:
        session.close()


@router.delete("/search-items/{item_id}")
def delete_search_item(item_id: int):
    session = get_session()
    try:
        item = session.get(SearchItem, item_id)
        if item is None:
            return {"error": "Not found"}
        session.delete(item)
        session.commit()
        return {"status": "deleted"}
    except Exception as e:
        session.rollback()
        return {"error": str(e)}
    finally:
        session.close()


@router.post("/search-items/{item_id}/regenerate-terms")
def regenerate_terms(item_id: int):
    session = get_session()
    try:
        item = session.get(SearchItem, item_id)
        if item is None:
            return {"error": "Not found"}
        terms = generate_search_terms(item)
        return {"terms": terms, "count": len(terms)}
    finally:
        session.close()


@router.get("/config")
def get_runtime_config():
    from dealcourier.config import get_config
    from dataclasses import asdict

    cfg = get_config()
    data = asdict(cfg)
    # Redact secrets
    data["api_key"] = "****" if cfg.api_key else "(not set)"
    data["discord_webhook_url"] = "****" if cfg.discord_webhook_url else "(not set)"
    return data


@router.get("/shops")
def get_enabled_shops():
    """Get global shop enable/disable settings."""
    session = get_session()
    try:
        setting = session.get(Setting, "enabled_shops")
        if setting:
            enabled = json.loads(setting.value)
        else:
            enabled = ALL_PLATFORMS[:]
        return {p: (p in enabled) for p in ALL_PLATFORMS}
    finally:
        session.close()


class ShopSettings(BaseModel):
    tutti: bool = True
    ricardo: bool = True
    anibis: bool = True


@router.put("/shops")
def update_enabled_shops(data: ShopSettings):
    """Update global shop enable/disable settings."""
    session = get_session()
    try:
        enabled = [p for p in ALL_PLATFORMS if getattr(data, p)]
        setting = session.get(Setting, "enabled_shops")
        if setting:
            setting.value = json.dumps(enabled)
        else:
            setting = Setting(key="enabled_shops", value=json.dumps(enabled))
            session.add(setting)
        session.commit()
        return {p: (p in enabled) for p in ALL_PLATFORMS}
    except Exception as e:
        session.rollback()
        return {"error": str(e)}
    finally:
        session.close()


def get_globally_enabled_shops() -> list[str]:
    """Return list of globally enabled shop names. Used by scheduler."""
    session = get_session()
    try:
        setting = session.get(Setting, "enabled_shops")
        if setting:
            return json.loads(setting.value)
        return ALL_PLATFORMS[:]
    finally:
        session.close()


# ─── EVAL ALL ──────────────────────────────────────

@router.post("/eval-all")
def eval_all_unevaluated():
    """Trigger evaluation of all unevaluated listings in the database."""
    import threading
    from sqlalchemy import select, func
    from dealcourier.db.models import Listing

    session = get_session()
    try:
        count = session.execute(
            select(func.count(Listing.id)).where(Listing.evaluated == False)
        ).scalar() or 0

        if count == 0:
            return {"status": "nothing_to_do", "count": 0}

        ids = [
            row[0] for row in session.execute(
                select(Listing.id).where(Listing.evaluated == False)
            ).all()
        ]
    finally:
        session.close()

    def _run_eval():
        import logging
        logger = logging.getLogger("dealcourier.scheduler")
        logger.info(f"Eval-all started: {len(ids)} listings")
        from dealcourier.ai.evaluator import evaluate_listings
        from dealcourier.notifications.discord import send_notifications_for_passed

        evaluated = evaluate_listings(ids)
        sent = send_notifications_for_passed(ids)
        logger.info(
            f"Eval-all complete: {evaluated} evaluated, {sent} notified"
        )

    thread = threading.Thread(target=_run_eval, daemon=True)
    thread.start()

    return {"status": "started", "count": count}


def _item_to_dict(item: SearchItem) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "enabled": item.enabled,
        "platforms": item.platforms,
        "search_terms_specific_prompt": item.search_terms_specific_prompt,
        "search_terms_general_prompt": item.search_terms_general_prompt,
        "search_terms_specific_count": item.search_terms_specific_count,
        "search_terms_general_count": item.search_terms_general_count,
        "cached_search_terms": item.cached_search_terms,
        "terms_generated_at": item.terms_generated_at.isoformat() if item.terms_generated_at else None,
        "min_price": item.min_price,
        "max_price": item.max_price,
        "min_profit": item.min_profit,
        "min_value_factor": item.min_value_factor,
        "eval_hint": item.eval_hint,
        "knowledge_base": item.knowledge_base,
        "custom_filters": item.custom_filters,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }
