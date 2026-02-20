"""Regression test case definitions.

Add new test cases to REGRESSION_TEST_CASES list.
Each case defines:
- api_base_url: Rossum API base URL
- api_token: Rossum API token
- prompt: What to ask the agent
- tool_expectation: Which tools should be used
- token_budget: Maximum token usage allowed
- success_criteria: What constitutes success
"""

from __future__ import annotations

from regression_tests.custom_checks import (
    check_business_validation_hook_settings,
    check_business_validation_rules,
    check_formula_field_for_table,
    check_formula_field_updated,
    check_hook_deleted_and_reverted,
    check_hook_test_results_reported,
    check_knowledge_base_hidden_multivalue_warning,
    check_lookup_field_configured,
    check_lookup_match_results,
    check_multi_turn_schema_reverted,
    check_net_terms_formula_field_added,
    check_no_misleading_training_suggestions,
    check_queue_deleted,
    check_queue_ui_settings,
    check_reasoning_field_configured,
    check_schema_replaced_and_reverted,
    check_schema_replaced_with_formula,
    check_schema_reverted_with_valid_types,
    check_serverless_hook_uses_txscript,
)
from regression_tests.framework.models import (
    CustomCheck,
    FileExpectation,
    MermaidExpectation,
    RegressionTestCase,
    SuccessCriteria,
    TokenBudget,
    ToolExpectation,
    ToolMatchMode,
)
from regression_tests.setup.schema_revert import create_queue_with_schema

HIDDEN_MULTIVALUE_CHECK = CustomCheck(
    name="Knowledge base warns about hidden/multivalue datapoints",
    check_fn=check_knowledge_base_hidden_multivalue_warning,
)

NO_MISLEADING_TRAINING_SUGGESTIONS_CHECK = CustomCheck(
    name="No misleading training suggestions (e.g., Inbox in training_queues)",
    check_fn=check_no_misleading_training_suggestions,
)

NET_TERMS_FORMULA_FIELD_CHECK = CustomCheck(
    name="Net Terms formula field was added to schema",
    check_fn=check_net_terms_formula_field_added,
)

BUSINESS_VALIDATION_RULES_CHECK = CustomCheck(
    name="Business validation rules have correct trigger conditions",
    check_fn=check_business_validation_rules,
)

BUSINESS_VALIDATION_HOOK_CHECK = CustomCheck(
    name="Business validation hook has correct check settings",
    check_fn=check_business_validation_hook_settings,
)

QUEUE_UI_SETTINGS_CHECK = CustomCheck(
    name="Queue UI has correct column settings",
    check_fn=check_queue_ui_settings,
)

QUEUE_DELETED_CHECK = CustomCheck(
    name="Queue was scheduled for deletion",
    check_fn=check_queue_deleted,
)

REASONING_FIELD_CHECK = CustomCheck(
    name="Reasoning field has correct type, context, and prompt",
    check_fn=check_reasoning_field_configured,
)

FORMULA_FIELD_FOR_TABLE_CHECK = CustomCheck(
    name="Formula field aggregates table column values",
    check_fn=check_formula_field_for_table,
)

HOOK_TEST_RESULTS_CHECK = CustomCheck(
    name="Hook testing reported test_hook results",
    check_fn=check_hook_test_results_reported,
)

FORMULA_FIELD_UPDATED_CHECK = CustomCheck(
    name="Formula field was updated with a new formula",
    check_fn=check_formula_field_updated,
)

SCHEMA_REPLACED_WITH_FORMULA_CHECK = CustomCheck(
    name="Schema replaced with single formula field returning constant",
    check_fn=check_schema_replaced_with_formula,
)

SCHEMA_REPLACED_AND_REVERTED_CHECK = CustomCheck(
    name="Schema replaced with formula field and then reverted to original",
    check_fn=check_schema_replaced_and_reverted,
)

