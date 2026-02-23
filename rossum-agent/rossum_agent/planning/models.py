from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class EntityRef(BaseModel):
    entity_type: str
    entity_id: str
    entity_name: str


class ScopeItem(BaseModel):
    entity_ref: EntityRef
    planned_operations: list[str] = Field(default_factory=list)
    notes: str | None = None


class SoWOutcome(BaseModel):
    """Actual operations performed, recorded after completion for estimation calibration."""

    actual_ops: dict[str, int] = Field(default_factory=dict)


class StatementOfWork(BaseModel):
    sow_id: str
    title: str
    description: str
    scope: list[ScopeItem] = Field(default_factory=list)
    estimated_ops: dict[str, int] = Field(default_factory=dict)
    status: Literal["draft", "approved", "completed"] = "draft"
    created_at: datetime
    outcome: SoWOutcome | None = None

    def render(self) -> str:
        """Full markdown render of this SoW."""
        lines = [f"# Statement of Work: {self.title}", "", "## Description", self.description, ""]
        if self.scope:
            lines += [
                "## Scope",
                "| Entity | Type | Operations | Notes |",
                "|--------|------|------------|-------|",
            ]
            for item in self.scope:
                ops = ", ".join(item.planned_operations)
                notes = item.notes or ""
                lines.append(f"| {item.entity_ref.entity_name} | {item.entity_ref.entity_type} | {ops} | {notes} |")
            lines.append("")
        if self.estimated_ops:
            lines += [
                "## Estimates",
                "| Entity Type | Estimated Operations |",
                "|-------------|---------------------|",
            ]
            for entity_type, count in sorted(self.estimated_ops.items()):
                lines.append(f"| {entity_type} | {count} |")
            lines.append("")
        lines.append(f"Status: {self.status}")
        return "\n".join(lines)

    def render_summary(self) -> str:
        """Compact one-line summary for use in prompts."""
        total_ops = sum(self.estimated_ops.values())
        return (
            f"SoW [{self.sow_id}]: {self.title} ({self.status})"
            f" — {len(self.scope)} scope items, ~{total_ops} estimated operations"
        )

    def render_calibration(self) -> str:
        """Render calibration comparison of estimates vs actuals."""
        if self.outcome is None:
            return f"SoW [{self.sow_id}]: {self.title} — no outcome recorded"
        lines = [
            f"# Calibration: {self.title}",
            "",
            "| Entity Type | Estimated | Actual | Delta |",
            "|-------------|-----------|--------|-------|",
        ]
        all_types = sorted(set(self.estimated_ops) | set(self.outcome.actual_ops))
        for entity_type in all_types:
            estimated = self.estimated_ops.get(entity_type, 0)
            actual = self.outcome.actual_ops.get(entity_type, 0)
            delta = actual - estimated
            delta_str = f"+{delta}" if delta > 0 else str(delta)
            lines.append(f"| {entity_type} | {estimated} | {actual} | {delta_str} |")
        return "\n".join(lines)


class PlannedStep(BaseModel):
    step_id: str
    description: str
    entity_refs: list[EntityRef] = Field(default_factory=list)
    status: Literal["pending", "in_progress", "done", "failed"] = "pending"


class ImplementationPhase(BaseModel):
    phase_id: str
    name: str
    steps: list[PlannedStep] = Field(default_factory=list)

    @property
    def done_count(self) -> int:
        return sum(1 for s in self.steps if s.status == "done")


class ImplementationPlan(BaseModel):
    plan_id: str
    sow_id: str
    phases: list[ImplementationPhase] = Field(default_factory=list)
    status: Literal["draft", "approved", "executing", "completed", "failed"] = "draft"
    created_at: datetime

    def render(self) -> str:
        """Full markdown render of the implementation plan."""
        lines = [
            f"# Implementation Plan [{self.plan_id}]",
            f"Linked SoW: {self.sow_id}",
            f"Status: {self.status}",
            "",
        ]
        for phase in self.phases:
            lines.append(f"## {phase.name}")
            for step in phase.steps:
                check = "x" if step.status == "done" else " "
                tag = f" [{step.status}]" if step.status not in ("pending", "done") else ""
                lines.append(f"- [{check}] {step.description}{tag}")
            lines.append("")
        return "\n".join(lines)

    def render_progress(self) -> str:
        """Compact progress summary."""
        total = sum(len(p.steps) for p in self.phases)
        done = sum(p.done_count for p in self.phases)
        pct = int(done / total * 100) if total > 0 else 0
        phase_parts = [f"{p.name} [{p.done_count}/{len(p.steps)}]" for p in self.phases]
        phases_str = ", ".join(phase_parts) if phase_parts else "no phases"
        return f"Plan [{self.plan_id}] {self.status} — {done}/{total} steps done ({pct}%) | {phases_str}"
