# Rossum Agents API Skill

**Goal**: Delegate Rossum document-processing tasks to the Rossum Agent — an Opus 4.6-powered expert with full access to the Rossum platform.

## Prerequisites

Three environment variables must be set. If any are missing, ask the user.

| Variable | Purpose | Example |
|----------|---------|---------|
| `ROSSUM_AGENT_API_URL` | Agent API endpoint | `https://agent.rossum.app` |
| `ROSSUM_API_BASE_URL` | Rossum API URL | `https://elis.rossum.ai/api/v1` |
| `ROSSUM_API_TOKEN` | Authentication token | (from user) |

Install the CLI if not available: `uv pip install rossum-agent-client`

## Usage

Send natural-language prompts to the Rossum Agent via `rossum-agent-client`. The agent understands the Rossum platform deeply and figures out the steps itself.

```bash
# Read-only query (default)
rossum-agent-client -x "List all queues with their IDs and names"

# Write operation — requires --mcp-mode read-write
rossum-agent-client --mcp-mode read-write -x "Add a required string field 'tax_id' to the schema on queue 12345"

# Complex prompt from file
rossum-agent-client -r /tmp/rossum-task.md

# Cautious mode — agent confirms before making changes
rossum-agent-client --mcp-mode read-write --persona cautious -x "Delete the 'obsolete_field' from queue 12345 schema"
```

### CLI Flags

| Flag | Purpose | Default |
|------|---------|---------|
| `-x PROMPT` | Execute prompt directly | — |
| `-r FILE` | Read prompt from file | — |
| `--mcp-mode` | `read-only` or `read-write` | `read-only` |
| `--persona` | `default` or `cautious` | `default` |
| `--show-thinking` | Show reasoning + tool calls on stderr | off |

### Output

| Stream | Content |
|--------|---------|
| **stdout** | Final answer text only — pipe-friendly, capturable |
| **stderr** | Progress indicators, tool calls, token usage |
| **Files** | Agent-created files (CSVs, PDFs, JSON) saved to current directory |

## What the Rossum Agent Can Do

### Queues & Workspaces

Create, list, inspect, configure, and delete queues. Create workspaces. Query queue settings including inbox configuration and automation rules.

**Example prompts**: "List all queues", "Create a queue from the Invoice template", "Show inbox settings for queue 12345", "Delete queue 67890"

### Schemas

Read full schema trees, add/update/remove individual fields, prune unused fields in bulk. Supports all field types including sections, multivalue (line items), enums, and nested structures.

**Example prompts**: "Show the schema tree for queue 12345", "Add a required 'vendor_vat' string field to the header section", "Remove all fields except invoice_id, amount, and currency", "Move the 'tax' field into the line_items section"

### Formula Fields

Create fields that compute values deterministically from other fields using TxScript — math operations, string manipulation, conditional logic, date calculations, and aggregations over line items.

**Example prompts**: "Add a formula field that calculates total_with_tax as amount * (1 + tax_rate/100)", "Create a field that concatenates vendor_name and vendor_id", "Add a formula that sums all line item amounts"

### AI Reasoning Fields

Create fields that use AI to interpret document context and extract values from natural-language instructions. Best for ambiguous formats, contextual interpretation, and unstructured text.

**Example prompts**: "Add a reasoning field that determines the payment terms from the invoice text", "Create a field that classifies the document type as invoice, credit note, or purchase order"

### Lookup Fields

Create fields that fetch values from external datasets in the Rossum Master Data Hub — vendor matching, product catalog lookups, and reference data enrichment.

**Example prompts**: "Add a lookup field that matches vendor_name against the vendor master data", "Create a lookup for product codes from the catalog dataset"

### Hooks & Extensions

Create, configure, test, and manage serverless hook functions. Supports creating from Rossum Store templates or custom Python 3.12 code. Can test hooks with auto-generated realistic payloads.

