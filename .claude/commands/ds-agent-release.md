# Release rossum-agent

**Goal**: Prepare rossum-agent for release by merging master, updating versions, re-pinning dependencies to PyPI, and finalizing changelog.

## Package Info

| Field | Value |
|-------|-------|
| Package | rossum-agent |
| Path | `rossum-agent/` |
| Module | `rossum_agent` |

## Workflow

| Step | Action |
|------|--------|
| Merge master | Run `git merge master` to incorporate latest changes |
| Determine version | Read `pyproject.toml`, strip `dev` suffix for release version |
| Update pyproject.toml | Remove `dev` suffix from version |
| Update __init__.py | Set `__version__` to match pyproject.toml |
| Update changelog | Change `[Unreleased] - YYYY-MM-DD` to `[X.Y.Z] - <today's date>` |
| Re-pin dependencies | Convert git dependencies to PyPI with version pins |
| Run uv lock | Regenerate lockfile: `cd rossum-agent && uv lock` |
| Verify | Run `pre-commit run -a` and `pytest rossum-agent/` |
| Output | Provide commit message |

## Version Derivation

| Current (pyproject.toml) | Release Version |
|--------------------------|-----------------|
| `X.Y.Zdev` | `X.Y.Z` |
| `X.Y.Z.devN` | `X.Y.Z` |
| `X.Y.ZrcN` | Bump rc number (e.g., `rc0` → `rc1`) |

## Dependency Re-pinning

Convert git-based monorepo dependencies to PyPI packages:

| Before (development) | After (release) |
|---------------------|-----------------|
| `rossum-mcp @ git+...` | `rossum-mcp>=X.Y.Z` |
| `rossum-deploy @ git+...` | `rossum-deploy>=X.Y.Z` |

Determine latest PyPI versions by:
1. Check recent release commits on master (format: `<pkg>: Release <pkg> X.Y.Z`)
2. Or query PyPI directly

## Changelog Update

Transform:
```
## [Unreleased] - YYYY-MM-DD
```

To:
```
## [X.Y.Z] - 2026-02-04
```

## Output Format

After all changes made:

```
## Ready to Release

Changed files:
- rossum-agent/pyproject.toml
- rossum-agent/rossum_agent/__init__.py
- rossum-agent/CHANGELOG.md
- rossum-agent/uv.lock

Suggested commit message:
rossum-agent: Release rossum-agent X.Y.Z

Git tag command (after commit):
git tag rossum-agent-vX.Y.Z
```

## Constraints

- **Never commit** - only make file changes, user handles all commits
- Resolve merge conflicts manually if they occur
- Use `AskUserQuestion` if version ambiguous
- Run pre-commit and tests before reporting ready
