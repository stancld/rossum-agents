"""Constrained Python execution tool with Rossum helper bindings."""

from __future__ import annotations

import ast
import functools
import io
import json
import logging
from contextlib import redirect_stdout
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

from anthropic import beta_tool

from rossum_agent.python_tools.copilot.formula import suggest_formula_field as _suggest_formula_field
from rossum_agent.python_tools.copilot.lookup import (
    evaluate_lookup_field as _evaluate_lookup_field,
)
from rossum_agent.python_tools.copilot.lookup import (
    get_lookup_dataset_raw_values as _get_lookup_dataset_raw_values,
)
from rossum_agent.python_tools.copilot.lookup import (
    query_lookup_dataset as _query_lookup_dataset,
)
from rossum_agent.python_tools.copilot.lookup import (
    suggest_lookup_field as _suggest_lookup_field,
)
from rossum_agent.python_tools.copilot.rule import evaluate_rules as _evaluate_rules
from rossum_agent.python_tools.copilot.rule import suggest_rule as _suggest_rule
from rossum_agent.tools.file_tools import write_file as _write_file_tool
from rossum_agent.tools.subagents.mcp_helpers import call_mcp_tool as _call_mcp_tool

if TYPE_CHECKING:
    from anthropic.types import ToolParam

logger = logging.getLogger(__name__)

_MAX_CODE_LENGTH = 12000

_SAFE_BUILTINS: dict[str, object] = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "filter": filter,
    "float": float,
    "getattr": getattr,
    "hasattr": hasattr,
    "int": int,
    "isinstance": isinstance,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "print": print,
    "range": range,
    "reversed": reversed,
    "round": round,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "type": type,
    "zip": zip,
}

_DISALLOWED_AST_NODES = (
    ast.AsyncFor,
    ast.AsyncFunctionDef,
    ast.AsyncWith,
    ast.Await,
    ast.ClassDef,
    ast.Delete,
    ast.Global,
    ast.Import,
    ast.ImportFrom,
    ast.Nonlocal,
    ast.Raise,
    ast.Try,
    ast.TryStar,
    ast.With,
    ast.Yield,
    ast.YieldFrom,
)


def _parse_json_result(raw: str) -> object:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _unwrap_mcp_result(obj: object) -> object:
    """Unwrap common MCP response envelopes used by unified get/search helpers."""
    if isinstance(obj, dict):
        d = cast("dict[str, object]", obj)
        if "data" in d and "entity" in d:
            return d["data"]
        if "result" in d:
            return d["result"]
    elif hasattr(obj, "result"):
        return obj.result
    return obj


def _extract_schema_content(obj: object) -> list[dict[str, object]] | None:
    """Return a schema content array from either a full schema object or the array itself."""
    unwrapped = _unwrap_mcp_result(obj)

    if isinstance(unwrapped, list):
        return cast("list[dict[str, object]]", unwrapped)
    if isinstance(unwrapped, dict):
        d = cast("dict[str, object]", unwrapped)
        content = d.get("content")
        return cast("list[dict[str, object]]", content) if isinstance(content, list) else None
    if hasattr(unwrapped, "content"):
        content = unwrapped.content
        return cast("list[dict[str, object]]", content) if isinstance(content, list) else None
    return None


