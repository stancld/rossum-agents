"""Tests for planning tools (create_sow, create_implementation_plan, etc.)."""

from __future__ import annotations

import json

import boto3
import pytest
from moto import mock_aws
from rossum_agent.storage.artifact_store import ArtifactStore
from rossum_agent.storage.s3_backend import S3StorageBackend
from rossum_agent.tools.core import AgentContext, reset_context, set_context
from rossum_agent.tools.planning import (
    create_implementation_plan,
    create_sow,
    get_active_plan,
    record_sow_outcome,
    update_plan_step,
)

BUCKET = "test-bucket"


@pytest.fixture
def artifact_store():
    with mock_aws():
        boto3.client(
            "s3",
            region_name="us-east-1",
            aws_access_key_id="test",
            aws_secret_access_key="test",
        ).create_bucket(Bucket=BUCKET)
        backend = S3StorageBackend(bucket=BUCKET, endpoint_url=None, access_key="test", secret_key="test")
        yield ArtifactStore(backend)


@pytest.fixture
def agent_ctx(artifact_store):
    ctx = AgentContext(
        rossum_credentials=("https://api.rossum.ai", "token"),
        rossum_environment="https://api.rossum.ai",
        artifact_store=artifact_store,
    )
    token = set_context(ctx)
    yield ctx
    reset_context(token)


@pytest.fixture
def ctx_no_store():
    ctx = AgentContext(
        rossum_credentials=("https://api.rossum.ai", "token"),
        rossum_environment="https://api.rossum.ai",
        artifact_store=None,
    )
    token = set_context(ctx)
    yield ctx
    reset_context(token)


_SCOPE = [
    {
        "entity_ref": {"entity_type": "schema", "entity_id": "123", "entity_name": "Invoice Schema"},
        "planned_operations": ["update"],
        "notes": "Add 2 fields",
    }
]
_ESTIMATED_OPS = {"schema": 1}


# ---------------------------------------------------------------------------
# create_sow
# ---------------------------------------------------------------------------


class TestCreateSow:
    def test_creates_sow_successfully(self, agent_ctx):
        result = json.loads(create_sow("My SoW", "Do the thing", _SCOPE, _ESTIMATED_OPS))
        assert result["status"] == "success"
        assert "sow_id" in result
        assert result["sow_id"].startswith("sow-")
        assert "My SoW" in result["content"]

    def test_sow_persisted_and_retrievable(self, agent_ctx):
        result = json.loads(create_sow("Persisted SoW", "desc", _SCOPE, _ESTIMATED_OPS))
        sow_id = result["sow_id"]

        # Verify it's in S3
        from rossum_agent.planning.models import StatementOfWork
        from rossum_agent.storage.handles import SoWHandle

        artifacts = agent_ctx.artifact_store.list_artifacts("api.rossum.ai", "sow", SoWHandle)
        assert len(artifacts) == 1
        assert isinstance(artifacts[0], StatementOfWork)
        assert artifacts[0].sow_id == sow_id
        assert artifacts[0].title == "Persisted SoW"

    def test_no_store_returns_error(self, ctx_no_store):
        result = json.loads(create_sow("SoW", "desc", _SCOPE, _ESTIMATED_OPS))
        assert result["status"] == "error"
        assert "not available" in result["message"]

    def test_invalid_scope_returns_error(self, agent_ctx):
        bad_scope = [{"entity_ref": "not-a-dict"}]
        result = json.loads(create_sow("SoW", "desc", bad_scope, {}))
        assert result["status"] == "error"
        assert "Invalid scope" in result["message"]

    def test_rendered_content_includes_scope(self, agent_ctx):
        result = json.loads(create_sow("My SoW", "desc", _SCOPE, {"schema": 2}))
        assert "Invoice Schema" in result["content"]
        assert "schema" in result["content"]


# ---------------------------------------------------------------------------
# create_implementation_plan
# ---------------------------------------------------------------------------


class TestCreateImplementationPlan:
    def test_creates_plan_successfully(self, agent_ctx):
        sow_result = json.loads(create_sow("SoW", "desc", _SCOPE, _ESTIMATED_OPS))
        sow_id = sow_result["sow_id"]

        phases = [{"name": "Phase 1", "steps": [{"description": "Update schema", "entity_refs": []}]}]
        result = json.loads(create_implementation_plan(sow_id, phases))

        assert result["status"] == "success"
        assert result["plan_id"].startswith("plan-")
        assert "Phase 1" in result["content"]

    def test_plan_persisted(self, agent_ctx):
        sow_id = json.loads(create_sow("SoW", "desc", _SCOPE, _ESTIMATED_OPS))["sow_id"]
        phases = [{"name": "Setup", "steps": [{"description": "Create hook"}]}]
        plan_id = json.loads(create_implementation_plan(sow_id, phases))["plan_id"]

        from rossum_agent.planning.models import ImplementationPlan
        from rossum_agent.storage.handles import PlanHandle

        artifacts = agent_ctx.artifact_store.list_artifacts("api.rossum.ai", "plan", PlanHandle)
        assert len(artifacts) == 1
        assert isinstance(artifacts[0], ImplementationPlan)
        assert artifacts[0].plan_id == plan_id
        assert artifacts[0].sow_id == sow_id

    def test_no_store_returns_error(self, ctx_no_store):
        result = json.loads(create_implementation_plan("sow-1", []))
        assert result["status"] == "error"

    def test_invalid_phases_returns_error(self, agent_ctx):
        # Step missing 'description' key
        bad_phases = [{"name": "P1", "steps": [{"no_description": True}]}]
        result = json.loads(create_implementation_plan("sow-1", bad_phases))
        assert result["status"] == "error"
        assert "Invalid phases" in result["message"]


