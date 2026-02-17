from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pydantic import BaseModel


class EntitySummary(BaseModel):
    """Base summary for any Rossum entity."""

    id: int
    name: str
    url: str
    last_seen: datetime
    notes: str = ""


class WorkspaceSummary(EntitySummary):
    queue_count: int = 0


class QueueSummary(EntitySummary):
    workspace_id: int = 0
    schema_id: int = 0
    hook_count: int = 0


class SchemaSummary(EntitySummary):
    top_level_sections: list[str] = []
    field_count: int = 0


class HookSummary(EntitySummary):
    hook_type: str = ""
    events: list[str] = []
    queue_ids: list[int] = []


def _format_age(age: timedelta) -> str:
    seconds = age.total_seconds()
    if seconds < 3600:
        return f"{int(seconds / 60)}m ago"
    if seconds < 86400:
        return f"{int(seconds / 3600)}h ago"
    return f"{age.days}d ago"


def _stale_suffix(last_seen: datetime, threshold: datetime) -> str:
    return " (stale)" if last_seen < threshold else ""


class EnvironmentContext(BaseModel):
    """Persistent knowledge about a Rossum environment."""

    environment: str
    last_updated: datetime
    workspaces: dict[int, WorkspaceSummary] = {}
    queues: dict[int, QueueSummary] = {}
    schemas: dict[int, SchemaSummary] = {}
    hooks: dict[int, HookSummary] = {}

    def has_data(self) -> bool:
        return bool(self.workspaces or self.queues or self.schemas or self.hooks)

    def to_compact_summary(self, staleness_days: int = 7) -> str:
        """Token-efficient summary for system prompt injection.

        Output format:
        [Environment Context — last updated 2h ago]
        Workspaces: W-456 "Production" (3 queues), W-789 "Sandbox" (1 queue)
        Queues: Q-101 "Invoices" (schema S-123, 2 hooks)
        ...

        Entries older than staleness_days get (stale) suffix.
        """
        if not self.has_data():
            return "[Environment Context — no data]"

        now = datetime.now(UTC)
        age_str = _format_age(now - self.last_updated)
        stale_threshold = now - timedelta(days=staleness_days)

        lines = [f"[Environment Context — last updated {age_str}]"]
        lines.extend(self._workspace_lines(stale_threshold))
        lines.extend(self._queue_lines(stale_threshold))
        lines.extend(self._schema_lines(stale_threshold))
        lines.extend(self._hook_lines(stale_threshold))
        return "\n".join(lines)

    def _workspace_lines(self, stale_threshold: datetime) -> list[str]:
        if not self.workspaces:
            return []
        parts = [
            f'W-{w.id} "{w.name}" ({w.queue_count} queues){_stale_suffix(w.last_seen, stale_threshold)}'
            for w in self.workspaces.values()
        ]
        return [f"Workspaces: {', '.join(parts)}"]

    def _queue_lines(self, stale_threshold: datetime) -> list[str]:
        if not self.queues:
            return []
        parts = [
            f'Q-{q.id} "{q.name}" (schema S-{q.schema_id}, {q.hook_count} hooks){_stale_suffix(q.last_seen, stale_threshold)}'
            for q in self.queues.values()
        ]
        return [f"Queues: {', '.join(parts)}"]

    def _schema_lines(self, stale_threshold: datetime) -> list[str]:
        if not self.schemas:
            return []
        parts = []
        for s in self.schemas.values():
            suffix = _stale_suffix(s.last_seen, stale_threshold)
            sections = ", ".join(s.top_level_sections) if s.top_level_sections else "no sections"
            parts.append(f'S-{s.id} "{s.name}" ({s.field_count} fields: {sections}){suffix}')
        return [f"Schemas: {', '.join(parts)}"]

    def _hook_lines(self, stale_threshold: datetime) -> list[str]:
        if not self.hooks:
            return []
        parts = []
        for h in self.hooks.values():
            suffix = _stale_suffix(h.last_seen, stale_threshold)
            queue_str = " ".join(f"Q-{qid}" for qid in h.queue_ids)
            events_str = ", ".join(h.events) if h.events else "no events"
            parts.append(f'H-{h.id} "{h.name}" ({h.hook_type}, {events_str}, {queue_str}){suffix}')
        return [f"Hooks: {', '.join(parts)}"]

    def merge(self, other: EnvironmentContext) -> None:
        """Merge another context into this one. Add/update, never remove."""
        for entity_type in ("workspaces", "queues", "schemas", "hooks"):
            existing = getattr(self, entity_type)
            incoming = getattr(other, entity_type)
            existing.update(incoming)
        if other.last_updated > self.last_updated:
            self.last_updated = other.last_updated
