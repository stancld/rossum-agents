from __future__ import annotations

from datetime import UTC, datetime

import boto3
import pytest
from moto import mock_aws
from rossum_agent.storage.artifact_store import ArtifactStore
from rossum_agent.storage.handles import (
    Context,
    ContextHandle,
    Plan,
    PlanHandle,
    SoW,
    SoWHandle,
)
from rossum_agent.storage.s3_backend import S3StorageBackend

BUCKET = "test-bucket"
TS1 = datetime(2026, 2, 23, 10, 0, 0, tzinfo=UTC)
TS2 = datetime(2026, 2, 23, 11, 0, 0, tzinfo=UTC)
TS3 = datetime(2026, 2, 23, 12, 0, 0, tzinfo=UTC)


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


# ---------------------------------------------------------------------------
# save / load roundtrip
# ---------------------------------------------------------------------------


def test_save_and_load_sow(artifact_store):
    handle = SoWHandle(org_id="org1", artifact_id="sow-1", timestamp=TS1)
    sow = SoW(title="Initial SoW", content="Build the thing")
    artifact_store.save(handle, sow)
    result = artifact_store.load(handle)
    assert result == sow


def test_save_and_load_plan(artifact_store):
    handle = PlanHandle(org_id="org1", artifact_id="plan-1", timestamp=TS1)
    plan = Plan(title="Phase 1", steps=["research", "implement", "test"])
    artifact_store.save(handle, plan)
    result = artifact_store.load(handle)
    assert result == plan


def test_save_and_load_context(artifact_store):
    handle = ContextHandle(org_id="org1", artifact_id="ctx-1", timestamp=TS1)
    ctx = Context(summary="Project context", data={"env": "prod", "queue": "42"})
    artifact_store.save(handle, ctx)
    result = artifact_store.load(handle)
    assert result == ctx


def test_load_missing_returns_none(artifact_store):
    handle = SoWHandle(org_id="org1", artifact_id="nonexistent", timestamp=TS1)
    assert artifact_store.load(handle) is None


# ---------------------------------------------------------------------------
# load_latest
# ---------------------------------------------------------------------------


def test_load_latest_empty(artifact_store):
    result = artifact_store.load_latest("org1", "sow", SoWHandle)
    assert result is None


def test_load_latest_single(artifact_store):
    handle = SoWHandle(org_id="org1", artifact_id="sow-1", timestamp=TS1)
    sow = SoW(title="Only one", content="content")
    artifact_store.save(handle, sow)
    result = artifact_store.load_latest("org1", "sow", SoWHandle)
    assert result == sow


def test_load_latest_returns_most_recent(artifact_store):
    sow_old = SoW(title="Old SoW", content="old content")
    sow_mid = SoW(title="Mid SoW", content="mid content")
    sow_new = SoW(title="New SoW", content="new content")

    artifact_store.save(SoWHandle(org_id="org1", artifact_id="sow-1", timestamp=TS1), sow_old)
    artifact_store.save(SoWHandle(org_id="org1", artifact_id="sow-2", timestamp=TS2), sow_mid)
    artifact_store.save(SoWHandle(org_id="org1", artifact_id="sow-3", timestamp=TS3), sow_new)

    result = artifact_store.load_latest("org1", "sow", SoWHandle)
    assert result == sow_new


def test_load_latest_isolated_by_org(artifact_store):
    sow_org1 = SoW(title="Org1 SoW", content="org1")
    sow_org2 = SoW(title="Org2 SoW", content="org2")

    artifact_store.save(SoWHandle(org_id="org1", artifact_id="sow-1", timestamp=TS1), sow_org1)
    artifact_store.save(SoWHandle(org_id="org2", artifact_id="sow-1", timestamp=TS2), sow_org2)

    assert artifact_store.load_latest("org1", "sow", SoWHandle) == sow_org1
    assert artifact_store.load_latest("org2", "sow", SoWHandle) == sow_org2


def test_load_latest_isolated_by_artifact_type(artifact_store):
    sow = SoW(title="SoW", content="content")
    plan = Plan(title="Plan", steps=["step"])

    artifact_store.save(SoWHandle(org_id="org1", artifact_id="sow-1", timestamp=TS1), sow)
    artifact_store.save(PlanHandle(org_id="org1", artifact_id="plan-1", timestamp=TS2), plan)

    assert artifact_store.load_latest("org1", "sow", SoWHandle) == sow
    assert artifact_store.load_latest("org1", "plan", PlanHandle) == plan


# ---------------------------------------------------------------------------
# list_artifacts
# ---------------------------------------------------------------------------


def test_list_artifacts_empty(artifact_store):
    result = artifact_store.list_artifacts("org1", "sow", SoWHandle)
    assert result == []


def test_list_artifacts_single(artifact_store):
    sow = SoW(title="My SoW", content="content")
    artifact_store.save(SoWHandle(org_id="org1", artifact_id="sow-1", timestamp=TS1), sow)
    result = artifact_store.list_artifacts("org1", "sow", SoWHandle)
    assert result == [sow]


def test_list_artifacts_multiple_in_chronological_order(artifact_store):
    sow1 = SoW(title="First", content="first")
    sow2 = SoW(title="Second", content="second")
    sow3 = SoW(title="Third", content="third")

    # Save out of order to verify sorting
    artifact_store.save(SoWHandle(org_id="org1", artifact_id="sow-3", timestamp=TS3), sow3)
    artifact_store.save(SoWHandle(org_id="org1", artifact_id="sow-1", timestamp=TS1), sow1)
    artifact_store.save(SoWHandle(org_id="org1", artifact_id="sow-2", timestamp=TS2), sow2)

    result = artifact_store.list_artifacts("org1", "sow", SoWHandle)
    assert result == [sow1, sow2, sow3]


def test_list_artifacts_isolated_by_org(artifact_store):
    sow_org1 = SoW(title="Org1", content="org1")
    sow_org2 = SoW(title="Org2", content="org2")

    artifact_store.save(SoWHandle(org_id="org1", artifact_id="sow-1", timestamp=TS1), sow_org1)
    artifact_store.save(SoWHandle(org_id="org2", artifact_id="sow-1", timestamp=TS1), sow_org2)

    assert artifact_store.list_artifacts("org1", "sow", SoWHandle) == [sow_org1]
    assert artifact_store.list_artifacts("org2", "sow", SoWHandle) == [sow_org2]


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


def test_delete(artifact_store):
    handle = SoWHandle(org_id="org1", artifact_id="sow-1", timestamp=TS1)
    sow = SoW(title="To be deleted", content="content")
    artifact_store.save(handle, sow)
    artifact_store.delete(handle)
    assert artifact_store.load(handle) is None


def test_delete_does_not_affect_other_artifacts(artifact_store):
    h1 = SoWHandle(org_id="org1", artifact_id="sow-1", timestamp=TS1)
    h2 = SoWHandle(org_id="org1", artifact_id="sow-2", timestamp=TS2)
    sow1 = SoW(title="Keep", content="keep")
    sow2 = SoW(title="Delete", content="delete")

    artifact_store.save(h1, sow1)
    artifact_store.save(h2, sow2)
    artifact_store.delete(h2)

    assert artifact_store.load(h1) == sow1
    assert artifact_store.load(h2) is None
