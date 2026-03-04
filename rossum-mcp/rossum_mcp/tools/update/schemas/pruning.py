"""Schema pruning utilities for removing fields from schema content."""

from __future__ import annotations

import copy


def _collect_all_field_ids(content: list[dict]) -> set[str]:
    """Collect all field IDs from schema content recursively."""
    ids: set[str] = set()

    def _traverse(node: dict) -> None:
        node_id = node.get("id")
        if node_id:
            ids.add(node_id)
        children = node.get("children")
        if children is not None:
            if isinstance(children, list):
                for child in children:
                    _traverse(child)
            elif isinstance(children, dict):
                _traverse(children)

    for section in content:
        _traverse(section)

    return ids


def _collect_ancestor_ids(content: list[dict], target_ids: set[str]) -> set[str]:
    """Collect all ancestor IDs for the given target field IDs.

    Returns set of IDs for all parent containers (multivalue, tuple, section) of target fields.
    """
    ancestors: set[str] = set()

    def _find_ancestors(node: dict, path: list[str]) -> None:
        node_id = node.get("id", "")
        current_path = [*path, node_id] if node_id else path

        if node_id in target_ids:
            ancestors.update(current_path[:-1])

        children = node.get("children")
        if children is not None:
            if isinstance(children, list):
                for child in children:
                    _find_ancestors(child, current_path)
            elif isinstance(children, dict):
                _find_ancestors(children, current_path)

    for section in content:
        _find_ancestors(section, [])

    return ancestors


def _remove_fields_from_content(content: list[dict], fields_to_remove: set[str]) -> tuple[list[dict], list[str]]:
    """Remove multiple fields from schema content.

    Returns (modified_content, list_of_removed_field_ids).
    Sections cannot be removed.
    """
    content = copy.deepcopy(content)
    removed: list[str] = []

    def _filter_children(children: list[dict]) -> list[dict]:
        result = []
        for child in children:
            child_id = child.get("id", "")
            category = child.get("category", "")

            if child_id in fields_to_remove and category != "section":
                removed.append(child_id)
                continue

            nested = child.get("children")
            if nested is not None:
                if isinstance(nested, list):
                    child["children"] = _filter_children(nested)
                elif isinstance(nested, dict):
                    nested_id = nested.get("id", "")
                    if nested_id in fields_to_remove:
                        removed.append(nested_id)
                        removed.append(child_id)
                        continue
                    nested_children = nested.get("children")
                    if isinstance(nested_children, list):
                        filtered_nested = _filter_children(nested_children)
                        if not filtered_nested:
                            removed.append(nested_id)
                            removed.append(child_id)
                            continue
                        nested["children"] = filtered_nested
            result.append(child)
        return result

    for section in content:
        section_children = section.get("children")
        if isinstance(section_children, list):
            section["children"] = _filter_children(section_children)

    removed_sections = [s.get("id", "") for s in content if not s.get("children")]
    removed.extend(removed_sections)
    content = [s for s in content if s.get("children")]

    return content, removed
