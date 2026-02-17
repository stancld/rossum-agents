# SoW Creation Skill

**Goal**: Scope and create a structured Statement of Work for multi-step Rossum projects.

## When to Create a SoW

| Signal | Action |
|--------|--------|
| Vague/business-level request ("set up invoice processing for EU") | SoW first |
| Multiple entities, multiple deliverables | SoW first |
| User says "scope this" or "plan this" | SoW first |
| Single entity change, clear ask | Skip SoW, execute directly |

## Discovery Process

Before writing the SoW, explore the environment using **read-only tools only**:

1. List workspaces, queues, schemas, hooks to understand current state
2. Identify existing entities relevant to the request
3. Note gaps between current state and desired outcome
4. Ask clarifying questions about business goals and constraints

**Critical discovery questions** — always clarify before estimating:

| Question | Why it matters |
|----------|----------------|
| What document types are in scope? (invoices only, or also credit notes, certificates, delivery notes, statements?) | Non-invoice types each require separate schema/matching deliverables and add 1–5 MD each |
| What is the export destination and how many distinct formats/targets? | Each format variant is typically 3–5 MD; middleware pick-up (e.g. S3) vs. direct API push differ significantly in complexity |
| Any regional document formats? (Swiss QR bill, ZUGFeRD, XRechnung, Factur-X, Peppol?) | Structured format import for XML-based e-invoices is separate from OCR; adds 2–5 MD per format family |

**Estimate early**: As soon as you understand the scope (even at a rough level), state your MD estimate — don't wait until the end. Revise it as you learn more.

## SoW Format — Match to Scope

Not all SoWs need the same structure. Match verbosity to task size:

| Size | MD range | Format |
|------|----------|--------|
| Small | ≤ 3 MD | Lightweight: context paragraph + deliverable table only |
| Medium | 3–15 MD | Standard: add out-of-scope, assumptions, risks |
| Large | > 15 MD | Full: all sections |

### Lightweight Format (≤ 3 MD)

Use this for simple, well-bounded tasks. Skip risk tables, Mermaid diagrams, and exhaustive section lists.

```
## Context
One paragraph: what the customer wants and why, plus relevant environment facts.

## Deliverables

| Deliverable | Note | Estimate [MD] |
|-------------|------|---------------|
| Configure X | Technical detail (e.g. specific DNS record level, field name) | N MD |

## Assumptions
- Bullet list of what customer must provide
```

Keep the deliverable note technically specific (name the DNS record level, field type, API endpoint — whatever makes it concrete). One deliverable per row.

## Standard/Full SoW Structure

Use `create_sow` with these fields:

| Field | Purpose | Guidance |
|-------|---------|----------|
| `title` | Project name | Short, descriptive (e.g. "EU Invoice Processing Setup") |
| `business_goal` | Why this project exists | One sentence connecting to business outcome |
| `in_scope` | Concrete deliverables | Each item = one actionable deliverable with clear boundary |
| `out_of_scope` | Explicit exclusions | Prevents scope creep; list anything adjacent but not included |
| `constraints` | Hard limits | Technical limits, deadlines, compliance requirements |
| `success_criteria` | Definition of done | Measurable outcomes to verify completion |
| `existing_entities` | Current environment state | Entities relevant to this project. Each entry: `type` (required), `id` (int, omit if unknown), `name` (omit if unknown), `notes` (string, omit if empty) |
| `gaps` | What's missing | Delta between current state and desired outcome |
| `assumptions` | Dependencies on customer | Things customer must provide or confirm |
| `risk_factors` | What could go wrong | Integration dependencies, data quality, unknowns |
| `estimated_entity_changes` | Rough size | Count of entities to create/modify |
| `estimated_md` | Effort in man-days (required) | Use estimation guidelines below; include 15-20% buffer |

## Writing Good Deliverables

Each `in_scope` item should be:
- **Specific**: "Configure supplier matching by VAT ID, Tax ID, and IBAN with fuzzy name fallback" not "Set up matching"
- **Bounded**: "Up to 20 business rules" not "Business rules"
- **Actionable**: Starts with a verb (configure, implement, create, migrate)
- **Testable**: Clear when it's done

## Common Deliverable Patterns

### Schema and Extraction Setup

| Deliverable | Typical Scope |
|------------|---------------|
| Field schema customization | Configure extraction fields for document type; specify custom fields count |
| Document ingestion | Configure inbox queues for email/API/SFTP ingestion |
| Document routing | Route documents from inbox to processing queues based on extracted values |
| Document splitting | Split multi-document files into individual documents |
| Duplicate detection | Configure duplicate detection within Rossum and/or against external system |

### Data Matching and Enrichment

