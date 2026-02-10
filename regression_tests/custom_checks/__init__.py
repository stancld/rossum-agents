"""Custom check functions for regression tests.

Each check function takes (steps, api_base_url, api_token) and returns tuple[bool, str] (passed, reasoning).
"""

from __future__ import annotations

from regression_tests.custom_checks.business_validation_hook import (
    check_business_validation_hook_settings,
)
from regression_tests.custom_checks.business_validation_rules import (
    check_business_validation_rules,
)
from regression_tests.custom_checks.formula_field import (
    check_formula_field_for_table,
)
from regression_tests.custom_checks.hidden_multivalue_warning import (
    check_knowledge_base_hidden_multivalue_warning,
)
from regression_tests.custom_checks.hook_test_payload import (
    check_hook_test_results_reported,
)
from regression_tests.custom_checks.net_terms_formula_field import (
    check_net_terms_formula_field_added,
)
from regression_tests.custom_checks.no_misleading_training_suggestions import (
    check_no_misleading_training_suggestions,
)
from regression_tests.custom_checks.queue_deletion import (
    check_queue_deleted,
)
from regression_tests.custom_checks.queue_ui_settings import (
    check_queue_ui_settings,
)
from regression_tests.custom_checks.reasoning_field import (
    check_reasoning_field_configured,
)
from regression_tests.custom_checks.serverless_hook_txscript import (
    check_serverless_hook_uses_txscript,
)

__all__ = [
    "check_business_validation_hook_settings",
    "check_business_validation_rules",
    "check_formula_field_for_table",
    "check_hook_test_results_reported",
    "check_knowledge_base_hidden_multivalue_warning",
    "check_net_terms_formula_field_added",
    "check_no_misleading_training_suggestions",
    "check_queue_deleted",
    "check_queue_ui_settings",
    "check_reasoning_field_configured",
    "check_serverless_hook_uses_txscript",
]
