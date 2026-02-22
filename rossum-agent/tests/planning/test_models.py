from __future__ import annotations

from datetime import UTC, datetime

from rossum_agent.planning.models import (
    EntityRef,
    ImplementationPhase,
    ImplementationPlan,
    PlannedStep,
    ScopeItem,
    StatementOfWork,
)

FIXED_DT = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)


# -- EntityRef & ScopeItem ----------------------------------------------------


def test_entity_ref_creation():
    ref = EntityRef(entity_type="queue", entity_id=42, entity_name="Invoices")
    assert ref.entity_type == "queue"
    assert ref.entity_id == 42
    assert ref.entity_name == "Invoices"
    assert ref.notes == ""


def test_entity_ref_with_notes():
    ref = EntityRef(entity_type="schema", entity_id=7, entity_name="Invoice Schema", notes="needs migration")
    assert ref.notes == "needs migration"


def test_entity_ref_without_id_or_name():
    # Group-level entity references (e.g., "email_templates") don't have specific IDs
    ref = EntityRef(**{"type": "email_templates", "notes": "multiple active templates"})
    assert ref.entity_type == "email_templates"
    assert ref.entity_id is None
    assert ref.entity_name is None
    assert ref.notes == "multiple active templates"


def test_scope_item_creation():
    item = ScopeItem(description="Create invoice queue")
    assert item.description == "Create invoice queue"
    assert item.entity_type is None
    assert item.action is None


def test_scope_item_with_all_fields():
    item = ScopeItem(description="Create invoice queue", entity_type="queue", action="create")
    assert item.entity_type == "queue"
    assert item.action == "create"


# -- StatementOfWork ----------------------------------------------------------


def _make_sow(**overrides) -> StatementOfWork:
    defaults = {
        "title": "Invoice Automation",
        "environment": "https://example.rossum.app/api/v1",
        "created_at": FIXED_DT,
        "business_goal": "Automate invoice processing end-to-end",
        "estimated_md": 5,
    }
    defaults.update(overrides)
    return StatementOfWork(**defaults)


def test_sow_defaults():
    sow = _make_sow()
    assert sow.status == "draft"
    assert sow.constraints == []
    assert sow.success_criteria == []
    assert sow.existing_entities == []
    assert sow.gaps == []
    assert sow.in_scope == []
    assert sow.out_of_scope == []
    assert sow.assumptions == []
    assert sow.estimated_entity_changes == 0
    assert sow.risk_factors == []


def test_sow_serialization_roundtrip():
    sow = _make_sow(
        status="approved",
        constraints=["No downtime"],
        success_criteria=["All invoices processed"],
        existing_entities=[EntityRef(entity_type="queue", entity_id=1, entity_name="Main Queue")],
        gaps=["Missing schema field"],
        in_scope=[ScopeItem(description="Add field", entity_type="schema", action="update")],
        out_of_scope=["Reporting"],
        assumptions=["API access available"],
        estimated_entity_changes=5,
        risk_factors=["Schema migration"],
    )
    json_str = sow.model_dump_json()
    restored = StatementOfWork.model_validate_json(json_str)
    assert restored == sow
    assert restored.existing_entities[0].entity_name == "Main Queue"
    assert restored.in_scope[0].action == "update"


