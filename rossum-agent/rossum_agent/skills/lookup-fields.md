# Lookup Fields Skill

**Goal**: Create or update lookup fields that fetch values from external datasets (Master Data Hub) using MongoDB aggregation pipelines.

## Workflow

1. Ensure the field exists in the schema with `ui_configuration: {"type": "lookup", "edit": "disabled"}` and a `matching` object
2. Call `patch_schema_with_subagent(schema_id, changes)` to add/update the lookup field with its `matching` configuration

### Creating a New Lookup Field

```
patch_schema_with_subagent(schema_id="12345", changes='[{"action": "add", "id": "vendor_match", "label": "Vendor Match", "type": "string", "parent_section": "vendor_section", "ui_configuration": {"type": "lookup", "edit": "disabled"}, "matching": {"type": "master_data_hub", "configuration": {"dataset": "Vendors", "queries": "[{\"//\": \"Exact VAT match\", \"aggregate\": [...]}]", "placeholders": {"sender_vat": {"__formula": "field.sender_vat_id"}}}}}]')
```

### Updating an Existing Lookup Field

To modify the queries or placeholders of an existing lookup field:

```
patch_schema_with_subagent(schema_id="12345", changes='[{"action": "update", "id": "vendor_match", "matching": {"type": "master_data_hub", "configuration": {"dataset": "Vendors", "queries": "[{\"//\": \"Updated query\", \"aggregate\": [...]}]", "placeholders": {"sender_vat": {"__formula": "field.sender_vat_id"}}}}}]')
```

## When to Use

| Scenario | Use Lookup Field |
|----------|-----------------|
| Match against external dataset | Yes — VAT ID, vendor name, SKU |
| Enrich from master data | Yes — fill address, account info from MDH |
| Aggregation/statistics from dataset | Yes — sum, average, count from MDH |
| Deterministic field-to-field logic | No — use formula field instead |
| AI interpretation of document text | No — use reasoning field instead |

## Matching Configuration

Lookup fields require a `matching` object with either a built-in `type` **or** a `hook_interface` URL (mutually exclusive):

### Built-in Types

| Type | Variant | Use Case |
|------|---------|----------|
| `simple_lookup` | `queue_lookup` | Basic exact-match filters |
| `complex_lookup` | `queue_lookup_aggregate` | MongoDB aggregation pipelines |
| `master_data_hub` | `queue_lookup_aggregate` | Master Data Hub integration |

### Configuration Structure

```json
{
  "matching": {
    "type": "master_data_hub",
    "configuration": {
      "dataset": "Dataset Name",
      "queries": "[{\"//\": \"Comment\", \"aggregate\": [...]}]",
      "placeholders": {
        "placeholder_name": {"__formula": "field.field_name"}
      }
    }
  }
}
```

| Field | Description |
|-------|-------------|
| `type` | Built-in handler name (`simple_lookup`, `complex_lookup`, `master_data_hub`) |
| `hook_interface` | Alternative to `type` — URL to a HookInterface of type `queue_lookup` |
| `configuration.dataset` | Name of the MDH dataset to query |
| `configuration.queries` | JSON string of query array with `//` comment and `aggregate` pipeline |
| `configuration.placeholders` | Map of placeholder names to TxScript `__formula` expressions |

## Placeholders (Field References)

Placeholders connect schema fields to MongoDB query variables using TxScript:

| Pattern | Use Case |
|---------|----------|
| `{"__formula": "field.field_name"}` | Required field reference |
| `{"__formula": "default_to(field.field_name, \"\")"}` | Optional field with fallback |
| `{"__formula": "default_to(field.field_name, \"UNKNOWN\")"}` | Non-empty fallback (required for `$search`) |
| `{"__formula": "field.item_field.all_values[0]"}` | Line item field reference |
| `{"__formula": "default_to(field.field_name, \"\").lower()"}` | Case-insensitive |
| `{"__formula": "\"static_string\""}` | Static value |

Reference placeholders in pipelines as `$$placeholder_name`.

## MongoDB Aggregation Guidelines

### Core Operators

`$match`, `$group`, `$sum`, `$avg`, `$count`, `$sort`, `$limit`, `$addFields`, `$project`, `$search`

### Mandatory Final Projection

