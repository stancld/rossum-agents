MCP to Rossum SDK Mapping
==========================

This page documents how the MCP server tools map to the underlying Rossum SDK
endpoints and methods.

Overview
--------

The Rossum MCP Server acts as a bridge between the Model Context Protocol and the
`Rossum API <https://github.com/rossumai/rossum-api>`_. Each MCP tool corresponds
to specific Rossum SDK client methods and API endpoints.

Tool-to-SDK Mapping
--------------------

upload_document
^^^^^^^^^^^^^^^

**MCP Tool:**
  ``upload_document(file_path: str, queue_id: int)``

**Rossum SDK Method:**
  ``AsyncRossumAPIClient.upload_document(queue_id, files)``

**API Endpoint:**
  ``POST /v1/queues/{queue_id}/upload``

**SDK Documentation:**
  https://github.com/rossumai/rossum-api

**Implementation:**
  The tool wraps the SDK's upload_document method in an async executor to maintain
  compatibility with MCP's async interface. See ``rossum_mcp.server:45-67``

get_annotation_content
^^^^^^^^^^^^^^^^^^^^^^

**MCP Tool:**
  ``get_annotation_content(annotation_id: int)``

**Rossum SDK Method:**
  ``AsyncRossumAPIClient.retrieve_annotation(annotation_id, sideloads=("content",))``

**API Endpoint:**
  ``GET /v1/annotations/{annotation_id}?sideload=content``

**Returns:**
  Path to a local JSON file at ``/tmp/rossum_annotation_{id}_content.json``

**SDK Documentation:**
  https://github.com/rossumai/rossum-api

**Implementation:**
  See ``rossum_mcp.tools.annotations``

get
^^^

**MCP Tool:**
  ``get(entity: EntityType, entity_id: int, include_related: bool = False)``

**Supported entities:**
  ``queue``, ``schema``, ``hook``, ``engine``, ``rule``, ``user``, ``workspace``,
  ``email_template``, ``organization_group``, ``organization_limit``, ``annotation``,
  ``relation``, ``document_relation``

**Returns:**
  ``{"entity": "<type>", "id": <id>, "data": {...}}``

**include_related enrichment:**
  - ``queue`` → adds ``schema_tree``, ``engine``, ``hooks``, ``hooks_count``
  - ``schema`` → adds ``queues``, ``rules``
  - ``hook`` → adds ``queues``, ``events``

**API Endpoints:**
  Varies by entity — ``GET /v1/{entity_plural}/{id}``

**Implementation:**
  See ``rossum_mcp.tools.generic.read``

search
^^^^^^

**MCP Tool:**
  ``search(query: SearchQuery)``

**Query object:** discriminated union on ``entity`` field — each entity type exposes only its valid filter params.

**Supported entities and their filters:**

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Entity
     - Available filters
   * - ``queue``
     - ``id``, ``workspace_id``, ``name``, ``use_regex``
   * - ``schema``
     - ``name``, ``queue_id``, ``use_regex``
   * - ``hook``
     - ``queue_id``, ``active``, ``first_n``
   * - ``engine``
     - ``id``, ``engine_type``, ``agenda_id``
   * - ``rule``
     - ``schema_id``, ``organization_id``, ``enabled``
   * - ``user``
     - ``username``, ``email``, ``first_name``, ``last_name``, ``is_active``, ``is_organization_group_admin``
   * - ``workspace``
     - ``organization_id``, ``name``, ``use_regex``
   * - ``email_template``
     - ``queue_id``, ``type``, ``name``, ``first_n``, ``use_regex``
   * - ``organization_group``
     - ``name``, ``use_regex``
   * - ``annotation``
     - ``queue_id`` (required), ``status``, ``ordering``, ``first_n``
   * - ``relation``
     - ``id``, ``type``, ``parent``, ``key``, ``annotation``
   * - ``document_relation``
     - ``id``, ``type``, ``annotation``, ``key``, ``documents``
   * - ``hook_log``
     - ``hook_id``, ``queue_id``, ``annotation_id``, ``email_id``, ``log_level``, ``status``, ``status_code``, ``request_id``, ``timestamp_before/after``, ``start/end_before/after``, ``search``, ``page_size``
   * - ``hook_template``
     - *(no filters)*
   * - ``user_role``
     - *(no filters)*
   * - ``queue_template_name``
     - *(no filters)*

