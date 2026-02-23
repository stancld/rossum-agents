from __future__ import annotations

import logging
import os

import boto3
from botocore.exceptions import ClientError

from rossum_agent.storage.backend import StorageBackend

logger = logging.getLogger(__name__)


class S3StorageBackend(StorageBackend):
    def __init__(
        self,
        bucket: str,
        endpoint_url: str | None,
        access_key: str | None,
        secret_key: str | None,
    ) -> None:
        self._bucket = bucket
        self._endpoint_url = endpoint_url
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )

    @classmethod
    def from_env(cls) -> S3StorageBackend:
        return cls(
            bucket=os.environ["S3_ARTIFACT_BUCKET"],
            endpoint_url=os.environ.get("S3_ENDPOINT_URL"),
            access_key=os.environ.get("S3_ACCESS_KEY_ID"),
            secret_key=os.environ.get("S3_SECRET_ACCESS_KEY"),
        )

    def save(self, key: str, data: bytes) -> None:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data)

    def load(self, key: str) -> bytes | None:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            return response["Body"].read()
        except ClientError as e:
            if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
                return None
            raise

    def list_keys(self, prefix: str) -> list[str]:
        paginator = self._client.get_paginator("list_objects_v2")
        keys: list[str] = []
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                keys.append(obj["Key"])
        return keys

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)

    def __repr__(self) -> str:
        return f"S3StorageBackend(bucket={self._bucket!r}, endpoint_url={self._endpoint_url!r})"
