# Hooks Skill

**Goal**: Create, configure, and test hooks — prefer Rossum Store templates over custom code.

## Constraints

| Constraint | Detail |
|------------|--------|
| Templates first | `search(query={"entity": "hook_template"})` before writing custom code — most use cases are covered |
| Custom code last resort | Only write custom serverless functions when no template covers the requirement |

## Creating from Templates

```
search(query={"entity": "hook_template"})
create_hook_from_template(name="My Hook", hook_template_id=123, queues=["https://..."], token_owner="https://.../users/456")
```

Check template's `use_token_owner` and `events` fields before calling `create_hook_from_template`.

## token_owner

| Rule | Detail |
|------|--------|
| Format | User URL: `https://<base>/users/<id>` |
| Required when | Template has `use_token_owner=true`, or hook needs API access (annotation actions, connector calls) |
| Forbidden role | `organization_group_admin` users cannot be token owners |
| Finding a valid user | `search(query={"entity": "user", "is_organization_group_admin": false})` → use `url` field of an active user |

## Creating Custom Hooks

```
create_hook(name="My Hook", type="function", queues=["https://..."], events=["annotation_content.export"], config={"source": "<code>"})
```

| Detail | Value |
|--------|-------|
| `config.source` | Auto-renamed to `config.code` |
| Default runtime | `python3.12` |
| Max timeout | 60 seconds |

### TxScript Boilerplate

Custom hooks use TxScript — a Python 3.12 DSL for field manipulation:

```python
from txscript import TxScript, is_set, is_empty, default_to

def rossum_hook_request_handler(payload):
    t = TxScript.from_payload(payload)

    # Read: t.field.<schema_id>
    # Write: t.field.<schema_id> = new_value
    # Check: is_set(t.field.x), is_empty(t.field.x)

    return t.hook_response()
```

| Rule | Detail |
|------|--------|
| Never use `is None` | Use `is_empty()` / `is_set()` — fields are `None`-like but not `None` |
| Always return `t.hook_response()` | Omitting causes silent failures |

Load `txscript` skill for advanced patterns (line items, table columns, messaging, annotation actions).

## Testing

```
test_hook(hook_id, event, action)
```

| Rule | Detail |
|------|--------|
| Annotation required | Events like `annotation_content` need an annotation — `test_hook` fails if the hook's queues have none |
| Before calling `test_hook` | `search(query={"entity": "annotation", "queue_id": <queue_id>})` to check if annotations exist |
| No annotations found | Pass an annotation URL from another queue via `annotation` parameter, or upload a document first |

## Debugging

`search(query={"entity": "hook_log", "hook_id": 123})` — 7-day retention, max 100 per call. Filter by `log_level`, `status`, `annotation_id`, time range.

## Cross-Reference

- Formula fields (no hook needed): load `formula-fields` skill
