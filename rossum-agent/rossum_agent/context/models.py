from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class EntitySummary(BaseModel):
    id: str
    name: str
    url: str | None = None


class HookSummary(EntitySummary):
    hook_type: str
    active: bool = True
    events: list[str] = Field(default_factory=list)


class SchemaSummary(EntitySummary):
    pass


class QueueSummary(EntitySummary):
    schema_id: str | None = None


class WorkspaceSummary(EntitySummary):
    queue_ids: list[str] = Field(default_factory=list)


class EnvironmentContext(BaseModel):
    org_id: str
    fetched_at: datetime
    workspaces: list[WorkspaceSummary] = Field(default_factory=list)
    queues: list[QueueSummary] = Field(default_factory=list)
    schemas: list[SchemaSummary] = Field(default_factory=list)
    hooks: list[HookSummary] = Field(default_factory=list)

    def is_stale(self, max_age_seconds: int = 3600) -> bool:
        """Return True if context is older than max_age_seconds."""
        return (datetime.now(UTC) - self.fetched_at).total_seconds() > max_age_seconds

    def to_compact_summary(self) -> str:
        """Return compact text summary for inclusion in agent prompts."""
        ws_names = ", ".join(w.name for w in self.workspaces[:5])
        q_names = ", ".join(q.name for q in self.queues[:5])
        s_names = ", ".join(s.name for s in self.schemas[:5])
        h_names = ", ".join(h.name for h in self.hooks[:5])
        return (
            f"Org: {self.org_id} | fetched: {self.fetched_at.isoformat()}\n"
            f"Workspaces ({len(self.workspaces)}): {ws_names or 'none'}\n"
            f"Queues ({len(self.queues)}): {q_names or 'none'}\n"
            f"Schemas ({len(self.schemas)}): {s_names or 'none'}\n"
            f"Hooks ({len(self.hooks)}): {h_names or 'none'}"
        )

    def merge(self, other: EnvironmentContext) -> EnvironmentContext:
        """Merge other into this context; other's entities win on ID conflicts."""
        return EnvironmentContext(
            org_id=self.org_id,
            fetched_at=max(self.fetched_at, other.fetched_at),
            workspaces=list(({e.id: e for e in self.workspaces} | {e.id: e for e in other.workspaces}).values()),
            queues=list(({e.id: e for e in self.queues} | {e.id: e for e in other.queues}).values()),
            schemas=list(({e.id: e for e in self.schemas} | {e.id: e for e in other.schemas}).values()),
            hooks=list(({e.id: e for e in self.hooks} | {e.id: e for e in other.hooks}).values()),
        )
