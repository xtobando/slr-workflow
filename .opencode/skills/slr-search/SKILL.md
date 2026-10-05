---
name: slr-search
description: Develop reproducible academic search strategies and import recorded JSON/CSV
  search results with source, query, dates and completeness information.
---

# Workflow

Read `../../../AGENTS.md` and `../../../docs/draft-contract.md` when producing structured drafts. Resolve executable commands from the project root, with the environment activated.

1. Read approved questions, sources, date limits and planned queries. Translate syntax per source; do not claim one universal search string fits every database.
2. Propose multiple query variants and known relevant studies for a search pilot. Have the user approve methodological changes through the protocol workflow.
3. Obtain a real database/API export or a user-supplied JSON/CSV file. Iteration 1 has no live academic API clients. Do not invent records or simulate results as real evidence.
4. Preserve the exact executed query, source/interface, timestamp with timezone, paging/limits and whether results were truncated. Put additional search details in imported metadata.
5. Run `slr import-records <export> --run-id <stable-search-run-id> --source <configured-source> --query <exact-query> --searched-at <ISO-time>`; add `--truncated` when applicable.
6. Reuse the run ID for a technical retry. Use a new ID for a genuinely new search round. Inspect `slr records` and the import receipt.
7. Keep citation searching and other sources identifiable. Record enough detail to meet PRISMA-S search reporting.
