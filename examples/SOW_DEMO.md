# Statement of Work — Demo Scenarios

This file shows how to use Rossum Agent to scope projects and create Statements of Work.

## How SoW Mode Works

Paste one of the prompts below into the agent. The agent:
1. Switches to **read-only discovery** — explores your environment without making changes
2. Asks clarifying questions about business goals and constraints
3. Creates a structured SoW via `create_sow`
4. Presents the SoW for your approval before doing anything

**Trigger phrases**: "scope this", "create a SoW", "switch to SoW mode", or any vague/multi-step request.

---

## Scenario 1: Small Add-On — Custom CSV Export to SFTP

**Context**: Customer has a working AP pipeline. They need a new SFTP export.

**Paste this into the agent:**

```
Scope the work needed to add a custom CSV export to SFTP for queue 2519495.

The customer wants:
- One CSV file per processed invoice
- Column mapping they'll define (to be provided)
- Automated delivery on document export event
- Retry on SFTP failure (up to 4 retries)

Store it in fabry_demo.md.

Switch to SoW mode.
```

**What the agent does:**
- Lists hooks already on the queue to check for existing export logic
- Lists the queue schema to understand available fields
- Asks: What is the target SFTP host/path? Has the customer confirmed the column mapping?
- Creates SoW via `create_sow`

**Expected SoW output:**

```
# Statement of Work: Custom CSV Export to SFTP
**Environment**: elis.rossum.ai/api/v1
**Status**: draft

## Business Goal
Export processed invoice data to the customer's downstream system via SFTP in a customer-defined CSV format.

## In Scope
- Configure CSV export hook with customer-defined column structure and file naming convention
- Set up automated SFTP delivery triggered on document export with 4 retries on connection failure
- One CSV file per processed document
- Communication and credential exchange for SFTP setup
- Technical documentation

## Out of Scope
- Aggregation of multiple documents into a single CSV file
- Changes to existing extraction or matching logic

## Assumptions
- Customer provides SFTP credentials and target directory path
- Customer confirms CSV column mapping before implementation begins

## Risk Factors
- SFTP credentials not yet provided — blocks implementation start

**Estimated entity changes**: 3
```

---

## Scenario 2: Medium Scope — Improvements to Existing Pipeline

**Context**: Working AP pipeline exists. Customer reports vendor matching gaps and sorting issues.

**Paste this into the agent:**

```
Create a SoW for improving the AP pipeline in workspace 1417456. Issues reported:
- Vendor matching fails for suppliers in countries without a Tax ID field
- Documents without a PO match get stuck in the sorting queue instead of going to a fallback queue
- PO status validation is configured as a formula field but doesn't block documents

I want to fix these without changing the export or schema setup.
```

**What the agent does:**
- Lists all hooks on the workspace queues to find vendor matching and sorting hooks
- Reads the relevant hook code to understand the current matching logic
- Lists queues to find the sorting queue and identify any fallback queue
- Lists the schema to locate the PO status formula field
- Creates SoW via `create_sow`, referencing discovered entity IDs

**Expected SoW output:**

```
# Statement of Work: Vendor Validation and Sorting Improvements
**Environment**: elis.rossum.ai/api/v1
**Status**: draft

## Business Goal
Reduce manual intervention by improving PO validation, vendor matching accuracy,
and document sorting reliability.

## Existing Entities
- hook 88001 "Vendor Matching" — functional but fails for countries without Tax ID
- hook 88002 "Sorting Hook" — leaves unmatched documents stuck in sorting queue
- hook 88003 "PO Validation" — PO status formula field not wired into any validator
- queue 72001 "Invoices" — main processing queue
- queue 72002 "Sorting Queue" — entry point for document routing

## Gaps
- Vendor matching fails silently for countries without a Tax ID field
- Sorting hook has no fallback route for documents without PO match
- PO status validation formula exists but is not enforced by a validation rule

## In Scope
- PO status validation: Block documents with closed/cancelled/draft PO statuses with an error message
- Vendor matching refactor: Match first by Tax ID (exact, normalized), then fuzzy name
  fallback for countries without Tax ID
- Sorting fallback: Route documents without PO match to default regional queue
  instead of leaving them in the sorting queue
- Testing support and bug fixes during UAT (limited to deliverables above)

## Out of Scope
- Changes to the export hook or export format
- Vendor matching by address (address not currently extracted)
- Schema changes

## Risk Factors
- Fuzzy name matching may produce false positives for short or common supplier names
- Sorting changes affect all document flow — thorough regression testing required

## Success Criteria
- PO status validation blocks non-approved POs with a clear error message
- Vendor matching succeeds for all configured countries
- Documents without PO match route to the fallback queue

**Estimated entity changes**: 5
```

---

## Scenario 3: Full AP Onboarding — New Customer Setup

**Context**: New customer. No existing Rossum setup. Needs full AP processing for EMEA.

**Paste this into the agent:**

```
Switch to SoW mode.

New customer onboarding for EMEA AP automation. Scope the full implementation.

Requirements we know:
- 20+ countries, single unified schema
- Invoices, credit notes, debit notes
- Supplier matching by VAT/Tax ID and fuzzy name
- PO header and line matching
- Up to 20 business rules
- Export to SAP (REST API)
- UAT with EMEA team

What questions do you need answered before writing the SoW?
```

**What the agent does:**
- Lists workspaces in the organization to identify if anything exists already
- Asks: Is there a sandbox environment? Who provides master data (suppliers, POs)? Will there be a single schema or per-country schemas? What's the deduplication strategy?
- After you answer, creates a comprehensive SoW covering all 8 sections

**Example clarifying questions the agent will ask:**

> Before writing the SoW, I need a few things confirmed:
>
> 1. **Master data**: How are suppliers and POs provided — file export, API, or manual upload?
> 2. **Deduplication**: Should duplicate detection run within Rossum only, or also check SAP records?
> 3. **Schema**: Single schema for all 20+ countries, or some country-specific fields?
> 4. **Environments**: Will you need sandbox → production promotion, or direct production setup?
> 5. **Approval workflows**: Are approval workflows in scope or handled in SAP?

After you answer, the agent calls `create_sow` and presents a structured SoW similar to the Example 3 in the `sow-creation` skill.

---

## After SoW Approval

Once you approve the SoW, the agent switches to planning mode:

```
The SoW looks good. Approve and proceed with implementation planning.
```

The agent then:
1. Calls `create_implementation_plan` with phased steps referencing the SoW
2. Presents the plan for your approval
3. After approval, executes phase by phase, calling `update_plan_step` before and after each step

---

## Tips

| Situation | What to say |
|-----------|-------------|
| Vague or multi-deliverable request | Just describe the goal — agent detects complexity |
| You want to force SoW mode | Add "switch to SoW mode" or "scope this" |
| Agent starts executing instead of scoping | "Stop. Create a SoW first." |
| SoW needs changes | "Update the SoW: add X to out of scope" |
| Ready to proceed | "Approved. Create an implementation plan." |