**Returns:**
  ``list`` of entity objects

**API Endpoints:**
  Varies by entity — ``GET /v1/{entity_plural}``

**Implementation:**
  See ``rossum_mcp.tools.generic.read``

get_create_schema
^^^^^^^^^^^^^^^^^

**MCP Tool:**
  ``get_create_schema(entity: CreateEntityType)``

Returns the JSON Schema for a specific entity type, including entity-specific notes.
Call before ``create`` to discover required/optional fields.

**Returns:**
  JSON Schema dict with ``properties``, ``required``, and optional ``note`` field.

create
^^^^^^

**MCP Tool:**
  ``create(entity: CreateEntityType, data: dict)``

Creates an entity. Server-side Pydantic validation is preserved — on validation error,
the response includes ``error``, ``details``, and ``expected_schema`` for self-correction.

**Supported entities:**
  ``workspace``, ``queue_from_template``, ``schema``, ``user``, ``hook``, ``hook_from_template``,
  ``engine``, ``engine_field``, ``rule``, ``email_template``

**Example:**

  .. code-block:: python

     # First, get the schema
     get_create_schema(entity="queue_from_template")

     # Then create
     create(entity="queue_from_template", data={"name": "ACME Invoices", "template_name": "...", "workspace_id": 123})

     create(entity="hook_from_template", data={"name": "Splitting", "hook_template_id": 5, "queues": [...]})

     create(entity="workspace", data={"name": "Production", "organization_id": 100})

**API Endpoints:**
  Varies by entity — ``POST /v1/{entity_plural}`` or entity-specific endpoints.

**Implementation:**
  See ``rossum_mcp.tools.generic.create``

update_queue
^^^^^^^^^^^^

**MCP Tool:**
  ``update_queue(queue_id: int, queue_data: dict)``

**Rossum SDK Method:**
  ``AsyncRossumAPIClient.internal_client.update(Resource.Queue, queue_id, queue_data)``

**API Endpoint:**
  ``PATCH /v1/queues/{queue_id}``

**Request Body:**
  Partial JSON object with only the fields to update (e.g., automation_enabled,
  automation_level, default_score_threshold).

**SDK Documentation:**
  https://github.com/rossumai/rossum-api

**Implementation:**
  Updates specific queue fields using PATCH semantics. Commonly used to configure
  automation thresholds and settings. See ``rossum_mcp.server:444-486``

update_schema
^^^^^^^^^^^^^

**MCP Tool:**
  ``update_schema(schema_id: int, schema_data: dict)``

**Rossum SDK Method:**
  ``AsyncRossumAPIClient.internal_client.update(Resource.Schema, schema_id, schema_data)``

**API Endpoint:**
  ``PATCH /v1/schemas/{schema_id}``

**Request Body:**
  Partial JSON object typically containing the 'content' array with field-level
  configuration including score_threshold properties.

**SDK Documentation:**
  https://github.com/rossumai/rossum-api

**Implementation:**
  Updates schema configuration, typically used to set field-level automation
  thresholds that override the queue's default threshold. See ``rossum_mcp.server:488-526``

update_engine
^^^^^^^^^^^^^

**MCP Tool:**
  ``update_engine(engine_id: int, engine_data: dict)``

**Rossum SDK Method:**
  ``AsyncRossumAPIClient.internal_client.update(Resource.Engine, engine_id, engine_data)``

**API Endpoint:**
  ``PATCH /v1/engines/{engine_id}``

**Request Body:**
  Partial JSON object with only the fields to update. Supported fields:
  - ``name`` (str): Engine name
  - ``description`` (str): Engine description
  - ``learning_enabled`` (bool): Enable/disable learning
  - ``training_queues`` (list[str]): List of queue URLs for training

**SDK Documentation:**
  https://github.com/rossumai/rossum-api

**Implementation:**
  Updates engine configuration using PATCH semantics. Commonly used to manage
  training queues and learning settings. See ``rossum_mcp.server:450-495``

