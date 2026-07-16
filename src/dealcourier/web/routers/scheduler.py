"""Schedule management API."""

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select, func, desc

from dealcourier.db.engine import get_session
from dealcourier.db.models import ScrapeRun
from dealcourier.scheduler.runner import (
    get_scheduler_status,
    trigger_scrape_now,
    update_scrape_interval,
)

router = APIRouter(tags=["scheduler"])


class IntervalUpdate(BaseModel):
    minutes: int


@router.get("/scheduler/status")
def scheduler_status():
    return get_scheduler_status()


@router.post("/scheduler/trigger")
def trigger_scrape():
    trigger_scrape_now()
    return {"status": "triggered"}


@router.put("/scheduler/interval")
def set_interval(data: IntervalUpdate):
    update_scrape_interval(data.minutes)
    return {"status": "updated", "minutes": data.minutes}


@router.get("/scrape-runs")
def list_scrape_runs(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    session = get_session()
    try:
        total = session.execute(select(func.count(ScrapeRun.id))).scalar() or 0
        runs = session.execute(
            select(ScrapeRun)
            .order_by(desc(ScrapeRun.started_at))
            .offset((page - 1) * per_page)
            .limit(per_page)
        ).scalars().all()

        return {
            "total": total,
            "page": page,
            "per_page": per_page,
            "runs": [
                {
                    "id": r.id,
                    "started_at": r.started_at.isoformat() if r.started_at else None,
                    "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                    "status": r.status,
                    "search_item_id": r.search_item_id,
                    "listings_found": r.listings_found,
                    "listings_new": r.listings_new,
                    "listings_evaluated": r.listings_evaluated,
                    "listings_passed": r.listings_passed,
                    "notifications_sent": r.notifications_sent,
                    "error_message": r.error_message,
                }
                for r in runs
            ],
        }
    finally:
        session.close()


@router.get("/scrape-runs/{run_id}")
def get_scrape_run(run_id: int):
    session = get_session()
    try:
        run = session.get(ScrapeRun, run_id)
        if run is None:
            return {"error": "Not found"}
        return {
            "id": run.id,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "status": run.status,
            "search_item_id": run.search_item_id,
            "listings_found": run.listings_found,
            "listings_new": run.listings_new,
            "listings_evaluated": run.listings_evaluated,
            "listings_passed": run.listings_passed,
            "notifications_sent": run.notifications_sent,
            "error_message": run.error_message,
        }
    finally:
        session.close()
