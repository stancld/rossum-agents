"""Schema dataclass models for Rossum MCP Server."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

DatapointType = Literal["string", "number", "date", "enum", "button"]
NodeCategory = Literal["datapoint", "multivalue", "tuple"]


@dataclass
class SchemaDatapoint:
    """A datapoint node for schema patch operations.

    Use for adding/updating fields that capture or display values.
    When used inside a tuple (table), id is required.
    """

    label: str
    id: str | None = None
    category: Literal["datapoint"] = "datapoint"
    type: DatapointType | None = None
    rir_field_names: list[str] | None = None
    default_value: str | None = None
    score_threshold: float | None = None
    hidden: bool = False
    disable_prediction: bool = False
    can_export: bool = True
    constraints: dict | None = None
    options: list[dict] | None = None
    ui_configuration: dict | None = None
    formula: str | None = None
    prompt: str | None = None
    context: list[str] | None = None
    width: int | None = None
    stretch: bool | None = None

    def to_dict(self) -> dict:
        """Convert to dict, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class SchemaTuple:
    """A tuple node for schema patch operations.

    Use within multivalue to define table row structure with multiple columns.
    """

    id: str
    label: str
    children: list[SchemaDatapoint]
    category: Literal["tuple"] = "tuple"
    hidden: bool = False

    def to_dict(self) -> dict:
        """Convert to dict, excluding None values."""
        result: dict = {"id": self.id, "category": self.category, "label": self.label}
        if self.hidden:
            result["hidden"] = self.hidden
        result["children"] = [child.to_dict() for child in self.children]
        return result


@dataclass
class SchemaMultivalue:
    """A multivalue node for schema patch operations.

    Use for repeating fields or tables. Children is a single Tuple or Datapoint (NOT a list).
    The id is optional here since it gets set from node_id in patch_schema.
    """

    label: str
    children: SchemaTuple | SchemaDatapoint
    id: str | None = None
    category: Literal["multivalue"] = "multivalue"
    rir_field_names: list[str] | None = None
    min_occurrences: int | None = None
    max_occurrences: int | None = None
    hidden: bool = False

    def to_dict(self) -> dict:
        """Convert to dict, excluding None values."""
        result: dict = {"label": self.label, "category": self.category}
        if self.id:
            result["id"] = self.id
        if self.rir_field_names:
            result["rir_field_names"] = self.rir_field_names
        if self.min_occurrences is not None:
            result["min_occurrences"] = self.min_occurrences
        if self.max_occurrences is not None:
            result["max_occurrences"] = self.max_occurrences
        if self.hidden:
            result["hidden"] = self.hidden
        result["children"] = self.children.to_dict()
        return result


@dataclass
class SchemaNodeUpdate:
    """Partial update for an existing schema node.

    Only include fields you want to update - all fields are optional.
    """

    label: str | None = None
    type: DatapointType | None = None
    score_threshold: float | None = None
    hidden: bool | None = None
    disable_prediction: bool | None = None
    can_export: bool | None = None
    default_value: str | None = None
    rir_field_names: list[str] | None = None
    constraints: dict | None = None
    options: list[dict] | None = None
    ui_configuration: dict | None = None
    formula: str | None = None
    prompt: str | None = None
    context: list[str] | None = None
    width: int | None = None
    stretch: bool | None = None
    min_occurrences: int | None = None
    max_occurrences: int | None = None

    def to_dict(self) -> dict:
        """Convert to dict, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class SchemaTreeNode:
    """Lightweight schema node for tree structure display."""

    id: str
    label: str
    category: str
    type: str | None = None
    children: list[SchemaTreeNode] | None = None

    def to_dict(self) -> dict:
        """Convert to dict, excluding None values."""
        result: dict = {"id": self.id, "label": self.label, "category": self.category}
        if self.type:
            result["type"] = self.type
        if self.children:
            result["children"] = [child.to_dict() for child in self.children]
        return result


SchemaNode = SchemaDatapoint | SchemaMultivalue | SchemaTuple


@dataclass
class SchemaListItem:
    """Schema summary for list responses (content omitted to save context)."""

    id: int
    name: str | None = None
    queues: list[str] | None = None
    url: str | None = None
    content: str = "<omitted>"
    metadata: dict | None = None
    modified_by: str | None = None
    modified_at: str | None = None
