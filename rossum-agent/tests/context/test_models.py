from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from rossum_agent.context.models import (
    EntitySummary,
    EnvironmentContext,
    HookSummary,
    QueueSummary,
    SchemaSummary,
    WorkspaceSummary,
)

FIXED_TS = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)
STALE_TS = datetime(2023, 12, 1, 10, 0, 0, tzinfo=UTC)


def _make_entity(cls: type, id: int, name: str, **kwargs) -> EntitySummary:
    return cls(
        id=id, name=name, url=f"https://example.rossum.app/api/v1/{name.lower()}/{id}", last_seen=FIXED_TS, **kwargs
    )


def _make_context(**kwargs) -> EnvironmentContext:
    defaults = {
        "environment": "https://example.rossum.app",
        "last_updated": FIXED_TS,
    }
    defaults.update(kwargs)
    return EnvironmentContext(**defaults)


class TestEntitySummaryCreation:
    def test_entity_summary(self):
        e = _make_entity(EntitySummary, 1, "Test")
        assert e.id == 1
        assert e.name == "Test"
        assert e.notes == ""

    def test_workspace_summary(self):
        w = _make_entity(WorkspaceSummary, 10, "Production", queue_count=3)
        assert w.queue_count == 3
        assert isinstance(w, EntitySummary)

    def test_queue_summary(self):
        q = _make_entity(QueueSummary, 20, "Invoices", workspace_id=10, schema_id=100, hook_count=2)
        assert q.workspace_id == 10
        assert q.schema_id == 100
        assert q.hook_count == 2

    def test_schema_summary(self):
        s = _make_entity(SchemaSummary, 100, "Invoice Schema", top_level_sections=["header", "items"], field_count=15)
        assert s.top_level_sections == ["header", "items"]
        assert s.field_count == 15

    def test_hook_summary(self):
        h = _make_entity(
            HookSummary,
            200,
            "Validation",
            hook_type="webhook",
            events=["annotation_content.initialize"],
            queue_ids=[20, 21],
        )
        assert h.hook_type == "webhook"
        assert h.events == ["annotation_content.initialize"]
        assert h.queue_ids == [20, 21]


class TestHasData:
    def test_empty_context_has_no_data(self):
        ctx = _make_context()
        assert ctx.has_data() is False

    def test_context_with_workspace_has_data(self):
        w = _make_entity(WorkspaceSummary, 10, "Production")
        ctx = _make_context(workspaces={10: w})
        assert ctx.has_data() is True

    def test_context_with_queue_has_data(self):
        q = _make_entity(QueueSummary, 20, "Invoices")
        ctx = _make_context(queues={20: q})
        assert ctx.has_data() is True

    def test_context_with_schema_has_data(self):
        s = _make_entity(SchemaSummary, 100, "Schema")
        ctx = _make_context(schemas={100: s})
        assert ctx.has_data() is True

    def test_context_with_hook_has_data(self):
        h = _make_entity(HookSummary, 200, "Hook")
        ctx = _make_context(hooks={200: h})
        assert ctx.has_data() is True


