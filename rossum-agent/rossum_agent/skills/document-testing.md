# Document Testing Skill

**Goal**: Test document processing end-to-end — generate a schema-aware mock PDF, upload it, verify extraction, optionally trigger hooks.

## Workflow

1. Get schema: `list_queues` → `get_schema(schema_id)`
2. Extract fields from schema content (walk sections → datapoints, multivalues → tuples)
3. `generate_mock_pdf(fields=[...], document_type="invoice")`
4. `upload_document(file_path, queue_id)`
5. Poll: `list_annotations(queue_id, ordering=["-created_at"], first_n=1)` every 5s, max 12 attempts
6. Verify: `get_annotation(annotation_id, sideloads=["content"])` → compare vs `expected_values`
7. Optional: `test_hook(hook_id, event, action, annotation=annotation_url)`

## Field Extraction from Schema

Walk `schema.content` recursively:

| Schema node | Mapping |
|-------------|---------|
| `category: "section"` | Container — recurse into `children` |
| `category: "datapoint"` | Header field → `{id, label, type, rir_field_names, options}` |
| `category: "multivalue"` | Table container — children are tuples |
| `category: "tuple"` | Table row template — children are line item columns |

Line item fields: `rir_field_names` containing `item_*` prefix, or `id` starting with `item_`.

## Constraints

| Constraint | Detail |
|------------|--------|
| Schema first | Always fetch the schema before generating — field list must match the queue's schema |
| Overrides for specifics | Use `overrides={field_id: value}` to force values for edge-case testing |
| One queue at a time | Upload to a single queue, verify there, then repeat for others |
| Poll with backoff | Extraction takes 5-30s; poll `list_annotations` with 5s intervals, 12 max attempts |

## Verification

| Field type | Match criteria |
|------------|---------------|
| IDs, dates, VAT numbers | Exact match |
| Amounts | Approximate (±0.01) — rounding differences |
| Addresses, names | Partial/fuzzy — extraction may split or reformat |
| Enums | Exact match on value |

Compare `expected_values` from `generate_mock_pdf` output against extracted annotation content. Report mismatches with field ID, expected value, and extracted value.

## Cross-Reference

- Hook testing after upload: load `hooks` skill
- Schema field configuration: load `schema-patching` skill
- Formula field verification: load `formula-fields` skill