def test_sow_render_contains_key_sections():
    sow = _make_sow(
        constraints=["No downtime"],
        success_criteria=["100% accuracy"],
        existing_entities=[EntityRef(entity_type="queue", entity_id=1, entity_name="Main Queue", notes="production")],
        gaps=["Missing vendor field"],
        in_scope=[ScopeItem(description="Add vendor field", entity_type="schema", action="update")],
        out_of_scope=["Reporting dashboard"],
        assumptions=["API credentials provided"],
        estimated_entity_changes=3,
        risk_factors=["Breaking change risk"],
    )
    rendered = sow.render()

    assert "# Statement of Work: Invoice Automation" in rendered
    assert "**Environment**: https://example.rossum.app/api/v1" in rendered
    assert "**Status**: draft" in rendered
    assert "2024-01-15T10:00:00" in rendered
    assert "## Business Goal" in rendered
    assert "Automate invoice processing end-to-end" in rendered
    assert "## Constraints" in rendered
    assert "- No downtime" in rendered
    assert "## Success Criteria" in rendered
    assert "- 100% accuracy" in rendered
    assert "## Existing Entities" in rendered
    assert 'queue 1 "Main Queue" — production' in rendered
    assert "## Gaps" in rendered
    assert "- Missing vendor field" in rendered
    assert "## In Scope" in rendered
    assert "- Add vendor field [update] (schema)" in rendered
    assert "## Out of Scope" in rendered
    assert "- Reporting dashboard" in rendered
    assert "## Assumptions" in rendered
    assert "- API credentials provided" in rendered
    assert "## Risk Factors" in rendered
    assert "- Breaking change risk" in rendered
    assert "**Estimated entity changes**: 3" in rendered


def test_sow_render_omits_empty_sections():
    sow = _make_sow()
    rendered = sow.render()
    assert "## Constraints" not in rendered
    assert "## Success Criteria" not in rendered
    assert "## Existing Entities" not in rendered
    assert "## Gaps" not in rendered
    assert "## In Scope" not in rendered
    assert "## Out of Scope" not in rendered
    assert "## Assumptions" not in rendered
    assert "## Risk Factors" not in rendered
    assert "**Estimated entity changes**" not in rendered
    assert "**Estimated effort**: 5 MD" in rendered  # rendered when non-zero; default from _make_sow


def test_sow_render_estimated_md():
    sow = _make_sow(estimated_md=20, estimated_entity_changes=45)
    rendered = sow.render()
    assert "**Estimated effort**: 20 MD" in rendered
    assert "**Estimated entity changes**: 45" in rendered


def test_sow_render_entity_without_notes():
    sow = _make_sow(existing_entities=[EntityRef(entity_type="workspace", entity_id=5, entity_name="WS")])
    rendered = sow.render()
    # No trailing dash when notes are empty
    assert 'workspace 5 "WS"' in rendered
    assert "—" not in rendered.split("## Existing Entities")[1].split("\n")[1]


def test_sow_render_entity_without_id_or_name():
    ref = EntityRef(**{"type": "email_templates", "notes": "multiple active"})
    sow = _make_sow(existing_entities=[ref])
    rendered = sow.render()
    assert "email_templates — multiple active" in rendered


def test_sow_render_summary():
    sow = _make_sow(
        in_scope=[ScopeItem(description="Task A"), ScopeItem(description="Task B"), ScopeItem(description="Task C")],
        estimated_entity_changes=12,
    )
    summary = sow.render_summary()
    assert summary == ('[Active SoW: "Invoice Automation" (draft) — 3 deliverables, ~12 entity changes]')


def test_sow_actuals_appear_in_render():
    sow = _make_sow(
        estimated_entity_changes=5,
        actual_entity_changes=8,
        estimation_notes="missed 3 queue config items",
    )
    rendered = sow.render()
    assert "**Actual entity changes**: 8 (delta: +3)" in rendered
    assert "**Estimation notes**: missed 3 queue config items" in rendered


def test_sow_render_no_actuals():
    sow = _make_sow(estimated_entity_changes=5)
    rendered = sow.render()
    assert "**Actual entity changes**" not in rendered
    assert "**Estimation notes**" not in rendered


def test_sow_actuals_negative_delta_in_render():
    sow = _make_sow(estimated_entity_changes=10, actual_entity_changes=7)
    rendered = sow.render()
    assert "**Actual entity changes**: 7 (delta: -3)" in rendered


