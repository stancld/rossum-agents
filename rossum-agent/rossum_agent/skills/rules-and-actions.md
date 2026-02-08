# Rules & Actions Skill

**Goal**: Create and configure rules with TxScript trigger conditions and actions using `create_rule` in a single call.

## Tool

```
create_rule(
    name="Rule name",
    trigger_condition="field.amount_total > 400",
    actions=[{...}],
    queue_ids=[12345]
)
```

## Trigger Conditions (TxScript)

Conditions are TxScript expressions that must evaluate strictly to `True` (not truthy — wrap with `bool()` if needed).

### Evaluation Modes

| Mode | When | Example |
|------|------|---------|
| Simple | Condition references only header fields | `field.amount_total > 400` |
| Line-item | Condition references a table column field | `field.item_quantity * field.item_amount_total != field.item_amount` |

Line-item mode evaluates once per row; duplicate actions are deduplicated automatically.

### Field References

| Syntax | Scope |
|--------|-------|
| `field.amount_total` | Header field value |
| `field.item_amount_total` | Line-item column (triggers line-item mode) |
| `field.item_amount_total.all_values` | All row values as `TableColumn` (NumPy-like) |

### Operators & Functions

| Pattern | Example |
|---------|---------|
| Comparison | `field.amount_total > 400` |
| Equality (round floats) | `round(field.amount_total, 2) != round(sum(field.item_amount_total.all_values), 2)` |
| Multiplication check | `field.item_quantity * field.item_amount_total != field.item_amount` |
| Sum | `sum(field.item_amount_total.all_values)` |
| Empty check | `is_empty(field.amount_due)` |
| Default | `default_to(field.amount_total, 0)` |
| Boolean wrap | `bool(field.amount_total > 400)` |

## Action Objects

Each action requires: `id` (unique string), `type`, `event` (always `"validation"`), `payload`.

### Action Types

| `type` | `payload` | Use Case |
|--------|-----------|----------|
| `show_message` | `{"type": "error"\|"warning"\|"info", "content": "msg"}` | Display validation message |
| `show_message` (field) | `{"type": "error", "content": "msg", "schema_id": "amount_total"}` | Message on specific field |
| `add_automation_blocker` | `{"content": "reason"}` | Stop automation |
| `add_validation_source` | `{"schema_id": "field_id"}` | Trigger field validation |
| `change_queue` | `{"queue_url": "https://..."}` | Route document |
| `change_status` | `{"status": "postponed"\|"rejected"\|"confirmed"\|"exported"\|"deleted"}` | Change document status |
| `show_hide_field` | `{"schema_ids": ["field_id"]}` | Dynamic visibility (auto-reverts) |
| `show_field` | `{"schema_ids": ["field_id"]}` | Show once (no revert) |
| `hide_field` | `{"schema_ids": ["field_id"]}` | Hide once (no revert) |
| `add_label` | `{"label": "name"}` | Assign label once |
| `remove_label` | `{"label": "name"}` | Remove label once |
| `send_email` | `{"content": "template"}` | Send notification email |

## Examples

### Threshold validation (single rule)

```json
{
    "name": "Total amount threshold",
    "trigger_condition": "field.amount_total > 400",
    "actions": [
        {
            "id": "total_too_high",
            "type": "show_message",
            "event": "validation",
            "payload": {
                "type": "error",
                "content": "Total amount is larger than allowed 400.",
                "schema_id": "amount_total"
            }
        }
    ],
    "queue_ids": [12345]
}
```

### Line items sum validation

```json
{
    "name": "Line items sum check",
    "trigger_condition": "round(field.amount_total, 2) != round(sum(field.item_amount_total.all_values), 2)",
    "actions": [
        {
            "id": "sum_mismatch",
            "type": "show_message",
            "event": "validation",
            "payload": {
                "type": "error",
                "content": "Sum of all total amount line items does not equal total amount."
            }
        }
    ],
    "queue_ids": [12345]
}
```

### Per-row multiplication check

```json
{
    "name": "Line item multiplication check",
    "trigger_condition": "field.item_quantity * field.item_amount_total != field.item_amount",
    "actions": [
        {
            "id": "mult_mismatch",
            "type": "show_message",
            "event": "validation",
            "payload": {
                "type": "error",
                "content": "quantity x unit price does not equal total amount."
            }
        }
    ],
    "queue_ids": [12345]
}
```

## Constraints

| Rule | Detail |
|------|--------|
| One `create_rule` per validation rule | Each rule has one `trigger_condition` — create multiple rules for independent checks |
| Floats: always `round()` | `round(field.x, 2) != round(field.y, 2)` — floating point equality is unreliable |
| `bool()` for truthy | `trigger_condition` must be strictly `True`, not just truthy |
| Scope with `queue_ids` or `schema_id` | At least one required |
| Line-item field = line-item mode | Referencing a table column auto-triggers per-row evaluation |
