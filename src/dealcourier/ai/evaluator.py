"""Listing evaluation pipeline using an OpenAI-compatible chat API."""

import logging
from datetime import datetime

from sqlalchemy import select

from dealcourier.ai.client import single_message
from dealcourier.ai.prompts import get_prompt, render_prompt
from dealcourier.config import get_config
from dealcourier.db.engine import get_session
from dealcourier.db.models import Listing, SearchItem
from dealcourier.knowledge.products import get_product_context, update_product_knowledge

logger = logging.getLogger("dealcourier.ai.evaluator")


def generate_search_terms(search_item: SearchItem) -> list[str]:
    """Generate search term variations for a search item.

    Uses `terms_model` when set, so search-term generation can target a
    different (e.g. smarter) model than the high-volume listing-eval pass,
    while still using the same OpenAI-compatible backend.
    """
    prompt = get_prompt("search_generation")
    if prompt is None:
        logger.error("search_generation prompt not found")
        return [search_item.name]

    user_content = render_prompt(
        prompt.user_prompt_template,
        name=search_item.name,
        specific_prompt=search_item.search_terms_specific_prompt or "",
        general_prompt=search_item.search_terms_general_prompt or "",
        specific_count=search_item.search_terms_specific_count,
        general_count=search_item.search_terms_general_count,
    )

    cfg = get_config()
    terms_model = cfg.terms_model or None
    if terms_model:
        logger.info(
            f"Generating terms for '{search_item.name}' via "
            f"model={terms_model or cfg.default_model}"
        )

    result = single_message(
        system=prompt.system_prompt,
        user_content=user_content,
        model=terms_model,
    )

    if result is None:
        logger.warning(f"Failed to generate search terms for '{search_item.name}'")
        return [search_item.name]

    specific = result.get("specific_search_terms", [])
    general = result.get("general_search_terms", [])
    terms = [search_item.name] + specific + general

    # Cache in DB
    session = get_session()
    try:
        item = session.get(SearchItem, search_item.id)
        if item:
            item.cached_search_terms = terms
            item.terms_generated_at = datetime.utcnow()
            session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to cache search terms: {e}")
    finally:
        session.close()

    logger.info(f"Generated {len(terms)} search terms for '{search_item.name}'")
    return terms


def _build_eval_request(listing: Listing, session) -> dict | None:
    """Build the prompt data for evaluating a single listing."""
    prompt = get_prompt("listing_evaluation")
    if prompt is None:
        return None

    product_context = get_product_context(listing.title, listing.description or "")

    filters = []
    eval_hint = ""
    knowledge_base = ""
    if listing.search_item_id:
        search_item = session.get(SearchItem, listing.search_item_id)
        if search_item:
            if search_item.custom_filters:
                filters = search_item.custom_filters
            if search_item.eval_hint:
                eval_hint = search_item.eval_hint
            if search_item.knowledge_base:
                knowledge_base = search_item.knowledge_base

    user_content = render_prompt(
        prompt.user_prompt_template,
        title=listing.title,
        description=listing.description or "",
        product_context=product_context,
        eval_hint=eval_hint,
        filters=filters,
    )

    # Place knowledge_base at the very start of the system prompt so it sits
    # in the stable prefix of every request for this search item. Backends with
    # automatic prefix caching (OpenAI, OpenRouter, DeepSeek, ...) will serve
    # it at the cheap cache-hit rate across all listings for the same item.
    if knowledge_base:
        system = (
            "<knowledge_base>\n"
            + knowledge_base.strip()
            + "\n</knowledge_base>\n\n"
            + prompt.system_prompt
        )
    else:
        system = prompt.system_prompt

    return {
        "system": system,
        "user_content": user_content,
    }


def _parse_int(value, fallback: int = 0) -> int:
    """Robustly parse a value to int. Handles None, strings, floats."""
    if value is None:
        return fallback
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return fallback


def _parse_float(value, fallback: float = 0.0) -> float:
    """Robustly parse a value to float."""
    if value is None:
        return fallback
    try:
        return float(value)
    except (ValueError, TypeError):
        return fallback


