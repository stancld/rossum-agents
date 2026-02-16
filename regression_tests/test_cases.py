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
    check_hook_test_results_reported,
    check_knowledge_base_hidden_multivalue_warning,
    check_net_terms_formula_field_added,
    check_no_misleading_training_suggestions,
    check_queue_deleted,
    check_queue_ui_settings,
    check_reasoning_field_configured,
    check_schema_replaced_with_formula,
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

SERVERLESS_HOOK_TXSCRIPT_CHECK = CustomCheck(
    name="Serverless hook code follows TxScript conventions",
    check_fn=check_serverless_hook_uses_txscript,
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
        token_budget=TokenBudget(min_total_tokens=4800, max_total_tokens=5500),
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
        token_budget=TokenBudget(min_total_tokens=60000, max_total_tokens=100000),
        success_criteria=SuccessCriteria(
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
        token_budget=TokenBudget(min_total_tokens=120000, max_total_tokens=200000),
        success_criteria=SuccessCriteria(
            required_keywords=["Invoices", "Credit Notes", "Net Terms"],
            max_steps=10,
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
        token_budget=TokenBudget(min_total_tokens=70000, max_total_tokens=185000),
        success_criteria=SuccessCriteria(
            require_subagent=True,
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
            "2. Create a business validation rule with these 3 checks:\n"
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
        token_budget=TokenBudget(min_total_tokens=100000, max_total_tokens=200000),
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
        token_budget=TokenBudget(min_total_tokens=120000, max_total_tokens=300000),
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
]