Every pipeline MUST end with:
```json
{"$project": {"value": "$value_field", "label": "$label_field"}}
```
- `value`: Identifier field (required)
- `label`: Display field (required)
- Additional fields only if explicitly requested

### Type Casting

Cast columns BEFORE using in aggregations:
```json
{"$addFields": {"price_num": {"$toDouble": "$price"}}}
```

### Placeholder vs Field Reference

- `$$placeholder` = incoming placeholder value (from `placeholders` object)
- `$field_name` = document field or field created by `$addFields`
- After `$addFields`, use single `$` to reference the created field

### $search Rules

- **$search MUST be the first pipeline stage** — no `$addFields`, `$match`, or other stages before it
- Always follow with: `{"$addFields": {"score": {"$meta": "searchScore"}}}`
- Add score threshold: `{"$match": {"score": {"$gte": 2}}}`
- Sort by score: `{"$sort": {"score": -1}}`
- Use non-empty placeholder defaults for `$search` (not `""`)

### Combining Exact Filters with Fuzzy Search

Use compound `$search` with filter clause:
```json
{"$search": {"compound": {"must": [{"text": {"path": "name", "query": "$$name", "fuzzy": {"maxEdits": 1}}}], "filter": [{"equals": {"path": "vat_id", "value": "$$vat"}}]}}}
```

**Never** put `$match` before `$search`.

### String Operations

- Pre-compute in `$addFields` before using in `$concat` or `$match`
- `$replaceAll` find argument MUST be a plain string, never `$regexFind`
- Use `$$` (double dollar) for regex end anchor in `$concat`

## Query Fallback Strategy

Always use multiple simpler queries ordered by confidence:

```json
"queries": "[
  {\"//\": \"Exact normalized VAT match\", \"aggregate\": [...]},
  {\"//\": \"Exact match on Tax Number\", \"aggregate\": [...]},
  {\"//\": \"Fuzzy name match\", \"aggregate\": [...]}
]"
```

### By Field Type

| Field Type | Strategy | Example |
|------------|----------|---------|
| Structured IDs (VAT, SKU) | Exact match with normalization, alternative ID fallbacks | VAT ID → Tax Number → Reg Number |
| Natural language (names) | Exact → Fuzzy (maxEdits:1) → Fuzzy multi-field (maxEdits:2) | Company name → Legal name |
| Hybrid (email, phone) | Exact normalized → format variations | With prefix → without prefix |

**Never** use fuzzy `$search` on structured identifiers — a "similar" ID is a different entity.

### Query Guidelines

- Each query MUST have `"//"` comment and `"aggregate"` array
- Order by confidence: most reliable first
- Keep each query simple: one clear strategy per query
- Limits: exact (1–5), fuzzy (5–10)

## Common Patterns

### Vendor Lookup by VAT ID

```json
{
  "matching": {
    "type": "master_data_hub",
    "configuration": {
      "dataset": "Vendors",
      "queries": "[{\"//\": \"Exact normalized VAT match\", \"aggregate\": [{\"$addFields\": {\"vat_norm\": {\"$toLower\": {\"$trim\": {\"input\": \"$VAT_ID\"}}}, \"search_norm\": {\"$toLower\": {\"$trim\": {\"input\": \"$$sender_vat\"}}}}}, {\"$match\": {\"$expr\": {\"$eq\": [\"$vat_norm\", \"$search_norm\"]}}}, {\"$limit\": 5}, {\"$project\": {\"value\": \"$VAT_ID\", \"label\": \"$entity_name\"}}]}, {\"//\": \"Exact match on Tax Number\", \"aggregate\": [{\"$match\": {\"tax_number\": \"$$sender_tax\"}}, {\"$limit\": 5}, {\"$project\": {\"value\": \"$tax_number\", \"label\": \"$entity_name\"}}]}]",
      "placeholders": {
        "sender_vat": {"__formula": "default_to(field.sender_vat_id, \"\")"},
        "sender_tax": {"__formula": "default_to(field.sender_tax_id, \"\")"}
      }
    }
  }
}
```

### Company Name Lookup (Fuzzy)