def test_sow_actuals_no_notes_omits_notes_line():
    sow = _make_sow(estimated_entity_changes=5, actual_entity_changes=5)
    rendered = sow.render()
    assert "**Actual entity changes**: 5 (delta: +0)" in rendered
    assert "**Estimation notes**" not in rendered


def test_render_calibration_returns_none_without_actuals():
    sow = _make_sow(estimated_entity_changes=5)
    assert sow.render_calibration() is None


def test_render_calibration_with_actuals():
    sow = _make_sow(
        estimated_entity_changes=5,
        actual_entity_changes=8,
        estimation_notes="missed queue configs",
    )
    line = sow.render_calibration()
    assert line is not None
    assert '"Invoice Automation"' in line
    assert "estimated 5" in line
    assert "actual 8" in line
    assert "(+3)" in line
    assert "Notes: 'missed queue configs'" in line


def test_render_calibration_positive_delta():
    sow = _make_sow(estimated_entity_changes=3, actual_entity_changes=7)
    line = sow.render_calibration()
    assert line is not None
    assert "(+4)" in line


def test_render_calibration_negative_delta():
    sow = _make_sow(estimated_entity_changes=10, actual_entity_changes=6)
    line = sow.render_calibration()
    assert line is not None
    assert "(-4)" in line


def test_render_calibration_zero_delta():
    sow = _make_sow(estimated_entity_changes=5, actual_entity_changes=5)
    line = sow.render_calibration()
    assert line is not None
    assert "(+0)" in line


def test_render_calibration_no_notes_omits_notes():
    sow = _make_sow(estimated_entity_changes=5, actual_entity_changes=8)
    line = sow.render_calibration()
    assert line is not None
    assert "Notes" not in line


def test_render_summary_with_actuals():
    sow = _make_sow(
        in_scope=[ScopeItem(description="Task A")],
        estimated_entity_changes=5,
        actual_entity_changes=8,
    )
    summary = sow.render_summary()
    assert "estimated 5 → actual 8 entity changes" in summary
    assert "~" not in summary


# -- PlannedStep --------------------------------------------------------------


def test_planned_step_defaults():
    step = PlannedStep(
        step_number=1,
        action="create",
        entity_type="queue",
        entity_name="Invoices",
        description="Create the invoice queue",
    )
    assert step.entity_id is None
    assert step.depends_on == []
    assert step.detailed_spec == ""
    assert step.estimated_tools == []
    assert step.verification == ""
    assert step.risk_level == "low"
    assert step.status == "pending"
    assert step.result_entity_id is None


def test_planned_step_all_status_values():
    for status in ("pending", "in_progress", "completed", "failed", "skipped"):
        step = PlannedStep(
            step_number=1,
            action="verify",
            entity_type="queue",
            entity_name="Q",
            description="Check queue",
            status=status,
        )
        assert step.status == status


def test_planned_step_all_action_values():
    for action in ("create", "update", "delete", "configure", "verify", "test"):
        step = PlannedStep(
            step_number=1, action=action, entity_type="schema", entity_name="S", description="Do something"
        )
        assert step.action == action


# -- ImplementationPlan -------------------------------------------------------


def _make_plan(**overrides) -> ImplementationPlan:
    defaults = {
        "environment": "https://example.rossum.app/api/v1",
        "created_at": FIXED_DT,
        "goal": "Deploy invoice automation",
        "phases": [
            ImplementationPhase(
                phase_number=1,
                name="Setup",
                description="Initial setup",
                steps=[
                    PlannedStep(
                        step_number=1,
                        action="create",
                        entity_type="workspace",
                        entity_name="WS",
                        description="Create workspace",
                        status="completed",
                    ),
                    PlannedStep(
                        step_number=2,
                        action="create",
                        entity_type="queue",
                        entity_name="Queue",
                        description="Create queue",
                        status="in_progress",
                    ),
                ],
                rollback_strategy="Delete workspace",
            ),
            ImplementationPhase(
                phase_number=2,
                name="Configure",
                steps=[
                    PlannedStep(
                        step_number=3,
                        action="configure",
                        entity_type="schema",
                        entity_name="Schema",
                        description="Configure schema",
                        status="pending",
                    ),
                    PlannedStep(
                        step_number=4,
                        action="verify",
                        entity_type="queue",
                        entity_name="Queue",
                        description="Verify queue works",
                        status="failed",
                    ),
                ],
            ),
        ],
    }
    defaults.update(overrides)
    return ImplementationPlan(**defaults)


