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

Full language reference: load `txscript` skill. Key rules-specific behavior:

- Conditions must evaluate strictly to `True` (not truthy — wrap with `bool()` if needed)
- Uses formula-field context: `field.x` syntax, no imports
- Referencing a line-item field (e.g., `field.item_x`) triggers per-row evaluation; duplicate actions are deduplicated
- Use `.all_values` for cross-row aggregation: `sum(field.item_amount.all_values)`

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
