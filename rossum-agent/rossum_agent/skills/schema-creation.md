# Schema Creation Skill

**Goal**: Create new schemas with sections, datapoints, multivalues, and tuples.

## Tool

```
create_schema_with_subagent(name="Invoice Schema", requirements="Describe sections, fields, and tables needed")
```

The sub-agent builds the full schema structure from natural language requirements.

## Content Array Structure

Schema content is a list of **sections**. Each section contains datapoints, multivalues, or tuples.

### Section

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique ID (≤50 chars) |
| `label` | string | Yes | Display name |
| `category` | string | Yes | Must be `"section"` |
| `children` | array | Yes | List of datapoints or multivalues |
| `hidden` | bool | No | Hide section (default: false) |
| `icon` | string | No | Section icon |

### Datapoint

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique ID |
| `label` | string | Yes | Display name |
| `category` | string | Yes | Must be `"datapoint"` |
| `type` | string | Yes | `string`, `number`, `date`, `enum`, `button` |
| `rir_field_names` | list | No | AI extraction hints |
| `default_value` | string | No | Default value |
| `hidden` | bool | No | Hide field |
| `disable_prediction` | bool | No | Disable AI extraction |
| `can_export` | bool | No | Include in exports (default: true) |
| `constraints` | object | No | Validation rules |
| `options` | list | No | For enum: `[{"value": "v1", "label": "Label"}]` |
| `ui_configuration` | object | No | UI behavior settings |
| `formula` | string | No | Formula expression for computed fields |
| `prompt` | string | No | LLM prompt for reasoning fields |
| `context` | list | No | Context field IDs for reasoning |
| `width` | int | No | Column width (tables only) |

### Multivalue (Lists/Tables)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique ID |
| `label` | string | Yes | Display name |
| `category` | string | Yes | Must be `"multivalue"` |
| `children` | object | Yes | Single datapoint OR tuple (NOT a list) |
| `rir_field_names` | list | No | AI extraction hints (e.g., `["line_items"]`) |
| `min_occurrences` | int | No | Minimum rows |
| `max_occurrences` | int | No | Maximum rows |

### Tuple (Table Row Structure)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique ID |
| `label` | string | Yes | Display name |
| `category` | string | Yes | Must be `"tuple"` |
| `children` | array | Yes | List of datapoints (table columns) |

## Schema Shapes

| Shape | Structure | Use Case |
|-------|-----------|----------|
| Simple | section → datapoint | Single values (invoice number, date) |
| List | section → multivalue → datapoint | Repeating values (PO numbers) |
| Table | section → multivalue → tuple → datapoints | Line items, tax details |

## Example: Complete Invoice Schema

```json
{
  "name": "Invoice Schema",
  "content": [
    {
      "id": "header_section",
      "label": "Header",
      "category": "section",
      "children": [
        {
          "id": "invoice_number",
          "label": "Invoice Number",
          "category": "datapoint",
          "type": "string",
          "rir_field_names": ["invoice_id"]
        },
        {
          "id": "invoice_date",
          "label": "Invoice Date",
          "category": "datapoint",
          "type": "date",
          "rir_field_names": ["date_issue"]
        }
      ]
    },
    {
      "id": "vendor_section",
      "label": "Vendor",
      "category": "section",
      "children": [
        {
          "id": "vendor_name",
          "label": "Vendor Name",
          "category": "datapoint",
          "type": "string",
          "rir_field_names": ["sender_name"]
        }
      ]
    },
    {
      "id": "line_items_section",
      "label": "Line Items",
      "category": "section",
      "children": [
        {
          "id": "line_items",
          "label": "Line Items",
          "category": "multivalue",
          "rir_field_names": ["line_items"],
          "children": {
            "id": "line_item",
            "label": "Line Item",
            "category": "tuple",
            "children": [
              {
                "id": "item_description",
                "label": "Description",
                "category": "datapoint",
                "type": "string",
                "rir_field_names": ["item_description"]
              },
              {
                "id": "item_quantity",
                "label": "Quantity",
                "category": "datapoint",
                "type": "number",
                "rir_field_names": ["item_quantity"]
              },
              {
                "id": "item_amount",
                "label": "Amount",
                "category": "datapoint",
                "type": "number",
                "rir_field_names": ["item_amount_total"]
              }
            ]
          }
        }
      ]
    }
  ]
}
```

## Helper Dataclasses (rossum-mcp)

Use these models from `rossum_mcp.tools.schemas.models`:

| Class | Purpose |
|-------|---------|
| `SchemaDatapoint` | Field definition with type, label, constraints |
| `SchemaTuple` | Table row structure containing datapoints |
| `SchemaMultivalue` | Repeating fields or tables |

## Common rir_field_names

| Field Type | Common Values |
|------------|---------------|
| Invoice ID | `invoice_id`, `document_id` |
| Date | `date_issue`, `date_due` |
| Amount | `amount_total`, `amount_due`, `amount_total_tax` |
| Vendor | `sender_name`, `sender_address`, `sender_vat_id` |
| Buyer | `recipient_name`, `recipient_address` |
| Line Items | `line_items` (for multivalue) |
| Item fields | `item_description`, `item_quantity`, `item_amount_total` |

## UI Configuration

Optional `ui_configuration` controls field behavior:

| Property | Values | Use Case |
|----------|--------|----------|
| `type` | `captured`, `data`, `manual`, `formula`, `reasoning` | Field source |
| `edit` | `enabled`, `disabled`, `enabled_without_warning` | Editability |

## Cross-Reference

- Modify existing schemas: load `schema-patching` skill
- Schema customization during queue setup: load `organization-setup` skill
