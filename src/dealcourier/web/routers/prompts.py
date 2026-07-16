"""Prompt template editing API."""

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from dealcourier.db.engine import get_session
from dealcourier.db.models import Prompt
from dealcourier.ai.client import single_message
from dealcourier.ai.prompts import render_prompt

router = APIRouter(tags=["prompts"])


class PromptUpdate(BaseModel):
    system_prompt: str | None = None
    user_prompt_template: str | None = None
    response_schema: dict | None = None
    description: str | None = None


class PromptTest(BaseModel):
    sample_data: dict


@router.get("/prompts")
def list_prompts():
    session = get_session()
    try:
        prompts = session.execute(
            select(Prompt).order_by(Prompt.name)
        ).scalars().all()
        return [_prompt_to_dict(p) for p in prompts]
    finally:
        session.close()


@router.get("/prompts/{prompt_id}")
def get_prompt(prompt_id: int):
    session = get_session()
    try:
        prompt = session.get(Prompt, prompt_id)
        if prompt is None:
            return {"error": "Not found"}
        return _prompt_to_dict(prompt)
    finally:
        session.close()


@router.put("/prompts/{prompt_id}")
def update_prompt(prompt_id: int, data: PromptUpdate):
    session = get_session()
    try:
        prompt = session.get(Prompt, prompt_id)
        if prompt is None:
            return {"error": "Not found"}

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(prompt, field, value)
        prompt.updated_at = datetime.utcnow()

        session.commit()
        session.refresh(prompt)
        return _prompt_to_dict(prompt)
    except Exception as e:
        session.rollback()
        return {"error": str(e)}
    finally:
        session.close()


@router.post("/prompts/{prompt_id}/test")
def test_prompt(prompt_id: int, data: PromptTest):
    """Test a prompt with sample data and return the AI response."""
    session = get_session()
    try:
        prompt = session.get(Prompt, prompt_id)
        if prompt is None:
            return {"error": "Not found"}

        rendered = render_prompt(prompt.user_prompt_template, **data.sample_data)

        result = single_message(
            system=prompt.system_prompt,
            user_content=rendered,
        )

        return {
            "rendered_prompt": rendered,
            "response": result,
        }
    finally:
        session.close()


def _prompt_to_dict(prompt: Prompt) -> dict:
    return {
        "id": prompt.id,
        "name": prompt.name,
        "system_prompt": prompt.system_prompt,
        "user_prompt_template": prompt.user_prompt_template,
        "response_schema": prompt.response_schema,
        "description": prompt.description,
        "updated_at": prompt.updated_at.isoformat() if prompt.updated_at else None,
    }
