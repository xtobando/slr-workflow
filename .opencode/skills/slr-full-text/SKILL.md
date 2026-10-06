---
name: slr-full-text
description: Draft full-text eligibility judgments with exact document evidence, primary
  exclusion reasons and separate study/publication identities.
---

# Workflow

Read `../../../AGENTS.md` and `../../../docs/draft-contract.md` when producing structured drafts. Resolve executable commands from the project root, with the environment activated.

1. Read workflow roles and run `python -m slr_workbench packet <report-screening-stage> <report-id>`.
2. Review actual attached full text. A PDF alone may require manual inspection or conversion; a citation to an abstract does not constitute full-text evidence.
3. Evaluate applicable criteria. Write a schema-valid draft using document_id, exact quote, and page/element anchors where known.
4. Use unclear when the available evidence cannot establish eligibility. For exclusion, list the primary criterion first; retain other relevant criteria separately in the same list.
5. Submit the draft with `python -m slr_workbench submit` and hand review to the user. Do not create final inclusion yourself.
6. For included reports, suggest potential shared-study relationships with evidence. Hand `python -m slr_workbench link-study` to the user; never assume one report equals one study.