def _validate_ast(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if isinstance(node, _DISALLOWED_AST_NODES):
            raise ValueError(f"{type(node).__name__} is not allowed in execute_python")
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            raise ValueError("Names starting with '__' are not allowed in execute_python")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ValueError("Attributes starting with '__' are not allowed in execute_python")


def _json_wrapper(fn: object) -> object:
    """Wrap a copilot function so its JSON string return is parsed into a Python object."""

    @functools.wraps(fn)  # type: ignore[arg-type]
    def wrapper(*args: object, **kwargs: object) -> object:
        return _parse_json_result(fn(*args, **kwargs))  # type: ignore[operator]

    return wrapper


def _build_copilot_helpers() -> SimpleNamespace:
    return SimpleNamespace(
        suggest_formula_field=_json_wrapper(_suggest_formula_field),
        suggest_lookup_field=_json_wrapper(_suggest_lookup_field),
        evaluate_lookup_field=_json_wrapper(_evaluate_lookup_field),
        get_lookup_dataset_raw_values=_json_wrapper(_get_lookup_dataset_raw_values),
        query_lookup_dataset=_json_wrapper(_query_lookup_dataset),
        suggest_rule=_json_wrapper(_suggest_rule),
        evaluate_rules=_json_wrapper(_evaluate_rules),
    )


def _build_helpers() -> dict[str, object]:
    copilot = _build_copilot_helpers()

    def write_file(filename: str, content: str | dict | list) -> object:
        return _parse_json_result(_write_file_tool(filename=filename, content=content))

    def mcp(tool_name: str, **kwargs: object) -> object:
        return _call_mcp_tool(tool_name, kwargs)

    def api_get(entity: str, entity_id: int) -> object:
        return mcp("get", entity=entity, entity_id=entity_id)

    def schema_content(value: object) -> list[dict[str, object]]:
        content = _extract_schema_content(value)
        if content is None:
            raise ValueError("schema_content() expected a schema object with 'content' or a content list")
        return content

    return {
        "copilot": copilot,
        "evaluate_lookup_field": copilot.evaluate_lookup_field,
        "evaluate_rules": copilot.evaluate_rules,
        "api_get": api_get,
        "get_lookup_dataset_raw_values": copilot.get_lookup_dataset_raw_values,
        "json": json,
        "query_lookup_dataset": copilot.query_lookup_dataset,
        "schema_content": schema_content,
        "suggest_formula_field": copilot.suggest_formula_field,
        "suggest_lookup_field": copilot.suggest_lookup_field,
        "suggest_rule": copilot.suggest_rule,
        "mcp": mcp,
        "write_file": write_file,
    }


def get_execute_python_definition() -> ToolParam:
    """Get the tool definition for execute_python."""
    return {
        "name": "execute_python",
        "description": (
            "Run short Python snippets in a constrained environment. "
            "Do not use imports. Assign the final structured value to `result` or leave it as the last expression. "
            "When the useful output is a large string, dict, or list, prefer `write_file(...)` inside the snippet instead of returning it inline. "
            "Load the relevant skill first for task-specific helper guidance."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute. No imports. Max 12000 characters.",
                },
                "operation_name": {
                    "type": "string",
                    "description": "Optional short label for the intent of this execution.",
                },
            },
            "required": ["code"],
        },
    }


@beta_tool
def execute_python(code: str, operation_name: str | None = None) -> str:
    """Execute constrained Python with preloaded Rossum helpers."""
    if len(code) > _MAX_CODE_LENGTH:
        return json.dumps({"status": "error", "error": f"Code exceeds {_MAX_CODE_LENGTH} characters."})

    try:
        tree = ast.parse(code, mode="exec")
        _validate_ast(tree)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e), "operation_name": operation_name})

    globals_dict = {"__builtins__": _SAFE_BUILTINS}
    locals_dict = _build_helpers()
    stdout = io.StringIO()
    result_value: object = None

    try:
        with redirect_stdout(stdout):
            if tree.body and isinstance(tree.body[-1], ast.Expr):
                prefix = ast.fix_missing_locations(ast.Module(body=tree.body[:-1], type_ignores=[]))
                suffix = ast.fix_missing_locations(ast.Expression(tree.body[-1].value))
                exec(compile(prefix, "<execute_python>", "exec"), globals_dict, locals_dict)
                result_value = eval(compile(suffix, "<execute_python>", "eval"), globals_dict, locals_dict)
            else:
                exec(compile(tree, "<execute_python>", "exec"), globals_dict, locals_dict)
                result_value = locals_dict.get("result")
    except Exception as e:
        logger.exception("execute_python failed")
        return json.dumps(
            {
                "status": "error",
                "error": f"{type(e).__name__}: {e}",
                "operation_name": operation_name,
                "stdout": stdout.getvalue() or None,
            }
        )

    return json.dumps(
        {
            "status": "success",
            "operation_name": operation_name,
            "result": result_value,
            "stdout": stdout.getvalue() or None,
        },
        default=str,
    )