# ---------------------------------------------------------------------------
# update_plan_step
# ---------------------------------------------------------------------------


class TestUpdatePlanStep:
    def _create_plan_with_steps(self, agent_ctx):
        sow_id = json.loads(create_sow("SoW", "desc", _SCOPE, _ESTIMATED_OPS))["sow_id"]
        phases = [
            {
                "phase_id": "phase-1",
                "name": "Phase 1",
                "steps": [
                    {"step_id": "step-1", "description": "Step one"},
                    {"step_id": "step-2", "description": "Step two"},
                ],
            }
        ]
        return json.loads(create_implementation_plan(sow_id, phases))["plan_id"]

    def test_marks_step_done(self, agent_ctx):
        plan_id = self._create_plan_with_steps(agent_ctx)
        result = json.loads(update_plan_step(plan_id, "phase-1", "step-1", "done"))
        assert result["status"] == "success"
        assert "progress" in result

    def test_plan_status_executing_when_in_progress(self, agent_ctx):
        plan_id = self._create_plan_with_steps(agent_ctx)
        update_plan_step(plan_id, "phase-1", "step-1", "in_progress")

        active = json.loads(get_active_plan())
        assert active["status"] == "success"
        assert "executing" in active["progress"]

    def test_plan_status_completed_when_all_done(self, agent_ctx):
        plan_id = self._create_plan_with_steps(agent_ctx)
        update_plan_step(plan_id, "phase-1", "step-1", "done")
        update_plan_step(plan_id, "phase-1", "step-2", "done")

        active = json.loads(get_active_plan())
        assert active["status"] == "completed"

    def test_unknown_plan_returns_error(self, agent_ctx):
        result = json.loads(update_plan_step("nonexistent-plan", "phase-1", "step-1", "done"))
        assert result["status"] == "error"
        assert "not found" in result["message"]

    def test_unknown_phase_returns_error(self, agent_ctx):
        plan_id = self._create_plan_with_steps(agent_ctx)
        result = json.loads(update_plan_step(plan_id, "bad-phase", "step-1", "done"))
        assert result["status"] == "error"
        assert "Phase" in result["message"]

    def test_unknown_step_returns_error(self, agent_ctx):
        plan_id = self._create_plan_with_steps(agent_ctx)
        result = json.loads(update_plan_step(plan_id, "phase-1", "bad-step", "done"))
        assert result["status"] == "error"
        assert "Step" in result["message"]

    def test_invalid_status_returns_error(self, agent_ctx):
        plan_id = self._create_plan_with_steps(agent_ctx)
        result = json.loads(update_plan_step(plan_id, "phase-1", "step-1", "complete"))
        assert result["status"] == "error"
        assert "Invalid status" in result["message"]


# ---------------------------------------------------------------------------
# get_active_plan
# ---------------------------------------------------------------------------


class TestGetActivePlan:
    def test_no_plan_returns_not_found(self, agent_ctx):
        result = json.loads(get_active_plan())
        assert result["status"] == "not_found"

    def test_returns_active_plan(self, agent_ctx):
        sow_id = json.loads(create_sow("SoW", "desc", _SCOPE, _ESTIMATED_OPS))["sow_id"]
        phases = [{"name": "Phase 1", "steps": [{"description": "Step one"}]}]
        plan_id = json.loads(create_implementation_plan(sow_id, phases))["plan_id"]

        result = json.loads(get_active_plan())
        assert result["status"] == "success"
        assert result["plan_id"] == plan_id
        assert "Phase 1" in result["content"]

    def test_no_store_returns_error(self, ctx_no_store):
        result = json.loads(get_active_plan())
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# record_sow_outcome
# ---------------------------------------------------------------------------


class TestRecordSowOutcome:
    def test_records_outcome_successfully(self, agent_ctx):
        sow_id = json.loads(create_sow("SoW", "desc", _SCOPE, {"schema": 1}))["sow_id"]
        result = json.loads(record_sow_outcome(sow_id, {"schema": 2}))

        assert result["status"] == "success"
        assert "calibration" in result
        assert "schema" in result["calibration"]

    def test_calibration_shows_delta(self, agent_ctx):
        sow_id = json.loads(create_sow("SoW", "desc", _SCOPE, {"schema": 1}))["sow_id"]
        result = json.loads(record_sow_outcome(sow_id, {"schema": 3}))

        # Estimated 1, actual 3 → delta +2
        assert "+2" in result["calibration"]

    def test_unknown_sow_returns_error(self, agent_ctx):
        result = json.loads(record_sow_outcome("nonexistent-sow", {"schema": 1}))
        assert result["status"] == "error"
        assert "not found" in result["message"]

    def test_no_store_returns_error(self, ctx_no_store):
        result = json.loads(record_sow_outcome("sow-1", {}))
        assert result["status"] == "error"
