Usage
=====

Running the MCP Server
-----------------------

Start the server using:

.. code-block:: bash

   python -m rossum_mcp.server

Or if installed as a package:

.. code-block:: bash

   rossum-mcp

Using with MCP Clients
----------------------

Claude Desktop Configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Configure your MCP client to use this server. For example, in Claude Desktop's config:

.. code-block:: json

   {
     "mcpServers": {
       "rossum": {
         "command": "python",
         "args": ["/path/to/rossum-mcp/rossum-mcp/rossum_mcp/server.py"],
         "env": {
           "ROSSUM_API_TOKEN": "your-api-token",
           "ROSSUM_API_BASE_URL": "https://api.elis.rossum.ai/v1",
           "ROSSUM_MCP_MODE": "read-write"
         }
       }
     }
   }

For read-only access , use ``"ROSSUM_MCP_MODE": "read-only"`` to restrict access to read-only operations (GET/LIST only).

Running the AI Agent
--------------------

The ``rossum_agent`` package provides a REST API interface:

.. code-block:: bash

   # REST API
   rossum-agent-api

   # Or run with Docker Compose
   docker-compose up rossum-agent

The agent includes file output, knowledge base search, hook testing, deployment tools,
and multi-environment MCP connections. See the :doc:`examples` section for complete workflows.

Using Rossum Deploy
-------------------

The ``rossum_deploy`` package provides Python API and CLI for configuration deployment.

Python API
^^^^^^^^^^

.. code-block:: python

   from rossum_deploy import Workspace

   # Initialize workspace
   ws = Workspace(
       "./my-project",
       api_base="https://api.elis.rossum.ai/v1",
       token="your-token"
   )

   # Pull all objects from an organization
   result = ws.pull(org_id=123456)
   print(result.summary())

   # Show diff between local and remote
   diff = ws.diff()
   print(diff.summary())

   # Push changes (dry run first)
   result = ws.push(dry_run=True)
   print(result.summary())

   # Push for real
   result = ws.push()

CLI Commands
^^^^^^^^^^^^

Set environment variables:

.. code-block:: bash

   export ROSSUM_API_BASE_URL="https://api.elis.rossum.ai/v1"
   export ROSSUM_API_TOKEN="your-token"

Commands:

.. code-block:: bash

   # Pull from organization
   rossum-deploy pull 123456

   # Show diff
   rossum-deploy diff

   # Push (dry run)
   rossum-deploy push --dry-run

   # Push for real
   rossum-deploy push

Cross-Organization Deployment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Deploy configurations from sandbox to production:

.. code-block:: python

   from rossum_deploy import Workspace

   ws = Workspace("./my-project", api_base="...", token="...")

   # Copy production config to sandbox (one-time setup)
   result = ws.copy_org(
       source_org_id=123456,  # Production
       target_org_id=789012,  # Sandbox
   )

   # After agent modifies sandbox, deploy back to production
   result = ws.deploy(target_org_id=123456, dry_run=True)
   print(result.summary())

Using with AI Agents
--------------------

The Rossum Agent is built with Anthropic Claude for intelligent document processing.
The agent includes file system tools, plotting capabilities, and seamless Rossum integration.

Slash Commands
^^^^^^^^^^^^^^

The REST API supports slash commands — messages starting with ``/`` that are intercepted
before reaching the agent. They return instant responses without consuming tokens.

.. code-block:: text

   /list-commands    List all available slash commands
   /list-commits     List configuration commits made in this chat
   /list-skills      List available agent skills
   /list-mcp-tools   List MCP tools by category
   /list-agent-tools List built-in agent tools

Available commands can be discovered via ``GET /api/v1/commands``.

Available Tools
---------------

Read Layer
^^^^^^^^^^

The read layer provides two unified tools — ``get`` and ``search`` — that replace all
previous per-entity get/list tools.