def test_plan_defaults():
    plan = _make_plan()
    assert plan.status == "draft"
    assert plan.sow_artifact_id is None
    assert plan.related_commit_hashes == []


def test_plan_render_step_markers():
    plan = _make_plan()
    rendered = plan.render()

    assert "# Implementation Plan: Deploy invoice automation" in rendered
    assert "**Environment**: https://example.rossum.app/api/v1" in rendered
    assert "**Status**: draft" in rendered
    assert "2024-01-15T10:00:00" in rendered

    # Phase headers
    assert "## Phase 1: Setup" in rendered
    assert "Initial setup" in rendered
    assert "## Phase 2: Configure" in rendered

    # Step markers match status
    assert '[x] Step 1: create workspace "WS"' in rendered
    assert '[>] Step 2: create queue "Queue"' in rendered
    assert '[ ] Step 3: configure schema "Schema"' in rendered
    assert '[!] Step 4: verify queue "Queue"' in rendered

    # Rollback
    assert "Rollback: Delete workspace" in rendered


def test_plan_render_with_sow_artifact_id():
    plan = _make_plan(sow_artifact_id="sow-abc-123")
    rendered = plan.render()
    assert "**SoW**: sow-abc-123" in rendered


def test_plan_render_skipped_marker():
    plan = ImplementationPlan(
        environment="https://test.rossum.app/api/v1",
        created_at=FIXED_DT,
        goal="Test",
        phases=[
            ImplementationPhase(
                phase_number=1,
                name="Only",
                steps=[
                    PlannedStep(
                        step_number=1,
                        action="test",
                        entity_type="queue",
                        entity_name="Q",
                        description="Skip this",
                        status="skipped",
                    )
                ],
            )
        ],
    )
    rendered = plan.render()
    assert '[-] Step 1: test queue "Q"' in rendered


def test_plan_render_progress():
    plan = _make_plan()
    progress = plan.render_progress()

    assert "Progress: 1/4 steps completed" in progress
    assert "(1 failed)" in progress
    assert "(1 in progress)" in progress
    assert "Phase 1 (Setup): 1/2" in progress
    assert "Phase 2 (Configure): 0/2" in progress


def test_plan_render_progress_clean():
    """No failed/in_progress annotations when counts are zero."""
    plan = ImplementationPlan(
        environment="https://test.rossum.app/api/v1",
        created_at=FIXED_DT,
        goal="Simple",
        phases=[
            ImplementationPhase(
                phase_number=1,
                name="Only",
                steps=[
                    PlannedStep(
                        step_number=1,
                        action="create",
                        entity_type="queue",
                        entity_name="Q",
                        description="Create it",
                        status="completed",
                    )
                ],
            )
        ],
    )
    progress = plan.render_progress()
    assert progress == "Progress: 1/1 steps completed\n  Phase 1 (Only): 1/1"


def test_plan_render_summary():
    plan = _make_plan(status="executing")
    summary = plan.render_summary()
    assert summary == ('[Active Plan: "Deploy invoice automation" (executing) — 1/4 steps, 2 phases]')


def test_plan_serialization_roundtrip():
    plan = _make_plan(sow_artifact_id="sow-1", related_commit_hashes=["abc123"])
    json_str = plan.model_dump_json()
    restored = ImplementationPlan.model_validate_json(json_str)
    assert restored == plan
    assert restored.phases[0].steps[0].status == "completed"
    assert restored.related_commit_hashes == ["abc123"]
