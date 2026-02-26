from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from rossum_agent.storage.handles import (
    Context,
    ContextHandle,
    Plan,
    PlanHandle,
    SoW,
    SoWHandle,
)

TIMESTAMP = datetime(2026, 2, 23, 10, 30, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# s3_key
# ---------------------------------------------------------------------------


def test_sow_handle_s3_key():
    handle = SoWHandle(org_id="org1", artifact_id="sow-abc", timestamp=TIMESTAMP)
    assert handle.s3_key == "artifacts/org1/sow/2026-02-23T10:30:00+00:00_sow-abc.json"


def test_plan_handle_s3_key():
    handle = PlanHandle(org_id="org1", artifact_id="plan-1", timestamp=TIMESTAMP)
    assert handle.s3_key == "artifacts/org1/plan/2026-02-23T10:30:00+00:00_plan-1.json"


def test_context_handle_s3_key():
    handle = ContextHandle(org_id="org1", artifact_id="ctx-1", timestamp=TIMESTAMP)
    assert handle.s3_key == "artifacts/org1/context/2026-02-23T10:30:00+00:00_ctx-1.json"


# ---------------------------------------------------------------------------
# from_key roundtrip
# ---------------------------------------------------------------------------


def test_sow_handle_from_key_roundtrip():
    original = SoWHandle(org_id="org1", artifact_id="sow-abc", timestamp=TIMESTAMP)
    restored = SoWHandle.from_key(original.s3_key)
    assert restored.org_id == "org1"
    assert restored.artifact_type == "sow"
    assert restored.artifact_id == "sow-abc"
    assert restored.timestamp == TIMESTAMP


def test_plan_handle_from_key_roundtrip():
    original = PlanHandle(org_id="org2", artifact_id="plan-xyz", timestamp=TIMESTAMP)
    restored = PlanHandle.from_key(original.s3_key)
    assert restored.org_id == "org2"
    assert restored.artifact_type == "plan"
    assert restored.artifact_id == "plan-xyz"
    assert restored.timestamp == TIMESTAMP


def test_context_handle_from_key_roundtrip():
    original = ContextHandle(org_id="org3", artifact_id="ctx-1", timestamp=TIMESTAMP)
    restored = ContextHandle.from_key(original.s3_key)
    assert restored.org_id == "org3"
    assert restored.artifact_type == "context"
    assert restored.artifact_id == "ctx-1"
    assert restored.timestamp == TIMESTAMP


def test_from_key_artifact_id_with_underscore():
    # artifact_id containing underscores must survive the split
    handle = SoWHandle(org_id="org1", artifact_id="sow_foo_bar", timestamp=TIMESTAMP)
    restored = SoWHandle.from_key(handle.s3_key)
    assert restored.artifact_id == "sow_foo_bar"


# ---------------------------------------------------------------------------
# serialize / deserialize
# ---------------------------------------------------------------------------


def test_sow_serialize_deserialize():
    handle = SoWHandle(org_id="org1", artifact_id="sow-1", timestamp=TIMESTAMP)
    sow = SoW(title="My SoW", content="Do the thing")
    data = handle.serialize(sow)
    restored = handle.deserialize(data)
    assert restored == sow


def test_plan_serialize_deserialize():
    handle = PlanHandle(org_id="org1", artifact_id="plan-1", timestamp=TIMESTAMP)
    plan = Plan(title="My Plan", steps=["step 1", "step 2"])
    data = handle.serialize(plan)
    restored = handle.deserialize(data)
    assert restored == plan


def test_context_serialize_deserialize():
    handle = ContextHandle(org_id="org1", artifact_id="ctx-1", timestamp=TIMESTAMP)
    ctx = Context(summary="some context", data={"key": "value"})
    data = handle.serialize(ctx)
    restored = handle.deserialize(data)
    assert restored == ctx


def test_serialize_produces_json_bytes():
    handle = SoWHandle(org_id="org1", artifact_id="sow-1", timestamp=TIMESTAMP)
    sow = SoW(title="T", content="C")
    data = handle.serialize(sow)
    assert isinstance(data, bytes)
    assert b'"title"' in data


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_sow_handle_wrong_artifact_type_rejected():
    plan_handle = PlanHandle(org_id="org1", artifact_id="plan-1", timestamp=TIMESTAMP)
    with pytest.raises(ValidationError):
        # Parsing a plan key with SoWHandle should fail Literal["sow"] validation
        SoWHandle.from_key(plan_handle.s3_key)
