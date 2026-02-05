# Schema Patching Skill

**Goal**: Add, update, or remove individual schema fields.

## Tool

```
patch_schema_with_subagent(schema_id="12345", changes='[{"action": "add", "id": "invoice_number", "parent_section": "header_section", "type": "string", "label": "Invoice Number"}]')
```

Sub-agent handles fetching, applying, and verifying changes.

## Changes Format

Each change object in the `changes` array:

| Field | Required | Description |
|-------|----------|-------------|
| `action` | No | "add" (default) or "remove" |
| `id` | Yes | Field ID |
| `parent_section` | For add | Section ID to add field to |
| `type` | For add | string, number, date, enum |
| `label` | No | Defaults to id |
| `table_id` | For table | Multivalue ID if adding column to table |

## Optional Field Properties

| Property | Description |
|----------|-------------|
| `format` | Number format (e.g., "#" for integer) |
| `options` | For enum: `[{"value": "v1", "label": "Label 1"}]` |
| `rir_field_names` | AI extraction hints |
| `hidden` | Hide field from UI |
| `can_export` | Include in exports |

Not supported: multiline fields, default_value, constraints. Use regular `string` type for multiline.

## UI Configuration

Optional `ui_configuration` object controls field behavior in the UI. Only set properties when explicitly requested - do not add ui_configuration if the user hasn't specified type or edit behavior.

| Property | Valid Values | Default |
|----------|--------------|---------|
| `type` | `captured`, `data`, `manual`, `formula`, `reasoning`, `null` | `null` |
| `edit` | `enabled`, `enabled_without_warning`, `disabled` | `enabled` |

Type meanings:
- `captured` - Value extracted by AI/OCR from document
- `data` - Value filled by extensions (no bounding box)
- `manual` - User-entered value (no bounding box)
- `formula` - Computed from formula definition
- `reasoning` - Updated per prompt and context
- `null` - Unset, behaves like captured

Common patterns:
- Formula field: `{"type": "formula", "edit": "disabled"}`
- Read-only captured field: `{"type": "captured", "edit": "disabled"}`
- Extension-filled field: `{"type": "data"}`

## Cross-Reference

- Create new schemas from scratch: load `schema-creation` skill
- Schema customization during queue creation: load `organization-setup` skill
- Sandbox testing before production: load `rossum-deployment` skill