**Common Use Case:**
  Update training queues to specify which queues an engine should learn from:

  .. code-block:: python

     engine_data = {
         "training_queues": [
             "https://api.elis.rossum.ai/v1/queues/12345",
             "https://api.elis.rossum.ai/v1/queues/67890"
         ]
     }
     result = await server.update_engine(engine_id=36032, engine_data=engine_data)

**Important:** When using the SDK directly with ``request_json``, always use the
``json=`` parameter, not ``data=``. The Rossum API expects JSON-encoded data
(application/json), not form-encoded data (application/x-www-form-urlencoded).

update_rule
^^^^^^^^^^^

**MCP Tool:**
  ``update_rule(rule_id: int, name: str, trigger_condition: str, actions: list[dict], enabled: bool, queue_ids: list[int] | None = None)``

**Rossum SDK Method:**
  ``AsyncRossumAPIClient._http_client.update(Resource.Rule, rule_id, rule_data)``

**API Endpoint:**
  ``PUT /v1/rules/{id}``

**Request Body:**
  - ``name``: Rule name (required)
  - ``trigger_condition``: TxScript formula string (required)
  - ``actions``: List of actions (required)
  - ``enabled``: Whether the rule is active (required)
  - ``queues``: List of queue URLs to limit rule to specific queues (optional)

**Implementation:**
  Full update (PUT) of a business rule. All fields are required.
  Schema cannot be changed after creation.

**Common Use Cases:**

  .. code-block:: python

     # Full update of a rule
     rule = await server.update_rule(
         rule_id=67890,
         name="Updated High Value Alert",
         trigger_condition="field.amount > 5000",
         actions=[{"id": "alert1", "type": "show_message", "event": "validation", "payload": {"type": "warning", "content": "Medium value invoice", "schema_id": "amount"}}],
         enabled=True
     )

patch_rule
^^^^^^^^^^

**MCP Tool:**
  ``patch_rule(rule_id: int, name: str | None, trigger_condition: str | None, actions: list[dict] | None, enabled: bool | None, queue_ids: list[int] | None = None)``

**Rossum SDK Method:**
  ``AsyncRossumAPIClient.update_part_rule(rule_id, rule_data)``

**API Endpoint:**
  ``PATCH /v1/rules/{id}``

**Request Body:**
  - ``name``: Rule name (optional)
  - ``trigger_condition``: TxScript formula string (optional)
  - ``actions``: List of actions (optional)
  - ``enabled``: Whether the rule is active (optional)
  - ``queues``: List of queue URLs (optional, empty list removes all queue associations)

**Implementation:**
  Partial update (PATCH) of a business rule. Only provided fields are updated.

**Common Use Cases:**

  .. code-block:: python

     # Disable a rule
     rule = await server.patch_rule(rule_id=67890, enabled=False)

     # Update only the trigger condition
     rule = await server.patch_rule(
         rule_id=67890,
         trigger_condition="field.amount > 20000"
     )

update_hook
^^^^^^^^^^^

**MCP Tool:**
  ``update_hook(hook_id: int, name: str | None, queues: list[str] | None, events: list[str] | None, config: dict | None, settings: dict | None, active: bool | None)``

**Rossum SDK Method:**
  ``AsyncRossumAPIClient.update_part_hook(hook_id, hook_data)``

**API Endpoint:**
  ``PATCH /v1/hooks/{hook_id}``

**Request Body:**
  Partial JSON object with only the fields to update.

**SDK Documentation:**
  https://github.com/rossumai/rossum-api

**Implementation:**
  Updates an existing hook's properties. Only provided fields are updated; others remain
  unchanged. Commonly used to modify hook name, attached queues, events, config, or active status.

test_hook
^^^^^^^^^

**MCP Tool:**
  ``test_hook(hook_id: int, event: HookEvent, action: HookAction, annotation: str | None, status: str | None, previous_status: str | None, config: dict | None)``

**API Endpoint:**
  ``POST /v1/hooks/{hook_id}/test``

**Request Body:**
  JSON object with ``event``, ``action``, optional ``annotation`` URL, optional ``status``/``previous_status``,
  and optional ``config`` override.

**Implementation:**
  Tests a hook by generating a payload from the given event/action parameters and sending it directly.
  Returns hook response and logs.

