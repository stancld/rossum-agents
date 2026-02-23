"""Planning tools for creating and managing Statements of Work and Implementation Plans."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from anthropic import beta_tool

from rossum_agent.planning.models import (
    EntityRef,
    ImplementationPhase,
    ImplementationPlan,
    PlannedStep,
    ScopeItem,
    SoWOutcome,
    StatementOfWork,
)
from rossum_agent.storage.handles import PlanHandle, SoWHandle
from rossum_agent.tools.core import get_context, url_to_org_id

if TYPE_CHECKING:
    from rossum_agent.storage.artifact_store import ArtifactStore

logger = logging.getLogger(__name__)


def _get_store_and_org() -> tuple[ArtifactStore, str] | tuple[None, str]:
    ctx = get_context()
    if ctx.artifact_store is None:
        return None, "Artifact store not available (S3 not configured)"
    env = ctx.rossum_environment or "default"
    org_id = url_to_org_id(env)
    return ctx.artifact_store, org_id


@beta_tool
def create_sow(
    title: str,
    description: str,
    scope: list[dict],
    estimated_ops: dict,
) -> str:
    """Create and persist a Statement of Work for user review.

    Call this when the user wants to plan a significant implementation before execution.
    The SoW captures scope, entities affected, and estimated operations.

    Args:
        title: Short descriptive title for this SoW.
        description: Full description of the work to be done.
        scope: List of scope items. Each item: {"entity_ref": {"entity_type": str,
            "entity_id": str, "entity_name": str}, "planned_operations": [str],
            "notes": str | null}.
        estimated_ops: Dict mapping entity types to estimated operation counts,
            e.g. {"schema": 3, "hook": 1}.

    Returns:
        JSON with status, sow_id, and rendered SoW markdown.
    """
    store, org_id = _get_store_and_org()
    if store is None:
        return json.dumps({"status": "error", "message": org_id})

    sow_id = f"sow-{uuid4().hex[:8]}"
    timestamp = datetime.now(UTC)

    try:
        scope_items = [
            ScopeItem(
                entity_ref=EntityRef(**item["entity_ref"]),
                planned_operations=item.get("planned_operations", []),
                notes=item.get("notes"),
            )
            for item in scope
        ]
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Invalid scope format: {e}"})

    sow = StatementOfWork(
        sow_id=sow_id,
        title=title,
        description=description,
        scope=scope_items,
        estimated_ops={str(k): int(v) for k, v in estimated_ops.items()},
        created_at=timestamp,
    )

    handle = SoWHandle(org_id=org_id, artifact_id=sow_id, timestamp=timestamp)
    try:
        store.save(handle, sow)
    except Exception as e:
        logger.error(f"Failed to save SoW: {e}")
        return json.dumps({"status": "error", "message": f"Failed to save SoW: {e}"})

    return json.dumps({"status": "success", "sow_id": sow_id, "content": sow.render()})


@beta_tool
def create_implementation_plan(
    sow_id: str,
    phases: list[dict],
) -> str:
    """Create and persist an ImplementationPlan linked to an approved SoW.

    Call this after the user approves the SoW. The plan breaks work into
    trackable phases and steps.

    Args:
        sow_id: ID of the approved SoW this plan implements.
        phases: List of phases. Each phase: {"phase_id": str (optional),
            "name": str, "steps": [{"step_id": str (optional), "description": str,
            "entity_refs": [{"entity_type": str, "entity_id": str,
            "entity_name": str}]}]}.

    Returns:
        JSON with status, plan_id, and rendered plan markdown.
    """
    store, org_id = _get_store_and_org()
    if store is None:
        return json.dumps({"status": "error", "message": org_id})

    plan_id = f"plan-{uuid4().hex[:8]}"
    timestamp = datetime.now(UTC)

    try:
        impl_phases = []
        for ph in phases:
            steps = [
                PlannedStep(
                    step_id=s.get("step_id", f"step-{uuid4().hex[:6]}"),
                    description=s["description"],
                    entity_refs=[EntityRef(**r) for r in s.get("entity_refs", [])],
                )
                for s in ph.get("steps", [])
            ]
            impl_phases.append(
                ImplementationPhase(
                    phase_id=ph.get("phase_id", f"phase-{uuid4().hex[:6]}"),
                    name=ph["name"],
                    steps=steps,
                )
            )
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Invalid phases format: {e}"})

    plan = ImplementationPlan(
        plan_id=plan_id,
        sow_id=sow_id,
        phases=impl_phases,
        created_at=timestamp,
    )

    handle = PlanHandle(org_id=org_id, artifact_id=plan_id, timestamp=timestamp)
    try:
        store.save(handle, plan)
    except Exception as e:
        logger.error(f"Failed to save plan: {e}")
        return json.dumps({"status": "error", "message": f"Failed to save plan: {e}"})

    return json.dumps({"status": "success", "plan_id": plan_id, "content": plan.render()})


@beta_tool
def update_plan_step(
    plan_id: str,
    phase_id: str,
    step_id: str,
    status: str,
) -> str:
    """Update a step's status in an ImplementationPlan.

    Call this as you execute each step to track progress. The plan's overall
    status transitions automatically: executing → completed (all done) or failed.

    Args:
        plan_id: ID of the plan to update.
        phase_id: ID of the phase containing the step.
        step_id: ID of the step to update.
        status: New status — one of: "pending", "in_progress", "done", "failed".

    Returns:
        JSON with status and updated progress summary.
    """
    valid_statuses: tuple[str, ...] = ("pending", "in_progress", "done", "failed")
    if status not in valid_statuses:
        return json.dumps(
            {"status": "error", "message": f"Invalid status {status!r}. Must be one of: {', '.join(valid_statuses)}"}
        )

    store, org_id = _get_store_and_org()
    if store is None:
        return json.dumps({"status": "error", "message": org_id})

    all_plans = store.list_artifacts(org_id, "plan", PlanHandle)
    # list_artifacts returns chronological order; use the most recent version of this plan
    target = next(
        (p for p in reversed(all_plans) if isinstance(p, ImplementationPlan) and p.plan_id == plan_id),
        None,
    )

    if target is None:
        return json.dumps({"status": "error", "message": f"Plan {plan_id!r} not found"})

    for phase in target.phases:
        if phase.phase_id == phase_id:
            for step in phase.steps:
                if step.step_id == step_id:
                    step.status = status  # type: ignore[assignment]
                    break
            else:
                return json.dumps({"status": "error", "message": f"Step {step_id!r} not found in phase {phase_id!r}"})
            break
    else:
        return json.dumps({"status": "error", "message": f"Phase {phase_id!r} not found in plan {plan_id!r}"})

    all_done = all(all(s.status == "done" for s in ph.steps) for ph in target.phases)
    has_failed = any(any(s.status == "failed" for s in ph.steps) for ph in target.phases)
    if all_done:
        target.status = "completed"
    elif has_failed:
        target.status = "failed"
    elif status in ("in_progress", "done"):
        target.status = "executing"

    timestamp = datetime.now(UTC)
    handle = PlanHandle(org_id=org_id, artifact_id=plan_id, timestamp=timestamp)
    try:
        store.save(handle, target)
    except Exception as e:
        logger.error(f"Failed to save updated plan: {e}")
        return json.dumps({"status": "error", "message": f"Failed to save plan: {e}"})

    return json.dumps({"status": "success", "progress": target.render_progress()})


@beta_tool
def get_active_plan() -> str:
    """Retrieve the current active implementation plan.

    Returns the most recently saved plan that is not yet completed or failed.
    Use this to check your current progress or resume work across turns.

    Returns:
        JSON with plan_id, full plan content, and progress summary; or
        status "not_found" if no active plan exists.
    """
    store, org_id = _get_store_and_org()
    if store is None:
        return json.dumps({"status": "error", "message": org_id})

    latest = store.load_latest(org_id, "plan", PlanHandle)
    if latest is None:
        return json.dumps({"status": "not_found", "message": "No active plan found"})

    if not isinstance(latest, ImplementationPlan):
        return json.dumps({"status": "error", "message": "Unexpected plan format"})

    if latest.status == "completed":
        return json.dumps(
            {
                "status": "completed",
                "message": f"Latest plan {latest.plan_id!r} is already completed",
                "progress": latest.render_progress(),
            }
        )

    return json.dumps(
        {
            "status": "success",
            "plan_id": latest.plan_id,
            "content": latest.render(),
            "progress": latest.render_progress(),
        }
    )


@beta_tool
def record_sow_outcome(
    sow_id: str,
    actual_ops: dict,
) -> str:
    """Record actual operations performed after completing a SoW.

    Call this when the implementation is complete. The recorded actuals are
    used to calibrate future estimates.

    Args:
        sow_id: ID of the completed SoW.
        actual_ops: Dict mapping entity types to actual operation counts,
            e.g. {"schema": 4, "hook": 2}.

    Returns:
        JSON with status and calibration comparison of estimates vs actuals.
    """
    store, org_id = _get_store_and_org()
    if store is None:
        return json.dumps({"status": "error", "message": org_id})

    all_sows = store.list_artifacts(org_id, "sow", SoWHandle)
    # list_artifacts returns chronological order; use the most recent version of this SoW
    target = next(
        (s for s in reversed(all_sows) if isinstance(s, StatementOfWork) and s.sow_id == sow_id),
        None,
    )

    if target is None:
        return json.dumps({"status": "error", "message": f"SoW {sow_id!r} not found"})

    target.outcome = SoWOutcome(actual_ops={str(k): int(v) for k, v in actual_ops.items()})
    target.status = "completed"

    timestamp = datetime.now(UTC)
    handle = SoWHandle(org_id=org_id, artifact_id=sow_id, timestamp=timestamp)
    try:
        store.save(handle, target)
    except Exception as e:
        logger.error(f"Failed to save SoW outcome: {e}")
        return json.dumps({"status": "error", "message": f"Failed to save SoW: {e}"})

    return json.dumps({"status": "success", "calibration": target.render_calibration()})