| Deliverable | Typical Scope |
|------------|---------------|
| Supplier matching | Match by VAT/Tax ID (exact), then fuzzy name+address fallback |
| PO header matching | Match by PO number (exact) |
| PO line matching | Match extracted lines to PO lines; filtering mechanism for large PO |
| Legal entity matching | Match customer entities by identifiers or fuzzy name |
| Master data import | Configure replication from external system (specify datasets) |
| Value recall/memorization | Remember user selections for ambiguous matches |

### Business Rules and Export

| Deliverable | Typical Scope |
|------------|---------------|
| Business rules | Validation rules (specify count cap, e.g. "up to 20 rules") |
| Credit/debit note handling | Detect document type and apply appropriate logic |
| Payment terms and due dates | Extract and validate against master data |
| Data export | Configure export to target system (specify format and destination) |
| Banking details normalization | Unify bank account formats (IBAN prefixes, digit formatting) |

### Operations

| Deliverable | Typical Scope |
|------------|---------------|
| Environment migration | Promote config from sandbox to production |
| Testing support | Bug fixes during UAT (specify duration) |
| Documentation | Internal technical documentation of implemented solution |
| Country/entity rollout | Copy existing config to new workspaces with entity-specific adjustments |

## Self-Review Loop

Run this review only when: estimated effort is ≥ 5 MD, or the requirements mention multiple document types, or there are multiple export targets/formats.

After drafting the SoW, review it against the requirements before saving. Run through this checklist and fix any issues found:

| Check | What to verify |
|-------|---------------|
| **All document types covered** | Every document type mentioned or implied in the requirements has a deliverable. No type is silently assumed to share another type's scope. |
| **Export destination correct** | Export target matches what was described (S3, SFTP, direct ERP API, middleware hand-off). Format count matches reality — each distinct format is a separate deliverable. |
| **MD estimate grounded** | Each deliverable has an explicit MD. Total matches sum. Buffer (15–20%) is included. No deliverable is left as "TBD". |
| **Nothing omitted from requirements** | Re-read the original request line by line. Every stated requirement maps to at least one deliverable or an explicit out-of-scope item. |
| **Out-of-scope is explicit** | Anything adjacent but excluded is listed. If the customer mentioned it and it's not in scope, it must appear in out-of-scope. |
| **Assumptions are actionable** | Each assumption names what the customer must provide and when. Vague assumptions ("customer provides data") are made specific ("customer provides vendor master in CSV with VAT ID, company name, and ERP source identifier"). |

If any check fails, fix the SoW before calling `create_sow`.

## Estimation Guidelines

| Complexity | Typical Size | Example |
|------------|-------------|---------|
| Simple export/integration | 1-3 MD | SFTP export with custom CSV formatting |
| Improvements to existing solution | 3-5 MD | Add PO validation, improve vendor matching, fix sorting |
| Single-country AP setup | 15-25 MD | Full AP with matching, rules, export |
| Multi-country rollout | 10-20 MD | Copy existing setup to new countries with adjustments |
| ESG/compliance add-on | 5-10 MD | Additional data extraction and matching on existing pipeline |

MD = man-day. Include 15-20% buffer for testing support.

## Anonymized Examples

### Example 1: Simple Integration (Small Scope — Lightweight Format)

**Context**: Customer has existing AP setup. Needs custom CSV export to SFTP.

```
## Context
Customer needs processed invoice data delivered to their downstream system via SFTP in a
customer-defined CSV format. Existing extraction and matching logic is unchanged.

## Deliverables

| Deliverable | Note | Estimate [MD] |
|-------------|------|---------------|
| Configure CSV export to SFTP | Custom column structure and file naming; 4-retry logic on connection failure; one CSV per document | 2 MD |

## Assumptions
- Customer provides SFTP credentials and target directory
- Customer confirms CSV column mapping before implementation
```

### Example 1b: Platform Feature (Small Scope — Lightweight Format)

**Context**: Customer wants outgoing emails from Rossum to show their own domain instead of the default Rossum domain. They are aware of the noreply limitation.

```
## Context
Customer has requested a custom domain for all outgoing e-mails (automatic replies, document
rejections, etc.) so the "from" address uses their domain instead of the default Rossum domain.
This SoW delivers on this requirement by configuring email subdomain (DNS records) delegation
from the customer to Rossum and by special configuration of the Cloud Based Solution.

## Deliverables

| Deliverable | Note | Estimate [MD] |
|-------------|------|---------------|
| Configure custom outgoing email domain | Third-level DNS record (e.g. invoices.customer.com) delegated to Rossum; SPF/DKIM setup; outgoing email delivery verification | 1 MD |

## Assumptions
- Customer IT provides DNS credentials and creates the delegated subdomain record
- Customer is aware that outgoing emails use a noreply address — recipients cannot reply directly
```

### Example 2: Improvements to Existing Solution (Medium Scope)

