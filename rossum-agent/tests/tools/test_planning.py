"""Tests for rossum_agent.tools.planning module."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from rossum_agent.planning.models import (
    ImplementationPhase,
    ImplementationPlan,
    PlannedStep,
    StatementOfWork,
)
from rossum_agent.storage.handles import PlanHandle, SoWHandle
from rossum_agent.tools.planning import (
    _slugify,
    create_implementation_plan,
    create_sow,
    get_active_plan,
    record_sow_outcome,
    update_plan_step,
)


class TestSlugify:
    def test_simple_text(self) -> None:
        assert _slugify("Deploy Schema") == "deploy-schema"

    def test_special_characters(self) -> None:
        assert _slugify("Hello, World! (test)") == "hello-world-test"

    def test_multiple_spaces_and_underscores(self) -> None:
        assert _slugify("foo   bar__baz") == "foo-bar-baz"

    def test_long_string_truncated(self) -> None:
        long_text = "a" * 100
        result = _slugify(long_text)
        assert len(result) <= 80

    def test_trailing_hyphens_stripped(self) -> None:
        assert _slugify("hello---") == "hello"

    def test_leading_hyphens_stripped(self) -> None:
        assert _slugify("---hello") == "hello"

    def test_empty_string(self) -> None:
        assert _slugify("") == ""

    def test_unicode_preserved(self) -> None:
        # \w matches unicode word characters in Python, so accented letters are kept
        assert _slugify("r\u00e9sum\u00e9 upload") == "r\u00e9sum\u00e9-upload"


MOCK_STORE = "rossum_agent.tools.planning.get_artifact_store"
MOCK_ENV = "rossum_agent.tools.planning.get_rossum_environment"


class TestCreateSoW:
    def test_creates_sow_and_saves(self) -> None:
        mock_store = MagicMock()
        with patch(MOCK_STORE, return_value=mock_store), patch(MOCK_ENV, return_value="test-env"):
            result = json.loads(
                create_sow(
                    title="Migrate Queues",
                    business_goal="Move all queues to new workspace",
                    in_scope=["Create new workspace", "Move queues"],
                    estimated_md=3,
                )
            )

        assert result["status"] == "created"
        assert result["artifact_id"] == "migrate-queues"
        assert result["title"] == "Migrate Queues"
        assert "rendered" in result
        mock_store.save.assert_called_once()

    def test_saves_with_correct_handle(self) -> None:
        mock_store = MagicMock()
        with patch(MOCK_STORE, return_value=mock_store), patch(MOCK_ENV, return_value="prod"):
            create_sow(
                title="Test Project",
                business_goal="Goal",
                in_scope=["Item 1"],
                estimated_md=5,
            )

        handle = mock_store.save.call_args[0][0]
        assert handle.environment == "prod"
        assert handle.artifact_id == "test-project"

    def test_with_all_optional_fields(self) -> None:
        mock_store = MagicMock()
        with patch(MOCK_STORE, return_value=mock_store), patch(MOCK_ENV, return_value="test-env"):
            result = json.loads(
                create_sow(
                    title="Full SoW",
                    business_goal="Complete goal",
                    in_scope=["Deliverable 1"],
                    estimated_md=10,
                    constraints=["No downtime"],
                    existing_entities=[{"entity_type": "queue", "entity_id": 123, "entity_name": "Main Queue"}],
                    gaps=["Missing schema"],
                    out_of_scope=["Billing changes"],
                    assumptions=["API is stable"],
                    success_criteria=["All tests pass"],
                    risk_factors=["Tight deadline"],
                    estimated_entity_changes=5,
                )
            )

        assert result["status"] == "created"
        sow = mock_store.save.call_args[0][1]
        assert len(sow.constraints) == 1
        assert len(sow.existing_entities) == 1
        assert sow.estimated_entity_changes == 5

    def test_store_unavailable_returns_error(self) -> None:
        with patch(MOCK_STORE, return_value=None), patch(MOCK_ENV, return_value="test-env"):
            result = json.loads(
                create_sow(
                    title="Test",
                    business_goal="Goal",
                    in_scope=["Item"],
                    estimated_md=2,
                )
            )

        assert "error" in result
        assert result["error"] == "Artifact storage not available"

    def test_env_unavailable_returns_error(self) -> None:
        mock_store = MagicMock()
        with patch(MOCK_STORE, return_value=mock_store), patch(MOCK_ENV, return_value=None):
            result = json.loads(
                create_sow(
                    title="Test",
                    business_goal="Goal",
                    in_scope=["Item"],
                    estimated_md=2,
                )
            )

        assert "error" in result
        mock_store.save.assert_not_called()


class TestCreateImplementationPlan:
    def test_creates_plan_and_saves(self) -> None:
        mock_store = MagicMock()
        phases = [
            {
                "phase_number": 1,
                "name": "Setup",
                "description": "Initial setup",
                "steps": [
                    {
                        "step_number": 1,
                        "action": "create",
                        "entity_type": "workspace",
                        "entity_name": "New WS",
                        "description": "Create workspace",
                    }
                ],
                "rollback_strategy": "Delete workspace",
            }
        ]

        with patch(MOCK_STORE, return_value=mock_store), patch(MOCK_ENV, return_value="test-env"):
            result = json.loads(
                create_implementation_plan(
                    goal="Deploy new workspace",
                    phases=phases,
                )
            )

        assert result["status"] == "created"
        assert result["artifact_id"] == "deploy-new-workspace"
        assert "rendered" in result
        mock_store.save.assert_called_once()

    def test_saves_with_sow_reference(self) -> None:
        mock_store = MagicMock()
        phases = [
            {
                "phase_number": 1,
                "name": "Phase 1",
                "steps": [
                    {
                        "step_number": 1,
                        "action": "create",
                        "entity_type": "schema",
                        "entity_name": "Invoice Schema",
                        "description": "Create schema",
                    }
                ],
            }
        ]

        with patch(MOCK_STORE, return_value=mock_store), patch(MOCK_ENV, return_value="test-env"):
            create_implementation_plan(
                goal="Setup schemas",
                phases=phases,
                sow_artifact_id="migrate-queues",
            )

        plan = mock_store.save.call_args[0][1]
        assert plan.sow_artifact_id == "migrate-queues"

    def test_multiple_phases_and_steps(self) -> None:
        mock_store = MagicMock()
        phases = [
            {
                "phase_number": 1,
                "name": "Phase 1",
                "steps": [
                    {
                        "step_number": 1,
                        "action": "create",
                        "entity_type": "workspace",
                        "entity_name": "WS",
                        "description": "Create workspace",
                    },
                    {
                        "step_number": 2,
                        "action": "create",
                        "entity_type": "queue",
                        "entity_name": "Q1",
                        "description": "Create queue",
                        "depends_on": [1],
                    },
                ],
            },
            {
                "phase_number": 2,
                "name": "Phase 2",
                "steps": [
                    {
                        "step_number": 3,
                        "action": "verify",
                        "entity_type": "queue",
                        "entity_name": "Q1",
                        "description": "Verify queue",
                        "depends_on": [2],
                    },
                ],
            },
        ]

        with patch(MOCK_STORE, return_value=mock_store), patch(MOCK_ENV, return_value="test-env"):
            result = json.loads(create_implementation_plan(goal="Full deploy", phases=phases))

        assert result["status"] == "created"
        plan = mock_store.save.call_args[0][1]
        assert len(plan.phases) == 2
        assert len(plan.phases[0].steps) == 2
        assert len(plan.phases[1].steps) == 1

    def test_store_unavailable_returns_error(self) -> None:
        with patch(MOCK_STORE, return_value=None), patch(MOCK_ENV, return_value="test-env"):
            result = json.loads(
                create_implementation_plan(
                    goal="Test",
                    phases=[],
                )
            )

        assert "error" in result


def _make_plan(
    status: str = "approved",
    step_statuses: list[str] | None = None,
) -> ImplementationPlan:
    """Helper to build a plan with one phase and configurable step statuses."""
    statuses = step_statuses or ["pending", "pending"]
    steps = [
        PlannedStep(
            step_number=i + 1,
            action="create",
            entity_type="schema",
            entity_name=f"Schema {i + 1}",
            description=f"Create schema {i + 1}",
            status=s,  # type: ignore[arg-type]
        )
        for i, s in enumerate(statuses)
    ]
    return ImplementationPlan(
        environment="test-env",
        created_at=datetime.now(UTC),
        goal="Test plan",
        status=status,  # type: ignore[arg-type]
        phases=[
            ImplementationPhase(
                phase_number=1,
                name="Phase 1",
                steps=steps,
            )
        ],
    )


class TestUpdatePlanStep:
    def test_updates_step_status(self) -> None:
        mock_store = MagicMock()
        plan = _make_plan()
        mock_handle = PlanHandle(environment="test-env", artifact_id="test-plan")
        mock_store.load_latest.return_value = (mock_handle, plan)

        with patch(MOCK_STORE, return_value=mock_store), patch(MOCK_ENV, return_value="test-env"):
            result = json.loads(
                update_plan_step(
                    step_number=1,
                    status="in_progress",
                )
            )

        assert result["status"] == "updated"
        assert result["step_number"] == 1
        assert result["step_status"] == "in_progress"
        assert "progress" in result

    def test_sets_result_entity_id(self) -> None:
        mock_store = MagicMock()
        plan = _make_plan()
        mock_handle = PlanHandle(environment="test-env", artifact_id="test-plan")
        mock_store.load_latest.return_value = (mock_handle, plan)

        with patch(MOCK_STORE, return_value=mock_store), patch(MOCK_ENV, return_value="test-env"):
            update_plan_step(
                step_number=1,
                status="completed",
                result_entity_id=42,
            )

        saved_plan = mock_store.save.call_args[0][1]
        assert saved_plan.phases[0].steps[0].result_entity_id == 42

    def test_transitions_plan_to_executing(self) -> None:
        mock_store = MagicMock()
        plan = _make_plan(status="approved")
        mock_handle = PlanHandle(environment="test-env", artifact_id="test-plan")
        mock_store.load_latest.return_value = (mock_handle, plan)

        with patch(MOCK_STORE, return_value=mock_store), patch(MOCK_ENV, return_value="test-env"):
            update_plan_step(
                step_number=1,
                status="in_progress",
            )

        saved_plan = mock_store.save.call_args[0][1]
        assert saved_plan.status == "executing"

    def test_transitions_plan_to_completed(self) -> None:
        mock_store = MagicMock()
        plan = _make_plan(step_statuses=["completed", "pending"])
        mock_handle = PlanHandle(environment="test-env", artifact_id="test-plan")
        mock_store.load_latest.return_value = (mock_handle, plan)

        with patch(MOCK_STORE, return_value=mock_store), patch(MOCK_ENV, return_value="test-env"):
            update_plan_step(
                step_number=2,
                status="completed",
            )

        saved_plan = mock_store.save.call_args[0][1]
        assert saved_plan.status == "completed"

    def test_skipped_steps_count_as_done(self) -> None:
        mock_store = MagicMock()
        plan = _make_plan(step_statuses=["completed", "pending"])
        mock_handle = PlanHandle(environment="test-env", artifact_id="test-plan")
        mock_store.load_latest.return_value = (mock_handle, plan)

        with patch(MOCK_STORE, return_value=mock_store), patch(MOCK_ENV, return_value="test-env"):
            update_plan_step(
                step_number=2,
                status="skipped",
            )

        saved_plan = mock_store.save.call_args[0][1]
        assert saved_plan.status == "completed"

    def test_no_active_plan_returns_error(self) -> None:
        mock_store = MagicMock()
        mock_store.load_latest.return_value = None

        with patch(MOCK_STORE, return_value=mock_store), patch(MOCK_ENV, return_value="test-env"):
            result = json.loads(
                update_plan_step(
                    step_number=1,
                    status="in_progress",
                )
            )

        assert "error" in result
        assert result["error"] == "No active plan found"

    def test_store_unavailable_returns_error(self) -> None:
        with patch(MOCK_STORE, return_value=None), patch(MOCK_ENV, return_value="test-env"):
            result = json.loads(
                update_plan_step(
                    step_number=1,
                    status="in_progress",
                )
            )

        assert "error" in result


class TestGetActivePlan:
    def test_returns_active_plan(self) -> None:
        mock_store = MagicMock()
        plan = _make_plan(status="approved")
        mock_handle = PlanHandle(environment="test-env", artifact_id="test-plan")
        mock_store.load_latest.return_value = (mock_handle, plan)

        with patch(MOCK_STORE, return_value=mock_store), patch(MOCK_ENV, return_value="test-env"):
            result = json.loads(get_active_plan())

        assert result["artifact_id"] == "test-plan"
        assert result["status"] == "approved"
        assert "rendered" in result
        assert "progress" in result

    def test_returns_executing_plan(self) -> None:
        mock_store = MagicMock()
        plan = _make_plan(status="executing")
        mock_handle = PlanHandle(environment="test-env", artifact_id="test-plan")
        mock_store.load_latest.return_value = (mock_handle, plan)

        with patch(MOCK_STORE, return_value=mock_store), patch(MOCK_ENV, return_value="test-env"):
            result = json.loads(get_active_plan())

        assert result["status"] == "executing"

    def test_returns_draft_plan(self) -> None:
        mock_store = MagicMock()
        plan = _make_plan(status="draft")
        mock_handle = PlanHandle(environment="test-env", artifact_id="test-plan")
        mock_store.load_latest.return_value = (mock_handle, plan)

        with patch(MOCK_STORE, return_value=mock_store), patch(MOCK_ENV, return_value="test-env"):
            result = json.loads(get_active_plan())

        assert result["status"] == "draft"

    def test_no_plan_found(self) -> None:
        mock_store = MagicMock()
        mock_store.load_latest.return_value = None

        with patch(MOCK_STORE, return_value=mock_store), patch(MOCK_ENV, return_value="test-env"):
            result = json.loads(get_active_plan())

        assert result["message"] == "No active plan found"

    def test_inactive_plan_returns_message(self) -> None:
        mock_store = MagicMock()
        plan = _make_plan(status="completed")
        mock_handle = PlanHandle(environment="test-env", artifact_id="test-plan")
        mock_store.load_latest.return_value = (mock_handle, plan)

        with patch(MOCK_STORE, return_value=mock_store), patch(MOCK_ENV, return_value="test-env"):
            result = json.loads(get_active_plan())

        assert "message" in result
        assert "completed" in result["message"]

    def test_aborted_plan_returns_message(self) -> None:
        mock_store = MagicMock()
        plan = _make_plan(status="aborted")
        mock_handle = PlanHandle(environment="test-env", artifact_id="test-plan")
        mock_store.load_latest.return_value = (mock_handle, plan)

        with patch(MOCK_STORE, return_value=mock_store), patch(MOCK_ENV, return_value="test-env"):
            result = json.loads(get_active_plan())

        assert "message" in result
        assert "aborted" in result["message"]

    def test_store_unavailable_returns_error(self) -> None:
        with patch(MOCK_STORE, return_value=None), patch(MOCK_ENV, return_value="test-env"):
            result = json.loads(get_active_plan())

        assert "error" in result


def _make_sow(estimated: int = 5, title: str = "EU Invoice Processing") -> StatementOfWork:
    return StatementOfWork(
        title=title,
        environment="test-env",
        created_at=datetime.now(UTC),
        business_goal="Automate invoice processing",
        estimated_entity_changes=estimated,
        estimated_md=5,
    )


class TestRecordSoWOutcome:
    def test_updates_latest_sow(self) -> None:
        mock_store = MagicMock()
        sow = _make_sow(estimated=5)
        mock_handle = SoWHandle(environment="test-env", artifact_id="eu-invoice-processing")
        mock_store.load_latest.return_value = (mock_handle, sow)

        with patch(MOCK_STORE, return_value=mock_store), patch(MOCK_ENV, return_value="test-env"):
            result = json.loads(record_sow_outcome(actual_entity_changes=8, notes="missed 3 items"))

        assert result["status"] == "recorded"
        assert result["estimated"] == 5
        assert result["actual"] == 8
        assert result["delta"] == 3
        assert result["artifact_id"] == "eu-invoice-processing"
        saved_sow = mock_store.save.call_args[0][1]
        assert saved_sow.actual_entity_changes == 8
        assert saved_sow.estimation_notes == "missed 3 items"

    def test_updates_specific_sow_by_id(self) -> None:
        mock_store = MagicMock()
        sow_a = _make_sow(estimated=3, title="Project A")
        sow_b = _make_sow(estimated=7, title="Project B")
        handle_a = SoWHandle(environment="test-env", artifact_id="project-a")
        handle_b = SoWHandle(environment="test-env", artifact_id="project-b")
        mock_store.list_artifacts.return_value = [(handle_a, sow_a), (handle_b, sow_b)]

        with patch(MOCK_STORE, return_value=mock_store), patch(MOCK_ENV, return_value="test-env"):
            result = json.loads(record_sow_outcome(actual_entity_changes=10, sow_artifact_id="project-b"))

        assert result["status"] == "recorded"
        assert result["artifact_id"] == "project-b"
        assert result["estimated"] == 7
        assert result["actual"] == 10
        assert result["delta"] == 3

    def test_specific_sow_not_found(self) -> None:
        mock_store = MagicMock()
        sow = _make_sow()
        handle = SoWHandle(environment="test-env", artifact_id="some-sow")
        mock_store.list_artifacts.return_value = [(handle, sow)]

        with patch(MOCK_STORE, return_value=mock_store), patch(MOCK_ENV, return_value="test-env"):
            result = json.loads(record_sow_outcome(actual_entity_changes=5, sow_artifact_id="nonexistent"))

        assert result == {"error": "No SoW found"}
        mock_store.save.assert_not_called()

    def test_no_sow_exists(self) -> None:
        mock_store = MagicMock()
        mock_store.load_latest.return_value = None

        with patch(MOCK_STORE, return_value=mock_store), patch(MOCK_ENV, return_value="test-env"):
            result = json.loads(record_sow_outcome(actual_entity_changes=5))

        assert result == {"error": "No SoW found"}
        mock_store.save.assert_not_called()

    def test_store_unavailable(self) -> None:
        with patch(MOCK_STORE, return_value=None), patch(MOCK_ENV, return_value="test-env"):
            result = json.loads(record_sow_outcome(actual_entity_changes=5))

        assert result == {"error": "Artifact storage not available"}

    def test_returns_delta(self) -> None:
        mock_store = MagicMock()
        sow = _make_sow(estimated=10)
        handle = SoWHandle(environment="test-env", artifact_id="some-sow")
        mock_store.load_latest.return_value = (handle, sow)

        with patch(MOCK_STORE, return_value=mock_store), patch(MOCK_ENV, return_value="test-env"):
            result = json.loads(record_sow_outcome(actual_entity_changes=6))

        assert result["delta"] == -4
