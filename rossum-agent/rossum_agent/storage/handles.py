from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import ClassVar, cast

from pydantic import BaseModel

from rossum_agent.context.models import EnvironmentContext
from rossum_agent.planning.models import ImplementationPlan, StatementOfWork

TIMESTAMP_FORMAT = "%Y%m%d%H%M%S%f"


@dataclass
class ArtifactHandle[T: BaseModel]:
    """Identity + serialization for a stored artifact.

    Inspired by rir/commons ResourceHandle[T]. Encapsulates:
    - Identity: environment, resource_type, artifact_id, timestamp
    - Key derivation: Redis key computed from identity
    - Serialization: Pydantic model_dump_json / model_validate_json
    """

    resource_type: ClassVar[str]
    model_class: ClassVar[type[BaseModel]]

    environment: str
    artifact_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def key(self) -> str:
        ts = self.timestamp.strftime(TIMESTAMP_FORMAT)
        return f"artifact:{self.environment}:{self.resource_type}:{self.artifact_id}:{ts}"

    @property
    def index_key(self) -> str:
        return f"artifact_index:{self.environment}:{self.resource_type}"

    def serialize(self, payload: T) -> str:
        return payload.model_dump_json()

    def deserialize(self, data: str) -> T:
        return cast("T", self.model_class.model_validate_json(data))


class SoWHandle(ArtifactHandle[StatementOfWork]):
    resource_type = "sow"
    model_class = StatementOfWork


class PlanHandle(ArtifactHandle[ImplementationPlan]):
    resource_type = "plan"
    model_class = ImplementationPlan


class ContextHandle(ArtifactHandle[EnvironmentContext]):
    resource_type = "context"
    model_class = EnvironmentContext