```json
{
  "matching": {
    "type": "master_data_hub",
    "configuration": {
      "dataset": "Companies",
      "queries": "[{\"//\": \"Exact company name match\", \"aggregate\": [{\"$match\": {\"company_name\": \"$$company_name\"}}, {\"$limit\": 5}, {\"$project\": {\"value\": \"$company_name\", \"label\": \"$company_name\"}}]}, {\"//\": \"Fuzzy company name match\", \"aggregate\": [{\"$search\": {\"text\": {\"path\": \"company_name\", \"query\": \"$$company_name\", \"fuzzy\": {\"maxEdits\": 1}}}}, {\"$addFields\": {\"score\": {\"$meta\": \"searchScore\"}}}, {\"$match\": {\"score\": {\"$gte\": 2}}}, {\"$sort\": {\"score\": -1}}, {\"$limit\": 5}, {\"$project\": {\"value\": \"$company_name\", \"label\": \"$company_name\"}}]}]",
      "placeholders": {
        "company_name": {"__formula": "default_to(field.sender_name, \"UNKNOWN\")"}
      }
    }
  }
}
```

### VAT ID + Fuzzy Name (Compound Search)

```json
{
  "matching": {
    "type": "master_data_hub",
    "configuration": {
      "dataset": "Vendors",
      "queries": "[{\"//\": \"Exact VAT and name match\", \"aggregate\": [{\"$match\": {\"vat_id\": \"$$vat\", \"entity_name\": \"$$name\"}}, {\"$limit\": 5}, {\"$project\": {\"value\": \"$vat_id\", \"label\": \"$entity_name\"}}]}, {\"//\": \"Fuzzy name with VAT filter via compound search\", \"aggregate\": [{\"$search\": {\"compound\": {\"must\": [{\"text\": {\"path\": \"entity_name\", \"query\": \"$$name\", \"fuzzy\": {\"maxEdits\": 1}}}], \"filter\": [{\"equals\": {\"path\": \"vat_id\", \"value\": \"$$vat\"}}]}}}, {\"$addFields\": {\"score\": {\"$meta\": \"searchScore\"}}}, {\"$sort\": {\"score\": -1}}, {\"$limit\": 5}, {\"$project\": {\"value\": \"$vat_id\", \"label\": \"$entity_name\"}}]}]",
      "placeholders": {
        "vat": {"__formula": "default_to(field.sender_vat_id, \"\")"},
        "name": {"__formula": "default_to(field.sender_name, \"UNKNOWN\")"}
      }
    }
  }
}
```

## Schema Config

Lookup fields require:
- `ui_configuration`: `{"type": "lookup", "edit": "disabled"}`
- `matching`: object with `type` or `hook_interface`, plus `configuration`

```json
{
  "id": "vendor_match",
  "label": "Vendor Match",
  "type": "string",
  "category": "datapoint",
  "ui_configuration": {"type": "lookup", "edit": "disabled"},
  "matching": {
    "type": "master_data_hub",
    "configuration": {
      "dataset": "Vendors",
      "queries": "[...]",
      "placeholders": {"sender_vat": {"__formula": "field.sender_vat_id"}}
    }
  }
}
```

## Constraints

| Rule | Detail |
|------|--------|
| Feature flag required | `lookup_fields` must be enabled on organization group |
| No `rir_field_names` | Lookup fields cannot use AI extraction hints |
| No `enabled_without_warning` | Edit mode cannot be `enabled_without_warning` |
| `type` or `hook_interface` | Provide one, not both |
| Final `$project` required | Every pipeline must end with `value` and `label` projection |
| `$search` must be first | No stages allowed before `$search` |
| No fuzzy on IDs | Use exact match for structured identifiers |
| Non-empty `$search` defaults | Placeholders used in `$search` need non-empty fallbacks |
| No `update_schema` | Use `patch_schema` or `patch_schema_with_subagent` |

## Key Differences from Other Computed Fields

| Aspect | Formula | Reasoning | Lookup |
|--------|---------|-----------|--------|
| Logic type | Deterministic rules | AI interpretation | External dataset query |
| Input | TxScript code | Natural language prompt | MongoDB aggregation |
| Data source | Other schema fields | Document context | Master Data Hub |
| Key config | `formula` | `prompt` + `context` | `matching` |
| Speed | Fastest | Slower | Depends on query |

## Cross-Reference

- Deterministic transformations: load `formula-fields` skill
- Contextual AI inference: load `reasoning-fields` skill
- Add lookup field to schema: load `schema-patching` skill
- TxScript reference for placeholders: load `txscript` skill
