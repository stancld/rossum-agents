# Persona + SoW Integration Plan

## Goal
Integrate persona-driven tempo (`balanced`, `cautious`) with SoW/planning workflow (`Auto`/`SoW` mode) so they work together without conflicting behavior.

## Scope
- Reuse existing persona support:
  - Chat/message API fields (`persona`)
  - Chat metadata persistence (`persona`)
  - Persona-aware system prompt composition
  - TUI persona config + quick replies
- Reuse SoW/planning support from `ds-sow-role`:
  - Execution planning prompt section
  - Artifact injection into system prompt
  - Planning/SoW tools + storage handles

## Integration Principles
1. Persona controls communication style and caution level.
2. SoW mode controls workflow constraints and allowed operations.
3. Hard workflow constraints win over persona style when they conflict.
4. Keep defaults safe and predictable:
   - `persona=balanced` default
   - `Auto` execution mode default

## Expected File Touchpoints
- `rossum-agent/rossum_agent/api/models/schemas.py`
- `rossum-agent/rossum_agent/redis_storage.py`
- `rossum-agent/rossum_agent/api/routes/chats.py`
- `rossum-agent/rossum_agent/api/routes/messages.py`
- `rossum-agent/rossum_agent/api/services/chat_service.py`
- `rossum-agent/rossum_agent/api/services/agent_service.py`
- `rossum-agent/rossum_agent/prompts/base_prompt.py`
- `rossum-agent/rossum_agent/prompts/system_prompt.py`
- `rossum-agent/rossum_agent/tools/core.py` (artifact store context)
- `rossum-agent/rossum_agent/tools/planning.py`
- `rossum-agent/rossum_agent/tools/__init__.py`
- `rossum-agent-tui/src/types.ts`
- `rossum-agent-tui/src/hooks/useConfig.ts`
- `rossum-agent-tui/src/index.tsx`
- `rossum-agent-tui/src/api/client.ts`
- `rossum-agent-tui/src/api/sse.ts`
- `rossum-agent-tui/src/app.tsx`
- `rossum-agent-tui/src/components/StatusBar.tsx`

## Merge Order
1. Merge SoW/planning branch (`ds-sow-role`) into target branch.
2. Reapply persona commits on top.
3. Resolve conflicts in prompt/service layers with the rules below.

## Conflict Resolution Rules
### 1) `agent_service.py`
- Keep artifact injection:
  - `ArtifactStore`, `PlanHandle`, `SoWHandle`
  - `_inject_active_artifacts(...)`
  - `set_artifact_store(...)` lifecycle hooks
- Keep persona plumbing:
  - `run_agent(..., persona: Literal["balanced", "cautious"] = "balanced")`
  - `system_prompt = get_system_prompt(persona)`
- Final order:
  1. Build persona-aware base prompt
  2. Append URL context (if present)
  3. Inject active SoW/Plan summaries

### 2) `base_prompt.py`
- Keep SoW/Execution planning section (`EXECUTION_PLANNING`).
- Keep persona behavior section (`PERSONA_BEHAVIORS` + getter).
- Ensure both appear in shared prompt sections.
- Add explicit guard clause in planning instructions:
  - In SoW mode, only read tools + `create_sow`, regardless of persona.

### 3) `system_prompt.py`
- Keep function signature:
  - `get_system_prompt(persona: Literal["balanced", "cautious"] = "balanced")`
- Compose:
  - `ROSSUM_EXPERT_INTRO`
  - `get_persona_behavior(persona)`
  - shared sections (including execution planning)

### 4) Routes + metadata
- Preserve both `mcp_mode` and `persona` resolution/persistence.
- Keep persona fallback for old records (`balanced` if missing).

## Behavioral Contract
- `balanced`:
  - concise planning for complex tasks
  - clarifying questions when ambiguity/risk is meaningful
- `cautious`:
  - explicit plan-first, more clarifying questions
  - asks permission before writes
- SoW mode:
  - discovery + scope only
  - no writes, regardless of persona

## UX Contract (TUI)
- Persona selectable via CLI/env:
  - `--persona balanced|cautious`
  - `ROSSUM_AGENT_PERSONA`
- Quick replies available during clarifications:
  - `Meta+1`: `Approve`
  - `Meta+2`: `Reject`
  - `Meta+3`: `Let's chat about it.`

## Test Plan
### Backend
- Schema tests:
  - `CreateChatRequest.persona` default + validation
  - `MessageRequest.persona` optional override + validation
- Route tests:
  - create chat persists persona
  - message-level persona override
  - fallback to chat-level persona
- Prompt tests:
  - persona-specific sections included
  - SoW section still present
- Agent service tests:
  - `get_system_prompt` called with persona
  - artifact injection still applied

### TUI
- Typecheck passes with new `persona` config.
- Request payloads include `persona`.
- Status bar renders persona and quick-reply hints.

## Rollout Steps
1. Merge code.
2. Run targeted tests and typechecks.
3. Update docs:
  - `rossum-agent/README.md`
  - `rossum-agent-tui/README.md`
4. Smoke test:
  - `balanced` + Auto mode
  - `cautious` + Auto mode
  - SoW mode behavior with both personas

## Risks
- Prompt bloat causing instruction dilution.
- Divergent behavior if SoW constraints are not clearly higher priority than persona style.
- Merge drift in `agent_service.py` due to multiple simultaneous feature edits.

## Mitigations
- Keep persona block concise (style constraints only).
- Keep SoW restrictions explicit and imperative.
- Add one regression test asserting SoW mode disallows writes even with `balanced`.