get
"""

Unified tool to fetch any entity by ID (single or batch).

**Parameters:**

- ``entity`` (string, required): Entity type. One of: ``queue``, ``schema``, ``hook``,
  ``engine``, ``rule``, ``user``, ``workspace``, ``email_template``,
  ``organization_group``, ``organization_limit``, ``annotation``, ``relation``,
  ``document_relation``
- ``entity_id`` (integer or list of integers, required): ID or list of IDs to fetch
- ``include_related`` (boolean, optional, default false): Enriches the result with related
  data. ``queue`` adds ``schema_tree``, ``engine``, ``hooks``, ``hooks_count``;
  ``schema`` adds ``queues``, ``rules``; ``hook`` adds ``queues``, ``events``

**Returns:**

Single entity:

.. code-block:: json

   {"entity": "queue", "id": 12345, "data": {"id": 12345, "name": "Invoices"}}

Batch: list of the above.

**Example usage:**

.. code-block:: python

   # Get a single queue
   get(entity="queue", entity_id=12345)

   # Get queue with related schema, engine, and hooks
   get(entity="queue", entity_id=12345, include_related=True)

   # Batch fetch multiple schemas
   get(entity="schema", entity_id=[100, 200, 300])

   # Get annotation metadata
   get(entity="annotation", entity_id=67890)

search
""""""

Unified tool to list/filter entities with typed, entity-specific query objects.

**Parameters:**

- ``query`` (object, required): A discriminated query object with ``entity`` as the
  discriminator. Each entity type exposes only its valid filter fields.

**Supported entities and their filters:**

.. list-table::
   :header-rows: 1
   :widths: 25 75

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
     - ``hook_id``, ``queue_id``, ``annotation_id``, ``email_id``, ``log_level``, ``status``,
       ``status_code``, ``request_id``, ``timestamp_before``, ``timestamp_after``, ``start_before``,
       ``start_after``, ``end_before``, ``end_after``, ``search``, ``page_size``
   * - ``hook_template``
     - *(no filters)*
   * - ``user_role``
     - *(no filters)*

**Returns:** List of entity objects.

**Example usage:**

.. code-block:: python

   # List all queues in a workspace
   search(query={"entity": "queue", "workspace_id": 11111})

   # List active hooks for a queue
   search(query={"entity": "hook", "queue_id": 12345, "active": True})

   # List recent annotations
   search(query={"entity": "annotation", "queue_id": 12345, "ordering": ["-created_at"], "first_n": 1})

   # List error hook logs for a hook
   search(query={"entity": "hook_log", "hook_id": 12345, "log_level": "ERROR"})

   # List all hook templates (Rossum Store)
   search(query={"entity": "hook_template"})

   # Find user by email for token_owner
   search(query={"entity": "user", "email": "john.doe@example.com", "is_organization_group_admin": False})

   # List enabled rules for a schema
   search(query={"entity": "rule", "schema_id": 200, "enabled": True})

upload_document
^^^^^^^^^^^^^^^

Uploads a document to Rossum for processing. Returns a task ID. Use ``search(query={"entity": "annotation", "queue_id": <id>})``
to get the annotation ID.

**Parameters:**

- ``file_path`` (string, required): Absolute path to the document file
- ``queue_id`` (integer, required): Rossum queue ID where the document should be uploaded

**Returns:**

.. code-block:: json

   {
     "task_id": "12345",
     "task_status": "created",
     "queue_id": 12345,
     "message": "Document upload initiated. Use `search` with entity=\"annotation\" to find the annotation ID for this queue."
   }

get_queue_template_names
^^^^^^^^^^^^^^^^^^^^^^^^

Returns a list of available template names for use with ``create_queue_from_template``.

**Parameters:** None

**Returns:**

.. code-block:: json

   [
     "EU Demo Template",
     "AP&R EU Demo Template",
     "Tax Invoice EU Demo Template",
     "US Demo Template",
     "AP&R US Demo Template",
     "Tax Invoice US Demo Template",
     "UK Demo Template",
     "AP&R UK Demo Template",
     "Tax Invoice UK Demo Template",
     "CZ Demo Template",
     "Empty Organization Template",
     "Delivery Notes Demo Template",
     "Delivery Note Demo Template",
     "Chinese Invoices (Fapiao) Demo Template",
     "Tax Invoice CN Demo Template",
     "Certificates of Analysis Demo Template",
     "Purchase Order Demo Template",
     "Credit Note Demo Template",
     "Debit Note Demo Template",
     "Proforma Invoice Demo Template"
   ]

create_queue_from_template
^^^^^^^^^^^^^^^^^^^^^^^^^^

Creates a new queue from a predefined template. **Preferred method for new customer setup.**
Templates include pre-configured schema and AI engine optimized for specific document types.

**Parameters:**

- ``name`` (string, required): Name of the queue to create
- ``template_name`` (string, required): Template name (use ``get_queue_template_names`` to list)
- ``workspace_id`` (integer, required): Workspace ID where the queue should be created
- ``include_documents`` (boolean, optional): Copy documents from template queue (default: false)
- ``engine_id`` (integer, optional): Override engine assignment

**Returns:**

.. code-block:: json

   {
     "id": 12345,
     "name": "ACME Corp - Invoices",
     "url": "https://elis.rossum.ai/api/v1/queues/12345",
     "workspace": "https://elis.rossum.ai/api/v1/workspaces/11111",
     "schema": "https://elis.rossum.ai/api/v1/schemas/67890"
   }

create_queue
^^^^^^^^^^^^

Creates a new queue with schema and optional engine assignment. Allows full configuration
of queue settings including automation and training.

**Parameters:**

- ``name`` (string, required): Name of the queue to create
- ``workspace_id`` (integer, required): Workspace ID where the queue should be created
- ``schema_id`` (integer, required): Schema ID to assign to the queue
- ``engine_id`` (integer, optional): Optional engine ID to assign for document processing
- ``inbox_id`` (integer, optional): Optional inbox ID to assign
- ``connector_id`` (integer, optional): Optional connector ID to assign
- ``locale`` (string, optional): Queue locale (default: "en_GB")
- ``automation_enabled`` (boolean, optional): Enable automation (default: false)
- ``automation_level`` (string, optional): Automation level - "never", "always", etc. (default: "never")
- ``training_enabled`` (boolean, optional): Enable training (default: true)

**Returns:**

.. code-block:: json

   {
     "id": "12345",
     "name": "My New Queue",
     "url": "https://elis.rossum.ai/api/v1/queues/12345",
     "workspace": "https://elis.rossum.ai/api/v1/workspaces/11111",
     "schema": "https://elis.rossum.ai/api/v1/schemas/67890",
     "engine": "https://elis.rossum.ai/api/v1/engines/54321",
     "inbox": null,
     "connector": null,
     "locale": "en_GB",
     "automation_enabled": false,
     "automation_level": "never",
     "training_enabled": true,
     "message": "Queue 'My New Queue' created successfully with ID 12345"
   }

update_queue
^^^^^^^^^^^^

Updates an existing queue's settings including automation thresholds. Use this to
configure automation settings like enabling automation, setting automation level,
and defining the default confidence score threshold.

**Parameters:**

- ``queue_id`` (integer, required): Queue ID to update
- ``queue_data`` (object, required): Dictionary containing queue fields to update. Common fields:

  - ``name`` (string): Queue name
  - ``automation_enabled`` (boolean): Enable/disable automation
  - ``automation_level`` (string): "never", "always", "confident", etc.
  - ``default_score_threshold`` (float): Default confidence threshold 0.0-1.0 (e.g., 0.90 for 90%)
  - ``locale`` (string): Queue locale
  - ``training_enabled`` (boolean): Enable/disable training

**Returns:**

.. code-block:: json

   {
     "id": "12345",
     "name": "Updated Queue",
     "url": "https://elis.rossum.ai/api/v1/queues/12345",
     "automation_enabled": true,
     "automation_level": "confident",
     "default_score_threshold": 0.90,
     "locale": "en_GB",
     "training_enabled": true,
     "message": "Queue 'Updated Queue' (ID 12345) updated successfully"
   }

delete_queue
^^^^^^^^^^^^

Schedules a queue for deletion. The queue will be deleted after a 24-hour delay,
allowing time to recover if needed.

**Parameters:**

- ``queue_id`` (integer, required): Queue ID to delete

**Returns:**

.. code-block:: json

   {
     "message": "Queue 12345 scheduled for deletion (starts after 24 hours)"
   }

**Note:** This operation is only available in read-write mode.

update_schema
^^^^^^^^^^^^^

Updates an existing schema, typically used to set field-level automation thresholds.
Field-level thresholds override the queue's default_score_threshold.

**Workflow:**

1. First get the schema using ``get(entity="queue", entity_id=queue_id, include_related=True)``
   or ``get(entity="schema", entity_id=schema_id)``
2. Modify the ``content`` array by adding/updating ``score_threshold`` properties on specific fields
3. Call this tool with the modified content

**Parameters:**

- ``schema_id`` (integer, required): Schema ID to update
- ``schema_data`` (object, required): Dictionary containing schema fields to update. Typically contains:

  - ``content`` (array): Full schema content array where each field can have a ``score_threshold`` property (float 0.0-1.0)

**Best Practices:**

- Use higher thresholds (0.95-0.98) for critical fields like amounts and IDs
- Use lower thresholds (0.80-0.90) for less critical fields

**Returns:**

.. code-block:: json

   {
     "id": "67890",
     "name": "Invoice Schema",
     "url": "https://elis.rossum.ai/api/v1/schemas/67890",
     "content": ["..."],
     "message": "Schema 'Invoice Schema' (ID 67890) updated successfully"
   }

patch_schema
^^^^^^^^^^^^

Patch a schema by adding, updating, or removing individual nodes without replacing the entire content.
This is particularly useful for making incremental changes to schemas.

**Parameters:**

- ``schema_id`` (integer, required): Schema ID to patch
- ``operation`` (string, required): One of "add", "update", or "remove"
- ``node_id`` (string, required): ID of the node to operate on
- ``node_data`` (object, optional): Data for add/update operations. Required for "add" and "update"
- ``parent_id`` (string, optional): Parent node ID for add operation. Required for "add"
- ``position`` (integer, optional): Position for add operation (appends if not specified)

**Operations:**

- **add**: Add a new datapoint/multivalue to a parent (section or tuple). Requires ``parent_id`` and ``node_data``.
- **update**: Update properties of an existing node. Requires ``node_data`` with fields to update.
- **remove**: Remove a node from the schema. Only ``node_id`` is required.

**Returns:**

.. code-block:: json

   {
     "id": 123,
     "name": "Invoice Schema",
     "content": [
       {
         "id": "header_section",
         "label": "Header",
         "category": "section",
         "children": [
           {"id": "invoice_number", "label": "Invoice Number", "category": "datapoint"},
           {"id": "vendor_name", "label": "Vendor Name", "category": "datapoint"}
         ]
       }
     ]
   }

**Example usage:**

.. code-block:: python

   # Add a new datapoint to a section
   patch_schema(
       schema_id=123,
       operation="add",
       node_id="vendor_name",
       parent_id="header_section",
       node_data={"label": "Vendor Name", "type": "string", "category": "datapoint"}
   )

   # Update a field's label and threshold
   patch_schema(
       schema_id=123,
       operation="update",
       node_id="invoice_number",
       node_data={"label": "Invoice #", "score_threshold": 0.9}
   )

   # Remove a field
   patch_schema(
       schema_id=123,
       operation="remove",
       node_id="old_field"
   )

update_engine
^^^^^^^^^^^^^

Updates an existing engine's settings including learning and training queues.

**Parameters:**

- ``engine_id`` (integer, required): Engine ID to update
- ``engine_data`` (object, required): Dictionary containing engine fields to update:

  - ``name`` (string): Engine name
  - ``description`` (string): Engine description
  - ``learning_enabled`` (boolean): Enable/disable learning
  - ``training_queues`` (array): List of queue URLs for training

**Example:**

.. code-block:: json

   {
     "learning_enabled": true,
     "training_queues": [
       "https://elis.rossum.ai/api/v1/queues/12345",
       "https://elis.rossum.ai/api/v1/queues/67890"
     ]
   }

**Returns:**

.. code-block:: json

   {
     "id": 12345,
     "name": "My Engine",
     "url": "https://elis.rossum.ai/api/v1/engines/12345",
     "type": "extractor",
     "learning_enabled": true,
     "training_queues": ["..."],
     "description": "Engine description",
     "message": "Engine 'My Engine' (ID 12345) updated successfully"
   }

create_schema
^^^^^^^^^^^^^

Creates a new schema with sections and datapoints.

**Parameters:**

- ``name`` (string, required): Schema name
- ``content`` (array, required): Schema content array containing sections with datapoints.
  Must follow Rossum schema structure with sections containing children.

**Example content structure:**

.. code-block:: json

   [
     {
       "category": "section",
       "id": "document_info",
       "label": "Document Information",
       "children": [
         {
           "category": "datapoint",
           "id": "document_type",
           "label": "Document Type",
           "type": "enum",
           "rir_field_names": [],
           "constraints": {"required": false},
           "options": [
             {"value": "invoice", "label": "Invoice"},
             {"value": "receipt", "label": "Receipt"}
           ]
         }
       ]
     }
   ]

**Returns:**

.. code-block:: json

   {
     "id": 12345,
     "name": "My Schema",
     "url": "https://elis.rossum.ai/api/v1/schemas/12345",
     "content": ["..."],
     "message": "Schema 'My Schema' created successfully with ID 12345"
   }

delete_schema
^^^^^^^^^^^^^

Deletes a schema. Schemas can only be deleted if they are not currently assigned to any queue.

**Parameters:**

- ``schema_id`` (integer, required): Schema ID to delete

**Returns:**

.. code-block:: json

   {
     "message": "Schema 12345 deleted successfully"
   }

**Note:** This operation is only available in read-write mode.

create_engine
^^^^^^^^^^^^^

Creates a new engine for document processing.

**Parameters:**

- ``name`` (string, required): Engine name
- ``organization_id`` (integer, required): Organization ID where the engine should be created
- ``engine_type`` (string, required): Engine type - either 'extractor' or 'splitter'

**Returns:**

.. code-block:: json

   {
     "id": 12345,
     "name": "My Engine",
     "url": "https://elis.rossum.ai/api/v1/engines/12345",
     "type": "extractor",
     "organization": "https://elis.rossum.ai/api/v1/organizations/123",
     "message": "Engine 'My Engine' created successfully with ID 12345"
   }

create_engine_field
^^^^^^^^^^^^^^^^^^^

Creates a new engine field and links it to schemas. Engine fields define what data the
engine extracts and must be created for each field in the schema when setting up an engine.

**Parameters:**

- ``engine_id`` (integer, required): Engine ID to which this field belongs
- ``name`` (string, required): Field name (slug format, max 50 chars)
- ``label`` (string, required): Human-readable label (max 100 chars)
- ``field_type`` (string, required): Field type - 'string', 'number', 'date', or 'enum'
- ``schema_ids`` (array, required): List of schema IDs to link this engine field to (at least one required)
- ``tabular`` (boolean, optional): Whether this field is in a table (default: false)
- ``multiline`` (string, optional): Multiline setting - 'true', 'false', or '' (default: 'false')
- ``subtype`` (string, optional): Optional field subtype (max 50 chars)
- ``pre_trained_field_id`` (string, optional): Optional pre-trained field ID (max 50 chars)

**Returns:**

.. code-block:: json

   {
     "id": 12345,
     "name": "invoice_number",
     "label": "Invoice Number",
     "url": "https://elis.rossum.ai/api/v1/engine_fields/12345",
     "type": "string",
     "engine": "https://elis.rossum.ai/api/v1/engines/123",
     "tabular": false,
     "multiline": "false",
     "schema_ids": [456, 789],
     "message": "Engine field 'Invoice Number' created successfully with ID 12345 and linked to 2 schema(s)"
   }

get_engine_fields
^^^^^^^^^^^^^^^^^

Retrieves engine fields for a specific engine or all engine fields.

**Parameters:**

- ``engine_id`` (integer, optional): Engine ID to filter fields by. If not provided, retrieves all engine fields.

**Returns:**

.. code-block:: json

   {
     "count": 2,
     "results": [
       {
         "id": 12345,
         "url": "https://elis.rossum.ai/api/v1/engine_fields/12345",
         "engine": "https://elis.rossum.ai/api/v1/engines/123",
         "name": "invoice_number",
         "label": "Invoice Number",
         "type": "string",
         "subtype": null,
         "tabular": false,
         "multiline": "false",
         "pre_trained_field_id": null,
         "schemas": ["https://elis.rossum.ai/api/v1/schemas/456"]
       },
       {
         "id": 12346,
         "url": "https://elis.rossum.ai/api/v1/engine_fields/12346",
         "engine": "https://elis.rossum.ai/api/v1/engines/123",
         "name": "invoice_date",
         "label": "Invoice Date",
         "type": "date",
         "subtype": null,
         "tabular": false,
         "multiline": "false",
         "pre_trained_field_id": null,
         "schemas": ["https://elis.rossum.ai/api/v1/schemas/456"]
       }
     ]
   }

**Example usage:**

.. code-block:: python

   # Get all engine fields for a specific engine
   engine_fields = get_engine_fields(engine_id=123)

   # Get all engine fields
   all_fields = get_engine_fields()

start_annotation
^^^^^^^^^^^^^^^^

Starts an annotation to move it from 'importing' to 'reviewing' status. This is required
before you can update annotation fields.

**Parameters:**

- ``annotation_id`` (integer, required): Rossum annotation ID to start

**Returns:**

.. code-block:: json

   {
     "annotation_id": 12345,
     "message": "Annotation 12345 started successfully. Status changed to 'reviewing'."
   }

bulk_update_annotation_fields
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Bulk update annotation field values using JSON Patch operations. This is the correct way
to update annotation field values. Must be called after ``start_annotation``.

**Parameters:**

- ``annotation_id`` (integer, required): Rossum annotation ID to update
- ``operations`` (array, required): List of JSON Patch operations with format:

  .. code-block:: json

     [
       {
         "op": "replace",
         "id": 1234,
         "value": {
           "content": {
             "value": "new_value",
             "page": 1,
             "position": [0, 0, 100, 50]
           }
         }
       }
     ]

**Important:** Use the numeric datapoint ``id`` from ``annotation.content``, NOT the ``schema_id``.

**Returns:**

.. code-block:: json

   {
     "annotation_id": 12345,
     "operations_count": 1,
     "message": "Annotation 12345 updated with 1 operations successfully."
   }

confirm_annotation
^^^^^^^^^^^^^^^^^^

Confirms an annotation to move it to 'confirmed' status. Can be called after
``bulk_update_annotation_fields``.

**Parameters:**

- ``annotation_id`` (integer, required): Rossum annotation ID to confirm

**Returns:**

.. code-block:: json

   {
     "annotation_id": 12345,
     "message": "Annotation 12345 confirmed successfully. Status changed to 'confirmed'."
   }

copy_annotations
^^^^^^^^^^^^^^^^

Copies one or more annotations to another queue. ``reimport=True`` re-extracts
data in the target queue (use when moving documents between queues).
``reimport=False`` (default) preserves original extracted data as-is.

**Parameters:**

- ``annotation_ids`` (array of integers, required): Annotation IDs to copy
- ``target_queue_id`` (integer, required): Target queue ID
- ``target_status`` (string, optional): Status of copied annotations (if not set, stays the same)
- ``reimport`` (boolean, optional): Whether to reimport (default: false)

**Returns:**

.. code-block:: json

   {
     "copied": 2,
     "failed": 0,
     "results": [
       {"annotation_id": 111, "copied_annotation": {"id": 99991, "status": "to_review"}},
       {"annotation_id": 222, "copied_annotation": {"id": 99992, "status": "to_review"}}
     ],
     "errors": []
   }

**Note:** This operation is only available in read-write mode.

delete_annotation
^^^^^^^^^^^^^^^^^

Deletes an annotation by moving it to 'deleted' status. The annotation is not
permanently removed but marked as deleted.

**Parameters:**

- ``annotation_id`` (integer, required): Rossum annotation ID to delete

**Returns:**

.. code-block:: json

   {
     "message": "Annotation 12345 deleted successfully"
   }

**Note:** This operation is only available in read-write mode.

create_hook
^^^^^^^^^^^

Creates a new hook (webhook or serverless function). Hooks respond to Rossum events and
can be used for custom validation, data enrichment, or integration with external systems.

**Parameters:**

- ``name`` (string, required): Hook name
- ``type`` (string, required): Hook type - either 'webhook' or 'function'
- ``queues`` (array, optional): List of queue URLs to attach the hook to. If not provided,
  hook applies to all queues. Format: ``["https://api.elis.rossum.ai/v1/queues/12345"]``
- ``events`` (array, optional): List of events that trigger the hook. Common events:

  - ``annotation_content.initialize`` - When annotation is first created
  - ``annotation_content.confirm`` - When annotation is confirmed
  - ``annotation_content.export`` - When annotation is exported
  - ``annotation_status`` - When annotation status changes
  - ``annotation_content`` - When annotation content changes
  - ``datapoint_value`` - When individual field value changes

- ``config`` (object, optional): Hook configuration

  - For webhook: ``{"url": "https://example.com/webhook"}``
  - For function: ``{"runtime": "python3.12", "function": "import json\ndef rossum_hook_request_handler(payload):\n    return {}"}``

- ``settings`` (object, optional): Specific settings included in the payload when executing the hook
- ``secret`` (string, optional): Secret key for securing webhook requests

**Returns:**

.. code-block:: json

   {
     "id": 12345,
     "name": "My Hook",
     "url": "https://elis.rossum.ai/api/v1/hooks/12345",
     "enabled": true,
     "queues": ["https://elis.rossum.ai/api/v1/queues/100"],
     "events": ["annotation_content.initialize"],
     "config": {"runtime": "python3.12", "function": "..."},
     "settings": {"custom_key": "custom_value"},
     "message": "Hook 'My Hook' created successfully with ID 12345"
   }

update_hook
^^^^^^^^^^^

Updates an existing hook. Use this to modify hook properties like name, queues, events, config,
settings, or active status. Only provide the fields you want to change - other fields will remain unchanged.

**Parameters:**

- ``hook_id`` (integer, required): ID of the hook to update
- ``name`` (string, optional): New name for the hook
- ``queues`` (array, optional): List of queue URLs to attach the hook to
- ``events`` (array, optional): List of events that trigger the hook
- ``config`` (object, optional): Hook configuration
- ``settings`` (object, optional): Hook settings
- ``active`` (boolean, optional): Whether the hook is active

**Returns:**

.. code-block:: json

   {
     "id": 12345,
     "name": "Updated Hook Name",
     "url": "https://elis.rossum.ai/api/v1/hooks/12345",
     "active": true,
     "queues": ["https://elis.rossum.ai/api/v1/queues/100"],
     "events": ["annotation_content.initialize"],
     "config": {"runtime": "python3.12", "function": "..."},
     "settings": {}
   }

**Example usage:**

.. code-block:: python

   # Rename a hook
   update_hook(hook_id=12345, name="New Hook Name")

   # Deactivate a hook
   update_hook(hook_id=12345, active=False)

   # Change hook events
   update_hook(hook_id=12345, events=["annotation_content.confirm"])

create_hook_from_template
^^^^^^^^^^^^^^^^^^^^^^^^^

Creates a hook from a Rossum Store template. Use ``search(query={"entity": "hook_template"})``
first to find available templates and their IDs. This is the recommended way to create hooks as it
uses battle-tested configurations from the Rossum Store.

**Parameters:**

- ``name`` (string, required): Name for the new hook
- ``hook_template_id`` (integer, required): ID of the hook template to use (from ``search(query={"entity": "hook_template"})``)
- ``queues`` (array, required): List of queue URLs to attach the hook to
- ``events`` (array, optional): List of events to trigger the hook (overrides template defaults if provided)
- ``token_owner`` (string, optional but required for some templates): User URL to use as token owner when the template has ``use_token_owner=True``. Obtain this via ``search(query={"entity": "user", ...})``.

**Returns:**

.. code-block:: json

   {
     "id": 12345,
     "name": "My Document Splitting Hook",
     "url": "https://elis.rossum.ai/api/v1/hooks/12345",
     "hook_template": "https://elis.rossum.ai/api/v1/hook_templates/5",
     "type": "function",
     "queues": ["https://elis.rossum.ai/api/v1/queues/100"],
     "events": ["annotation_content.initialize"],
     "config": {},
     "settings": {}
   }

**Example usage:**

.. code-block:: python

   # Create a hook from template
   create_hook_from_template(
       name="Invoice Splitting",
       hook_template_id=5,
       queues=["https://api.elis.rossum.ai/v1/queues/12345"],
       token_owner="https://api.elis.rossum.ai/v1/users/12345"
   )

delete_hook
^^^^^^^^^^^

Deletes a hook/extension.

**Parameters:**

- ``hook_id`` (integer, required): Hook ID to delete

**Returns:**

.. code-block:: json

   {
     "message": "Hook 12345 deleted successfully"
   }

**Note:** This operation is only available in read-write mode.

create_rule
^^^^^^^^^^^

Creates a new business rule. Rules automate field operations based on trigger conditions.

**Parameters:**

- ``name`` (string, required): Rule name
- ``trigger_condition`` (string, required): TxScript formula (e.g., ``"field.amount > 10000"``)
- ``actions`` (array, required): List of actions with required fields: ``id`` (unique string), ``type``, ``event``, ``payload``
- ``enabled`` (boolean, optional): Whether the rule is enabled (default: true)
- ``schema_id`` (integer, optional): Schema ID to associate the rule with (at least one of ``schema_id`` or ``queue_ids`` required)
- ``queue_ids`` (array of integers, optional): List of queue IDs to limit the rule to specific queues

**Action types:** ``show_message``, ``add_automation_blocker``, ``add_validation_source``, ``change_queue``, ``send_email``, ``hide_field``, ``show_field``, ``show_hide_field``, ``change_status``, ``add_label``, ``remove_label``, ``custom``

**Event:** ``validation``

**Returns:**

.. code-block:: json

   {
     "id": 67890,
     "name": "High Value Alert",
     "url": "https://elis.rossum.ai/api/v1/rules/67890",
     "schema": "https://elis.rossum.ai/api/v1/schemas/12345",
     "trigger_condition": "field.amount > 10000",
     "actions": [{"id": "alert1", "type": "show_message", "event": "validation", "payload": {"type": "error", "content": "High value invoice", "schema_id": "amount"}}],
     "enabled": true
   }

**Example usage:**

.. code-block:: python

   # Create a simple validation rule
   rule = create_rule(
       name="High Value Alert",
       trigger_condition="field.amount > 10000",
       actions=[{"id": "alert1", "type": "show_message", "event": "validation", "payload": {"type": "error", "content": "High value invoice", "schema_id": "amount"}}],
       schema_id=12345
   )

**Note:** This operation is only available in read-write mode.

update_rule
^^^^^^^^^^^

Full update (PUT) of a business rule. All fields are required.

**Parameters:**

- ``rule_id`` (integer, required): Rule ID to update
- ``name`` (string, required): Rule name
- ``trigger_condition`` (string, required): TxScript formula
- ``actions`` (array, required): List of actions
- ``enabled`` (boolean, required): Whether the rule is enabled
- ``queue_ids`` (array of integers, optional): List of queue IDs to limit the rule to specific queues

**Returns:**

.. code-block:: json

   {
     "id": 67890,
     "name": "Updated Rule",
     "url": "https://elis.rossum.ai/api/v1/rules/67890",
     "schema": "https://elis.rossum.ai/api/v1/schemas/12345",
     "trigger_condition": "field.amount > 5000",
     "actions": ["..."],
     "enabled": true
   }

**Example usage:**

.. code-block:: python

   # Full update of a rule
   rule = update_rule(
       rule_id=67890,
       name="Updated High Value Alert",
       trigger_condition="field.amount > 5000",
       actions=[{"id": "alert1", "type": "show_message", "event": "validation", "payload": {"type": "warning", "content": "Check value", "schema_id": "amount"}}],
       enabled=True
   )

**Note:** This operation is only available in read-write mode.

patch_rule
^^^^^^^^^^

Partial update (PATCH) of a business rule. Only provided fields are updated.

**Parameters:**

- ``rule_id`` (integer, required): Rule ID to update
- ``name`` (string, optional): Rule name
- ``trigger_condition`` (string, optional): TxScript formula
- ``actions`` (array, optional): List of actions
- ``enabled`` (boolean, optional): Whether the rule is enabled
- ``queue_ids`` (array of integers, optional): List of queue IDs (empty list removes all queue associations)

**Returns:**

.. code-block:: json

   {
     "id": 67890,
     "name": "Patched Rule",
     "enabled": false
   }

**Example usage:**

.. code-block:: python

   # Disable a rule
   rule = patch_rule(rule_id=67890, enabled=False)

   # Update only the name
   rule = patch_rule(rule_id=67890, name="New Rule Name")

**Note:** This operation is only available in read-write mode.

delete_rule
^^^^^^^^^^^

Deletes a business rule.

**Parameters:**

- ``rule_id`` (integer, required): Rule ID to delete

**Returns:**

.. code-block:: json

   {
     "message": "Rule 12345 deleted successfully"
   }

**Note:** This operation is only available in read-write mode.

Workspace Management
--------------------

create_workspace
^^^^^^^^^^^^^^^^

Creates a new workspace in an organization.

**Parameters:**

- ``name`` (string, required): Workspace name
- ``organization_id`` (integer, required): Organization ID where the workspace should be created

**Returns:**

.. code-block:: json

   {
     "id": 12345,
     "name": "My New Workspace",
     "url": "https://elis.rossum.ai/api/v1/workspaces/12345",
     "organization": "https://elis.rossum.ai/api/v1/organizations/100",
     "message": "Workspace 'My New Workspace' created successfully with ID 12345"
   }

delete_workspace
^^^^^^^^^^^^^^^^

Deletes a workspace. The workspace must be empty (no queues) before deletion.

**Parameters:**

- ``workspace_id`` (integer, required): Workspace ID to delete

**Returns:**

.. code-block:: json

   {
     "message": "Workspace 12345 deleted successfully"
   }

**Note:** This operation is only available in read-write mode.

User Management
---------------

create_user
^^^^^^^^^^^

Creates a new user in the organization.

**Parameters:** See API documentation for full parameter list.

update_user
^^^^^^^^^^^

Updates an existing user's properties.

**Parameters:** See API documentation for full parameter list.

Email Template Tools
^^^^^^^^^^^^^^^^^^^^

create_email_template
"""""""""""""""""""""

