from __future__ import annotations

from datetime import UTC, datetime, timedelta

from rossum_agent.context.models import (
    EntitySummary,
    EnvironmentContext,
    HookSummary,
    QueueSummary,
    SchemaSummary,
    WorkspaceSummary,
)

NOW = datetime(2026, 2, 23, 14, 0, 0, tzinfo=UTC)
OLD = datetime(2020, 1, 1, tzinfo=UTC)


# ---------------------------------------------------------------------------
# EntitySummary and subtypes
# ---------------------------------------------------------------------------


class TestEntitySummary:
    def test_basic_fields(self):
        e = EntitySummary(id="e1", name="My Entity")
        assert e.id == "e1"
        assert e.name == "My Entity"
        assert e.url is None

    def test_with_url(self):
        e = EntitySummary(id="e1", name="My Entity", url="https://example.com/e1")
        assert e.url == "https://example.com/e1"


class TestWorkspaceSummary:
    def test_defaults(self):
        ws = WorkspaceSummary(id="ws1", name="Main WS")
        assert ws.queue_ids == []

    def test_with_queue_ids(self):
        ws = WorkspaceSummary(id="ws1", name="Main WS", queue_ids=["q1", "q2"])
        assert ws.queue_ids == ["q1", "q2"]


class TestQueueSummary:
    def test_defaults(self):
        q = QueueSummary(id="q1", name="Invoice Queue")
        assert q.schema_id is None

    def test_with_schema_id(self):
        q = QueueSummary(id="q1", name="Invoice Queue", schema_id="s1")
        assert q.schema_id == "s1"


class TestSchemaSummary:
    def test_creation(self):
        s = SchemaSummary(id="s1", name="Invoice Schema")
        assert s.id == "s1"
        assert s.name == "Invoice Schema"


class TestHookSummary:
    def test_defaults(self):
        h = HookSummary(id="h1", name="Webhook", hook_type="webhook")
        assert h.active is True
        assert h.events == []

    def test_with_events(self):
        h = HookSummary(id="h1", name="Processor", hook_type="function", active=False, events=["annotation_created"])
        assert h.active is False
        assert h.events == ["annotation_created"]


# ---------------------------------------------------------------------------
# EnvironmentContext
# ---------------------------------------------------------------------------


def _make_context(
    org_id: str = "org1",
    fetched_at: datetime = NOW,
    workspaces: list[WorkspaceSummary] | None = None,
    queues: list[QueueSummary] | None = None,
    schemas: list[SchemaSummary] | None = None,
    hooks: list[HookSummary] | None = None,
) -> EnvironmentContext:
    return EnvironmentContext(
        org_id=org_id,
        fetched_at=fetched_at,
        workspaces=workspaces or [],
        queues=queues or [],
        schemas=schemas or [],
        hooks=hooks or [],
    )


class TestEnvironmentContextCreation:
    def test_defaults(self):
        ctx = EnvironmentContext(org_id="org1", fetched_at=NOW)
        assert ctx.org_id == "org1"
        assert ctx.fetched_at == NOW
        assert ctx.workspaces == []
        assert ctx.queues == []
        assert ctx.schemas == []
        assert ctx.hooks == []

    def test_with_entities(self):
        ctx = _make_context(
            workspaces=[WorkspaceSummary(id="ws1", name="Main")],
            schemas=[SchemaSummary(id="s1", name="Invoice")],
        )
        assert len(ctx.workspaces) == 1
        assert len(ctx.schemas) == 1

    def test_json_roundtrip(self):
        ctx = _make_context(
            workspaces=[WorkspaceSummary(id="ws1", name="Main", queue_ids=["q1"])],
            queues=[QueueSummary(id="q1", name="Invoice Q", schema_id="s1")],
            schemas=[SchemaSummary(id="s1", name="Invoice Schema")],
            hooks=[HookSummary(id="h1", name="Webhook", hook_type="webhook", events=["annotation_created"])],
        )
        restored = EnvironmentContext.model_validate_json(ctx.model_dump_json())
        assert restored.org_id == ctx.org_id
        assert restored.fetched_at == ctx.fetched_at
        assert len(restored.workspaces) == 1
        assert restored.workspaces[0].queue_ids == ["q1"]
        assert len(restored.hooks) == 1
        assert restored.hooks[0].events == ["annotation_created"]


