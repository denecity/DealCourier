"""Prompt template management."""

import logging
from datetime import datetime

from jinja2 import Template
from sqlalchemy import select

from dealcourier.db.engine import get_session
from dealcourier.db.models import Prompt

logger = logging.getLogger("dealcourier.ai.prompts")

# Default prompts seeded on first run
DEFAULT_PROMPTS = [
    {
        "name": "search_generation",
        "description": "Generates search term variations for marketplace coverage",
        "system_prompt": (
            "You are a marketplace search expert. Generate creative variations of search "
            "terms to maximize coverage on Swiss marketplaces like tutti.ch, ricardo.ch, "
            "and anibis.ch. Mix German and English terms. Include brand names, model "
            "variations, common misspellings, and colloquial terms."
        ),
        "user_prompt_template": (
            "Generate search term variations for: {{ name }}\n\n"
            "{% if specific_prompt %}Specific terms guidance: {{ specific_prompt }}{% endif %}\n"
            "{% if general_prompt %}General terms guidance: {{ general_prompt }}{% endif %}\n\n"
            "Generate {{ specific_count }} specific search terms and {{ general_count }} general search terms.\n\n"
            "Respond with JSON only:\n"
            '{"specific_search_terms": ["term1", "term2", ...], "general_search_terms": ["term1", "term2", ...]}'
        ),
        "response_schema": {
            "type": "object",
            "properties": {
                "specific_search_terms": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "general_search_terms": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
        },
        "model": "",
    },
    {
        "name": "listing_evaluation",
        "description": "Evaluates marketplace listings for value, components, and custom filters in a single pass",
        "system_prompt": (
            "You are a used marketplace expert specializing in the Swiss market. "
            "Your job is to estimate the fair market value of listings in CHF and "
            "apply any provided filters. Consider condition, included components, "
            "current market trends, and typical Swiss used-market pricing. "
            "Be precise and conservative. Always return valid JSON with all "
            "required fields. estimated_value MUST be a positive integer (whole "
            "number in CHF, never null, never a string)."
        ),
        "user_prompt_template": (
            "Evaluate this marketplace listing:\n\n"
            "Title: {{ title }}\n"
            "Description: {{ description }}\n"
            "{% if product_context %}Known product data: {{ product_context }}{% endif %}\n"
            "{% if eval_hint %}\nEvaluation hint: {{ eval_hint }}\n{% endif %}\n"
            "{% if filters %}"
            "Apply ALL of the following filters and include results in your response:\n"
            "{% for f in filters %}"
            "- filter_{{ loop.index }}: {{ f }}\n"
            "{% endfor %}\n"
            "{% endif %}"
            "Respond ONLY with a JSON object, no markdown:\n"
            "{\n"
            '  "estimated_value": <int, CHF, must be > 0>,\n'
            '  "confidence": <float 0.0-1.0>,\n'
            '  "reasoning": "<one sentence>",\n'
            '  "components": ["<part1>", "<part2>"],\n'
            '  "component_values": [<int>, <int>]'
            "{% if filters %},\n"
            '  "filters": {\n'
            "{% for f in filters %}"
            '    "filter_{{ loop.index }}": {"passed": <bool>, "reason": "<why>"}'
            "{% if not loop.last %},{% endif %}\n"
            "{% endfor %}"
            "  }"
            "{% endif %}\n"
            "}"
        ),
        "response_schema": {
            "type": "object",
            "required": ["estimated_value", "confidence", "reasoning"],
            "properties": {
                "reasoning": {"type": "string"},
                "estimated_value": {"type": "integer", "minimum": 1},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "components": {"type": "array", "items": {"type": "string"}},
                "component_values": {"type": "array", "items": {"type": "integer"}},
                "filters": {"type": "object"},
            },
        },
        "model": "",
    },
]


def seed_default_prompts() -> None:
    """Insert or update default prompts."""
    session = get_session()
    try:
        for prompt_data in DEFAULT_PROMPTS:
            existing = session.execute(
                select(Prompt).where(Prompt.name == prompt_data["name"])
            ).scalar_one_or_none()

            if existing is None:
                prompt = Prompt(**prompt_data)
                session.add(prompt)
                logger.info(f"Seeded default prompt: {prompt_data['name']}")
            else:
                # Update existing prompt to latest defaults
                for key, value in prompt_data.items():
                    if key != "name":
                        setattr(existing, key, value)
                logger.info(f"Updated default prompt: {prompt_data['name']}")

        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to seed prompts: {e}")
    finally:
        session.close()


def get_prompt(name: str) -> Prompt | None:
    """Load a prompt template by name."""
    session = get_session()
    try:
        return session.execute(
            select(Prompt).where(Prompt.name == name)
        ).scalar_one_or_none()
    finally:
        session.close()


def render_prompt(template_str: str, **kwargs) -> str:
    """Render a Jinja2 prompt template with the given variables."""
    template = Template(template_str)
    return template.render(**kwargs)
