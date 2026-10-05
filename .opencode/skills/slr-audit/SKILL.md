---
name: slr-audit
description: Audit source provenance, configuration revisions, human decisions, evidence
  anchors, counts and local archive integrity before reporting or resuming a review.
---

# Workflow

Read `../../../AGENTS.md` and `../../../docs/draft-contract.md` when producing structured drafts. Resolve executable commands from the project root, with the environment activated.

1. Run `slr audit`, `slr status` and `python scripts/validate_project.py` from the active environment.
2. Inspect hash-chain/integrity results, source completeness flags, pending decisions, study-link coverage and extraction approvals.
3. Trace a sample of claims back to original PDFs, not only converted text. Exact quotation validation does not assess scientific entailment.
4. Inspect the registered protocol revision and amendments. Do not silently reuse decisions from earlier revisions.
5. Distinguish agent suggestions, human judgments and mechanical operations. Confirm reviewer identity labels and actual provider/model metadata were not invented.
6. Explain that local triggers/hash chains detect some changes but do not secure the history against a file owner who can rewrite the entire database/history.
7. Report concrete discrepancies with entity/event IDs. Never repair scientific decisions by editing stored rows; propose an audited operation or new revision.
