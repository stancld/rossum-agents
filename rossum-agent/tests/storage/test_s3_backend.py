from __future__ import annotations

import boto3
import pytest
from moto import mock_aws
from rossum_agent.storage.s3_backend import S3StorageBackend

BUCKET = "test-bucket"


@pytest.fixture
def s3_backend():
    with mock_aws():
        boto3.client(
            "s3",
            region_name="us-east-1",
            aws_access_key_id="test",
            aws_secret_access_key="test",
        ).create_bucket(Bucket=BUCKET)
        yield S3StorageBackend(bucket=BUCKET, endpoint_url=None, access_key="test", secret_key="test")


def test_save_and_load(s3_backend):
    s3_backend.save("artifacts/org/sow/2026-02-23_sow_1.json", b'{"title": "SoW"}')
    assert s3_backend.load("artifacts/org/sow/2026-02-23_sow_1.json") == b'{"title": "SoW"}'


def test_load_missing_key_returns_none(s3_backend):
    assert s3_backend.load("artifacts/org/sow/nonexistent.json") is None


def test_list_keys_prefix_filtering(s3_backend):
    s3_backend.save("artifacts/org_a/sow/2026-02-23_sow_1.json", b"a")
    s3_backend.save("artifacts/org_a/sow/2026-02-24_sow_2.json", b"b")
    s3_backend.save("artifacts/org_b/sow/2026-02-23_sow_1.json", b"c")

    keys = s3_backend.list_keys("artifacts/org_a/sow/")
    assert sorted(keys) == [
        "artifacts/org_a/sow/2026-02-23_sow_1.json",
        "artifacts/org_a/sow/2026-02-24_sow_2.json",
    ]


def test_list_keys_no_matches_returns_empty(s3_backend):
    assert s3_backend.list_keys("artifacts/nonexistent/") == []


def test_delete(s3_backend):
    s3_backend.save("artifacts/org/sow/2026-02-23_sow_1.json", b"data")
    s3_backend.delete("artifacts/org/sow/2026-02-23_sow_1.json")
    assert s3_backend.load("artifacts/org/sow/2026-02-23_sow_1.json") is None


def test_from_env(monkeypatch):
    # Use no endpoint_url so moto can intercept; verifies env var wiring end-to-end
    monkeypatch.setenv("S3_ARTIFACT_BUCKET", "my-bucket")
    monkeypatch.delenv("S3_ENDPOINT_URL", raising=False)
    monkeypatch.setenv("S3_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "test")

    with mock_aws():
        boto3.client(
            "s3",
            region_name="us-east-1",
            aws_access_key_id="test",
            aws_secret_access_key="test",
        ).create_bucket(Bucket="my-bucket")
        backend = S3StorageBackend.from_env()
        backend.save("test.json", b"hello")
        assert backend.load("test.json") == b"hello"
