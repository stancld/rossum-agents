"""Copilot tools for the Rossum Agent.

AI-powered suggestion tools that call Rossum's internal copilot APIs:
- Formula field suggestions
- Lookup field suggestions and evaluation
- Rule suggestions and evaluation
"""

from __future__ import annotations

from rossum_agent.tools.copilot.formula import suggest_formula_field
from rossum_agent.tools.copilot.lookup import (
    evaluate_lookup_field,
    get_lookup_dataset_raw_values,
    query_lookup_dataset,
    suggest_lookup_field,
)
from rossum_agent.tools.copilot.rule import evaluate_rules, suggest_rule

__all__ = [
    "evaluate_lookup_field",
    "evaluate_rules",
    "get_lookup_dataset_raw_values",
    "query_lookup_dataset",
    "suggest_formula_field",
    "suggest_lookup_field",
    "suggest_rule",
]
