# Regression Test Runner Memory

## Project Structure

- Regression tests live in `/Users/daniel.stancl/projects/rossum-agents/regression_tests/`
- Unit tests for custom checks: `regression_tests/test_custom_checks.py` (fast, no API calls)
- Live agent tests: `regression_tests/test_regressions.py` (requires API token + AWS credentials)
- Custom check functions: `regression_tests/custom_checks/` — each check is a `(steps, api_base_url, api_token) -> tuple[bool, str]`
- Shared utilities: `regression_tests/custom_checks/_utils.py`

## Running Tests

- Unit tests for custom checks (fast): `pytest regression_tests/test_custom_checks.py -v`
- rossum-agent unit tests: `pytest rossum-agent/tests/ -v` (run from repo root, not from rossum-agent/)
- Pass API token via env: `ROSSUM_API_TOKEN=<token> pytest ...`

## Known Pre-existing Failures (as of 2026-03)

- `rossum-agent/tests/prompts/test_system_prompt.py::TestSystemPromptSchemaInstructions::test_includes_schema_shape_discipline`
  — Fails on both master and feature branches. Pre-existing issue, not a regression.

## Key Patterns

- `extract_schema_id_from_steps()` is the canonical utility for extracting schema_id; it lives in `_utils.py` and checks `create_queue_from_template` result first, then final answer fallback.
- The branch `ds-agent-python-tool` replaced `suggest_formula_field`, `suggest_rule`, `suggest_lookup_field` tool references with `execute_python` in test expectations.
