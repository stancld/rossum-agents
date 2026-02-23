from __future__ import annotations

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel

from rossum_agent.context.models import EnvironmentContext
from rossum_agent.planning.models import ImplementationPlan, StatementOfWork


class ArtifactHandle[T: BaseModel](BaseModel):
    org_id: str
    artifact_type: str
    artifact_id: str
    timestamp: datetime

    @property
    def s3_key(self) -> str:
        return f"artifacts/{self.org_id}/{self.artifact_type}/{self.timestamp.isoformat()}_{self.artifact_id}.json"

    @classmethod
    def from_key(cls, key: str) -> Self:
        # key = "artifacts/{org_id}/{artifact_type}/{timestamp}_{artifact_id}.json"
        parts = key.split("/")
        stem = parts[3].removesuffix(".json")
        timestamp_str, artifact_id = stem.split("_", 1)
        return cls(
            org_id=parts[1],
            artifact_type=parts[2],
            artifact_id=artifact_id,
            timestamp=datetime.fromisoformat(timestamp_str),
        )

    def serialize(self, artifact: T) -> bytes:
        return artifact.model_dump_json().encode()

    def deserialize(self, data: bytes) -> T:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Concrete handles
# ---------------------------------------------------------------------------


class SoWHandle(ArtifactHandle[StatementOfWork]):
    artifact_type: Literal["sow"] = "sow"

    def deserialize(self, data: bytes) -> StatementOfWork:
        return StatementOfWork.model_validate_json(data)


class PlanHandle(ArtifactHandle[ImplementationPlan]):
    artifact_type: Literal["plan"] = "plan"

    def deserialize(self, data: bytes) -> ImplementationPlan:
        return ImplementationPlan.model_validate_json(data)


class ContextHandle(ArtifactHandle[EnvironmentContext]):
    artifact_type: Literal["context"] = "context"

    def deserialize(self, data: bytes) -> EnvironmentContext:
        return EnvironmentContext.model_validate_json(data)
