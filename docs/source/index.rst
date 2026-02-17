Rossum MCP Server Documentation
=================================

.. toctree::
   :maxdepth: 2
   :caption: Getting Started:

   installation
   usage
   workflow

.. toctree::
   :maxdepth: 2
   :caption: Reference:

   api
   mcp_reference
   skills_and_subagents

.. toctree::
   :maxdepth: 2
   :caption: Examples:

   examples

Welcome to Rossum MCP Server
-----------------------------

**AI-powered Rossum orchestration: Document workflows conversationally, debug pipelines automatically, and configure automation through natural language.**

A Model Context Protocol (MCP) server and AI agent toolkit for the Rossum intelligent document processing platform. Transforms complex workflow setup, debugging, and configuration into natural language conversations.

Built with Python and the official `rossum-api <https://github.com/rossumai/rossum-api>`_.

Vision & Roadmap
----------------

This project enables three progressive levels of AI-powered Rossum orchestration:

1. **📝 Workflow Documentation** *(Current Focus)* - Conversationally document Rossum setups, analyze existing workflows, and generate comprehensive configuration reports through natural language prompts
2. **🔍 Automated Debugging** *(In Progress)* - Automatically diagnose pipeline issues, identify misconfigured hooks, detect schema problems, and suggest fixes through intelligent analysis
3. **🤖 Agentic Configuration** *(Planned)* - Fully autonomous setup and optimization of Rossum workflows - from queue creation to engine training to hook deployment - guided only by high-level business requirements

Features
--------

The MCP server provides **68 tools** organized into twelve categories:

**Document Processing**

* **upload_document** - Upload documents for AI extraction
* **get_annotation** - Retrieve extracted data and status
* **list_annotations** - List all annotations with filtering
* **start_annotation** - Start annotation for field updates
* **bulk_update_annotation_fields** - Update field values with JSON Patch
* **confirm_annotation** - Confirm and finalize annotations
* **copy_annotations** - Copy annotations to another queue

**Queue Management**

* **get_queue** - Retrieve queue details
* **list_queues** - List queues with optional filtering
* **get_queue_schema** - Retrieve queue schema in one call
* **get_queue_engine** - Get engine information
* **create_queue** - Create new queues
* **create_queue_from_template** - Create queues from predefined templates (EU/US/UK/CZ/CN)
* **get_queue_template_names** - List available queue template names
* **update_queue** - Configure automation thresholds

**Schema Management**

* **get_schema** - Retrieve schema details
* **list_schemas** - List schemas with optional filtering
* **create_schema** - Create new schemas
* **update_schema** - Configure field-level thresholds
* **patch_schema** - Add, update, or remove individual schema nodes
* **get_schema_tree_structure** - Get lightweight tree structure of schema
* **prune_schema_fields** - Remove multiple fields from schema at once

**Workspace Management**

* **get_workspace** - Retrieve workspace details by ID
* **list_workspaces** - List all workspaces with optional filtering
* **create_workspace** - Create a new workspace

**Organization Groups**

* **get_organization_group** - Retrieve organization group (license) details by ID
* **list_organization_groups** - List organization groups with optional name filter

**Organization Limits**

* **get_organization_limit** - Retrieve email sending limits and usage counters for an organization

**User Management**

* **get_user** - Retrieve user details by ID
* **list_users** - List users with filtering (for finding user URLs for token_owner)
* **list_user_roles** - List all user roles (permission groups) in the organization

**Engine Management**

* **get_engine** - Retrieve a single engine by ID
* **list_engines** - List all engines with optional filters
* **create_engine** - Create extraction or splitting engines
* **update_engine** - Configure learning and training queues
* **create_engine_field** - Define engine fields and link to schemas
* **get_engine_fields** - Retrieve engine fields for a specific engine or all fields

**Extensions (Hooks)**

* **get_hook** - Get hook/extension details
* **list_hooks** - List webhooks and extensions
* **create_hook** - Create webhooks or serverless function hooks
* **update_hook** - Update hook properties (name, queues, events, config, settings, active)
* **list_hook_templates** - List available hook templates from Rossum Store
* **create_hook_from_template** - Create hooks from pre-built templates
* **list_hook_logs** - List hook execution logs for debugging and monitoring
* **delete_hook** - Delete a hook/extension

**Rules & Actions**

* **get_rule** - Get business rule details
* **list_rules** - List business rules with trigger conditions and actions
* **create_rule** - Create business rules with trigger conditions and actions
* **update_rule** - Full update of business rules (PUT)
* **patch_rule** - Partial update of business rules (PATCH)
* **delete_rule** - Delete a business rule

**Relations Management**

* **get_relation** - Retrieve relation details by ID
* **list_relations** - List all relations between annotations (edit, attachment, duplicate)
* **get_document_relation** - Retrieve document relation details by ID
* **list_document_relations** - List all document relations (export, einvoice)

**Email Templates**

* **get_email_template** - Retrieve email template details
* **list_email_templates** - List email templates with optional filtering
* **create_email_template** - Create new email templates

**Deployment Toolkit**

The ``rossum_deploy`` package provides configuration deployment:

* Pull configurations from Rossum organizations to local files
* Diff local vs remote configurations
* Push changes back to Rossum (with dry-run support)
* Cross-organization deployment with ID mapping
* Workspace comparison for safe agent workflows

**AI Agent Toolkit**

The ``rossum_agent`` package provides additional capabilities:

* Formula field suggestions via Rossum Local Copilot integration
* Elis API OpenAPI search via jq queries and free-text grep with sub-agent analysis
* Knowledge Base search with direct regex tools (``kb_grep``, ``kb_get_article``) and Opus-powered sub-agent analysis
* Hook testing via native Rossum API endpoints
* Deployment tools for pull/push/diff of Rossum configurations across environments
* Multi-environment support with spawnable MCP connections
* Skills system for domain-specific workflows (deployment, TxScript, formula fields, reasoning fields)
* File output for saving reports, documentation, and analysis results
* Integration with AI agent frameworks (Anthropic Claude via AWS Bedrock)
* REST API interface
* See the :doc:`examples` section for complete workflows

**Deployment Tools**

The ``rossum_deploy`` package provides lightweight deployment capabilities:

* Pull/diff/push workflow for Rossum configurations
* Support for Workspace, Queue, Schema, Hook, and Inbox objects
* Conflict detection when both local and remote have changed
* Python-first API designed for agent integration
* Lightweight alternative to `deployment-manager (PRD2) <https://github.com/rossumai/deployment-manager>`_

Quick Start
-----------

**Prerequisites:** Python 3.12+, Rossum account with API credentials

.. code-block:: bash

   git clone https://github.com/stancld/rossum-agents.git
   cd rossum-mcp

   # Install both packages with all features
   uv sync --extra all --no-install-project

   # Set up environment variables
   export ROSSUM_API_TOKEN="your-api-token"
   export ROSSUM_API_BASE_URL="https://api.elis.rossum.ai/v1"
   export ROSSUM_MCP_MODE="read-write"  # Optional: "read-only" or "read-write" (default)

Run the MCP server:

.. code-block:: bash

   rossum-mcp

Run the AI agent:

.. code-block:: bash

   # CLI interface
   rossum-agent

   # Or run with Docker Compose
   docker-compose up rossum-agent

For detailed installation options, see :doc:`installation`

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