Creates a new email template. Templates can be automated to send emails automatically
on specific triggers, or manual for user-initiated sending.

**Parameters:**

- ``name`` (string, required): Name of the email template
- ``queue`` (string, required): URL of the queue to associate with
- ``subject`` (string, required): Email subject line
- ``message`` (string, required): Email body (HTML supported)
- ``type`` (string, optional): Template type - 'rejection', 'rejection_default',
  'email_with_no_processable_attachments', 'custom' (default: 'custom')
- ``automate`` (boolean, optional): If true, email is sent automatically on trigger (default: false)
- ``to`` (array, optional): List of recipient objects with 'type' and 'value' keys
- ``cc`` (array, optional): List of CC recipient objects
- ``bcc`` (array, optional): List of BCC recipient objects
- ``triggers`` (array, optional): List of trigger URLs

**Recipient object types:**

- ``{"type": "annotator", "value": ""}`` - Send to the document annotator
- ``{"type": "constant", "value": "email@example.com"}`` - Send to a fixed email address
- ``{"type": "datapoint", "value": "email_field_id"}`` - Send to email from a datapoint field

**Returns:**

.. code-block:: json

   {
     "id": 1502,
     "name": "Custom Notification",
     "url": "https://elis.rossum.ai/api/v1/email_templates/1502",
     "queue": "https://elis.rossum.ai/api/v1/queues/8199",
     "subject": "Document Processed",
     "message": "<p>Your document has been processed.</p>",
     "type": "custom",
     "automate": true,
     "to": [{"type": "constant", "value": "notifications@example.com"}]
   }

