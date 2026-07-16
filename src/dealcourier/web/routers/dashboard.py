"""Listing browsing and filtering API."""

from datetime import datetime

from fastapi import APIRouter, Query
from sqlalchemy import select, func, desc, asc

from dealcourier.db.engine import get_session
from dealcourier.db.models import Listing, Product

router = APIRouter(tags=["dashboard"])


@router.get("/listings")
def list_listings(
    platform: str | None = None,
    search_item_id: int | None = None,
    passed: str | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    sort: str = "scraped_at",
    order: str = "desc",
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
):
    session = get_session()
    try:
        query = select(Listing)

        if platform:
            query = query.where(Listing.platform == platform)
        if search_item_id is not None:
            query = query.where(Listing.search_item_id == search_item_id)
        if passed == "true":
            query = query.where(Listing.passed_filters == True)
        elif passed == "false":
            query = query.where(Listing.passed_filters == False)
        if min_price is not None:
            query = query.where(Listing.price >= min_price)
        if max_price is not None:
            query = query.where(Listing.price <= max_price)

        # Sorting
        sort_col = getattr(Listing, sort, Listing.scraped_at)
        if order == "asc":
            query = query.order_by(asc(sort_col))
        else:
            query = query.order_by(desc(sort_col))

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = session.execute(count_query).scalar() or 0

        # Paginate
        query = query.offset((page - 1) * per_page).limit(per_page)
        listings = session.execute(query).scalars().all()

        return {
            "total": total,
            "page": page,
            "per_page": per_page,
            "listings": [_listing_to_dict(l) for l in listings],
        }
    finally:
        session.close()


@router.get("/listings/stats")
def listing_stats():
    session = get_session()
    try:
        total = session.execute(select(func.count(Listing.id))).scalar() or 0
        evaluated = session.execute(
            select(func.count(Listing.id)).where(Listing.evaluated == True)
        ).scalar() or 0
        passed = session.execute(
            select(func.count(Listing.id)).where(Listing.passed_filters == True)
        ).scalar() or 0
        notified = session.execute(
            select(func.count(Listing.id)).where(Listing.notified == True)
        ).scalar() or 0

        # Per platform
        platforms = {}
        for row in session.execute(
            select(Listing.platform, func.count(Listing.id))
            .group_by(Listing.platform)
        ).all():
            platforms[row[0]] = row[1]

        return {
            "total": total,
            "evaluated": evaluated,
            "passed": passed,
            "notified": notified,
            "by_platform": platforms,
        }
    finally:
        session.close()


@router.delete("/listings")
def delete_all_listings():
    """Delete all listings from the database."""
    session = get_session()
    try:
        count = session.execute(select(func.count(Listing.id))).scalar() or 0
        session.execute(Listing.__table__.delete())
        session.commit()
        return {"status": "deleted", "count": count}
    except Exception as e:
        session.rollback()
        return {"error": str(e)}
    finally:
        session.close()


@router.post("/listings/{listing_id}/unpass")
def unpass_listing(listing_id: int):
    """Manually mark a listing as filtered — used when the AI filter
    passed something it shouldn't have."""
    session = get_session()
    try:
        listing = session.get(Listing, listing_id)
        if listing is None:
            return {"error": "Not found"}
        listing.passed_filters = False
        session.commit()
        return {"status": "unpassed", "id": listing_id}
    except Exception as e:
        session.rollback()
        return {"error": str(e)}
    finally:
        session.close()


@router.get("/listings/{listing_id}")
def get_listing(listing_id: int):
    session = get_session()
    try:
        listing = session.get(Listing, listing_id)
        if listing is None:
            return {"error": "Not found"}, 404
        return _listing_to_dict(listing)
    finally:
        session.close()


@router.get("/products")
def list_products(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
):
    session = get_session()
    try:
        total = session.execute(select(func.count(Product.id))).scalar() or 0
        products = session.execute(
            select(Product)
            .order_by(desc(Product.last_updated))
            .offset((page - 1) * per_page)
            .limit(per_page)
        ).scalars().all()

        return {
            "total": total,
            "page": page,
            "per_page": per_page,
            "products": [
                {
                    "id": p.id,
                    "name": p.name,
                    "category": p.category,
                    "properties": p.properties,
                    "estimated_value": p.estimated_value,
                    "value_trend": p.value_trend,
                    "sample_count": p.sample_count,
                    "last_updated": p.last_updated.isoformat() if p.last_updated else None,
                }
                for p in products
            ],
        }
    finally:
        session.close()


@router.get("/products/{product_id}")
def get_product(product_id: int):
    session = get_session()
    try:
        product = session.get(Product, product_id)
        if product is None:
            return {"error": "Not found"}, 404
        return {
            "id": product.id,
            "name": product.name,
            "category": product.category,
            "properties": product.properties,
            "estimated_value": product.estimated_value,
            "value_trend": product.value_trend,
            "sample_count": product.sample_count,
            "last_updated": product.last_updated.isoformat() if product.last_updated else None,
        }
    finally:
        session.close()


def _listing_to_dict(listing: Listing) -> dict:
    return {
        "id": listing.id,
        "platform": listing.platform,
        "platform_id": listing.platform_id,
        "search_item_id": listing.search_item_id,
        "title": listing.title,
        "description": listing.description,
        "category": listing.category,
        "price": listing.price,
        "currency": listing.currency,
        "url": listing.url,
        "image_url": listing.image_url,
        "search_term": listing.search_term,
        "seller_name": listing.seller_name,
        "postcode": listing.postcode,
        "location": listing.location,
        "shipping_cost": listing.shipping_cost,
        "distance_km": listing.distance_km,
        "listed_at": listing.listed_at.isoformat() if listing.listed_at else None,
        "auction_end_at": listing.auction_end_at.isoformat() if listing.auction_end_at else None,
        "scraped_at": listing.scraped_at.isoformat() if listing.scraped_at else None,
        "evaluated": listing.evaluated,
        "eval_reasoning": listing.eval_reasoning,
        "estimated_value": listing.estimated_value,
        "value_factor": listing.value_factor,
        "confidence": listing.confidence,
        "components": listing.components,
        "component_values": listing.component_values,
        "filter_results": listing.filter_results,
        "passed_filters": listing.passed_filters,
        "notified": listing.notified,
        "notified_at": listing.notified_at.isoformat() if listing.notified_at else None,
    }