**Example prompts**: "Create a hook from the 'Copy value to another field' template on queue 12345", "Write a custom hook that validates IBAN format", "Test the validation hook on queue 12345", "List all hooks and their events"

### Validation Rules

Create and manage validation rules using TxScript trigger conditions with configurable actions (errors, warnings, info, automates).

**Example prompts**: "Add a rule that shows an error when amount_total > 1000000", "Create a warning rule when due_date is in the past", "List all rules on queue 12345 and their trigger conditions"

### Annotations & Documents

Query annotations, inspect extracted data, update field values, change annotation status (start reviewing, confirm), copy annotations between queues, upload new documents.

**Example prompts**: "List recent annotations on queue 12345", "Show the extracted data from annotation 99999", "Upload invoice.pdf to queue 12345", "Copy annotations 111,222,333 to queue 67890 with re-import"

### UI Settings

Configure queue UI layout — which columns appear in the annotation list, sidebar ordering, and field visibility.

**Example prompts**: "Show the current UI settings for queue 12345", "Add 'vendor_name' and 'amount_total' columns to the annotation list table"

### Document Testing (End-to-End)

Generate schema-aware mock PDF documents, upload them to a queue, verify extraction results, and optionally trigger hooks — a full end-to-end processing test.

**Example prompts**: "Generate a test invoice PDF matching queue 12345's schema, upload it, and verify the extraction"

### Users & Permissions

Create and update users, manage roles and group assignments, list available roles.

**Example prompts**: "List all users", "Create a user with email john@example.com as annotator on queue 12345", "Update user 555 to manager role"

### Email Templates

Create email templates for automated notifications with configurable recipients (annotators, constants, datapoint values).

**Example prompts**: "Create an auto-send email template for confirmed invoices on queue 12345"

### Change History & Rollback

Review all configuration changes made by the agent, inspect diffs, and revert any commit. Full audit trail with entity-level version history and point-in-time restore.

**Example prompts**: "Show recent changes", "Revert the last commit", "Show version history for schema 444 and restore the version from before today's changes"

### Knowledge Base & Documentation

Search Rossum platform documentation and API docs for feature explanations, configuration guides, and API reference.

**Example prompts**: "How do formula fields work in Rossum?", "What events can hooks listen to?", "Explain the annotation lifecycle"

## Writing Effective Prompts

| Principle | Example |
|-----------|---------|
| Be specific about the target | "On queue **12345**, list all schema fields with their types" |
| State the goal, not steps | "Add a required vendor_name field" — the agent figures out how |
| Include IDs when known | "Queue 12345", "Hook 67890" — avoids ambiguity |
| Request structured output when needed | "Return the result as JSON" or "Format as a markdown table" |
| Combine read + write | "Check if queue 12345 has a tax_id field; if not, add it" |

## Choosing MCP Mode

| Mode | Use When |
|------|---------|
| `read-only` | Querying, listing, inspecting, explaining — no side effects |
| `read-write` | Creating, modifying, or deleting any Rossum resource |

Default to `read-only`. Only use `read-write` when the task requires mutations.

## Choosing Persona

| Persona | Use When |
|---------|---------|
| `default` | Standard tasks — agent acts autonomously |
| `cautious` | Destructive or production changes — agent confirms before acting |

## Constraints

| Constraint | Value |
|-----------|-------|
| Chat creates | 30/min |
| Messages | 10/min |
| Message length | 50,000 chars max |
| Images per message | 5 (max 5 MB each; jpeg/png/gif/webp) |
| PDFs per message | 5 (max 20 MB each) |
| Timeout | 300s default |

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| "Missing required configuration" | Set the three env vars above |
| 401 error | Token expired — get a fresh `ROSSUM_API_TOKEN` |
| 429 error | Rate limit hit — wait and retry |
| Timeout | Break the task into smaller, more focused prompts |
| "read-only mode" rejection | Add `--mcp-mode read-write` |
