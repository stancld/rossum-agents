# SoW Creation Skill

**Goal**: Scope, document, and plan Rossum implementation work before execution.

## When to Create a SoW

Create a SoW for any request that involves:
- Multiple entity types (schema + hooks + queues)
- 3+ distinct configuration changes
- Work spanning multiple conversations or sessions
- User explicitly asks for a plan or proposal

Skip SoW for quick single-step changes (e.g. "rename this field", "fix this hook").

## Scope Clarification (Do This First)

Before drafting, resolve the scope dimension:

| Question | Options |
|----------|---------|
| **General or specific?** | "Does this apply to all queues / all schemas, or to a specific one?" |
| **Which entities?** | List workspaces, queues, schemas, hooks by name |
| **What operations?** | create / update / delete per entity |
| **Constraints?** | Sandbox first? Read-only restrictions? |

**If the user's message is ambiguous** (e.g. "add reasoning fields to invoices"), ask:
> "Should this apply to all invoice queues, or a specific queue? And is this for a specific workspace?"

Do not guess. Wrong scope leads to incorrect estimates and wasted work.

## SoW Format

### Lightweight (1-3 entities, low complexity)

```
## Description
[One paragraph explaining the goal and approach]

## Scope
| Entity | Type | Operations |
|--------|------|------------|
| Queue A | queue | update |
| Schema A | schema | update (add 2 fields) |

## Estimates
| Entity Type | Estimated Operations |
|-------------|---------------------|
| schema | 1 |
| queue | 1 |
```

### Standard (4-10 entities)

Full SoW with description, scope table, estimates, and open questions.

### Full (10+ entities or multi-org)

Full SoW plus risk section and phased rollout notes.

## Estimation Guidelines

Base estimates on typical operation counts:

| Change | Typical Ops |
|--------|------------|
| Add 1 formula field | 1 schema update |
| Add reasoning field | 1 schema update |
| Create hook from template | 1 hook create |
| Add lookup field | 1 schema update + 1 dataset check |
| New queue setup | 1 queue + 1 schema + 2-4 hooks |
| Deploy to sandbox + prod | +2 operations (deploy tools) |

Round up for complexity. Note if estimates are uncertain.

## Workflow

1. **Clarify scope** — resolve general vs. specific, identify all affected entities
2. **Call `create_sow`** — persist the SoW for user review
3. **Present to user** — show the rendered SoW, ask for approval
4. **On approval** — call `create_implementation_plan` with phases
5. **Execute** — call `update_plan_step` as each step completes
6. **Finish** — call `record_sow_outcome` with actual operation counts

## Calibration

After completing a SoW, record actuals via `record_sow_outcome`. This builds
estimation accuracy over time. Compare estimated vs actual — if delta > 50%,
note the reason (scope creep, unexpected complexity, etc.).