class TestIsStaleness:
    def test_fresh_context_not_stale(self):
        ctx = _make_context(fetched_at=datetime.now(UTC))
        assert ctx.is_stale() is False

    def test_old_context_is_stale(self):
        ctx = _make_context(fetched_at=OLD)
        assert ctx.is_stale() is True

    def test_custom_max_age_fresh(self):
        recent = datetime.now(UTC) - timedelta(seconds=50)
        ctx = _make_context(fetched_at=recent)
        assert ctx.is_stale(max_age_seconds=200) is False

    def test_custom_max_age_stale(self):
        recent = datetime.now(UTC) - timedelta(seconds=100)
        ctx = _make_context(fetched_at=recent)
        assert ctx.is_stale(max_age_seconds=50) is True

    def test_boundary_just_within(self):
        # 1 second within the window → not stale
        ctx = _make_context(fetched_at=datetime.now(UTC) - timedelta(seconds=59))
        assert ctx.is_stale(max_age_seconds=60) is False


class TestToCompactSummary:
    def test_empty_context(self):
        ctx = _make_context()
        summary = ctx.to_compact_summary()
        assert "org1" in summary
        assert "Workspaces (0)" in summary
        assert "none" in summary

    def test_contains_entity_names(self):
        ctx = _make_context(
            workspaces=[WorkspaceSummary(id="ws1", name="Main WS")],
            schemas=[SchemaSummary(id="s1", name="Invoice Schema")],
        )
        summary = ctx.to_compact_summary()
        assert "Main WS" in summary
        assert "Invoice Schema" in summary

    def test_shows_counts(self):
        ctx = _make_context(
            queues=[QueueSummary(id=f"q{i}", name=f"Queue {i}") for i in range(3)],
        )
        summary = ctx.to_compact_summary()
        assert "Queues (3)" in summary

    def test_caps_display_at_five(self):
        # 7 schemas → only first 5 names shown, but count shows 7
        ctx = _make_context(
            schemas=[SchemaSummary(id=f"s{i}", name=f"Schema {i}") for i in range(7)],
        )
        summary = ctx.to_compact_summary()
        assert "Schemas (7)" in summary
        assert "Schema 5" not in summary
        assert "Schema 4" in summary


class TestMerge:
    def test_merge_no_overlap_combines(self):
        ctx1 = _make_context(
            fetched_at=NOW,
            schemas=[SchemaSummary(id="s1", name="Schema 1")],
        )
        ctx2 = _make_context(
            fetched_at=NOW,
            schemas=[SchemaSummary(id="s2", name="Schema 2")],
        )
        merged = ctx1.merge(ctx2)
        assert len(merged.schemas) == 2
        ids = {s.id for s in merged.schemas}
        assert ids == {"s1", "s2"}

    def test_merge_overlap_other_wins(self):
        ctx1 = _make_context(schemas=[SchemaSummary(id="s1", name="Old Name")])
        ctx2 = _make_context(schemas=[SchemaSummary(id="s1", name="New Name")])
        merged = ctx1.merge(ctx2)
        assert len(merged.schemas) == 1
        assert merged.schemas[0].name == "New Name"

    def test_merge_uses_latest_fetched_at(self):
        earlier = datetime(2026, 2, 23, 10, 0, 0, tzinfo=UTC)
        later = datetime(2026, 2, 23, 12, 0, 0, tzinfo=UTC)
        ctx1 = _make_context(fetched_at=earlier)
        ctx2 = _make_context(fetched_at=later)
        merged = ctx1.merge(ctx2)
        assert merged.fetched_at == later

    def test_merge_preserves_org_id(self):
        ctx1 = _make_context(org_id="org1")
        ctx2 = _make_context(org_id="org2")
        merged = ctx1.merge(ctx2)
        assert merged.org_id == "org1"

    def test_merge_all_entity_types(self):
        ctx1 = _make_context(
            workspaces=[WorkspaceSummary(id="ws1", name="WS1")],
            queues=[QueueSummary(id="q1", name="Q1")],
            schemas=[SchemaSummary(id="s1", name="S1")],
            hooks=[HookSummary(id="h1", name="H1", hook_type="webhook")],
        )
        ctx2 = _make_context(
            workspaces=[WorkspaceSummary(id="ws2", name="WS2")],
            queues=[QueueSummary(id="q2", name="Q2")],
            schemas=[SchemaSummary(id="s2", name="S2")],
            hooks=[HookSummary(id="h2", name="H2", hook_type="function")],
        )
        merged = ctx1.merge(ctx2)
        assert len(merged.workspaces) == 2
        assert len(merged.queues) == 2
        assert len(merged.schemas) == 2
        assert len(merged.hooks) == 2

    def test_merge_empty_other(self):
        ctx1 = _make_context(schemas=[SchemaSummary(id="s1", name="S1")])
        ctx2 = _make_context()
        merged = ctx1.merge(ctx2)
        assert len(merged.schemas) == 1
        assert merged.schemas[0].name == "S1"