SERVERLESS_HOOK_TXSCRIPT_CHECK = CustomCheck(
    name="Serverless hook code follows TxScript conventions",
    check_fn=check_serverless_hook_uses_txscript,
)

HOOK_DELETED_AND_REVERTED_CHECK = CustomCheck(
    name="Hook was deleted and deletion was reverted",
    check_fn=check_hook_deleted_and_reverted,
)

LOOKUP_FIELD_CHECK = CustomCheck(
    name="Lookup field has valid matching config and evaluation succeeded",
    check_fn=check_lookup_field_configured,
)

LOOKUP_MATCH_RESULTS_CHECK = CustomCheck(
    name="Lookup match results match expected vendor matches",
    check_fn=check_lookup_match_results,
)

SCHEMA_REVERT_TYPE_VALIDATION_CHECK = CustomCheck(
    name="Reverted schema has valid field types (not dicts) and expected fields",
    check_fn=check_schema_reverted_with_valid_types,
)

MULTI_TURN_SCHEMA_REVERTED_CHECK = CustomCheck(
    name="Multi-turn session fields reverted and feature availability checked",
    check_fn=check_multi_turn_schema_reverted,
)


REGRESSION_TEST_CASES: list[RegressionTestCase] = [
    RegressionTestCase(
        name="agent_introduction",
        description="Rossum agent can introduce itself",
        api_base_url="https://mr-fabry.rossum.app/api/v1",
        mode="read-only",
        rossum_url=None,
        prompt="Hey, what can you do?",
        tool_expectation=ToolExpectation(expected_tools=[], mode=ToolMatchMode.EXACT_SEQUENCE),
        token_budget=TokenBudget(min_total_tokens=6000, max_total_tokens=6500),
        success_criteria=SuccessCriteria(
            required_keywords=["hook", "queue"],
            max_steps=1,
            file_expectation=FileExpectation(),
        ),
    ),
    RegressionTestCase(
        name="explain_aurora_sas_workflow",
        description="Explain a document workflow on a queue",
        api_base_url="https://mr-fabry.rossum.app/api/v1",
        mode="read-only",
        rossum_url="https://mr-fabry.rossum.app/documents?filtering=%7B%22items%22%3A%5B%7B%22field%22%3A%22queue%22%2C%22value%22%3A%5B%222500259%22%5D%2C%22operator%22%3A%22isAnyOf%22%7D%5D%2C%22logicOperator%22%3A%22and%22%7D&level=queue&page=1&page_size=100",
        prompt="Explain a document workflow and learning workflow on this queue.",
        tool_expectation=ToolExpectation(expected_tools=["get_queue", "get_queue_engine"], mode=ToolMatchMode.SUBSET),
        token_budget=TokenBudget(min_total_tokens=18000, max_total_tokens=50000),
        success_criteria=SuccessCriteria(
            required_keywords=["document_type", "classification", "training", "workflow"],
            max_steps=5,
            mermaid_expectation=MermaidExpectation(
                descriptions=[
                    "Document workflow showing upload, classification, review, and routing to specialized queues",
                    "Learning workflow showing how the classification engine learns from training queues",
                ],
                min_diagrams=2,
            ),
            file_expectation=FileExpectation(),  # no files are expected to be generated
            custom_checks=[NO_MISLEADING_TRAINING_SUGGESTIONS_CHECK],
        ),
    ),
    RegressionTestCase(
        name="analyze_broken_document_splitting",
        description="Analyze broken document splitting extension based on invoice ID field",
        api_base_url="https://mr-fabry.rossum.app/api/v1",
        mode="read-only",
        rossum_url=None,
        prompt=(
            "Please, investigate the errors with document splitting extension based on extracted invoice ID field on the queue 2500317.\n\n"
            "Give me a one-paragraph executive summary of the root cause and store it in `roast.md`."
        ),
        tool_expectation=ToolExpectation(
            expected_tools=[
                "list_hooks",
                "list_hook_logs",
                "search_knowledge_base",
                "write_file",
                ("get_schema", "get_queue_schema", "get_schema_tree_structure"),  # OR: either is valid
            ],
            mode=ToolMatchMode.SUBSET,
        ),
        token_budget=TokenBudget(min_total_tokens=60000, max_total_tokens=130000),
        success_criteria=SuccessCriteria(
            require_subagent=True,
            required_keywords=[],
            max_steps=7,
            file_expectation=FileExpectation(expected_files=["roast.md"]),
            custom_checks=[HIDDEN_MULTIVALUE_CHECK],
        ),
    ),
    RegressionTestCase(
        name="create_and_delete_credit_note_queue",
        description="Create a credit note queue from template and then delete it",
        api_base_url="https://mr-fabry.rossum.app/api/v1",
        rossum_url=None,
        prompt=(
            "# Create and delete a Credit Note queue\n\n"
            "Workspace: 785638\n\n"
            "## Tasks:\n\n"
            "1. Create a new queue for EU Credit Note with name: Test Credit Note Queue\n"
            "2. Delete the queue you just created\n\n"
            "Return the queue_id that was deleted."
        ),
        tool_expectation=ToolExpectation(
            expected_tools=["create_queue_from_template", "delete_queue"], mode=ToolMatchMode.SUBSET
        ),
        token_budget=TokenBudget(min_total_tokens=20000, max_total_tokens=40000),
        success_criteria=SuccessCriteria(
            required_keywords=["deleted"],
            max_steps=4,
            file_expectation=FileExpectation(),
            custom_checks=[QUEUE_DELETED_CHECK],
        ),
    ),
    RegressionTestCase(
        name="create_invoice_queue_with_reasoning_and_formula_field",
        description="Create invoice queue with reasoning field and formula field for table aggregation",
        api_base_url="https://mr-fabry.rossum.app/api/v1",
        rossum_url=None,
        prompt=(
            "# Create Invoice queue with reasoning field and formula field\n\n"
            "Workspace: 785638\n"
            "Region: EU\n\n"
            "## Tasks:\n\n"
            "1. Create a new queue from EU Invoice template with name: Invoices with Reasoning\n"
            "2. Add a reasoning field to the schema:\n"
            "    - Field name: month_in_spanish\n"
            "    - Section: basic_info_section\n"
            "    - Logic: Take the month from the date due field and return it in Spanish\n"
            "3. Add a formula field to the schema:\n"
            "    - Field name: total_quantity\n"
            "    - Section: basic_info_section\n"
            "    - Logic: Sum of all quantity values across line items\n"
            "Output format: Return ONLY the field configurations as JSON/dict."
        ),
        tool_expectation=ToolExpectation(
            expected_tools=[
                "create_queue_from_template",
                "load_skill",
                "create_task",  # model should plan
                ("patch_schema", "patch_schema_with_subagent"),
                "suggest_formula_field",
            ],
            mode=ToolMatchMode.SUBSET,
            forbidden_tools=[
                "search_knowledge_base",
                "kb_grep",
                "elis_openapi_grep",
                "elis_openapi_jq",
                "search_elis_docs",
            ],
        ),
        token_budget=TokenBudget(min_total_tokens=70000, max_total_tokens=125000),
        success_criteria=SuccessCriteria(
            require_subagent=None,
            required_keywords=[],
            max_steps=6,
            file_expectation=FileExpectation(),
            custom_checks=[REASONING_FIELD_CHECK, FORMULA_FIELD_FOR_TABLE_CHECK],
        ),
    ),
    RegressionTestCase(
        name="setup_customer_queues_and_schema",
        description="Set up customer with Invoices and Credit Notes queues with custom schema and formula field",
        api_base_url="https://mr-fabry.rossum.app/api/v1",
        rossum_url=None,
        prompt=(
            "# Set up a new customer\n\n"
            "Workspace: 785641\n"
            "Region: EU\n\n"
            "## Tasks:\n\n"
            "1. Create two new queues: Invoices and Credit Notes.\n"
            "2. Update schemas w.r.t. ## Schemas section\n"
            "3. Add field to Invoices queue.\n"
            "    - Field name: The Net Terms\n"
            "    - Section: basic_info_section\n"
            "    - Logic: Compute 'Due Date' - 'Issue Date' and categorize it as 'Net 15', 'Net 30' and 'Outstanding'\n\n"
            "## Schemas\n\n"
            "### Invoices\n"
            "| Field | Type | Table field |\n"
            "|-------|------| ----------- |\n"
            "| Document ID | String | No |\n"
            "| Issue Date | Date | No |\n"
            "| Due Date | Date | No |\n"
            "| Vendor Name | String | No |\n"
            "| Vendor Address | String, multiline | No |\n"
            "| Customer Name | String | No |\n"
            "| Customer Address | String, multiline | No |\n"
            "| Total Amount | Float | No |\n"
            "| Total Tax | Float | No |\n"
            "| Currency | String | No |\n"
            "| Code | String, multiline | Yes |\n"
            "| Description | String, multiline | Yes |\n"
            "| Quantity | Integer | Yes |\n"
            "| Unit Price | Float | Yes |\n"
            "| Total | Float | Yes |\n\n"
            "Constraints:\n"
            "- No payment instructions fields\n"
            "- No customer delivery address / name fields\n\n"
            "### Credit notes\n"
            "- Keep it as it is\n"
        ),
        tool_expectation=ToolExpectation(
            expected_tools=[
                "load_skill",
                "create_queue_from_template",
                "suggest_formula_field",
                "patch_schema",
                "get_schema_tree_structure",
                "prune_schema_fields",
            ],
            mode=ToolMatchMode.SUBSET,
        ),
        token_budget=TokenBudget(min_total_tokens=120000, max_total_tokens=300000),
        success_criteria=SuccessCriteria(
            required_keywords=["Invoices", "Credit Notes"],
            max_steps=11,
            file_expectation=FileExpectation(),
            custom_checks=[NET_TERMS_FORMULA_FIELD_CHECK],
        ),
    ),
    RegressionTestCase(
        name="setup_invoice_queue_with_business_validation_hook",
        description="Create Invoice queue with business validation hook and return hook_id",
        api_base_url="https://mr-fabry.rossum.app/api/v1",
        rossum_url=None,
        prompt=(
            "# Set up Invoice queue with business validation hook\n\n"
            "Workspace: 785643\n"
            "Region: EU\n\n"
            "## Tasks:\n\n"
            "1. Create a new queue: Invoices\n"
            "2. Add business validations with these 3 checks:\n"
            '    - Total amount is smaller than 400. Error message: "Total amount is larger than allowed 400."\n'
            '    - Sum of all total amount line items equals total amount. Error message: "Sum of all total amount line items does not equal total amount."\n'
            '    - All line items it holds: "quantity x unit price = total amount"\n\n'
            "Return only the hook_id as a one-word answer."
        ),
        tool_expectation=ToolExpectation(
            expected_tools=[
                "create_queue_from_template",
                "search_knowledge_base",
                "list_hook_templates",
                "create_hook_from_template",
                "update_hook",
            ],
            mode=ToolMatchMode.SUBSET,
        ),
        token_budget=TokenBudget(min_total_tokens=130000, max_total_tokens=220000),
        success_criteria=SuccessCriteria(
            require_subagent=None,
            required_keywords=[],
            max_steps=8,
            file_expectation=FileExpectation(),
            custom_checks=[BUSINESS_VALIDATION_HOOK_CHECK],
        ),
    ),
    RegressionTestCase(
        name="setup_invoice_queue_with_business_validation_rules",
        description="Create Invoice queue with rules business validation using rules (not hooks)",
        api_base_url="https://mr-fabry.rossum.app/api/v1",
        rossum_url=None,
        prompt=(
            "# Set up Invoice queue with business validation\n\n"
            "Workspace: 785643\n"
            "Region: EU\n\n"
            "## Tasks:\n\n"
            "1. Create a new queue: Invoices\n"
            "2. Create a SINGLE business validation rule with these 3 checks:\n"
            '    - Total amount is smaller than 400. Error message: "Total amount is larger than allowed 400."\n'
            '    - Sum of all total amount line items equals total amount. Error message: "Sum of all total amount line items does not equal total amount."\n'
            '    - All line items it holds: "quantity x unit price = total amount"\n\n'
            "Return only the rule ID as a one-word answer."
        ),
        tool_expectation=ToolExpectation(
            expected_tools=[
                "create_queue_from_template",
                "create_rule",
            ],
            mode=ToolMatchMode.SUBSET,
            forbidden_tools=[
                "search_knowledge_base",
                "kb_grep",
                "elis_openapi_grep",
                "elis_openapi_jq",
                "search_elis_docs",
            ],
        ),
        token_budget=TokenBudget(min_total_tokens=40000, max_total_tokens=90000),
        success_criteria=SuccessCriteria(
            require_subagent=False,
            required_keywords=[],
            max_steps=5,
            file_expectation=FileExpectation(),
            custom_checks=[BUSINESS_VALIDATION_RULES_CHECK],
        ),
    ),
    RegressionTestCase(
        name="setup_us_invoice_queue_with_ui_settings",
        description="Create US Invoice queue from template and configure UI settings",
        api_base_url="https://mr-fabry.rossum.app/api/v1",
        rossum_url=None,
        prompt=(
            "# Set up US Invoice queue with custom UI settings\n\n"
            "Workspace: 785643\n"
            "Region: US\n\n"
            "## Tasks:\n\n"
            "1. Create a new queue from US Invoice template: Invoices\n"
            "2. Update queue UI settings to display the following fields:\n"
            "    - status\n"
            "    - original file name\n"
            "    - details\n"
            "    - Document ID\n"
            "    - Due Date\n"
            "    - Total Amount\n"
            "    - Vendor Name\n"
            "    - Received at\n\n"
            "Return only the queue_id as a one-word answer."
        ),
        tool_expectation=ToolExpectation(
            expected_tools=["create_queue_from_template", "load_skill", "update_queue"],
            mode=ToolMatchMode.SUBSET,
        ),
        token_budget=TokenBudget(min_total_tokens=30000, max_total_tokens=50000),
        success_criteria=SuccessCriteria(
            required_keywords=[],
            max_steps=4,
            file_expectation=FileExpectation(),
            custom_checks=[QUEUE_UI_SETTINGS_CHECK],
        ),
    ),
    RegressionTestCase(
        name="create_serverless_hook_and_test",
        description="Create a serverless hook using TxScript and test it",
        api_base_url="https://mr-fabry.rossum.app/api/v1",
        rossum_url=None,
        prompt=(
            "# Create and test a serverless hook\n\n"
            "Workspace: 785638\n"
            "Region: EU\n\n"
            "## Tasks:\n\n"
            "1. Create a new queue from EU Invoice template: Hook Testing Queue\n"
            "2. Create a serverless function hook that normalizes vendor names to uppercase "
            "on annotation content initialization\n"
            "3. Test it\n\n"
            "Return the hook_id."
        ),
        tool_expectation=ToolExpectation(
            expected_tools=[
                "create_queue_from_template",
                "load_skill",
                ("create_hook", "create_hook_from_template"),
                "test_hook",
            ],
            mode=ToolMatchMode.SUBSET,
        ),
        token_budget=TokenBudget(min_total_tokens=150000, max_total_tokens=250000),
        success_criteria=SuccessCriteria(
            required_keywords=[],
            max_steps=10,
            file_expectation=FileExpectation(),
            custom_checks=[SERVERLESS_HOOK_TXSCRIPT_CHECK, HOOK_TEST_RESULTS_CHECK],
        ),
    ),
    RegressionTestCase(
        name="create_queue_add_formula_then_update_formula",
        description="Multi-turn: create queue, add formula field, then update it",
        api_base_url="https://mr-fabry.rossum.app/api/v1",
        rossum_url=None,
        prompt=(
            "# Create queue, add formula field, then update it\n\n"
            "Workspace: 'Another workspace'\n"
            "Region: EU\n\n"
            "## Tasks:\n\n"
            "1. Create a new queue from EU Invoice template: Formula Update Queue\n"
            "2. Add a formula field to the schema:\n"
            "    - Field name: total_quantity\n"
            "    - Section: basic_info_section\n"
            "    - Logic: Sum of all quantity values across line items\n"
            "    - After adding, store the full schema JSON to `schema_v1.json`\n"
            "3. Update the formula field you just created:\n"
            "    - Field name: total_quantity\n"
            "    - New logic: Sum of all total amount values across line items\n"
            "    - After updating, store the full schema JSON to `schema_v2.json`"
        ),
        tool_expectation=ToolExpectation(
            expected_tools=[
                "create_queue_from_template",
                "suggest_formula_field",
                ("patch_schema", "patch_schema_with_subagent"),
                "get_schema",
                "write_file",
            ],
            mode=ToolMatchMode.SUBSET,
        ),
        token_budget=TokenBudget(min_total_tokens=180000, max_total_tokens=320000),
        success_criteria=SuccessCriteria(
            required_keywords=[],
            max_steps=12,
            file_expectation=FileExpectation(expected_files=["schema_v1.json", "schema_v2.json"]),
            custom_checks=[FORMULA_FIELD_UPDATED_CHECK],
        ),
    ),
    RegressionTestCase(
        name="replace_schema_with_single_formula_field",
        description="Create queue, clear schema, add single formula field returning a constant",
        api_base_url="https://mr-fabry.rossum.app/api/v1",
        rossum_url=None,
        prompt=(
            "# Create queue and replace schema with a single formula field\n\n"
            "Workspace: 785638\n"
            "Region: EU\n\n"
            "## Tasks:\n\n"
            '1. Create a new queue from EU Invoice template: "We Love Rossum Queue"\n'
            "2. Remove ALL existing fields from the schema\n"
            "3. Add a single formula field to the schema:\n"
            "    - Field name: we_love_rossum\n"
            "    - Section: basic_info_section\n"
            '    - Logic: Return the constant string "We love Rossum"\n\n'
            "Return only the schema_id as a one-word answer."
        ),
        tool_expectation=ToolExpectation(
            expected_tools=[
                "create_queue_from_template",
                "get_schema_tree_structure",
                "prune_schema_fields",
                ("patch_schema", "patch_schema_with_subagent"),
            ],
            mode=ToolMatchMode.EXACT_SEQUENCE,
        ),
        token_budget=TokenBudget(min_total_tokens=40000, max_total_tokens=90000),
        success_criteria=SuccessCriteria(
            require_subagent=None,
            required_keywords=[],
            max_steps=6,
            file_expectation=FileExpectation(),
            custom_checks=[SCHEMA_REPLACED_WITH_FORMULA_CHECK],
        ),
    ),
    RegressionTestCase(
        name="replace_schema_and_revert",
        description="Create queue, replace schema with a formula field, then revert to original",
        api_base_url="https://mr-fabry.rossum.app/api/v1",
        rossum_url=None,
        requires_redis=True,
        prompt=(
            "# Create queue, replace schema with a formula field, then revert\n\n"
            "Workspace: 785638\n"
            "Region: EU\n\n"
            "## Tasks:\n\n"
            '1. Create a new queue from EU Invoice template: "We Love Rossum Queue"\n'
            "2. Remove ALL existing fields from the schema\n"
            "3. Add a single formula field to the schema:\n"
            "    - Field name: we_love_rossum\n"
            "    - Section: basic_info_section\n"
            '    - Logic: Return the constant string "We love Rossum"\n'
            "4. Revert the last commit to restore the original schema\n\n"
            "Return only the schema_id as a one-word answer."
        ),
        tool_expectation=ToolExpectation(
            expected_tools=[
                "create_queue_from_template",
                "prune_schema_fields",
                ("patch_schema", "patch_schema_with_subagent"),
                "show_change_history",
                "revert_commit",
            ],
            mode=ToolMatchMode.SUBSET,
        ),
        token_budget=TokenBudget(min_total_tokens=80000, max_total_tokens=200000),
        success_criteria=SuccessCriteria(
            require_subagent=None,
            required_keywords=[],
            max_steps=12,
            file_expectation=FileExpectation(),
            custom_checks=[SCHEMA_REPLACED_AND_REVERTED_CHECK],
        ),
    ),
    RegressionTestCase(
        name="create_hook_delete_and_revert",
        description="Create queue with hook, delete hook, then revert the deletion",
        api_base_url="https://mr-fabry.rossum.app/api/v1",
        rossum_url=None,
        requires_redis=True,
        prompt=(
            "# Create queue with hook, delete hook, then revert\n\n"
            "Workspace: 785638\n"
            "Region: EU\n\n"
            "## Tasks:\n\n"
            "1. Create a new queue from EU Invoice template: Hook Revert Queue\n"
            "2. Create a webhook hook on this queue:\n"
            "    - Name: Test Webhook\n"
            "    - Events: annotation_content.initialize\n"
            "    - URL: https://example.com/webhook\n"
            "3. Delete the hook you just created\n"
            "4. Revert the last commit to restore the deleted hook\n\n"
            "Return only the new hook_id as a one-word answer."
        ),
        tool_expectation=ToolExpectation(
            expected_tools=[
                "create_queue_from_template",
                "create_hook",
                "delete_hook",
                "show_change_history",
                "revert_commit",
            ],
            mode=ToolMatchMode.SUBSET,
        ),
        token_budget=TokenBudget(min_total_tokens=80000, max_total_tokens=150000),
        success_criteria=SuccessCriteria(
            require_subagent=None,
            required_keywords=[],
            max_steps=12,
            file_expectation=FileExpectation(),
            custom_checks=[HOOK_DELETED_AND_REVERTED_CHECK],
        ),
    ),
    RegressionTestCase(
        name="revert_schema_with_formula_and_mixed_types",
        description="Empty a pre-loaded schema (with formula + mixed types) and revert — validates type safety",
        api_base_url="https://mr-fabry.rossum.app/api/v1",
        rossum_url=None,
        requires_redis=True,
        setup_fn=create_queue_with_schema,
        prompt=(
            "# Empty schema and revert\n\n"
            "Schema ID: {schema_id}\n\n"
            "## Tasks:\n\n"
            "1. Remove ALL existing fields from schema {schema_id}\n"
            "2. Revert the last commit to restore the original schema\n\n"
            "Return only the schema_id as a one-word answer."
        ),
        tool_expectation=ToolExpectation(
            expected_tools=[
                "prune_schema_fields",
                "show_change_history",
                "revert_commit",
            ],
            mode=ToolMatchMode.SUBSET,
        ),
        token_budget=TokenBudget(min_total_tokens=30000, max_total_tokens=90000),
        success_criteria=SuccessCriteria(
            require_subagent=None,
            required_keywords=[],
            max_steps=6,
            file_expectation=FileExpectation(),
            custom_checks=[SCHEMA_REVERT_TYPE_VALIDATION_CHECK],
        ),
    ),
    RegressionTestCase(
        name="multi_turn_create_and_restore_schema",
        description=(
            "Multi-turn: create queue, add formula + reasoning fields via conversation, "
            "verify feature availability, then revert all schema changes"
        ),
        api_base_url="https://mr-fabry.rossum.app/api/v1",
        rossum_url=None,
        requires_redis=True,
        prompts=[
            "Create a 'New revert queue' in workspace 785638. Use EU template.",
            (
                "Add field to the queue.\n"
                "    - Field name: The Net Terms\n"
                "    - Section: basic_info_section\n"
                "    - Logic: Compute 'Due Date' - 'Issue Date' and categorize it as 'Net 15', 'Net 30' and 'Outstanding'"
            ),
            "If either date missing, please return 'Unavailable' instead of 'Outstanding'.",
            (
                "Add a reasoning field that will take city from the customer address and derive the country of the customer. "
                "Before adding that, can you reason it's a good idea to do it like that?"
            ),
            "Thank you for the considerations. Also, are reasoning fields available on my account?",
            "Then derive it from the whole address, let's see. Add it to the schema.",
            "Print me the list of changes we made.",
            "Add timestamps pls also",
            "I'm not really sure we took a good approach. Please restore the schema back to how it was right after the queue was created.",
        ],
        tool_expectation=ToolExpectation(
            expected_tools=[
                "create_queue_from_template",
                "suggest_formula_field",
                ("patch_schema", "patch_schema_with_subagent"),
                "are_reasoning_fields_enabled",
                "load_skill",
                "restore_entity_version",
            ],
            mode=ToolMatchMode.SUBSET,
        ),
        token_budget=TokenBudget(min_total_tokens=300000, max_total_tokens=700000),
        success_criteria=SuccessCriteria(
            require_subagent=None,
            required_keywords=[],
            max_steps=30,
            file_expectation=FileExpectation(),
            custom_checks=[MULTI_TURN_SCHEMA_REVERTED_CHECK],
        ),
    ),
    RegressionTestCase(
        name="setup_invoice_queue_with_lookup_field",
        description=(
            "Create EU Invoice queue, upload documents, set up vendor lookup field, "
            "and reason about unmatched records using raw MDH dataset data"
        ),
        api_base_url="https://mr-fabry.rossum.app/api/v1",
        rossum_url=None,
        prompt=(
            "# Set up Invoice queue with vendor lookup field\n\n"
            "Workspace: 789108\n"
            "Region: EU\n\n"
            "## Tasks:\n\n"
            "1. Create a new queue from EU Invoice template: Invoices with Lookup\n"
            "2. Upload documents from queue `2519295` to the new queue\n"
            "3. Set up a lookup field for vendor matching following best practices:\n"
            "    - Field name: Vendor match\n"
            "    - Section: vendor_section\n"
            "    - Match vendors from the `approved-vendors` Master Data Hub dataset\n"
            "4. Evaluate the lookup field on the uploaded documents\n"
            "    - If evaluation shows issues, adjust the matching configuration and re-evaluate\n"
            "    - Iterate until results look correct\n"
            "5. For any non-matched cases, verify them against the real matching dataset before finalizing.\n\n"
            'Store `output.json` as a single JSON object with `schema_id` merged into the final `evaluate_lookup_field` result (e.g. `{"schema_id": <id>, "status": ..., "results": [...]}`).'
        ),
        tool_expectation=ToolExpectation(
            expected_tools=[
                "create_queue_from_template",
                "list_annotations",
                "copy_annotations",
                "load_skill",
                "suggest_lookup_field",
                ("patch_schema", "patch_schema_with_subagent"),
                "evaluate_lookup_field",
                "get_lookup_dataset_raw_values",
                "query_lookup_dataset",
                "write_file",
            ],
            mode=ToolMatchMode.SUBSET,
        ),
        token_budget=TokenBudget(min_total_tokens=250000, max_total_tokens=600000),
        success_criteria=SuccessCriteria(
            require_subagent=None,
            required_keywords=[],
            max_steps=18,
            file_expectation=FileExpectation(expected_files=["output.json"]),
            custom_checks=[LOOKUP_FIELD_CHECK, LOOKUP_MATCH_RESULTS_CHECK],
        ),
    ),
]
