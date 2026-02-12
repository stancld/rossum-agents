# Hooks Skill

**Goal**: Create, configure, and test hooks — prefer Rossum Store templates over custom code.

## Constraints

| Constraint | Detail |
|------------|--------|
| Templates first | `list_hook_templates()` before writing custom code — most use cases are covered |
| Research before custom code | `search_knowledge_base` for hook configuration guides before resorting to custom serverless functions |
| Custom code last resort | Load `txscript` skill only when no template covers the requirement |

## Creating from Templates

```
list_hook_templates()
create_hook_from_template(name="My Hook", hook_template_id=123, queues=["https://..."], token_owner="https://.../users/456")
```

Check template's `use_token_owner` and `events` fields before calling `create_hook_from_template`.

## token_owner

| Rule | Detail |
|------|--------|
| Format | User URL: `https://<base>/users/<id>` |
| Required when | Template has `use_token_owner=true`, or hook needs API access (annotation actions, connector calls) |
| Forbidden role | `organization_group_admin` users cannot be token owners |
| Finding a valid user | `list_users(is_organization_group_admin=false)` → use `url` field of an active user |

## Creating Custom Hooks

```
create_hook(name="My Hook", type="function", queues=["https://..."], events=["annotation_content.export"], config={"source": "<code>"})
```

| Detail | Value |
|--------|-------|
| `config.source` | Auto-renamed to `config.function` |
| Default runtime | `python3.12` |
| Max timeout | 60 seconds |

## Testing

```
test_hook(hook_id, event, action)
```

Generates a realistic payload and executes it in one call. No annotations on hook's queues → pass annotation URL from another queue via `annotation` parameter.

## Debugging

`list_hook_logs(hook_id=123)` — 7-day retention, max 100 per call. Filter by `log_level`, `status`, `annotation_id`, time range.

## Cross-Reference

- Custom function hook code: load `txscript` skill
- Formula fields (no hook needed): load `formula-fields` skill
- Queue creation with hooks: load `organization-setup` skill
