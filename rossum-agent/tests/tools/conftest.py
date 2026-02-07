"""Shared fixtures for tools tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from rossum_agent.tools.knowledge_base_search import KBCache

_KB_DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "rossum-kb.json"


@pytest.fixture
def real_kb_cache() -> KBCache:
    """KBCache backed by the real scraped KB data file (git-lfs tracked)."""
    if not _KB_DATA_PATH.exists():
        pytest.skip("rossum-kb.json not available (git-lfs not pulled?)")
    try:
        json.loads(_KB_DATA_PATH.read_text())
    except (json.JSONDecodeError, UnicodeDecodeError):
        pytest.skip("rossum-kb.json is not valid JSON (git-lfs pointer?)")
    return KBCache(cache_path=_KB_DATA_PATH)
