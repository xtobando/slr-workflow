---
name: slr-retrieve
description: Retrieve or import full texts, preserve originals and content hashes,
  convert documents with source anchors, and track unretrieved publications.
---

# Workflow

Read `../../../AGENTS.md` and `../../../docs/draft-contract.md` when producing structured drafts. Resolve executable commands from the project root, with the environment activated.

1. Locate the retrieval stage and reports advanced by human title/abstract decisions.
2. Use a user-supplied PDF or an accessible source identified in actual metadata. Keep retrieval URLs/attempt details in the recorded rationale and metadata. Never guess a PDF's identity.
3. Run `python -m slr_workbench attach <report-id> <file.pdf> --kind pdf`. For manually prepared text, run `python -m slr_workbench attach <report-id> <file.md> --kind markdown`.
4. When original page information is known, preserve physical PDF pages using `<!-- page: 1 -->` Markdown markers. Do not invent page markers.
5. For lightweight text extraction, use the `slr-read-pdf` skill and attach its verified Markdown to the report. For OCR or structured tables, if optional Docling dependencies are installed, run `python -m slr_workbench convert <report-id> <file.pdf>`; preserve PDF, structured JSON, Markdown and converter provenance. Manually inspect important tables/formulas.
6. Hand retrieval attempts/non-retrieval to the user via `python -m slr_workbench retrieval <report-id> sought|not_retrieved --reviewer <identity> --reason <reason>`.
7. Conversion failure is an operational issue; do not classify it as scientific exclusion. Marker can be substituted by implementing the adapter's contract in docs/customization.md.
