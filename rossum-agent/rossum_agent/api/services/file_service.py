"""File service for managing chat session files."""

from __future__ import annotations

import mimetypes

from rossum_agent.api.models.schemas import FileInfo
from rossum_agent.redis_storage import RedisStorage


class FileService:
    """Wraps RedisStorage file operations with MIME type detection."""

    def __init__(self, redis_storage: RedisStorage | None = None) -> None:
        self._storage = redis_storage or RedisStorage()

    @property
    def storage(self) -> RedisStorage:
        return self._storage

    def list_files(self, chat_id: str) -> list[FileInfo]:
        files_data = self._storage.list_files(chat_id)
        return [
            FileInfo(
                filename=f["filename"],
                size=f["size"],
                timestamp=f["timestamp"],
                mime_type=self._guess_mime_type(f["filename"]),
            )
            for f in files_data
        ]

    def get_file(self, chat_id: str, filename: str) -> tuple[bytes, str] | None:
        if (content := self._storage.load_file(chat_id, filename)) is None:
            return None
        return content, self._guess_mime_type(filename)

    def _guess_mime_type(self, filename: str) -> str:
        mime_type, _ = mimetypes.guess_type(filename)
        return mime_type or "application/octet-stream"
