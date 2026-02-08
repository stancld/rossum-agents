# Formula Fields Skill

**Goal**: Create or update formula fields that compute values from other fields using TxScript (Python-based).

## Workflow

1. Call `suggest_formula_field(label, hint, schema_id, section_id, field_schema_id)` to get AI-generated formula
2. Call `patch_schema_with_subagent(schema_id, changes)` to add the field with the generated formula to the schema

## When to Use

| Scenario | Use Formula Field |
|----------|-------------------|
| Deterministic transformation | Yes — clear rules, math, string ops |
| Conditional logic | Yes — if/else on field values |
| Aggregation across line items | Yes — `sum()`, `all_values` |
| Ambiguous interpretation | No — use reasoning field instead |

## TxScript Basics

| Concept | Syntax |
|---------|--------|
| Reference field | `field.invoice_id` |
| Empty check | `is_empty(field.amount_due)` |
| Set check | `is_set(field.amount_total_base)` |
| Default fallback | `default_to(field.discount_rate, 0)` |
| No return statements | Last expression = output |
| Line item per-row | `field.item_quantity * field.item_price` |
| All row values | `field.item_amount_total.all_values` |
| Regex substitution | `substitute(r'[^a-z0-9]', '', field.sender_vat_id, flags=re.IGNORECASE)` |
| Pre-imported | `timedelta`, `datetime`, `date`, `re` |

## Messaging Functions

| Function | Effect |
|----------|--------|
| `show_info("msg", field.x)` | Informational, field-level |
| `show_warning("msg", field.x)` | Warning, field-level |
| `show_error("msg", field.x)` | Error — blocks export |
| `show_info("msg")` | Document-level info |
| `automation_blocker("reason", field.x)` | Blocks automation |

## Common Patterns

```python
# Date + 14 days
field.date_issue + timedelta(days=14)

# Conditional discount
field.amount_total * 0.8 if field.amount_total > 20000 else field.amount_total

# Fallback chain
default_to(default_to(field.amount_total, field.amount_total_base), sum(default_to(field.item_amount_total.all_values, 0)))

# Sum check with warning
line_items_sum = sum(default_to(field.item_amount_total.all_values, 0))
if round(line_items_sum, 2) != round(field.amount_total, 2):
    show_warning('Sum of line items does not equal total amount!', field.amount_total)

# Iterate line items
for row in field.line_items:
    if is_set(row.item_amount_total) and row.item_amount_total < 0:
        show_error("Negative amount", row.item_amount_total)

# Distribute header value to line items
if is_set(field.item_order_id):
    field.item_order_id
else:
    field.order_id
```

## Schema Config

Formula fields require:
- `ui_configuration`: `{"type": "formula", "edit": "disabled"}`
- `formula`: TxScript code string

## Constraints

| Rule | Detail |
|------|--------|
| No circular refs | Formula must not reference itself |
| No return statements | Last expression is the output |
| Always produce result | Empty formula = empty field |
| Round floats | `round(x, 2)` for equality checks |
| Use `suggest_formula_field` first | Get AI-generated formula, then patch |

## Cross-Reference

- AI-generated formula suggestions: `suggest_formula_field` tool (always available)
- Add formula field to schema: load `schema-patching` skill
- Contextual AI inference: load `reasoning-fields` skill
