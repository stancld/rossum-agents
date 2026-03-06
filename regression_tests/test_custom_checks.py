from __future__ import annotations

import json
from types import SimpleNamespace

from rossum_agent.agent.models import ToolCall, ToolResult, ToolResultStep

from regression_tests.custom_checks.formula_field_updated import check_formula_field_updated
from regression_tests.custom_checks.lookup_field import check_lookup_field_configured, check_lookup_match_results


def _tool_step(name: str, arguments: dict, content: str) -> ToolResultStep:
    tool_call = ToolCall(id=f"{name}-1", name=name, arguments=arguments)
    tool_result = ToolResult(tool_call_id=tool_call.id, name=name, content=content)
    return ToolResultStep(step_number=1, tool_calls=[tool_call], tool_results=[tool_result])


def test_formula_field_updated_does_not_require_direct_write_file(monkeypatch) -> None:
    steps = [
        _tool_step(
            "create_queue_from_template",
            {"workspace": "785638"},
            '{"id": 123, "schema": "https://example.test/api/v1/schemas/456"}',
        ),
        _tool_step(
            "patch_schema_with_subagent",
            {
                "schema_id": "456",
                "changes": json.dumps(
                    [{"action": "add", "id": "total_quantity", "formula": "sum(field.quantity.all_values)"}]
                ),
            },
            '{"status": "success"}',
        ),
        _tool_step(
            "patch_schema_with_subagent",
            {
                "schema_id": "456",
                "changes": json.dumps(
                    [{"action": "update", "id": "total_quantity", "formula": "sum(field.amount_total.all_values)"}]
                ),
            },
            '{"status": "success"}',
        ),
        _tool_step(
            "execute_python",
            {"code": "write_file('schema_v1.json', schema)\nwrite_file('schema_v2.json', schema)"},
            '{"status": "success"}',
        ),
    ]

    class DummyClient:
        def retrieve_schema(self, schema_id: int) -> SimpleNamespace:
            assert schema_id == 456
            return SimpleNamespace(content=[])

    monkeypatch.setattr(
        "regression_tests.custom_checks.formula_field_updated.create_api_client",
        lambda api_base_url, api_token: DummyClient(),
    )
    monkeypatch.setattr(
        "regression_tests.custom_checks.formula_field_updated.extract_datapoints",
        lambda content: [SimpleNamespace(id="total_quantity", formula="sum(field.amount_total.all_values)")],
    )

    passed, reasoning = check_formula_field_updated(steps, "https://example.test/api/v1", "token")

    assert passed is True
    assert "sum(field.quantity.all_values)" in reasoning
    assert "sum(field.amount_total.all_values)" in reasoning


def test_lookup_field_configured_uses_schema_id_from_queue_creation(monkeypatch) -> None:
    steps = [
        _tool_step(
            "create_queue_from_template",
            {"workspace": "789108"},
            '{"id": 123, "schema": "https://example.test/api/v1/schemas/456"}',
        ),
        _tool_step(
            "evaluate_lookup_field",
            {"schema_id": 456},
            json.dumps(
                {
                    "status": "success",
                    "results": [
                        {
                            "lookup_results": [
                                {"matching_fields": {"sender_name": "Microsoft"}, "value": "mdh-1", "options": []}
                            ]
                        }
                    ],
                }
            ),
        ),
    ]

    class DummyClient:
        def request_json(self, method: str, path: str) -> dict:
            assert method == "GET"
            assert path == "schemas/456"
            return {
                "content": [
                    {
                        "id": "vendor_section",
                        "children": [
                            {
                                "id": "vendor_match",
                                "ui_configuration": {"type": "lookup"},
                                "matching": {
                                    "type": "master_data_hub",
                                    "configuration": {
                                        "dataset": "approved-vendors",
                                        "queries": ["sender_name"],
                                        "placeholders": ["sender_name"],
                                    },
                                },
                            }
                        ],
                    }
                ]
            }

    monkeypatch.setattr(
        "regression_tests.custom_checks.lookup_field.create_api_client",
        lambda api_base_url, api_token: DummyClient(),
    )

    passed, reasoning = check_lookup_field_configured(steps, "https://example.test/api/v1", "token")

    assert passed is True
    assert "Schema 456 has lookup field 'vendor_match'" in reasoning


def test_lookup_match_results_does_not_require_output_json() -> None:
    steps = [
        _tool_step(
            "evaluate_lookup_field",
            {"schema_id": 456},
            json.dumps(
                {
                    "status": "success",
                    "results": [
                        {"lookup_results": [{"matching_fields": {"sender_name": "Copy General"}, "value": "mdh-1"}]},
                        {"lookup_results": [{"matching_fields": {"sender_name": "Microsoft"}, "value": "mdh-2"}]},
                        {"lookup_results": [{"matching_fields": {"sender_name": "Siemens AG"}, "value": "mdh-3"}]},
                        {"lookup_results": [{"matching_fields": {"sender_name": "McDonald's"}, "value": ""}]},
                        {"lookup_results": [{"matching_fields": {"sender_name": "Google"}, "value": "mdh-4"}]},
                        {
                            "lookup_results": [
                                {"matching_fields": {"sender_name": "General Electric Ltd."}, "value": "mdh-5"}
                            ]
                        },
                        {
                            "lookup_results": [
                                {"matching_fields": {"sender_name": "Blockbuster LLC"}, "value": "mdh-6"}
                            ]
                        },
                    ],
                }
            ),
        )
    ]

    passed, reasoning = check_lookup_match_results(steps, "https://example.test/api/v1", "token")

    assert passed is True
    assert "All 7 vendor match expectations correct" in reasoning
