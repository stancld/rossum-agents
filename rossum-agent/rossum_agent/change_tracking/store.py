from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from rossum_agent.change_tracking.models import ConfigCommit

if TYPE_CHECKING:
    import redis

logger = logging.getLogger(__name__)

# Default TTL for commit data (30 days, matching chat TTL)
DEFAULT_COMMIT_TTL_SECONDS = 30 * 24 * 3600


class CommitStore:
    """Redis-backed persistence for ConfigCommit objects."""

    def __init__(self, client: redis.Redis, ttl_seconds: int = DEFAULT_COMMIT_TTL_SECONDS) -> None:
        self.client = client
        self._ttl = ttl_seconds

    def save_commit(self, commit: ConfigCommit) -> None:
        key = f"config_commit:{commit.environment}:{commit.hash}"
        data = commit.model_dump_json()
        pipe = self.client.pipeline()
        pipe.setex(key, self._ttl, data)
        # Update sorted set index (score = timestamp for ordering)
        index_key = f"config_commits:{commit.environment}"
        pipe.zadd(index_key, {commit.hash: commit.timestamp.timestamp()})
        pipe.expire(index_key, self._ttl)
        # Update latest pointer
        latest_key = f"config_commit_latest:{commit.environment}"
        pipe.setex(latest_key, self._ttl, commit.hash)
        pipe.execute()
        logger.info(f"Saved config commit {commit.hash} for {commit.environment}")

    def get_commit(self, environment: str, commit_hash: str) -> ConfigCommit | None:
        key = f"config_commit:{environment}:{commit_hash}"
        if (data := self.client.get(key)) is None:
            return None
        return ConfigCommit.model_validate_json(cast("bytes", data))

    def get_latest_hash(self, environment: str) -> str | None:
        """Get the hash of the latest commit for an environment."""
        latest_key = f"config_commit_latest:{environment}"
        if (result := self.client.get(latest_key)) is None:
            return None
        return result.decode() if isinstance(result, bytes) else str(result)

    def list_commits(self, environment: str, limit: int = 10) -> list[ConfigCommit]:
        """List recent commits for an environment, newest first."""
        index_key = f"config_commits:{environment}"
        # Get hashes from sorted set, newest first
        hashes = cast("list[bytes]", self.client.zrevrange(index_key, 0, limit - 1))
        if not hashes:
            return []

        commits: list[ConfigCommit] = []
        for h in hashes:
            hash_str = h.decode() if isinstance(h, bytes) else h
            commit = self.get_commit(environment, hash_str)
            if commit is not None:
                commits.append(commit)
        return commits
