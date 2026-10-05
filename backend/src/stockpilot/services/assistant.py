import json
import re
from datetime import timedelta
from typing import cast, get_args

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm import Session

from stockpilot.api.errors import AppError
from stockpilot.api.schemas import AssistantInput
from stockpilot.config import settings
from stockpilot.db.models import (
    AssistantMessage,
    AssistantSession,
    ForecastRun,
    RecommendationItem,
    RecommendationRun,
    utcnow,
)
from stockpilot.db.repositories import get, latest
from stockpilot.domain.assistant.provider import OpenAIProvider
from stockpilot.domain.assistant.tools import Arguments, ToolName, invoke


def answer(
    session: Session, dataset_id: str, inputs: AssistantInput, owner_hash: str | None
) -> dict:
    conversation = get(session, AssistantSession, inputs.session_id) if inputs.session_id else None
    if conversation:
        # Cleanup skips conversations being used by an active request.
        conversation = session.scalar(
            select(AssistantSession).where(AssistantSession.id == conversation.id).with_for_update()
        )
    if inputs.session_id and (
        not conversation
        or conversation.dataset_id != dataset_id
        or conversation.owner_hash != owner_hash
        or (owner_hash and conversation.created_at <= utcnow() - timedelta(hours=24))
    ):
        raise AppError(404, "NOT_FOUND", "Assistant session not found")
    if not conversation:
        conversation = AssistantSession(dataset_id=dataset_id, owner_hash=owner_hash)
        session.add(conversation)
        session.flush()
    match = re.search(r"\b(?:DEMO-\d{3}|\d{5}[A-Z]?)\b", inputs.text, re.I)
    sources, calls = [], []
    if match:
        sku = match.group().upper()
        facts = invoke(
            session,
            dataset_id,
            "get_recommendation_explanation",
            Arguments(identifier=sku),
            owner_hash,
        )
        calls.append("get_recommendation_explanation")
        explanation = facts.get("explanation")
        if explanation:
            text = (
                f"{sku}: target {explanation['target']:.1f} units over {explanation['protection_days']} days. "
                f"Available {explanation['available']} + eligible inbound {explanation['eligible_inbound']} = position {explanation['position']}. "
                f"Raw need {explanation['raw']}; packs of {explanation['pack_size']} and MOQ {explanation['minimum_order_units']} "
                f"give {explanation['requested_units']} requested, {explanation['allocated_units']} allocated. "
                f"Unit cost GBP {explanation['unit_cost']}. This is a proposal, not a supplier order."
            )
            sources.append(facts["reference"])
        else:
            text = "No recommendation is available for this product in the selected dataset."
    elif "risk" in inputs.text.lower():
        forecast = latest(session, ForecastRun, dataset_id)
        run = (
            session.scalar(
                select(RecommendationRun)
                .where(RecommendationRun.forecast_run_id == forecast.id)
                .order_by(RecommendationRun.created_at.desc())
                .limit(1)
            )
            if forecast
            else None
        )
        rows = (
            session.scalars(
                select(RecommendationItem)
                .where(RecommendationItem.run_id == run.id)
                .order_by(RecommendationItem.risk.desc().nulls_last())
                .limit(5)
            ).all()
            if run
            else []
        )
        text = (
            "Highest projected shortage risk: "
            + "; ".join(
                f"{r.explanation['sku']} ({float(r.risk):.0%})" for r in rows if r.risk is not None
            )
            if rows
            else "No calibrated risk results available."
        )
        sources.extend({"type": "recommendation", "id": r.id, "version": r.run_id} for r in rows)
        calls.append("get_recommendation_explanation")
    elif any(word in inputs.text.lower() for word in ("delay", "extra days", "delivery")):
        facts = invoke(session, dataset_id, "preview_scenario", Arguments(), owner_hash)
        text = (
            facts["message"]
            + " A delay moves both existing inbound and new arrivals. Results require an explicit simulation."
        )
        calls.append("preview_scenario")
    else:
        facts = invoke(
            session, dataset_id, "search_policy", Arguments(query=inputs.text), owner_hash
        )
        sources = facts["sources"]
        calls.append("search_policy")
        text = (
            "\n\n".join(source["excerpt"] for source in sources)
            if sources
            else "No relevant policy source found. Ask about a product SKU, shortage risk, delivery delays or purchasing constraints."
        )
    mode = "Offline explanation mode"
    if settings.ai_enabled and settings.app_mode == "local":
        try:

            def execute(name: str, raw_arguments: dict) -> dict:
                if name not in get_args(ToolName) or len(calls) >= 4:
                    raise ValueError("Tool not permitted")
                arguments = Arguments.model_validate(raw_arguments)
                result = invoke(session, dataset_id, cast(ToolName, name), arguments, owner_hash)
                calls.append(name)
                if result.get("reference"):
                    sources.append(result["reference"])
                sources.extend(result.get("sources", []))
                return jsonable_encoder(result)

            text = OpenAIProvider().explain(
                inputs.text,
                json.dumps(jsonable_encoder({"answer": text, "sources": sources})),
                executor=execute,
                remaining_calls=4 - len(calls),
            )
            mode = "Optional LLM explanation"
        except Exception:
            mode = "Offline explanation mode · provider unavailable"
    session.add(
        AssistantMessage(
            session_id=conversation.id, question=inputs.text, answer=text, references=sources
        )
    )
    return {
        "session_id": conversation.id,
        "text": text,
        "mode": mode,
        "sources": sources,
        "tools": calls,
    }