**Context**: Customer has working AP pipeline. Needs validation improvements and sorting fixes.

```
Title: Vendor Validation and Sorting Improvements
Business Goal: Reduce manual intervention by improving PO validation, vendor matching accuracy, and document sorting reliability.

In Scope:
- PO status validation: Block documents with closed/cancelled/draft PO statuses with error messages
- Vendor matching improvement: Refactor to always match supplier on document against PO supplier;
  first by Tax ID (exact, normalized), then fuzzy name fallback for countries without Tax ID
- Sorting queue improvements: Route documents without PO match to default regional queue
  instead of leaving them unrouted
- Testing support and bug fixes during UAT (limited to SoW deliverables)

Out of Scope:
- Export improvements for specific country tax requirements
- Vendor matching based on address (address not currently extracted)

Existing Entities:
- Sorting queues for Core and regional inboxes (already configured)
- PO validation hook (exists but incomplete)
- Vendor matching hook (functional but needs refactoring)

Gaps:
- PO status validation exists as a formula field but is not wired into any validator
- Vendor matching fails silently for countries without Tax ID field
- Documents without PO match are stuck in sorting queue

Risk Factors:
- Fuzzy name matching may produce false positives for short/common supplier names
- Sorting changes affect all document flow; thorough regression testing required

Estimated Entity Changes: 5 (3 hook updates, 1 formula field update, 1 queue config)
```

### Example 3: Full AP Implementation (Large Scope)

**Context**: New customer onboarding with full AP workflow including matching, rules, and ERP export.

```
Title: AP Invoice Processing - EMEA Region
Business Goal: Automate accounts payable processing for EMEA business unit with
  header and line-level data matching and export to ERP system.

In Scope:
- Schema configuration: Extract and process invoices, credit notes, and debit notes
  for 20+ countries with one unified field set; up to 10 additional custom fields
- Document ingestion: Configure email inbox per AP team
- Document routing: Route from inbox to processing queues based on extracted values
- Email data extraction: Extract PO numbers from email subjects when missing from document
- Duplicate detection: Within Rossum and against ERP system (by invoice number + supplier)
- Master data import: Automated replication from ERP for suppliers, legal entities, POs
  (with line items), banking details, and payment terms
- Supplier matching: By VAT/Tax ID and IBAN (exact), then fuzzy name+address,
  then name-only fallback; recall mechanism for ambiguous matches
- Legal entity matching: Same matching cascade as supplier matching
- PO/PO line matching: Exact PO number match, then show active lines with text search filter
- Banking details normalization: Unify IBAN formats per country (e.g. add country prefix)
- Payment terms: Extract and validate against PO or supplier master data
- Value recall mechanism: Remember user selections for ambiguous matching scenarios
- Business rules: Up to 20 validation rules (credit note handling, line type validation,
  invoice vs. PO data checks for quantity, unit price, supplier, entity)
- Credit and debit note handling: Detect document type, apply separate business logic
- Additional charges: Handle rounding and shipping charges with aggregation for ERP export
- Data export to ERP: Map and export validated data; auto-submit fully prepared documents
- UAT support for EMEA team
- UAT support for APAC team

Out of Scope:
- E-invoicing integration for any country
- Line item splitting or merging
- Withholding tax calculations
- Tax code assignment to extracted tax rates
- Three-way matching (invoice lines to goods receipts)
- Due date calculation using reasoning fields
- Integration with secondary ERP system
- Sensitive master data handling via live API calls (vs. stored in Rossum)

Assumptions:
- Customer provides master data feeds in agreed format
- Customer confirms PO number extraction pattern from email subjects
- One unified field set works across all EMEA countries (no per-country schemas)
- Duplicate detection conditions are the same across all countries and vendors

Risk Factors:
- 20+ countries with varying document formats and languages
- Master data quality affects matching accuracy
- ERP API rate limits may slow line-level matching during peak processing

Success Criteria:
- All document types (invoices, credit notes, debit notes) processed end-to-end
- Supplier and PO matching functional for all configured countries
- Validated data exported to ERP with correct field mapping
- Duplicate detection catches cross-system duplicates
- UAT completed with both EMEA and APAC teams

Estimated Entity Changes: 45 (4 workspaces, 8 queues, 4 schemas, 15 hooks, 14 config items)
```

### Example 4: Country Rollout (Copy Existing Setup)

**Context**: Existing implementation for one country works well. Roll out to 3 new countries/entities.

