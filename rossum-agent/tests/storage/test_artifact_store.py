from __future__ import annotations

from datetime import UTC, datetime

import boto3
import pytest
from moto import mock_aws
from rossum_agent.context.models import EnvironmentContext
from rossum_agent.planning.models import ImplementationPlan, StatementOfWork
from rossum_agent.storage.artifact_store import ArtifactStore
from rossum_agent.storage.handles import ContextHandle, PlanHandle, SoWHandle
from rossum_agent.storage.s3_backend import S3StorageBackend

BUCKET = "test-bucket"
TS1 = datetime(2026, 2, 23, 10, 0, 0, tzinfo=UTC)
TS2 = datetime(2026, 2, 23, 11, 0, 0, tzinfo=UTC)
TS3 = datetime(2026, 2, 23, 12, 0, 0, tzinfo=UTC)


def _make_sow(sow_id: str, title: str) -> StatementOfWork:
    return StatementOfWork(sow_id=sow_id, title=title, description="desc", created_at=TS1)


def _make_plan(plan_id: str, sow_id: str = "sow-1") -> ImplementationPlan:
    return ImplementationPlan(plan_id=plan_id, sow_id=sow_id, created_at=TS1)


def _make_context(org_id: str = "org1") -> EnvironmentContext:
    return EnvironmentContext(org_id=org_id, fetched_at=TS1)


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
    sow = _make_sow("sow-1", "Initial SoW")
    artifact_store.save(handle, sow)
    result = artifact_store.load(handle)
    assert result == sow


def test_save_and_load_plan(artifact_store):
    handle = PlanHandle(org_id="org1", artifact_id="plan-1", timestamp=TS1)
    plan = _make_plan("plan-1")
    artifact_store.save(handle, plan)
    result = artifact_store.load(handle)
    assert result == plan


def test_save_and_load_context(artifact_store):
    handle = ContextHandle(org_id="org1", artifact_id="ctx-1", timestamp=TS1)
    ctx = _make_context("org1")
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
    sow = _make_sow("sow-1", "Only one")
    artifact_store.save(handle, sow)
    result = artifact_store.load_latest("org1", "sow", SoWHandle)
    assert result == sow


def test_load_latest_returns_most_recent(artifact_store):
    sow_old = _make_sow("sow-1", "Old SoW")
    sow_mid = _make_sow("sow-2", "Mid SoW")
    sow_new = _make_sow("sow-3", "New SoW")

    artifact_store.save(SoWHandle(org_id="org1", artifact_id="sow-1", timestamp=TS1), sow_old)
    artifact_store.save(SoWHandle(org_id="org1", artifact_id="sow-2", timestamp=TS2), sow_mid)
    artifact_store.save(SoWHandle(org_id="org1", artifact_id="sow-3", timestamp=TS3), sow_new)

    result = artifact_store.load_latest("org1", "sow", SoWHandle)
    assert result == sow_new


def test_load_latest_isolated_by_org(artifact_store):
    sow_org1 = _make_sow("sow-1", "Org1 SoW")
    sow_org2 = _make_sow("sow-1", "Org2 SoW")

    artifact_store.save(SoWHandle(org_id="org1", artifact_id="sow-1", timestamp=TS1), sow_org1)
    artifact_store.save(SoWHandle(org_id="org2", artifact_id="sow-1", timestamp=TS2), sow_org2)

    assert artifact_store.load_latest("org1", "sow", SoWHandle) == sow_org1
    assert artifact_store.load_latest("org2", "sow", SoWHandle) == sow_org2


def test_load_latest_isolated_by_artifact_type(artifact_store):
    sow = _make_sow("sow-1", "SoW")
    plan = _make_plan("plan-1")

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
    sow = _make_sow("sow-1", "My SoW")
    artifact_store.save(SoWHandle(org_id="org1", artifact_id="sow-1", timestamp=TS1), sow)
    result = artifact_store.list_artifacts("org1", "sow", SoWHandle)
    assert result == [sow]


def test_list_artifacts_multiple_in_chronological_order(artifact_store):
    sow1 = _make_sow("sow-1", "First")
    sow2 = _make_sow("sow-2", "Second")
    sow3 = _make_sow("sow-3", "Third")

    # Save out of order to verify sorting
    artifact_store.save(SoWHandle(org_id="org1", artifact_id="sow-3", timestamp=TS3), sow3)
    artifact_store.save(SoWHandle(org_id="org1", artifact_id="sow-1", timestamp=TS1), sow1)
    artifact_store.save(SoWHandle(org_id="org1", artifact_id="sow-2", timestamp=TS2), sow2)

    result = artifact_store.list_artifacts("org1", "sow", SoWHandle)
    assert result == [sow1, sow2, sow3]


def test_list_artifacts_isolated_by_org(artifact_store):
    sow_org1 = _make_sow("sow-1", "Org1")
    sow_org2 = _make_sow("sow-1", "Org2")

    artifact_store.save(SoWHandle(org_id="org1", artifact_id="sow-1", timestamp=TS1), sow_org1)
    artifact_store.save(SoWHandle(org_id="org2", artifact_id="sow-1", timestamp=TS1), sow_org2)

    assert artifact_store.list_artifacts("org1", "sow", SoWHandle) == [sow_org1]
    assert artifact_store.list_artifacts("org2", "sow", SoWHandle) == [sow_org2]


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


def test_delete(artifact_store):
    handle = SoWHandle(org_id="org1", artifact_id="sow-1", timestamp=TS1)
    sow = _make_sow("sow-1", "To be deleted")
    artifact_store.save(handle, sow)
    artifact_store.delete(handle)
    assert artifact_store.load(handle) is None


def test_delete_does_not_affect_other_artifacts(artifact_store):
    h1 = SoWHandle(org_id="org1", artifact_id="sow-1", timestamp=TS1)
    h2 = SoWHandle(org_id="org1", artifact_id="sow-2", timestamp=TS2)
    sow1 = _make_sow("sow-1", "Keep")
    sow2 = _make_sow("sow-2", "Delete")

    artifact_store.save(h1, sow1)
    artifact_store.save(h2, sow2)
    artifact_store.delete(h2)

    assert artifact_store.load(h1) == sow1
    assert artifact_store.load(h2) is None
