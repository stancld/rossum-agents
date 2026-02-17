from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class EntityRef(BaseModel):
    """Reference to a Rossum entity discovered during scoping."""

    model_config = {"populate_by_name": True}

    entity_type: str = Field(validation_alias="type")
    entity_id: int | None = Field(default=None, validation_alias="id")
    entity_name: str | None = Field(default=None, validation_alias="name")
    notes: str = ""


class ScopeItem(BaseModel):
    """A concrete deliverable in the SoW."""

    description: str
    entity_type: str | None = None
    action: str | None = None


class StatementOfWork(BaseModel):
    title: str
    environment: str
    created_at: datetime
    status: Literal["draft", "approved", "superseded"] = "draft"
    business_goal: str
    constraints: list[str] = []
    success_criteria: list[str] = []
    existing_entities: list[EntityRef] = []
    gaps: list[str] = []
    in_scope: list[ScopeItem] = []
    out_of_scope: list[str] = []
    assumptions: list[str] = []
    estimated_entity_changes: int = 0
    actual_entity_changes: int | None = None
    estimation_notes: str = ""
    estimated_md: int = 0
    risk_factors: list[str] = []

    @staticmethod
    def _render_section(lines: list[str], heading: str, items: list[str]) -> None:
        if items:
            lines.extend(["", f"## {heading}"])
            lines.extend(f"- {item}" for item in items)

    def _render_entity(self, e: EntityRef) -> str:
        note = f" — {e.notes}" if e.notes else ""
        identity = f' {e.entity_id} "{e.entity_name}"' if e.entity_id is not None else ""
        return f"{e.entity_type}{identity}{note}"

    def _render_scope_item(self, item: ScopeItem) -> str:
        parts = [item.description]
        if item.action:
            parts.append(f"[{item.action}]")
        if item.entity_type:
            parts.append(f"({item.entity_type})")
        return " ".join(parts)

    def render(self) -> str:
        """Human-readable formatted text."""
        lines = [
            f"# Statement of Work: {self.title}",
            f"**Environment**: {self.environment}",
            f"**Status**: {self.status}",
            f"**Created**: {self.created_at.isoformat()}",
            "",
            "## Business Goal",
            self.business_goal,
        ]
        self._render_section(lines, "Constraints", self.constraints)
        self._render_section(lines, "Success Criteria", self.success_criteria)
        self._render_section(lines, "Existing Entities", [self._render_entity(e) for e in self.existing_entities])
        self._render_section(lines, "Gaps", self.gaps)
        self._render_section(lines, "In Scope", [self._render_scope_item(item) for item in self.in_scope])
        self._render_section(lines, "Out of Scope", self.out_of_scope)
        self._render_section(lines, "Assumptions", self.assumptions)
        self._render_section(lines, "Risk Factors", self.risk_factors)
        if self.estimated_md:
            lines.extend(["", f"**Estimated effort**: {self.estimated_md} MD"])
        if self.estimated_entity_changes:
            lines.append(f"**Estimated entity changes**: {self.estimated_entity_changes}")
        if self.actual_entity_changes is not None:
            delta = self.actual_entity_changes - self.estimated_entity_changes
            sign = "+" if delta >= 0 else ""
            lines.append(f"**Actual entity changes**: {self.actual_entity_changes} (delta: {sign}{delta})")
            if self.estimation_notes:
                lines.append(f"**Estimation notes**: {self.estimation_notes}")
        return "\n".join(lines)

    def render_summary(self) -> str:
        """Compact summary for system prompt injection."""
        scope_count = len(self.in_scope)
        if self.actual_entity_changes is not None:
            entity_changes = (
                f"estimated {self.estimated_entity_changes} → actual {self.actual_entity_changes} entity changes"
            )
        else:
            entity_changes = f"~{self.estimated_entity_changes} entity changes"
        return f'[Active SoW: "{self.title}" ({self.status}) — {scope_count} deliverables, {entity_changes}]'

    def render_calibration(self) -> str | None:
        """Compact line for system prompt calibration context. None if actuals not recorded."""
        if self.actual_entity_changes is None:
            return None
        delta = self.actual_entity_changes - self.estimated_entity_changes
        sign = "+" if delta >= 0 else ""
        note = f" Notes: {self.estimation_notes!r}" if self.estimation_notes else ""
        return (
            f'- "{self.title}": estimated {self.estimated_entity_changes}'
            f" → actual {self.actual_entity_changes} ({sign}{delta}){note}"
        )


class PlannedStep(BaseModel):
    step_number: int
    action: Literal["create", "update", "delete", "configure", "verify", "test"]
    entity_type: str
    entity_id: int | None = None
    entity_name: str
    description: str
    depends_on: list[int] = []
    detailed_spec: str = ""
    estimated_tools: list[str] = []
    verification: str = ""
    risk_level: Literal["low", "medium", "high"] = "low"
    status: Literal["pending", "in_progress", "completed", "failed", "skipped"] = "pending"
    result_entity_id: int | None = None


class ImplementationPhase(BaseModel):
    phase_number: int
    name: str
    description: str = ""
    steps: list[PlannedStep]
    rollback_strategy: str = ""


class ImplementationPlan(BaseModel):
    sow_artifact_id: str | None = None
    environment: str
    created_at: datetime
    status: Literal["draft", "approved", "executing", "completed", "aborted"] = "draft"
    goal: str
    phases: list[ImplementationPhase]
    related_commit_hashes: list[str] = []

    def render(self) -> str:
        """Phased checklist format."""
        lines = [
            f"# Implementation Plan: {self.goal}",
            f"**Environment**: {self.environment}",
            f"**Status**: {self.status}",
            f"**Created**: {self.created_at.isoformat()}",
        ]
        if self.sow_artifact_id:
            lines.append(f"**SoW**: {self.sow_artifact_id}")
        for phase in self.phases:
            lines.extend(["", f"## Phase {phase.phase_number}: {phase.name}"])
            if phase.description:
                lines.append(phase.description)
            for step in phase.steps:
                marker = {
                    "pending": "[ ]",
                    "in_progress": "[>]",
                    "completed": "[x]",
                    "failed": "[!]",
                    "skipped": "[-]",
                }[step.status]
                lines.append(
                    f'  {marker} Step {step.step_number}: {step.action} {step.entity_type} "{step.entity_name}" — {step.description}'
                )
            if phase.rollback_strategy:
                lines.append(f"  Rollback: {phase.rollback_strategy}")
        return "\n".join(lines)

    def render_progress(self) -> str:
        """Execution progress view."""
        all_steps = [s for p in self.phases for s in p.steps]
        total = len(all_steps)
        completed = sum(1 for s in all_steps if s.status == "completed")
        failed = sum(1 for s in all_steps if s.status == "failed")
        in_progress = sum(1 for s in all_steps if s.status == "in_progress")
        lines = [f"Progress: {completed}/{total} steps completed"]
        if failed:
            lines[0] += f" ({failed} failed)"
        if in_progress:
            lines[0] += f" ({in_progress} in progress)"
        for phase in self.phases:
            phase_done = sum(1 for s in phase.steps if s.status == "completed")
            lines.append(f"  Phase {phase.phase_number} ({phase.name}): {phase_done}/{len(phase.steps)}")
        return "\n".join(lines)

    def render_summary(self) -> str:
        """Compact summary for system prompt injection."""
        all_steps = [s for p in self.phases for s in p.steps]
        total = len(all_steps)
        completed = sum(1 for s in all_steps if s.status == "completed")
        return f'[Active Plan: "{self.goal}" ({self.status}) — {completed}/{total} steps, {len(self.phases)} phases]'
