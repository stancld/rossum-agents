from __future__ import annotations

from datetime import UTC, datetime

from rossum_agent.planning.models import (
    EntityRef,
    ImplementationPhase,
    ImplementationPlan,
    PlannedStep,
    ScopeItem,
    SoWOutcome,
    StatementOfWork,
)

NOW = datetime(2026, 2, 23, 14, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# EntityRef and ScopeItem
# ---------------------------------------------------------------------------


class TestEntityRef:
    def test_creation(self):
        ref = EntityRef(entity_type="schema", entity_id="s1", entity_name="Invoice Schema")
        assert ref.entity_type == "schema"
        assert ref.entity_id == "s1"
        assert ref.entity_name == "Invoice Schema"


class TestScopeItem:
    def test_defaults(self):
        item = ScopeItem(entity_ref=EntityRef(entity_type="queue", entity_id="q1", entity_name="Main Queue"))
        assert item.planned_operations == []
        assert item.notes is None

    def test_with_operations_and_notes(self):
        item = ScopeItem(
            entity_ref=EntityRef(entity_type="schema", entity_id="s1", entity_name="Invoice"),
            planned_operations=["update"],
            notes="Add vendor_name field",
        )
        assert item.planned_operations == ["update"]
        assert item.notes == "Add vendor_name field"


# ---------------------------------------------------------------------------
# SoWOutcome
# ---------------------------------------------------------------------------


class TestSoWOutcome:
    def test_defaults(self):
        outcome = SoWOutcome()
        assert outcome.actual_ops == {}

    def test_with_ops(self):
        outcome = SoWOutcome(actual_ops={"schema": 2, "queue": 1})
        assert outcome.actual_ops["schema"] == 2


# ---------------------------------------------------------------------------
# StatementOfWork
# ---------------------------------------------------------------------------


def _make_sow(**overrides) -> StatementOfWork:
    defaults = {
        "sow_id": "sow-001",
        "title": "Add Invoice Fields",
        "description": "Add vendor_name and total_amount fields to Invoice schema.",
        "created_at": NOW,
    }
    defaults.update(overrides)
    return StatementOfWork(**defaults)


class TestStatementOfWork:
    def test_defaults(self):
        sow = _make_sow()
        assert sow.status == "draft"
        assert sow.scope == []
        assert sow.estimated_ops == {}
        assert sow.outcome is None

    def test_json_roundtrip(self):
        sow = _make_sow(
            scope=[
                ScopeItem(
                    entity_ref=EntityRef(entity_type="schema", entity_id="s1", entity_name="Invoice"),
                    planned_operations=["update"],
                )
            ],
            estimated_ops={"schema": 1},
            status="approved",
        )
        restored = StatementOfWork.model_validate_json(sow.model_dump_json())
        assert restored.sow_id == sow.sow_id
        assert restored.status == "approved"
        assert len(restored.scope) == 1
        assert restored.scope[0].planned_operations == ["update"]


class TestStatementOfWorkRender:
    def test_render_contains_title_and_description(self):
        sow = _make_sow()
        rendered = sow.render()
        assert "Add Invoice Fields" in rendered
        assert "Add vendor_name and total_amount fields" in rendered

    def test_render_contains_status(self):
        sow = _make_sow(status="approved")
        assert "Status: approved" in sow.render()

    def test_render_scope_table(self):
        sow = _make_sow(
            scope=[
                ScopeItem(
                    entity_ref=EntityRef(entity_type="schema", entity_id="s1", entity_name="Invoice"),
                    planned_operations=["update"],
                    notes="two fields",
                )
            ]
        )
        rendered = sow.render()
        assert "## Scope" in rendered
        assert "Invoice" in rendered
        assert "schema" in rendered
        assert "update" in rendered
        assert "two fields" in rendered

    def test_render_estimates_table(self):
        sow = _make_sow(estimated_ops={"schema": 2, "hook": 1})
        rendered = sow.render()
        assert "## Estimates" in rendered
        assert "schema" in rendered
        assert "| 2 |" in rendered

    def test_render_no_scope_omits_scope_section(self):
        sow = _make_sow()
        assert "## Scope" not in sow.render()

    def test_render_no_estimates_omits_estimates_section(self):
        sow = _make_sow()
        assert "## Estimates" not in sow.render()


class TestStatementOfWorkRenderSummary:
    def test_contains_sow_id_title_status(self):
        sow = _make_sow(status="approved")
        summary = sow.render_summary()
        assert "sow-001" in summary
        assert "Add Invoice Fields" in summary
        assert "approved" in summary

    def test_shows_scope_count(self):
        sow = _make_sow(
            scope=[
                ScopeItem(entity_ref=EntityRef(entity_type="schema", entity_id="s1", entity_name="S1")),
                ScopeItem(entity_ref=EntityRef(entity_type="queue", entity_id="q1", entity_name="Q1")),
            ]
        )
        summary = sow.render_summary()
        assert "2 scope items" in summary

    def test_shows_total_estimated_ops(self):
        sow = _make_sow(estimated_ops={"schema": 3, "queue": 2})
        assert "~5 estimated operations" in sow.render_summary()


class TestStatementOfWorkRenderCalibration:
    def test_no_outcome(self):
        sow = _make_sow()
        result = sow.render_calibration()
        assert "no outcome recorded" in result
        assert "sow-001" in result

    def test_with_outcome_shows_table(self):
        sow = _make_sow(
            estimated_ops={"schema": 2, "queue": 1},
            outcome=SoWOutcome(actual_ops={"schema": 3, "queue": 1}),
        )
        result = sow.render_calibration()
        assert "# Calibration" in result
        assert "schema" in result
        assert "+1" in result  # 3 - 2 = +1

    def test_calibration_zero_delta(self):
        sow = _make_sow(
            estimated_ops={"hook": 2},
            outcome=SoWOutcome(actual_ops={"hook": 2}),
        )
        result = sow.render_calibration()
        assert "0" in result

    def test_calibration_negative_delta(self):
        sow = _make_sow(
            estimated_ops={"schema": 5},
            outcome=SoWOutcome(actual_ops={"schema": 3}),
        )
        result = sow.render_calibration()
        assert "-2" in result

    def test_calibration_includes_actual_only_types(self):
        # entity type appears only in actual, not estimated
        sow = _make_sow(
            estimated_ops={"schema": 1},
            outcome=SoWOutcome(actual_ops={"schema": 1, "hook": 2}),
        )
        result = sow.render_calibration()
        assert "hook" in result


# ---------------------------------------------------------------------------
# PlannedStep
# ---------------------------------------------------------------------------


class TestPlannedStep:
    def test_defaults(self):
        step = PlannedStep(step_id="s1", description="Create schema")
        assert step.status == "pending"
        assert step.entity_refs == []

    def test_with_refs_and_status(self):
        step = PlannedStep(
            step_id="s1",
            description="Update queue",
            entity_refs=[EntityRef(entity_type="queue", entity_id="q1", entity_name="Invoice Q")],
            status="done",
        )
        assert step.status == "done"
        assert len(step.entity_refs) == 1


# ---------------------------------------------------------------------------
# ImplementationPhase
# ---------------------------------------------------------------------------


class TestImplementationPhase:
    def test_done_count_empty(self):
        phase = ImplementationPhase(phase_id="p1", name="Setup")
        assert phase.done_count == 0

    def test_done_count_mixed(self):
        phase = ImplementationPhase(
            phase_id="p1",
            name="Setup",
            steps=[
                PlannedStep(step_id="s1", description="Step 1", status="done"),
                PlannedStep(step_id="s2", description="Step 2", status="done"),
                PlannedStep(step_id="s3", description="Step 3", status="pending"),
                PlannedStep(step_id="s4", description="Step 4", status="failed"),
            ],
        )
        assert phase.done_count == 2

    def test_done_count_all_done(self):
        phase = ImplementationPhase(
            phase_id="p1",
            name="Phase",
            steps=[PlannedStep(step_id=f"s{i}", description=f"Step {i}", status="done") for i in range(3)],
        )
        assert phase.done_count == 3


# ---------------------------------------------------------------------------
# ImplementationPlan
# ---------------------------------------------------------------------------


def _make_plan(**overrides) -> ImplementationPlan:
    defaults = {
        "plan_id": "plan-001",
        "sow_id": "sow-001",
        "created_at": NOW,
    }
    defaults.update(overrides)
    return ImplementationPlan(**defaults)


class TestImplementationPlan:
    def test_defaults(self):
        plan = _make_plan()
        assert plan.status == "draft"
        assert plan.phases == []

    def test_json_roundtrip(self):
        plan = _make_plan(
            phases=[
                ImplementationPhase(
                    phase_id="p1",
                    name="Phase 1",
                    steps=[PlannedStep(step_id="s1", description="Do something", status="done")],
                )
            ],
            status="executing",
        )
        restored = ImplementationPlan.model_validate_json(plan.model_dump_json())
        assert restored.plan_id == plan.plan_id
        assert restored.status == "executing"
        assert len(restored.phases) == 1
        assert restored.phases[0].steps[0].status == "done"


class TestImplementationPlanRender:
    def test_render_header(self):
        plan = _make_plan()
        rendered = plan.render()
        assert "# Implementation Plan [plan-001]" in rendered
        assert "Linked SoW: sow-001" in rendered
        assert "Status: draft" in rendered

    def test_render_phases_and_steps(self):
        plan = _make_plan(
            phases=[
                ImplementationPhase(
                    phase_id="p1",
                    name="Phase 1",
                    steps=[
                        PlannedStep(step_id="s1", description="Create schema", status="done"),
                        PlannedStep(step_id="s2", description="Update queue", status="pending"),
                    ],
                )
            ]
        )
        rendered = plan.render()
        assert "## Phase 1" in rendered
        assert "- [x] Create schema" in rendered
        assert "- [ ] Update queue" in rendered

    def test_render_in_progress_step_has_tag(self):
        plan = _make_plan(
            phases=[
                ImplementationPhase(
                    phase_id="p1",
                    name="Phase 1",
                    steps=[PlannedStep(step_id="s1", description="Deploy hook", status="in_progress")],
                )
            ]
        )
        rendered = plan.render()
        assert "[in_progress]" in rendered

    def test_render_done_step_no_extra_tag(self):
        plan = _make_plan(
            phases=[
                ImplementationPhase(
                    phase_id="p1",
                    name="Phase 1",
                    steps=[PlannedStep(step_id="s1", description="Done step", status="done")],
                )
            ]
        )
        rendered = plan.render()
        assert "[done]" not in rendered
        assert "[x]" in rendered


class TestImplementationPlanRenderProgress:
    def test_no_phases(self):
        plan = _make_plan()
        progress = plan.render_progress()
        assert "plan-001" in progress
        assert "0/0" in progress
        assert "no phases" in progress

    def test_progress_counts(self):
        plan = _make_plan(
            phases=[
                ImplementationPhase(
                    phase_id="p1",
                    name="Setup",
                    steps=[
                        PlannedStep(step_id="s1", description="S1", status="done"),
                        PlannedStep(step_id="s2", description="S2", status="done"),
                        PlannedStep(step_id="s3", description="S3", status="pending"),
                    ],
                ),
                ImplementationPhase(
                    phase_id="p2",
                    name="Deploy",
                    steps=[PlannedStep(step_id="s4", description="S4", status="pending")],
                ),
            ]
        )
        progress = plan.render_progress()
        assert "2/4" in progress
        assert "50%" in progress
        assert "Setup [2/3]" in progress
        assert "Deploy [0/1]" in progress

    def test_all_done_shows_100(self):
        plan = _make_plan(
            status="completed",
            phases=[
                ImplementationPhase(
                    phase_id="p1",
                    name="Phase",
                    steps=[PlannedStep(step_id=f"s{i}", description=f"S{i}", status="done") for i in range(4)],
                )
            ],
        )
        progress = plan.render_progress()
        assert "4/4" in progress
        assert "100%" in progress
