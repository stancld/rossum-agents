# Review Code Changes

**Goal**: Review uncommitted changes for quality issues, ensure tests pass, and produce MR-ready summary.

## Scope

| Context | What to Review |
|---------|----------------|
| No argument | Uncommitted changes; if none, review last commit |
| Commit provided | The specified commit(s) |

## Review Checklist

| Category | Check For |
|----------|-----------|
| Unused code | Dead imports, variables, unreachable branches |
| Duplication | Repeated logic that should use shared components |
| AI slop | Excessive try/catch, defensive checks in trusted paths, `Any` casts, style drift |
| Documentation | Changes reflected in README.md and CLAUDE.md |
| Tests | New features/bug fixes have tests; existing tests not deleted without cause |
| Breaking changes | Public API or tool signatures changed without backward compatibility |
| Opus prompts | If `rossum_agent/prompts/` or `rossum_agent/skills/` changed — see **Opus Prompt Guidelines** below |

## Opus Prompt Guidelines

Apply when reviewing changes to `rossum_agent/prompts/` or `rossum_agent/skills/`:

| Principle | Violation to flag |
|-----------|-------------------|
| Goals over procedures | Step-by-step instructions where a single goal statement suffices |
| Constraints over explanations | Prose explaining *why* a constraint exists instead of stating it directly |
| Tables for structure | Prose lists that would be clearer as markdown tables |
| No redundancy | Repeating information Opus can infer from context or earlier in the same prompt |
| Facts not warnings | "IMPORTANT:", "Note:", "WARNING:" preambles — state the rule directly instead |

## Approach

| Step | Action |
|------|--------|
| Analyze | Review diff for issues in checklist |
| Critical issues | Use `AskUserQuestion` for each - fix or skip |
| Tests | If test files changed, ask whether to run `pytest` |
| Summary | Generate short MR description of what was done |

## Merge Verdict

After review, assign one of three verdicts:

| Verdict | Criteria |
|---------|----------|
| **Mergeable** | No blocking issues found |
| **Mergeable with notes** | Minor issues noted but none block merging |
| **Not mergeable** | Any of the blocking conditions below are true |

Blocking conditions (any one is sufficient to block merge):
- Missing tests for new features or bug fixes
- Breaking API/tool changes without justification
- Critical bugs introduced by the change
- Documentation not updated when required by CLAUDE.md

## Output

Provide MR-ready summary:

```
## Summary
- <1-3 bullets describing changes>

## Review Notes
- <any issues found and addressed>

## Verdict
<Mergeable | Mergeable with notes | Not mergeable>
<one-line rationale>
```

## Constraints

- Ask before running tests (use `AskUserQuestion`)
- No automatic commits
- Report only critical issues, not style nitpicks
