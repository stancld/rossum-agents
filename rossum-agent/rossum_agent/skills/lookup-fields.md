# Lookup Fields Skill

**Goal**: Create or update lookup fields that fetch values from external datasets (Master Data Hub).

## When to Use

| Scenario | Use Lookup Field |
|----------|-----------------|
| Match against external dataset | Yes — VAT ID, vendor name, SKU |
| Enrich from master data | Yes — fill address, account info from MDH |
| Aggregation/statistics from dataset | Yes — sum, average, count from MDH |
| Deterministic field-to-field logic | No — use formula field instead |
| AI interpretation of document text | No — use reasoning field instead |

## Approach

Generate config with `suggest_lookup_field`, test with `evaluate_lookup_field`, write with `patch_schema_with_subagent`. Never write to the schema until evaluation passes. Re-generate at most 3 times; stop and report if results don't improve.

`suggest_lookup_field` caches the field definition internally and returns `field_schema_id` + `matching`. Pass `field_schema_id` to `evaluate_lookup_field` — do not pass `field_definition` (avoids repeating the large JSON in context).

For `patch_schema_with_subagent`, pass the `matching` object from the suggest result in the changes array.

When matches fail, use `get_lookup_dataset_raw_values` + `query_lookup_dataset` to inspect raw data — start with `.[0] | keys` to discover columns — then re-call `suggest_lookup_field` with corrected hints.

For existing fields, pass `action: "update"` in `patch_schema_with_subagent` changes.

## Match Quality — Prefer No Match Over Wrong Match

A false match is worse than no match. Apply this principle at every query tier:

| Signal strength | Action |
|-----------------|--------|
| Strong identifier (VAT ID, exact code) | Match |
| Name alone, near-exact (≥ 0.9 similarity) | Match |
| Name alone, partial/low similarity | Do **not** match — leave unmatched |
| Multiple candidates, none dominant | Do **not** match — leave unmatched |

**Fuzzy fallback queries are high-risk.** Only include a name-only fuzzy fallback when the dataset has no reliable identifier column and the name field is the sole matching signal. When you do use one, set the score threshold high (≥ 0.85) and verify during evaluation that no unrelated records are being matched. Lower the threshold only if the evaluation shows missed matches on records that are clearly the same entity — never to chase a higher match count.

## Debugging Non-Matches

| Root Cause | Symptom | Resolution |
|------------|---------|------------|
| Missing record | No match despite correct columns | Record doesn't exist — report |
| Field mismatch | Wrong column name | Inspect with `.[0] \| keys`, re-call `suggest_lookup_field` |
| Normalization gap | Values differ by case/whitespace | Re-call `suggest_lookup_field` with hint about format difference |
| Ambiguous results | Multiple candidates, none dominant | Re-call to tighten — if ambiguity persists, leave unmatched |

## Schema Config

```json
{
  "id": "vendor_match",
  "label": "Vendor Match",
  "type": "enum",
  "category": "datapoint",
  "ui_configuration": {"type": "lookup", "edit": "disabled"},
  "matching": {
    "type": "master_data_hub",
    "configuration": {
      "dataset": "imported-0d652b68-fd8b-4fc8-9cee-d39105b1304b",
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
| Always pass `dataset` | Pass dataset when known; `suggest_lookup_field` resolves it to an `imported-...` ID |
| No wrong match | A false positive is worse than no match. Multiple candidates without a clear winner → leave unmatched. Fuzzy name-only fallback threshold must be ≥ 0.85 unless there is no other signal. |
| No `rir_field_names` | Lookup fields cannot use AI extraction hints |
| No `enabled_without_warning` | Edit mode cannot be `enabled_without_warning` |
| `type` or `hook_interface` | Provide one, not both |
| No `update_schema` or `patch_schema` | Use `patch_schema_with_subagent` — direct schema writes lose the matching config |