patch_schema
^^^^^^^^^^^^

**MCP Tool:**
  ``patch_schema(schema_id: int, operation: str, node_id: str, node_data: dict | None, parent_id: str | None, position: int | None)``

**Rossum SDK Method:**
  ``AsyncRossumAPIClient.update_schema(schema_id, data)`` (with modified content)

**API Endpoint:**
  ``PATCH /v1/schemas/{schema_id}``

**Request Body:**
  JSON object with modified schema content array.

**SDK Documentation:**
  https://github.com/rossumai/rossum-api

**Implementation:**
  Patches a schema by adding, updating, or removing individual nodes without replacing the
  entire content. Operations: "add" (requires parent_id, node_data), "update" (requires node_data),
  "remove" (only node_id needed).

get_schema_tree_structure
^^^^^^^^^^^^^^^^^^^^^^^^^

**MCP Tool:**
  ``get_schema_tree_structure(schema_id: int | None, queue_id: int | None)``

**Rossum SDK Method:**
  ``AsyncRossumAPIClient.retrieve_schema(schema_id)``

**API Endpoint:**
  ``GET /v1/schemas/{schema_id}``

**SDK Documentation:**
  https://github.com/rossumai/rossum-api

**Implementation:**
  Returns a lightweight tree structure of the schema with only ids, labels, categories, and types.
  Accepts either ``schema_id`` or ``queue_id`` (resolves to schema automatically). Exactly one
  parameter must be provided.

prune_schema_fields
^^^^^^^^^^^^^^^^^^^

**MCP Tool:**
  ``prune_schema_fields(schema_id: int, fields_to_keep: list[str])``

**Rossum SDK Method:**
  ``AsyncRossumAPIClient.update_schema(schema_id, data)``

**API Endpoint:**
  ``PUT /v1/schemas/{schema_id}``

**SDK Documentation:**
  https://github.com/rossumai/rossum-api

**Implementation:**
  Removes multiple fields from a schema at once, keeping only specified fields and their
  ancestor sections/multivalues. Efficient for pruning unwanted fields during setup.

list_tool_categories
^^^^^^^^^^^^^^^^^^^^

**MCP Tool:**
  ``list_tool_categories()``

**API Endpoint:**
  N/A (returns data from local catalog)

**Implementation:**
  Returns all available tool categories with their metadata. The catalog is defined
  in ``rossum_mcp.tools.catalog`` and includes category names, descriptions, tool
  lists, and keywords for automatic pre-loading based on user request text.
  See ``rossum_mcp.tools.discovery:18-36``

**Returns:**
  List of category objects with structure:

  - ``name``: Category identifier (e.g., "queues", "schemas")
  - ``description``: Human-readable category description
  - ``tool_count``: Number of tools in the category
  - ``tools``: List of tool metadata (name, description)
  - ``keywords``: Keywords for automatic category matching

**Available Categories:**

.. list-table::
   :header-rows: 1
   :widths: 20 50 30

   * - Category
     - Description
     - Keywords
   * - ``read``
     - Unified read layer: get one entity by ID or search/list with typed filters
     - get, search, list, read, retrieve, find, lookup
   * - ``write``
     - Create and delete entities (unified create/delete tools)
     - create, delete, new, remove
   * - ``annotations``
     - Document processing: upload, retrieve, update, confirm
     - annotation, document, upload, extract, confirm, review
   * - ``queues``
     - Queue management: update, configure
     - queue, inbox, connector
   * - ``schemas``
     - Schema management: define, modify field structures
     - schema, field, datapoint, section, multivalue, tuple
   * - ``engines``
     - AI engine management: update engines, get engine fields
     - engine, ai, extractor, splitter, training
   * - ``hooks``
     - Extensions/webhooks: update and test hooks
     - hook, extension, webhook, automation, function, serverless
   * - ``rules``
     - Validation rules: update and patch rules
     - rule, validation, constraint
   * - ``users``
     - User management: update users
     - user, role, permission, token_owner
**Example:**

.. code-block:: python

   # Get all available categories
   categories = await server.list_tool_categories()

   # Find categories matching a keyword
   for cat in categories:
       if "schema" in cat["keywords"]:
           print(f"{cat['name']}: {cat['tool_count']} tools")