**Example usage:**

.. code-block:: python

   # Create a simple custom email template
   template = create_email_template(
       name="Processing Complete",
       queue="https://elis.rossum.ai/api/v1/queues/8199",
       subject="Document Processing Complete",
       message="<p>Your document has been successfully processed.</p>"
   )

   # Create an automated rejection template
   template = create_email_template(
       name="Auto Rejection",
       queue="https://elis.rossum.ai/api/v1/queues/8199",
       subject="Document Rejected",
       message="<p>Your document could not be processed.</p>",
       type="rejection",
       automate=True,
       to=[{"type": "annotator", "value": ""}]
   )

   # Create template with multiple recipients
   template = create_email_template(
       name="Team Notification",
       queue="https://elis.rossum.ai/api/v1/queues/8199",
       subject="New Document",
       message="<p>A new document has arrived.</p>",
       to=[{"type": "constant", "value": "team@example.com"}],
       cc=[{"type": "datapoint", "value": "sender_email"}]
   )

Agent Tools
-----------

The ``rossum_agent`` package provides additional tools beyond the MCP server.

File System Tools
^^^^^^^^^^^^^^^^^

write_file
""""""""""

Write content to a file in the agent's output directory.

Use this tool to save analysis results, export data, or create reports.
Files are saved to a session-specific directory that can be shared with the user.

**Parameters:**

- ``filename`` (string, required): The name of the file to write (e.g., 'report.md', 'analysis.json')
- ``content`` (string, required): The content to write to the file

**Returns:**

.. code-block:: json

   {
     "status": "success",
     "message": "Successfully wrote 1234 characters to report.md",
     "path": "/path/to/outputs/report.md"
   }

Document Testing Tools
^^^^^^^^^^^^^^^^^^^^^^

generate_mock_pdf
"""""""""""""""""

