"""In-memory cache for pre-scraped Knowledge Base articles."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

_KB_DATA_PATH_ENV = "ROSSUM_KB_DATA_PATH"
_BUNDLED_KB_PATH = Path(__file__).resolve().parent.parent.parent.parent / "data" / "rossum-kb.json"


class KBCache:
    """In-memory cache for pre-scraped Knowledge Base articles."""

    def __init__(self, cache_path: Path = _BUNDLED_KB_PATH) -> None:
        self._cache_path = cache_path
        self._data: dict[str, Any] | None = None
        self._mtime: float = 0

    def load(self) -> dict[str, Any]:
        """Load KB data with in-memory caching keyed on file mtime."""
        path = self._resolve_path()
        current_mtime = path.stat().st_mtime

        if self._data is not None and current_mtime == self._mtime:
            return self._data

        data = json.loads(path.read_text())
        self._data = data
        self._mtime = current_mtime
        return data

    def _resolve_path(self) -> Path:
        """Return the KB data file path (env override or bundled)."""
        local_path = os.environ.get(_KB_DATA_PATH_ENV)
        if local_path:
            p = Path(local_path)
            if p.exists():
                return p
            raise FileNotFoundError(f"{_KB_DATA_PATH_ENV} points to non-existent file: {local_path}")
        return self._cache_path


cache = KBCache()
