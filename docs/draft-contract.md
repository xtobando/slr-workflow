# Structured draft contract

Read `schemas/draft.schema.json` or run `python -m slr_workbench schema`. A generic dataclass-generated schema
checks shape; submission additionally checks the current protocol and workflow.

Run `python -m slr_workbench packet <stage-id> <entity-id>` for the current revision, target, criteria,
documents and a draft skeleton. Replace all skeleton instructions with actual
evidence-backed content. Skeletons are not scientific findings.

Required fields: protocol_revision, entity_type, entity_id, stage, suggestion,
rationale. Optional fields: criteria, evidence, values, provenance.

## Evidence

- Bibliographic evidence uses source `title` or `abstract` and an exact quote.
- Full-text evidence uses source `document`, document_id and an exact quote.
- Page numbers are **physical PDF pages starting at 1**, when a reliable mapping
  exists. Do not invent a printed/physical page mapping.
- element_id identifies a preserved element. Both page and element may be supplied.
- The validator checks quotes at the claimed anchor after whitespace/NFKC
  normalization. It does not validate paraphrases or scientific entailment.
- Quotes must contain non-whitespace text after normalization, including when
  the source is an attached PDF without extracted text.
- Full-text screening, quality and extraction use document evidence.
- Tables represented in Docling JSON retain structured export and anchors;
  important values must still be checked in the original PDF.

Example fragment (replace every identifier and quotation with real packet data):

```json
{
  "source": "document",
  "document_id": "doc_actual_identifier",
  "page": 2,
  "element_id": "actual_element_identifier",
  "quote": "An exact passage present at the claimed source."
}
```

## Extraction and quality values

Each values entry has status, value and evidence. For `observed`, value and
evidence are required. For `not_reported`, `not_applicable` or `unclear`, value
must be null. Not reported cannot be proven merely from a missing retrieval hit;
the reviewer should inspect the relevant full text.

Protocol extraction types are text, number, integer, boolean and list. Variable
IDs, definitions, required flags, allowed choices and research-question mappings
are user-defined. Quality drafts use all configured checklist IDs and answers.
For list variables with configured choices, every list member must be an allowed
choice. For scalar variables, the value itself must be an allowed choice.
Quote `yes`/`no` in YAML to prevent their interpretation as booleans by PyYAML.

## Proposals and decisions

`python -m slr_workbench submit` validates and stores an agent proposal. It changes no eligibility.
`python -m slr_workbench review` requires a human-operated terminal and produces a new decision.
Criteria on an exclusion must be applicable; the first ID is the primary reason.
Reviewer revisions supersede their earlier decision without deleting it.

If minimum_per_decision is greater than one, consensus requires the configured
number of distinct reviewer labels agreeing on the choice. Quality/extraction
also require agreement on statuses and values. Disagreements remain unresolved
until consensus or explicit human adjudication. Reviewer labels are not secure
authentication; independence is a research procedure that users must follow.

Protocol or workflow changes create a new revision. Earlier proposals cannot be
approved under that revision, and prior scientific decisions are not silently
reused. Record an amendment and reevaluate; this version has no bulk carry-forward.

## Provenance

Record wrapper, provider, model, session_id and prompt_sha256 when known. Use null
for unavailable fields and describe limitations in notes. The service hashes the
actual skill file at submission. OpenCode does not automatically fill all audit
metadata for this project; the agent/user must report available identifiers.