Generate a mock PDF document with realistic values matching schema fields.

Use for end-to-end extraction testing: generate PDF → upload → verify extracted values match expected.

**Parameters:**

- ``fields`` (list[dict], required): Schema field descriptors: ``[{id, label, type, rir_field_names?, options?}]``. Extract from schema content (sections → datapoints, multivalues → tuples).
- ``document_type`` (string, optional): ``invoice``, ``purchase_order``, ``receipt``, ``delivery_note``, ``credit_note``. Default: ``invoice``.
- ``line_item_count`` (int, optional): Number of line item rows to generate. Default: 3.
- ``overrides`` (dict[str, str], optional): Force specific field values: ``{field_id: value}``.
- ``filename`` (string, optional): Output filename (auto-generated if omitted).

**Returns:**

.. code-block:: json

   {
     "status": "success",
     "file_path": "/path/to/mock.pdf",
     "expected_values": {"invoice_id": "INV-2026-00142", "date_issue": "2026-02-10"},
     "line_items": [{"item_description": "Office supplies", "item_amount_total": "150.00"}]
   }

Lookup Field Tools
^^^^^^^^^^^^^^^^^^

suggest_lookup_field
""""""""""""""""""""

Suggest matching configuration for a lookup field backed by Master Data Hub dataset.

