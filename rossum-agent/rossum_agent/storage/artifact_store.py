from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from rossum_agent.storage.handles import ArtifactHandle

if TYPE_CHECKING:
    from pydantic import BaseModel

    from rossum_agent.storage.backend import StorageBackend

_H = TypeVar("_H", bound=ArtifactHandle)  # type: ignore[type-arg]


class ArtifactStore:
    def __init__(self, backend: StorageBackend) -> None:
        self._backend = backend

    def save(self, handle: ArtifactHandle, artifact: BaseModel) -> None:  # type: ignore[type-arg]
        self._backend.save(handle.s3_key, handle.serialize(artifact))

    def load(self, handle: ArtifactHandle) -> BaseModel | None:  # type: ignore[type-arg]
        data = self._backend.load(handle.s3_key)
        return handle.deserialize(data) if data is not None else None

    def load_latest(
        self,
        org_id: str,
        artifact_type: str,
        handle_cls: type[_H],
    ) -> BaseModel | None:
        prefix = f"artifacts/{org_id}/{artifact_type}/"
        keys = sorted(self._backend.list_keys(prefix))
        if not keys:
            return None
        handle = handle_cls.from_key(keys[-1])
        data = self._backend.load(keys[-1])
        return handle.deserialize(data) if data is not None else None

    def list_artifacts(
        self,
        org_id: str,
        artifact_type: str,
        handle_cls: type[_H],
    ) -> list[BaseModel]:
        prefix = f"artifacts/{org_id}/{artifact_type}/"
        result: list[BaseModel] = []
        for key in sorted(self._backend.list_keys(prefix)):
            handle = handle_cls.from_key(key)
            data = self._backend.load(key)
            if data is not None:
                result.append(handle.deserialize(data))
        return result

    def delete(self, handle: ArtifactHandle) -> None:  # type: ignore[type-arg]
        self._backend.delete(handle.s3_key)