```
Title: Multi-Country Rollout - France, New Zealand, and Regional Entity
Business Goal: Extend existing invoice processing to three new countries/entities,
  reusing proven configuration with country-specific adjustments.

In Scope:
- Queue and integration setup: Copy existing country config into 3 new workspaces,
  each with sorting, PO, non-PO, and exception queues
- E-invoicing setup: Connect to e-invoicing network for 2 entities (country-specific
  gateway integration); route e-invoices through standard sorting and processing logic
- Approval workflows: Reuse existing approval workflow with entity-specific matrix adjustments
- Admin and end-user enablement (per workspace)
- 40 hours of ad-hoc consultation and development for custom requirements
- Testing, UAT, and hypercare support (UAT up to 2 weeks, hypercare up to 2 weeks)
- Project management and account setup

Out of Scope:
- New matching logic or business rules beyond what exists in the source configuration
- Changes to export format or target system
- Queue types not present in the source configuration

Assumptions:
- Source country configuration is stable and production-proven
- E-invoicing gateway credentials and VAT IDs provided by customer
- Each entity uses the same business rules as the source country

Risk Factors:
- E-invoicing integration for new countries not previously done (unknown gateway specifics)
- Translation requirements for non-English documents
- Entity-specific tax requirements may surface during UAT

Estimated Entity Changes: 30 (3 workspaces, 12 queues, 3 schemas, 6 hooks, 6 config items)
```

### Example 5: Add-On Feature (Extend Existing Pipeline)

**Context**: Customer has working AP pipeline with ERP export. Needs additional data extraction for ESG/compliance reporting.

```
Title: ESG Data Extraction and ERP Update
Business Goal: Extract ESG-relevant data from invoices and update existing ERP records
  with sustainability metrics for compliance reporting.

In Scope:
- Document routing: Copy ESG-relevant documents (based on supplier classification in ERP)
  to dedicated ESG processing queue; maintain link to original exported document
- Master data replication: Import ESG-specific datasets from ERP (media types,
  fuel types, units of measurement, stationary/mobile classification)
- Data matching - Media Type: Match by supplier's assigned types; memorize user
  selections with supplier+description context
- Data matching - Stationary/Mobile: Fuzzy match from line item description;
  full list fallback; memorize selections
- Data matching - Fuel Type: Mandatory for fuel media type; fuzzy match from
  description; full list fallback; memorize selections
- Data matching - Unit of Measurement: Fuzzy match from extracted abbreviations;
  full list fallback; memorize selections
- Line aggregation: Aggregate extracted ESG lines by media type, fuel type,
  and unit of measurement (sum consumed amounts)
- ERP record update: Update existing invoice/credit note records with aggregated
  ESG data using external ID from original export
- Environment migration: Deploy from sandbox to production (different ERP instances)
- Technical documentation

Out of Scope:
- Additional ERP environments beyond one sandbox and one production
- Per-country or per-subsidiary custom logic (all countries share same matching rules)
- Country-specific ESG regulatory requirements outside EU
- Three-way matching (expected to happen in ERP)

Assumptions:
- Customer has ESG-specific fields configured in ERP
- Supplier classification ("Type of Media") maintained in ERP master data
- Same matching and business logic applies across all countries/subsidiaries

Risk Factors:
- ESG data quality in ERP master data may be incomplete
- Aggregation logic must handle edge cases (mixed units, missing classifications)

Estimated Entity Changes: 20 (1 workspace, 2 queues, 1 schema, 8 hooks, 8 config items)
```

## Structured File Ingestion SoW Pattern

For customers needing to ingest structured data (JSON, XML) instead of scanned documents:

```
Title: Structured File Ingestion via API
Business Goal: Accept structured invoice/credit note data via API to leverage
  existing validation and export workflows without document scanning.

In Scope:
- API endpoint configuration: Accept JSON or XML format aligned with existing queue schema
- Process structured data through existing queues using established business logic,
  validation, and export workflows
- Status and error reporting: Customer can query processing status and error messages
  for each ingested document via API
- API documentation and technical support for customer's integration development
- Business logic review: Adapt validation rules for compatibility with structured data
  (identify rules dependent on visual document elements)
- Environment promotion: Deploy from DEV to TEST and PROD
- Testing support during customer integration development

Out of Scope:
- Building the integration on the customer side (customer responsibility)
- Handling attachments or supporting documents
- Changes to existing export pipeline

Assumptions:
- Customer develops and maintains the API integration
- Data schema aligns with fields configured in target queues
- Existing business logic is largely compatible with structured data

Risk Factors:
- Some validation rules may depend on visual document elements (OCR confidence, etc.)
- API response data from downstream systems may require platform-level support
```

## Calibration

The system prompt includes recent estimate vs. actual data from completed projects (when available).
Use these as reference points when sizing similar work. If the calibration shows consistent
over/under-estimation for a category, adjust your estimates accordingly.

## Cross-Reference

- After SoW approval, create implementation plan: handled by `create_implementation_plan` tool
- Schema work: load `schema-creation` or `schema-patching` skill
- Hook configuration: load `hooks` skill
- Queue setup: load `organization-setup` skill
- Deployment: load `rossum-deployment` skill
