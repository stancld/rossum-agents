# Reasoning Fields Skill

**Goal**: Create reasoning fields that use AI to interpret document context and generate values from instructions.

## Workflow

1. Call `patch_schema_with_subagent(schema_id, changes)` to add the reasoning field with `prompt`, `context`, and `ui_configuration` set
   - `changes` JSON must include: `id`, `label`, `type`, `parent_section`, and the reasoning-specific fields (`prompt`, `context`)
2. The sub-agent handles fetching the schema and patching the field in

## When to Use

| Scenario | Use Reasoning Field |
|----------|---------------------|
| Ambiguous/variable formats | Yes — AI interprets context |
| Contextual interpretation | Yes — sentiment, categorization |
| Extract from unstructured text | Yes — email bodies, notes |
| Deterministic math/logic | No — use formula field instead |

## Configuration

Reasoning fields use two key properties on the schema datapoint:

| Property | Description |
|----------|-------------|
| `prompt` | Instructions for the AI (max 2000 chars) |
| `context` | List of field references the AI can read (TxScript format) |

Schema datapoint also requires:
- `ui_configuration`: `{"type": "reasoning", "edit": "disabled"}`
- `score_threshold`: float (default `0.8`)

## Writing Instructions

| Principle | Example |
|-----------|---------|
| Be specific | "Extract the early payment discount percentage from field.notes" |
| Use field_ids | "Look at field.vendor_name and field.sender_address" |
| Say what to exclude | "Ignore shipping-related terms" |
| Provide examples | "Output: 'Net 30', 'Net 60', '2/10 Net 30'" |
| Define fallback | "If not found, output 'N/A'" |
| Define output format | "Return as 'YYYY-MM-DD' date string" |
| Keep under 2000 chars | Concise instructions perform best |

## Common Use Cases

| Use Case | Context Fields | Instructions Pattern |
|----------|---------------|---------------------|
| Early payment discounts | `field.notes`, `field.terms` | "Extract discount % and deadline" |
| Categorize line items | `field.item_description` | "Classify as: Office Supplies, Equipment, Services" |
| Email sentiment | `field.email_body` | "Rate urgency: Low, Medium, High" |
| Header from email | `field.email_body` | "Extract sender company name" |
| Structured line items | `field.item_description` | "Parse quantity and unit from description" |

## Schema Config

```json
{
    "id": "payment_terms",
    "label": "Payment Terms",
    "type": "string",
    "category": "datapoint",
    "ui_configuration": {"type": "reasoning", "edit": "disabled"},
    "prompt": "Extract payment terms from the invoice...",
    "context": ["field.notes", "field.terms_conditions"],
    "score_threshold": 0.8
}
```

## Key Differences from Formula Fields

| Aspect | Formula | Reasoning |
|--------|---------|-----------|
| Logic type | Deterministic rules | AI interpretation |
| Speed | Faster | Slower |
| Cost | Lower | Higher |
| Learning | No | Yes — learns from corrections |
| Input | TxScript code | Natural language instructions |

## Cross-Reference

- Deterministic transformations: load `formula-fields` skill
- Add reasoning field to schema: load `schema-patching` skill
- AI-generated formulas: `suggest_formula_field` tool
