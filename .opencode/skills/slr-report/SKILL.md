---
name: slr-report
description: Export deterministic PRISMA count data and approved summary tables, then
  draft transparent methods and checklist coverage without inventing completed steps.
---

# Workflow

Read `../../../AGENTS.md` and `../../../docs/draft-contract.md` when producing structured drafts. Resolve executable commands from the project root, with the environment activated.

1. Run `slr status` and `slr audit`. Resolve pending entries or clearly label the review as provisional.
2. Run `slr report` for count JSON, CSV tables, a simple LaTeX publication table and file hashes.
3. Read protocol revision/event cutoff from the export. Do not recompute counts with the LLM.
4. Choose the appropriate official PRISMA flow template for new/updated reviews and database/register/other sources. Iteration 1 exports count data; it does not render a publication-ready diagram or support carried-over prior reviews.
5. Map counts with their units: record, report, study. Preserve unretrieved publications and primary full-text exclusion reasons. AI suggestions approved by humans are not automatic pre-screen exclusions.
6. Use docs/prisma-checklist.md to draft methods and checklist coverage. Document reviewers, independence, disagreements, actual automation, validation, protocol access/amendments and data/code availability.
7. Keep missing checklist information marked as unresolved. Exported tables/diagram counts alone do not establish PRISMA compliance.