**Parameters:**

- ``label`` (string, required): Field label.
- ``hint`` (string, required): Matching intent and constraints.
- ``schema_id`` (int, required): Target schema ID.
- ``section_id`` (string, required): Section where the field belongs.
- ``field_schema_id`` (string, optional): Field ID override.
- ``dataset`` (string, optional): Dataset name or identifier.

evaluate_lookup_field
"""""""""""""""""""""

Evaluate lookup field values on one or more annotations.

**Parameters:**

- ``schema_id`` (int, required): Schema containing lookup field.
- ``annotation_urls`` (list[str], required): Annotation URLs or paths (e.g., ``['/api/v1/annotations/123456']``).

get_lookup_dataset_raw_values
"""""""""""""""""""""""""""""

Fetch raw rows from a Master Data Hub dataset for unmatched/ambiguous lookup result verification.

**Parameters:**

- ``dataset`` (string, required): Dataset name or identifier.
- ``limit`` (int, optional): Maximum rows to fetch (default ``10000``).

**Returns:**

.. code-block:: json

   {
     "status": "success",
     "dataset": "imported-0d652b68-fd8b-4fc8-9cee-d39105b1304b",
     "limit": 10000,
     "row_count": 2,
     "note": "Dataset cached. Use query_lookup_dataset to explore rows."
   }

