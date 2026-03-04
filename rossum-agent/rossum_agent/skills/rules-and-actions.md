# Rules & Actions Skill

**Goal**: Translate user-described validations into Rossum rules via `suggest_rule` → `create(entity="rule", ...)`.

## Workflow

Call `suggest_rule(user_query, queue_id)`, then `create(entity="rule", data={...})` immediately with the returned values — no confirmation needed.

If the user asks to test a rule, call `evaluate_rules(queue_id, annotation_id, schema_rules)` to preview which actions would trigger.
`evaluate_rules` requires an existing annotation in the queue — upload documents first if none exist:
1. Fetch schema fields (`get(entity="schema", id=schema_id)`)
2. Generate test PDFs (`generate_mock_pdf` with `overrides` to control field values)
3. Upload each PDF (`upload_document`)
4. Call `evaluate_rules` with the returned annotation IDs

**Example query**: `'Show error on amount_total when >= 400. Message: "Total exceeds 400."'`

## Constraints

| Constraint | Detail |
|------------|--------|
| `suggest_rule` before `create` | Never hand-write trigger conditions or actions |
| One call per check | One `suggest_rule` + one `create(entity="rule", ...)` per independent validation |
| Concise `user_query` | Field, condition, error message — one sentence, no elaboration |
| `queue_ids` required | Scope every rule to at least one queue |
