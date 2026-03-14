# Lookup Fields Skill

**Goal**: Create or update lookup fields that fetch values from external datasets (Master Data Hub).

## How Lookup Fields Work

Lookup fields are **schema-level configuration** — a `matching` object on the datapoint definition. The Rossum engine evaluates them automatically during **prediction**, the same as any other AI field. No hooks, no serverless functions, no external automation. Once the `matching` config is on the schema, the field is populated for every new document without any additional setup.

A lookup field **before configuration** has no `matching` property and an empty `options` array — this is the expected initial state, not a defect. Do not flag missing `matching` or empty `options` as problems. The `suggest_lookup_field` tool adds the `matching` config, and `options` stay empty because values come dynamically from MDH at prediction time.

If a configured lookup field is not producing matches, the issue is in the `matching` configuration or the dataset — never in missing hooks or automation. Always check the connected dataset from MDH first.

## When to Use

| Scenario | Use Lookup Field |
|----------|-----------------|
| Match against external dataset | Yes — VAT ID, vendor name, SKU |
| Enrich from master data | Yes — fill address, account info from MDH |
| Aggregation/statistics from dataset | Yes — sum, average, count from MDH |
| Deterministic field-to-field logic | No — use formula field instead |
| AI interpretation of document text | No — use reasoning field instead |

## Approach

Always use `execute_python` with `suggest_lookup_field` and `evaluate_lookup_field` — never hand-write matching configurations. Write to the schema only after evaluation passes. Re-generate at most 3 times; stop and report if results don't improve.

```python
suggested = suggest_lookup_field(
    label="Vendor Match",
    hint="Match vendors by VAT ID, prefer no match over wrong match",
    schema_id=9389721,
    section_id="basic_info",
    dataset="Approved Vendors",
)
evaluation = evaluate_lookup_field(
    schema_id=9389721,
    annotation_urls=["/api/v1/annotations/123456"],
    field_schema_id=suggested["field_schema_id"],
)
```

`suggest_lookup_field` caches the field definition internally and returns `field_schema_id` + `matching`. Pass `field_schema_id` to `evaluate_lookup_field` — do not pass `field_definition` unless you are intentionally overriding the cached version.

For `patch_schema_with_subagent`, pass the `matching` object from the suggest result in the changes array.

When matches fail, inspect raw data — then re-call `suggest_lookup_field` with corrected hints:

```python
get_lookup_dataset_raw_values(dataset="Approved Vendors")
result = query_lookup_dataset(dataset="Approved Vendors", jq_query=".[0] | keys")
```

`get_lookup_dataset_raw_values` takes `dataset` and optional `limit` — no `schema_id`. Start with `.[0] | keys` to discover columns.

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

**First step**: Always check the connected dataset from MDH — use `get_lookup_dataset_raw_values` and `query_lookup_dataset` to verify data exists and columns match expectations.

A lookup field without a `matching` property or with empty `options` is **not broken** — it simply hasn't been configured yet. Use `suggest_lookup_field` to add the configuration. Do not report missing `matching` or empty `options` as errors.

When a **configured** lookup field produces no match or wrong matches, the cause is in the `matching` configuration or the dataset content — never in missing hooks, automation, or external logic.

| Root Cause | Symptom | Resolution |
|------------|---------|------------|
| No `matching` config yet | Field exists with no `matching` and empty `options` | Expected initial state — run `suggest_lookup_field` to configure |
| Wrong `matching` config | Field has `matching` but never matches | Inspect dataset with `query_lookup_dataset`, re-call `suggest_lookup_field` with corrected hints |
| Missing record | No match despite correct config | Record doesn't exist in dataset — report to user |
| Field mismatch | Wrong column name in query | Inspect with `query_lookup_dataset(dataset, ".[0] | keys")`, re-call `suggest_lookup_field` |
| Normalization gap | Values differ by case/whitespace | Re-call `suggest_lookup_field` with hint about format difference |
| Ambiguous results | Multiple candidates, none dominant | Re-call to tighten — if ambiguity persists, leave unmatched |

## Schema Config

Before configuration (expected initial state — no `matching`, empty `options`):

```json
{
  "id": "vendor_match",
  "label": "Vendor Match",
  "type": "enum",
  "category": "datapoint",
  "options": [],
  "ui_configuration": {"type": "lookup", "edit": "disabled"}
}
```

After `suggest_lookup_field` adds the `matching` config:

```json
{
  "id": "vendor_match",
  "label": "Vendor Match",
  "type": "enum",
  "category": "datapoint",
  "options": [],
  "ui_configuration": {"type": "lookup", "edit": "disabled"},
  "matching": {
    "type": "master_data_hub",
    "configuration": {
      "dataset": "imported-0d652b68-fd8b-4fc8-9cee-d39105b1304b",
      "queries": "[...]",
      "variables": {"sender_vat": {"__formula": "field.sender_vat_id"}}
    }
  }
}
```

## Constraints

| Rule | Detail |
|------|--------|
| Not a hook | Lookup fields are populated during prediction like any other AI field. They require only a `matching` config on the schema datapoint. Never create, attach, or investigate hooks for lookup fields. Never suggest missing hooks as a root cause. |
| Feature flag required | `lookup_fields` must be enabled on organization group |
| Always pass `dataset` | Pass dataset when known; `suggest_lookup_field` resolves it to an `imported-...` ID |
| No wrong match | A false positive is worse than no match. Multiple candidates without a clear winner → leave unmatched. Fuzzy name-only fallback threshold must be ≥ 0.85 unless there is no other signal. |
| No `rir_field_names` | Lookup fields cannot use AI extraction hints |
| No `enabled_without_warning` | Edit mode cannot be `enabled_without_warning` |
| `type` field | Typically `"enum"` (required when options are used), but `"string"` is also valid |
