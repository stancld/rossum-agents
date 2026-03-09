from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SchemaTreeNode:
    """Lightweight schema node for tree structure display."""

    id: str
    label: str
    category: str
    type: str | None = None
    children: list[SchemaTreeNode] | None = None

    def to_dict(self) -> dict:
        result: dict = {"id": self.id, "label": self.label, "category": self.category}
        if self.type:
            result["type"] = self.type
        if self.children:
            result["children"] = [child.to_dict() for child in self.children]
        return result
