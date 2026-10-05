---
name: slr-deduplicate
description: Identify same-publication bibliographic duplicates while preserving source
  records and keeping multiple reports of one study distinct.
---

# Workflow

Read `../../../AGENTS.md` and `../../../docs/draft-contract.md` when producing structured drafts. Resolve executable commands from the project root, with the environment activated.

1. Read `slr records` and `slr status`. Run deduplication before screening.
2. Run `slr deduplicate` for exact normalized DOI matches; inspect the retained/duplicate pairs and underlying metadata.
3. Keep DOI-free and fuzzy matches as candidates for human inspection. Iteration 1 does not resolve fuzzy matches or merge publications manually.
4. Do not treat preprint and journal versions, or multiple publications of one investigation, automatically as duplicate records. Plan human-confirmed study links separately.
5. Do not delete source records or edit SQLite. If an exact-match identity is wrong, stop and extend the merge/reversal service with an audited operation before proceeding.
