# Schema Pruning Skill

**Goal**: Remove unwanted fields from schema in one call.

## Tool

```
prune_schema_fields(schema_id=12345, fields_to_keep=["invoice_number", "invoice_date", "total_amount"])
```

Returns `{removed_fields: [...], remaining_fields: [...]}`.

## Behavior

- Specify leaf field IDs only (parent containers are preserved automatically)
- Sections with no remaining children are removed automatically
- Section IDs in `fields_to_keep` are preserved as empty containers ready for `patch_schema`
- `fields_to_keep=[]` removes everything including sections

## Cross-Reference

- Adding fields after pruning: load `schema-patching` skill
- Queue creation: load `organization-setup` skill
