---
name: slr-quality
description: Draft methodological quality assessment using the approved study-specific
  checklist and full-text evidence, without automatic score-based exclusion.
---

# Workflow

Read `../../../AGENTS.md` and `../../../docs/draft-contract.md` when producing structured drafts. Resolve executable commands from the project root, with the environment activated.

1. Find the quality role and obtain a packet for a human-included report.
2. Read every quality item and its allowed answers from protocol.yaml. Do not apply a generic checklist or an invented threshold.
3. Fill the draft values dictionary with one entry per checklist ID. Use observed plus an allowed answer and exact document evidence, or an explicit uncertainty/missingness status with null.
4. Separate author-reported limitations from your methodological appraisal. Do not infer a procedure happened merely because it is common practice.
5. Submit the quality draft and hand human review to the user. Describe how the approved synthesis plan uses quality; this version does not turn a checklist score into an automatic exclusion.
