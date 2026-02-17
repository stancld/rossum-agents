from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from anthropic import beta_tool

from rossum_agent.planning.models import (
    EntityRef,
    ImplementationPhase,
    ImplementationPlan,
    PlannedStep,
    ScopeItem,
    StatementOfWork,
)
from rossum_agent.storage.handles import PlanHandle, SoWHandle
from rossum_agent.tools.core import get_artifact_store, get_rossum_environment

if TYPE_CHECKING:
    from rossum_agent.storage.artifact_store import ArtifactStore

logger = logging.getLogger(__name__)

_STORE_ERROR = json.dumps({"error": "Artifact storage not available"})


def _slugify(text: str) -> str:
    """Convert text to a URL-friendly slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug[:80].strip("-")


def _require_store_and_env() -> tuple[ArtifactStore, str] | None:
    """Get artifact store and environment, returning None if unavailable."""
    store = get_artifact_store()
    env = get_rossum_environment()
    if store is None or env is None:
        return None
    return store, env


@beta_tool
def create_sow(
    title: str,
    business_goal: str,
    in_scope: list[str],
    estimated_md: int,
    constraints: list[str] | None = None,
    existing_entities: list[dict] | None = None,
    gaps: list[str] | None = None,
    out_of_scope: list[str] | None = None,
    assumptions: list[str] | None = None,
    success_criteria: list[str] | None = None,
    risk_factors: list[str] | None = None,
    estimated_entity_changes: int | None = None,
) -> str:
    """Create a Statement of Work for a multi-step project. Present to user for approval before planning."""
    pair = _require_store_and_env()
    if pair is None:
        return _STORE_ERROR
    store, env = pair

    scope_items = [ScopeItem(description=s) for s in in_scope]
    entity_refs = [EntityRef(**e) for e in (existing_entities or [])]

    sow = StatementOfWork(
        title=title,
        environment=env,
        created_at=datetime.now(UTC),
        business_goal=business_goal,
        in_scope=scope_items,
        constraints=constraints or [],
        existing_entities=entity_refs,
        gaps=gaps or [],
        out_of_scope=out_of_scope or [],
        assumptions=assumptions or [],
        success_criteria=success_criteria or [],
        risk_factors=risk_factors or [],
        estimated_entity_changes=estimated_entity_changes or 0,
        estimated_md=estimated_md,
    )

    slug = _slugify(title)
    handle = SoWHandle(environment=env, artifact_id=slug)
    store.save(handle, sow)

    logger.info(f"Created SoW '{title}' with artifact_id='{slug}'")
    return json.dumps(
        {
            "status": "created",
            "artifact_id": slug,
            "title": title,
            "rendered": sow.render(),
        }
    )


@beta_tool
def create_implementation_plan(
    goal: str,
    phases: list[dict],
    sow_artifact_id: str | None = None,
) -> str:
    """Create an implementation plan with phased steps. Present to user for approval before executing."""
    pair = _require_store_and_env()
    if pair is None:
        return _STORE_ERROR
    store, env = pair

    plan_phases = []
    for p in phases:
        steps = [PlannedStep(**s) for s in p.get("steps", [])]
        plan_phases.append(
            ImplementationPhase(
                phase_number=p["phase_number"],
                name=p["name"],
                description=p.get("description", ""),
                steps=steps,
                rollback_strategy=p.get("rollback_strategy", ""),
            )
        )

    plan = ImplementationPlan(
        sow_artifact_id=sow_artifact_id,
        environment=env,
        created_at=datetime.now(UTC),
        goal=goal,
        phases=plan_phases,
    )

    slug = _slugify(goal)
    handle = PlanHandle(environment=env, artifact_id=slug)
    store.save(handle, plan)

    logger.info(f"Created plan '{goal}' with artifact_id='{slug}'")
    return json.dumps(
        {
            "status": "created",
            "artifact_id": slug,
            "goal": goal,
            "rendered": plan.render(),
        }
    )


@beta_tool
def update_plan_step(
    step_number: int,
    status: str,
    result_entity_id: int | None = None,
) -> str:
    """Update a step status in the latest active plan. Called before/after each step."""
    pair = _require_store_and_env()
    if pair is None:
        return _STORE_ERROR
    store, env = pair

    result = store.load_latest(PlanHandle, env)
    if result is None:
        return json.dumps({"error": "No active plan found"})

    handle, plan = result

    for phase in plan.phases:
        for step in phase.steps:
            if step.step_number == step_number:
                step.status = status
                if result_entity_id is not None:
                    step.result_entity_id = result_entity_id
                break

    all_steps = [s for p in plan.phases for s in p.steps]
    if any(s.status == "in_progress" for s in all_steps) and plan.status == "approved":
        plan.status = "executing"
    if all(s.status in ("completed", "skipped") for s in all_steps):
        plan.status = "completed"

    new_handle = PlanHandle(environment=env, artifact_id=handle.artifact_id)
    store.save(new_handle, plan)

    logger.info(f"Updated step {step_number} to '{status}' in plan '{handle.artifact_id}'")
    return json.dumps(
        {
            "status": "updated",
            "step_number": step_number,
            "step_status": status,
            "progress": plan.render_progress(),
        }
    )


@beta_tool
def record_sow_outcome(
    actual_entity_changes: int,
    notes: str = "",
    sow_artifact_id: str | None = None,
) -> str:
    """Record actual entity changes after project completion. Calibrates future estimates."""
    pair = _require_store_and_env()
    if pair is None:
        return _STORE_ERROR
    store, env = pair

    if sow_artifact_id:
        results = store.list_artifacts(SoWHandle, env)
        result = next(((h, s) for h, s in results if h.artifact_id == sow_artifact_id), None)
    else:
        result = store.load_latest(SoWHandle, env)

    if result is None:
        return json.dumps({"error": "No SoW found"})

    handle, sow = result
    estimated = sow.estimated_entity_changes
    sow.actual_entity_changes = actual_entity_changes
    sow.estimation_notes = notes

    new_handle = SoWHandle(environment=env, artifact_id=handle.artifact_id)
    store.save(new_handle, sow)

    delta = actual_entity_changes - estimated
    logger.info(
        f"Recorded outcome for SoW '{handle.artifact_id}': estimated={estimated}, actual={actual_entity_changes}, delta={delta}"
    )
    return json.dumps(
        {
            "status": "recorded",
            "artifact_id": handle.artifact_id,
            "estimated": estimated,
            "actual": actual_entity_changes,
            "delta": delta,
        }
    )


@beta_tool
def get_active_plan() -> str:
    """Get the current active plan (status=approved or executing) for this environment."""
    pair = _require_store_and_env()
    if pair is None:
        return _STORE_ERROR
    store, env = pair

    result = store.load_latest(PlanHandle, env)
    if result is None:
        return json.dumps({"message": "No active plan found"})

    handle, plan = result
    if plan.status not in ("approved", "executing", "draft"):
        return json.dumps({"message": f"Latest plan is '{plan.status}', not active"})

    return json.dumps(
        {
            "artifact_id": handle.artifact_id,
            "status": plan.status,
            "rendered": plan.render(),
            "progress": plan.render_progress(),
        }
    )