copy_annotations
^^^^^^^^^^^^^^^^

**MCP Tool:**
  ``copy_annotations(annotation_ids: Sequence[int], target_queue_id: int, target_status: str | None = None, reimport: bool = False)``

**API Endpoint:**
  ``POST /v1/annotations/{annotation_id}/copy`` (called per annotation)

**Implementation:**
  Iterates over ``annotation_ids``, calling the copy endpoint for each. Collects
  results and errors separately for graceful partial failure handling. Uses
  ``_http_client.request_json`` directly since the SDK has no copy method.

Delete Layer
------------

The unified ``delete`` tool replaces all individual ``delete_X`` tools. It routes
to the appropriate SDK method based on the ``entity`` parameter, using the
``delete_resource`` helper from ``rossum_mcp.tools.base`` for consistent
read-only mode checks and response formatting.

delete
^^^^^^

**MCP Tool:**
  ``delete(entity: str, entity_id: int)``

**Supported entities and SDK methods:**

.. list-table::
   :header-rows: 1

   * - Entity
     - SDK Method
     - API Endpoint
     - Notes
   * - ``queue``
     - ``AsyncRossumAPIClient.delete_queue(id)``
     - ``DELETE /v1/queues/{id}``
     - Schedules deletion after 24h; cascades to annotations/documents
   * - ``schema``
     - ``AsyncRossumAPIClient.delete_schema(id)``
     - ``DELETE /v1/schemas/{id}``
     - Fails with 409 if linked to any queue/annotation
   * - ``hook``
     - ``AsyncRossumAPIClient.delete_hook(id)``
     - ``DELETE /v1/hooks/{id}``
     -
   * - ``rule``
     - ``AsyncRossumAPIClient.delete_rule(id)``
     - ``DELETE /v1/rules/{id}``
     -
   * - ``workspace``
     - ``AsyncRossumAPIClient.delete_workspace(id)``
     - ``DELETE /v1/workspaces/{id}``
     - Fails if workspace contains queues
   * - ``annotation``
     - ``AsyncRossumAPIClient.delete_annotation(id)``
     - ``DELETE /v1/annotations/{id}``
     - Soft delete — moves to 'deleted' status

**Implementation:**
  Defined in ``rossum_mcp/tools/generic/delete.py``. A registry maps entity
  names to existing private delete functions from individual tool modules.

Rossum API Resources
---------------------

* **Rossum API Documentation**: https://elis.rossum.ai/api/docs/
* **Rossum SDK Repository**: https://github.com/rossumai/rossum-sdk
* **Rossum SDK Python Package**: Available via git installation

Authentication
--------------

The server uses token-based authentication configured via environment variables:

* ``ROSSUM_API_TOKEN``: Your Rossum API authentication token
* ``ROSSUM_API_BASE_URL``: The Rossum API base URL (e.g., https://api.elis.rossum.ai/v1)
* ``ROSSUM_MCP_MODE``: Controls which tools are available (``read-only`` or ``read-write``, default: ``read-write``)

The token is passed to the SDK client as:

.. code-block:: python

   from rossum_api import AsyncRossumAPIClient
   from rossum_api.dtos import Token

   client = AsyncRossumAPIClient(
       base_url=base_url,
       credentials=Token(token=api_token)
   )

Mode Control Tools
^^^^^^^^^^^^^^^^^^

get_mcp_mode
""""""""""""

Returns the current MCP operation mode.

**Parameters:** None

**Returns:**

.. code-block:: json

   {"mode": "read-only"}

set_mcp_mode
""""""""""""

Sets the MCP operation mode at runtime.

**Parameters:**

- ``mode`` (string, required): The mode to set ("read-only" or "read-write")

**Returns:**

.. code-block:: json

   {"message": "MCP mode set to 'read-write'"}

If an invalid mode is provided:

.. code-block:: json

   {"error": "Invalid mode 'invalid'. Must be one of: ('read-only', 'read-write')"}

Error Handling
--------------

All SDK exceptions are caught and returned as JSON error responses:

.. code-block:: json

   {
     "error": "Error message",
     "traceback": "Full Python traceback..."
   }

This allows MCP clients to handle errors gracefully without losing debugging context.