class TestToCompactSummary:
    def _now_2h_after_fixed(self):
        return FIXED_TS + timedelta(hours=2)

    def test_no_data_returns_no_data_message(self):
        ctx = _make_context()
        assert ctx.to_compact_summary() == "[Environment Context — no data]"

    def test_workspace_prefix(self):
        w = _make_entity(WorkspaceSummary, 456, "Production", queue_count=3)
        ctx = _make_context(workspaces={456: w})
        with patch("rossum_agent.context.models.datetime") as mock_dt:
            mock_dt.now.return_value = self._now_2h_after_fixed()
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            summary = ctx.to_compact_summary()
        assert "W-456" in summary
        assert '"Production"' in summary
        assert "(3 queues)" in summary
        assert "2h ago" in summary

    def test_queue_prefix(self):
        q = _make_entity(QueueSummary, 101, "Invoices", schema_id=123, hook_count=2)
        ctx = _make_context(queues={101: q})
        with patch("rossum_agent.context.models.datetime") as mock_dt:
            mock_dt.now.return_value = self._now_2h_after_fixed()
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            summary = ctx.to_compact_summary()
        assert "Q-101" in summary
        assert "S-123" in summary
        assert "2 hooks" in summary

    def test_schema_prefix(self):
        s = _make_entity(SchemaSummary, 300, "Invoice Schema", top_level_sections=["header", "items"], field_count=15)
        ctx = _make_context(schemas={300: s})
        with patch("rossum_agent.context.models.datetime") as mock_dt:
            mock_dt.now.return_value = self._now_2h_after_fixed()
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            summary = ctx.to_compact_summary()
        assert "S-300" in summary
        assert "15 fields" in summary
        assert "header, items" in summary

    def test_hook_prefix(self):
        h = _make_entity(
            HookSummary,
            400,
            "Validator",
            hook_type="webhook",
            events=["annotation_content.initialize"],
            queue_ids=[101],
        )
        ctx = _make_context(hooks={400: h})
        with patch("rossum_agent.context.models.datetime") as mock_dt:
            mock_dt.now.return_value = self._now_2h_after_fixed()
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            summary = ctx.to_compact_summary()
        assert "H-400" in summary
        assert "webhook" in summary
        assert "Q-101" in summary

    def test_stale_entries(self):
        w = _make_entity(WorkspaceSummary, 10, "OldWS")
        w.last_seen = STALE_TS
        ctx = _make_context(workspaces={10: w})
        with patch("rossum_agent.context.models.datetime") as mock_dt:
            mock_dt.now.return_value = self._now_2h_after_fixed()
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            summary = ctx.to_compact_summary(staleness_days=7)
        assert "(stale)" in summary

    def test_minutes_ago_format(self):
        w = _make_entity(WorkspaceSummary, 10, "WS")
        ctx = _make_context(workspaces={10: w})
        with patch("rossum_agent.context.models.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_TS + timedelta(minutes=30)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            summary = ctx.to_compact_summary()
        assert "30m ago" in summary

    def test_days_ago_format(self):
        w = _make_entity(WorkspaceSummary, 10, "WS")
        ctx = _make_context(workspaces={10: w})
        with patch("rossum_agent.context.models.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_TS + timedelta(days=3)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            summary = ctx.to_compact_summary()
        assert "3d ago" in summary

    def test_schema_no_sections(self):
        s = _make_entity(SchemaSummary, 300, "Empty Schema", field_count=0)
        ctx = _make_context(schemas={300: s})
        with patch("rossum_agent.context.models.datetime") as mock_dt:
            mock_dt.now.return_value = self._now_2h_after_fixed()
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            summary = ctx.to_compact_summary()
        assert "no sections" in summary


class TestMerge:
    def test_merge_adds_new_entries(self):
        ctx = _make_context()
        w = _make_entity(WorkspaceSummary, 10, "Production")
        other = _make_context(workspaces={10: w})
        ctx.merge(other)
        assert 10 in ctx.workspaces
        assert ctx.workspaces[10].name == "Production"

    def test_merge_updates_existing_entries(self):
        w_old = _make_entity(WorkspaceSummary, 10, "Old Name", queue_count=1)
        ctx = _make_context(workspaces={10: w_old})

        w_new = _make_entity(WorkspaceSummary, 10, "New Name", queue_count=5)
        other = _make_context(workspaces={10: w_new})

        ctx.merge(other)
        assert ctx.workspaces[10].name == "New Name"
        assert ctx.workspaces[10].queue_count == 5

    def test_merge_never_removes_entries(self):
        w = _make_entity(WorkspaceSummary, 10, "Keep Me")
        q = _make_entity(QueueSummary, 20, "Keep Queue")
        ctx = _make_context(workspaces={10: w}, queues={20: q})

        other = _make_context(workspaces={99: _make_entity(WorkspaceSummary, 99, "New WS")})
        ctx.merge(other)

        assert 10 in ctx.workspaces
        assert 99 in ctx.workspaces
        assert 20 in ctx.queues

    def test_merge_updates_last_updated_if_newer(self):
        ctx = _make_context(last_updated=FIXED_TS)
        newer_ts = FIXED_TS + timedelta(hours=5)
        other = _make_context(last_updated=newer_ts)
        ctx.merge(other)
        assert ctx.last_updated == newer_ts

    def test_merge_keeps_last_updated_if_older(self):
        ctx = _make_context(last_updated=FIXED_TS)
        older_ts = FIXED_TS - timedelta(hours=5)
        other = _make_context(last_updated=older_ts)
        ctx.merge(other)
        assert ctx.last_updated == FIXED_TS

    def test_merge_all_entity_types(self):
        ctx = _make_context()
        other = _make_context(
            workspaces={10: _make_entity(WorkspaceSummary, 10, "WS")},
            queues={20: _make_entity(QueueSummary, 20, "Q")},
            schemas={30: _make_entity(SchemaSummary, 30, "S")},
            hooks={40: _make_entity(HookSummary, 40, "H")},
        )
        ctx.merge(other)
        assert 10 in ctx.workspaces
        assert 20 in ctx.queues
        assert 30 in ctx.schemas
        assert 40 in ctx.hooks


class TestSerializationRoundTrip:
    def test_round_trip(self):
        w = _make_entity(WorkspaceSummary, 10, "Production", queue_count=3)
        q = _make_entity(QueueSummary, 20, "Invoices", workspace_id=10, schema_id=100, hook_count=2)
        s = _make_entity(SchemaSummary, 100, "Schema", top_level_sections=["header"], field_count=10)
        h = _make_entity(HookSummary, 200, "Hook", hook_type="webhook", events=["event1"], queue_ids=[20])

        ctx = _make_context(workspaces={10: w}, queues={20: q}, schemas={100: s}, hooks={200: h})

        json_str = ctx.model_dump_json()
        restored = EnvironmentContext.model_validate_json(json_str)

        assert restored.environment == ctx.environment
        assert restored.last_updated == ctx.last_updated
        assert restored.workspaces[10].name == "Production"
        assert restored.workspaces[10].queue_count == 3
        assert restored.queues[20].schema_id == 100
        assert restored.schemas[100].top_level_sections == ["header"]
        assert restored.hooks[200].hook_type == "webhook"
        assert restored.hooks[200].queue_ids == [20]