query_lookup_dataset
""""""""""""""""""""

Run a jq query on a previously downloaded MDH dataset. The dataset must be fetched first with ``get_lookup_dataset_raw_values``.

**Parameters:**

- ``dataset`` (string, required): Dataset name or identifier (same as used in ``get_lookup_dataset_raw_values``).
- ``jq_query`` (string, required): A jq query string. The cached data is always a flat array of row objects — query with ``.[0] | keys`` to discover columns, ``.[]``, ``.[0]``, etc.

Knowledge Base Tools
^^^^^^^^^^^^^^^^^^^^

The Knowledge Base tools provide access to pre-scraped Rossum documentation articles. Articles are cached locally (24-hour TTL) from an S3-hosted JSON file.

kb_grep
"""""""

Search Knowledge Base article titles and content by keyword or regex.

Use to discover relevant articles when you don't know the exact slug.

**Parameters:**

- ``pattern`` (string, required): Text pattern to search for (supports regex).
  Examples: ``"document splitting"``, ``"webhook"``, ``"email_template"``, ``"formula"``.
- ``case_insensitive`` (bool, optional): Whether to ignore case (default: ``true``).

**Returns:**

.. code-block:: json

   {
     "status": "success",
     "matches": 3,
     "result": [
       {
         "slug": "document-splitting-extension",
         "title": "Document Splitting Extension",
         "url": "https://knowledge-base.rossum.ai/docs/document-splitting-extension",
         "snippet": "[title] Document Splitting Extension\n[content] ...split documents into multiple pages..."
       }
     ]
   }

kb_get_article
""""""""""""""

Retrieve a full Knowledge Base article by its slug.

Use after ``kb_grep`` to read the complete content of a specific article.

**Parameters:**

- ``slug`` (string, required): Article slug (e.g. ``"document-splitting-extension"``). Partial match supported.

**Returns:**

.. code-block:: json

   {
     "status": "success",
     "slug": "document-splitting-extension",
     "title": "Document Splitting Extension",
     "url": "https://knowledge-base.rossum.ai/docs/document-splitting-extension",
     "content": "# Document Splitting Extension\n\nSplit documents into multiple pages..."
   }

search_knowledge_base
"""""""""""""""""""""

Search the Rossum Knowledge Base using an Opus sub-agent for complex questions requiring multiple lookups.

The sub-agent iterates through pre-scraped KB articles using ``kb_grep`` and ``kb_get_article`` to find comprehensive answers. Use for complex questions; for quick lookups, use ``kb_grep`` and ``kb_get_article`` directly.

**Parameters:**

- ``query`` (string, required): Search query. Be specific - include extension names, error messages,
  or feature names. Examples: 'document splitting extension', 'duplicate handling configuration',
  'webhook timeout error'.
- ``user_query`` (string, optional): The original user question for context. Pass the user's full
  question here so the sub-agent can tailor the analysis to address their specific needs.

**Returns:**

.. code-block:: json

   {
     "status": "success",
     "answer": "## Document Splitting Extension\n\nThe document splitting extension...",
     "iterations": 2,
     "input_tokens": 1500,
     "output_tokens": 800,
     "searches": [{"tool": "kb_grep", "input": {"pattern": "splitting"}}]
   }

Hook Testing Tools (MCP)
^^^^^^^^^^^^^^^^^^^^^^^^

Hook testing uses the native Rossum API endpoint via the ``test_hook`` MCP tool.

test_hook
"""""""""

Test a hook by generating a payload from the given event/action and sending it directly.
Returns hook response and logs.

**Parameters:**

- ``hook_id`` (int, required): The hook ID.
- ``event`` (HookEvent, required): Hook event (e.g. ``annotation_content``, ``upload``).
- ``action`` (HookAction, required): Hook action (e.g. ``initialize``, ``export``).
- ``annotation`` (string, optional): Annotation URL to use real data.
- ``status`` (string, optional): Annotation status.
- ``previous_status`` (string, optional): Previous annotation status.
- ``config`` (dict, optional): Config override for the test run.

**Returns:** Dict with hook response and execution logs.

Multi-Environment Tools
^^^^^^^^^^^^^^^^^^^^^^^

spawn_mcp_connection
""""""""""""""""""""

Spawn a new MCP connection to a different Rossum environment.

Use this when you need to make changes to a different Rossum environment than the one
the agent was initialized with. For example, when deploying changes from source to target.

**Parameters:**

- ``connection_id`` (string, required): A unique identifier for this connection (e.g., 'target', 'sandbox')
- ``api_token`` (string, required): API token for the target environment
- ``api_base_url`` (string, required): API base URL for the target environment
- ``mcp_mode`` (string, optional): "read-only" or "read-write" (default: "read-write")

**Returns:**

Success message with list of available tools on the spawned connection.

call_on_connection
""""""""""""""""""

Call a tool on a spawned MCP connection.

Use this to execute MCP tools on a connection that was previously spawned with ``spawn_mcp_connection``.

**Parameters:**

- ``connection_id`` (string, required): The identifier of the spawned connection
- ``tool_name`` (string, required): The name of the MCP tool to call
- ``arguments`` (string, required): JSON string of arguments to pass to the tool

**Returns:**

The result of the tool call as a JSON string.

close_connection
""""""""""""""""

Close a spawned MCP connection.

**Parameters:**

- ``connection_id`` (string, required): The connection to close

**Returns:**

Success or error message.

User Interaction Tools
^^^^^^^^^^^^^^^^^^^^^^

ask_user_question
"""""""""""""""""

Ask the user one or more structured questions mid-execution. Supports free-text input and multiple-choice selectors. Streamed to the frontend via SSE ``agent_question`` event.

Use when you need required information that you cannot determine on your own (e.g. queue name, template choice, workspace ID), or when the user explicitly asks for confirmation before proceeding.

**Parameters (single question):**

- ``question`` (string): The question text.
- ``options`` (list[object], optional): Choices with ``value``, ``label``, and optional ``description`` (max 90 chars). Omit for free-text.
- ``multi_select`` (bool, optional): Allow multiple selections. Default: ``false``.

