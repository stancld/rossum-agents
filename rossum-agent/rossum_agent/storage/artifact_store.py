from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

from pydantic import BaseModel

from rossum_agent.storage.handles import TIMESTAMP_FORMAT, ArtifactHandle

if TYPE_CHECKING:
    import redis

logger = logging.getLogger(__name__)

DEFAULT_ARTIFACT_TTL = 30 * 24 * 3600  # 30 days


class ArtifactStore:
    """Redis-backed persistence for typed artifacts via handles.

    Follows CommitStore pattern: Redis with TTL, sorted set indices.
    """

    def __init__(self, client: redis.Redis, ttl_seconds: int = DEFAULT_ARTIFACT_TTL) -> None:
        self.client = client
        self._ttl = ttl_seconds

    def save[T: BaseModel](self, handle: ArtifactHandle[T], payload: T) -> None:
        data = handle.serialize(payload)
        pipe = self.client.pipeline()
        pipe.setex(handle.key, self._ttl, data)
        pipe.zadd(handle.index_key, {handle.key: handle.timestamp.timestamp()})
        pipe.expire(handle.index_key, self._ttl)
        pipe.execute()
        logger.info(f"Saved artifact {handle.key}")

    def load[T: BaseModel](self, handle: ArtifactHandle[T]) -> T | None:
        data = self.client.get(handle.key)
        if data is None:
            return None
        raw = cast("bytes", data).decode() if isinstance(data, bytes) else str(data)
        return handle.deserialize(raw)

    def load_latest[T: BaseModel](
        self, handle_type: type[ArtifactHandle[T]], environment: str
    ) -> tuple[ArtifactHandle[T], T] | None:
        index_key = f"artifact_index:{environment}:{handle_type.resource_type}"
        keys = cast("list[bytes]", self.client.zrevrange(index_key, 0, 0))
        if not keys:
            return None
        key_str = keys[0].decode() if isinstance(keys[0], bytes) else str(keys[0])
        data = self.client.get(key_str)
        if data is None:
            return None
        raw = cast("bytes", data).decode() if isinstance(data, bytes) else str(data)
        handle = _handle_from_key(handle_type, key_str)
        return handle, handle.deserialize(raw)

    def list_artifacts[T: BaseModel](
        self, handle_type: type[ArtifactHandle[T]], environment: str, limit: int = 20
    ) -> list[tuple[ArtifactHandle[T], T]]:
        index_key = f"artifact_index:{environment}:{handle_type.resource_type}"
        keys = cast("list[bytes]", self.client.zrevrange(index_key, 0, limit - 1))
        results: list[tuple[ArtifactHandle[T], T]] = []
        for k in keys:
            key_str = k.decode() if isinstance(k, bytes) else str(k)
            data = self.client.get(key_str)
            if data is None:
                continue
            raw = cast("bytes", data).decode() if isinstance(data, bytes) else str(data)
            handle = _handle_from_key(handle_type, key_str)
            results.append((handle, handle.deserialize(raw)))
        return results

    def delete(self, handle: ArtifactHandle) -> bool:
        pipe = self.client.pipeline()
        pipe.delete(handle.key)
        pipe.zrem(handle.index_key, handle.key)
        result = pipe.execute()
        deleted = result[0] > 0
        if deleted:
            logger.info(f"Deleted artifact {handle.key}")
        return deleted


# Key format: artifact:{environment}:{type}:{id}:{timestamp}
_KEY_PATTERN = re.compile(r"^artifact:(.+):([^:]+):([^:]+):(\d{20})$")


def _handle_from_key[T: BaseModel](handle_type: type[ArtifactHandle[T]], key: str) -> ArtifactHandle[T]:
    """Reconstruct a handle from a Redis key string."""
    match = _KEY_PATTERN.match(key)
    if not match:
        msg = f"Invalid artifact key format: {key}"
        raise ValueError(msg)
    environment, _resource_type, artifact_id, ts_str = match.groups()
    timestamp = datetime.strptime(ts_str, TIMESTAMP_FORMAT).replace(tzinfo=UTC)
    return handle_type(environment=environment, artifact_id=artifact_id, timestamp=timestamp)