def _apply_eval_result(listing: Listing, data: dict, session) -> bool:
    """Apply parsed evaluation result to a listing and run all filters.

    This combines the AI response parsing with numeric threshold checks
    and custom filter validation in a single pass. Returns True on success.
    """
    try:
        listing.evaluated = True
        listing.eval_reasoning = data.get("reasoning", "")
        listing.estimated_value = _parse_int(data.get("estimated_value"), 0)
        listing.confidence = _parse_float(data.get("confidence"), 0.0)
        listing.components = data.get("components", [])
        listing.component_values = data.get("component_values", [])
        listing.filter_results = data.get("filters", {})

        # Compute value factor
        if listing.price > 0 and listing.estimated_value > 0:
            listing.value_factor = round(listing.estimated_value / listing.price, 2)
        else:
            listing.value_factor = None

        # Update product knowledge base
        components = data.get("components", [])
        comp_values = data.get("component_values", [])
        if components and comp_values:
            update_product_knowledge(components, comp_values)

        # ── Apply all filters in one pass ─────────────────────────
        passed = True

        # 1. Numeric thresholds from SearchItem
        search_item = None
        if listing.search_item_id:
            search_item = session.get(SearchItem, listing.search_item_id)

        if search_item:
            if search_item.min_price is not None and listing.price < search_item.min_price:
                passed = False
                logger.debug(f"Listing {listing.id} below min_price {search_item.min_price}")
            if search_item.max_price is not None and listing.price > search_item.max_price:
                passed = False
                logger.debug(f"Listing {listing.id} above max_price {search_item.max_price}")

            if search_item.min_profit is not None and listing.estimated_value:
                profit = listing.estimated_value - listing.price
                if profit < search_item.min_profit:
                    passed = False
                    logger.debug(
                        f"Listing {listing.id} profit {profit} below min_profit "
                        f"{search_item.min_profit}"
                    )

            if search_item.min_value_factor is not None and listing.value_factor is not None:
                if listing.value_factor < search_item.min_value_factor:
                    passed = False
                    logger.debug(
                        f"Listing {listing.id} factor {listing.value_factor} below "
                        f"min_value_factor {search_item.min_value_factor}"
                    )

        # 2. AI-evaluated custom filters — ALL must explicitly pass
        if listing.filter_results and isinstance(listing.filter_results, dict):
            for key, result in listing.filter_results.items():
                if isinstance(result, dict) and not result.get("passed", False):
                    passed = False
                    logger.info(
                        f"Listing {listing.id} failed filter '{key}': "
                        f"{result.get('reason', 'no reason')}"
                    )

        # 3. Verify all expected custom filters have results
        if search_item and search_item.custom_filters:
            expected = len(search_item.custom_filters)
            actual = len(listing.filter_results or {})
            if actual < expected:
                passed = False
                logger.info(
                    f"Listing {listing.id}: only {actual}/{expected} custom filters evaluated"
                )

        listing.passed_filters = passed
        return True

    except (ValueError, TypeError, KeyError) as e:
        logger.warning(f"Failed to process result for listing {listing.id}: {e}")
        return False


def _prefilter_hard(listing: Listing, search_item: SearchItem) -> tuple[bool, str | None]:
    """Apply numeric thresholds that don't require AI judgment.

    Currently just price bounds — these are the only thresholds whose outcome
    is fully determined by listing fields already in hand. Profit and
    value-factor thresholds depend on the AI's estimated_value, so they stay
    in _apply_eval_result.

    Returns (passed, rejection_reason). passed=False means skip the AI call
    entirely and mark the listing as filtered.
    """
    if search_item.min_price is not None and listing.price < search_item.min_price:
        return False, (
            f"price {listing.price} CHF below min_price "
            f"{search_item.min_price} CHF"
        )
    if search_item.max_price is not None and listing.price > search_item.max_price:
        return False, (
            f"price {listing.price} CHF above max_price "
            f"{search_item.max_price} CHF"
        )
    return True, None


def evaluate_listing_single(listing_id: int) -> bool:
    """Evaluate a single listing using the realtime API.
    Runs value estimation, custom filters, and threshold checks in one step.
    Returns True if a decision was reached (either prefiltered or AI-evaluated)."""
    session = get_session()
    try:
        listing = session.get(Listing, listing_id)
        if listing is None or listing.evaluated:
            return False

        # Hard-filter pre-check: if the listing can't pass numeric thresholds
        # regardless of what the AI would estimate, skip the API call entirely
        # and mark as filtered. Saves tokens on obviously-out-of-range items.
        search_item = None
        if listing.search_item_id:
            search_item = session.get(SearchItem, listing.search_item_id)

        if search_item is not None:
            ok, reason = _prefilter_hard(listing, search_item)
            if not ok:
                listing.evaluated = True
                listing.passed_filters = False
                listing.eval_reasoning = f"Prefiltered: {reason}"
                session.commit()
                logger.info(
                    f"[PREFILTERED] Listing {listing.id} '{listing.title}': {reason}"
                )
                return True

        req = _build_eval_request(listing, session)
        if req is None:
            logger.error("listing_evaluation prompt not found")
            return False

        result = single_message(
            system=req["system"],
            user_content=req["user_content"],
        )

        if result is None:
            logger.warning(f"Eval failed for listing {listing.id}")
            return False

        success = _apply_eval_result(listing, result, session)
        if success:
            session.commit()
            status = "PASSED" if listing.passed_filters else "FILTERED"
            logger.info(
                f"[{status}] Listing {listing.id} '{listing.title}' "
                f"-> {listing.estimated_value} CHF "
                f"({listing.value_factor}x, confidence={listing.confidence})"
            )
        return success

    except Exception as e:
        session.rollback()
        logger.error(f"Evaluation failed for listing {listing_id}: {e}")
        return False
    finally:
        session.close()


def evaluate_listings(listing_ids: list[int]) -> int:
    """Evaluate multiple listings one-by-one using the realtime API.
    Each call does value estimation + filtering in a single prompt.
    Returns count of successfully evaluated listings."""
    if not listing_ids:
        return 0

    evaluated = 0
    total = len(listing_ids)
    logger.info(f"Starting evaluation of {total} listings")

    for i, lid in enumerate(listing_ids):
        if evaluate_listing_single(lid):
            evaluated += 1
        if (i + 1) % 10 == 0 or (i + 1) == total:
            logger.info(f"Eval progress: {i+1}/{total} processed, {evaluated} succeeded")

    logger.info(f"Evaluation complete: {evaluated}/{total} succeeded")
    return evaluated