**Parameters (multiple questions):**

- ``questions`` (list[object]): Array of question objects, each with ``question``, optional ``options``, and optional ``multi_select``. Presented to the user one at a time.

**Returns:**

.. code-block:: json

   {
     "status": "question_sent",
     "question_count": 1,
     "question": "Which queue template should I use?",
     "option_count": 3
   }

Skills Tools
^^^^^^^^^^^^

load_skill
""""""""""

Load a specialized skill that provides domain-specific instructions and workflows.

Use this tool when you recognize that a task matches one of the available skills.
The skill will provide detailed instructions, workflows, and context for the task.

**Parameters:**

- ``name`` (string, required): The name of the skill to load (e.g., "rossum-deployment", "txscript")

**Returns:**

.. code-block:: json

   {
     "status": "success",
     "skill_name": "rossum-deployment",
     "instructions": "## Rossum Deployment Workflow\n\n..."
   }

Agent Deployment Tools
^^^^^^^^^^^^^^^^^^^^^^

The agent includes deployment tools that wrap the ``rossum_deploy`` package for use within agent conversations.

deploy_pull
"""""""""""

Pull Rossum configuration objects from an organization to local files.

**Parameters:**

- ``org_id`` (int, required): Organization ID to pull from
- ``workspace_path`` (string, optional): Path to workspace directory
- ``api_base_url`` (string, optional): API base URL for target environment
- ``token`` (string, optional): API token for target environment

deploy_diff
"""""""""""

Compare local workspace files with remote Rossum configuration.

**Parameters:**

- ``workspace_path`` (string, optional): Path to workspace directory

deploy_push
"""""""""""

Push local changes to Rossum.

**Parameters:**

- ``dry_run`` (bool, optional): Only show what would be pushed
- ``force`` (bool, optional): Push even if there are conflicts
- ``workspace_path`` (string, optional): Path to workspace directory

deploy_copy_org
"""""""""""""""

Copy all objects from source organization to target organization.

**Parameters:**

- ``source_org_id`` (int, required): Source organization ID
- ``target_org_id`` (int, required): Target organization ID
- ``target_api_base`` (string, optional): Target API base URL
- ``target_token`` (string, optional): Target API token
- ``workspace_path`` (string, optional): Path to workspace directory

deploy_copy_workspace
"""""""""""""""""""""

Copy a single workspace and all its objects to target organization.

**Parameters:**

- ``source_workspace_id`` (int, required): Source workspace ID
- ``target_org_id`` (int, required): Target organization ID
- ``target_api_base`` (string, optional): Target API base URL
- ``target_token`` (string, optional): Target API token
- ``workspace_path`` (string, optional): Path to workspace directory

deploy_compare_workspaces
"""""""""""""""""""""""""

Compare two local workspaces to see differences between source and target.

**Parameters:**

- ``source_workspace_path`` (string, required): Path to source workspace
- ``target_workspace_path`` (string, required): Path to target workspace
- ``id_mapping_path`` (string, optional): Path to ID mapping JSON from copy operations

deploy_to_org
"""""""""""""

Deploy local configuration changes to a target organization.

**Parameters:**

- ``target_org_id`` (int, required): Target organization ID
- ``target_api_base`` (string, optional): Target API base URL
- ``target_token`` (string, optional): Target API token
- ``dry_run`` (bool, optional): Only show what would be deployed
- ``workspace_path`` (string, optional): Path to workspace directory

Deployment Tools
----------------

The ``rossum_deploy`` package provides lightweight configuration deployment capabilities.
This is a minimalistic alternative to `deployment-manager (PRD2) <https://github.com/rossumai/deployment-manager>`_.

Workspace
^^^^^^^^^

The ``Workspace`` class is the main entry point for deployment operations.

.. code-block:: python

   from rossum_deploy import Workspace

   # Initialize workspace
   ws = Workspace(
       "./my-project",
       api_base="https://api.elis.rossum.ai/v1",
       token="your-token"
   )

   # Pull all objects from an organization
   result = ws.pull(org_id=123456)
   print(result.summary())

   # Show diff between local and remote
   diff = ws.diff()
   print(diff.summary())

   # Push changes (dry run first)
   result = ws.push(dry_run=True)
   print(result.summary())

   # Push for real
   result = ws.push(confirm=True)
   print(result.summary())

pull
^^^^

Pull objects from Rossum to local workspace.

**Parameters:**

- ``org_id`` (integer, optional): Organization ID to pull from
- ``types`` (list, optional): Object types to pull (default: all)

**Returns:**

``PullResult`` with summary of pulled objects.

.. code-block:: python

   # Pull all objects
   result = ws.pull(org_id=123456)

   # Pull specific types only
   from rossum_deploy import ObjectType
   result = ws.pull(org_id=123456, types=[ObjectType.QUEUE, ObjectType.HOOK])

diff
^^^^

Compare local workspace with remote Rossum.

**Returns:**

``DiffResult`` with status of each object (unchanged, local_modified, remote_modified, conflict).

.. code-block:: python

   diff = ws.diff()
   print(diff.summary())
   # Output:
   # # Diff Summary
   # - Unchanged: 10
   # - Local modified: 2
   # - Remote modified: 0
   # - Conflicts: 0

push
^^^^

Push local changes to Rossum.

**Parameters:**

- ``dry_run`` (boolean): If True, only show what would be pushed
- ``confirm`` (boolean): Must be True to actually push (safety mechanism)
- ``force`` (boolean): If True, push even if there are conflicts

**Returns:**

``PushResult`` with summary of pushed objects.

.. code-block:: python

   # Dry run first
   result = ws.push(dry_run=True)
   print(result.summary())

   # Push for real
   result = ws.push(confirm=True)

   # Force push (override conflicts)
   result = ws.push(confirm=True, force=True)

CLI Usage
^^^^^^^^^

Set environment variables:

.. code-block:: bash

   export ROSSUM_API_BASE_URL="https://api.elis.rossum.ai/v1"
   export ROSSUM_API_TOKEN="your-token"

Commands:

.. code-block:: bash

   # Pull from organization
   rossum-deploy pull 123456

   # Show diff
   rossum-deploy diff

   # Push (dry run)
   rossum-deploy push --dry-run

   # Push for real
   rossum-deploy push

Comparison with deployment-manager
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

For complex deployments across multiple organizations, attribute overrides, and GIT-based
workflow tracking, use `deployment-manager (PRD2) <https://github.com/rossumai/deployment-manager>`_.

``rossum_deploy`` is designed for:

- Simple pull/push workflows within an AI agent
- Minimal dependency footprint
- Programmatic Python-first access
