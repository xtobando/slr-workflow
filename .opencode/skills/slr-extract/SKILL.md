---
name: slr-extract
description: Extract user-defined research variables into typed, evidence-backed drafts
  with explicit missingness and human approval before summary export.
---

# Workflow

Read `../../../AGENTS.md` and `../../../docs/draft-contract.md` when producing structured drafts. Resolve executable commands from the project root, with the environment activated.

1. Locate the extraction role and read a packet for a report that satisfies its prerequisites.
2. Read protocol extraction definitions, types, choices, required flags and research-question mappings. Never assume a fixed methodology/algorithm/metric schema.
3. Populate required variables. Use observed with a value and exact document evidence; otherwise use not_reported, not_applicable or unclear with null.
4. Preserve metric units, dataset, experimental split, baseline and evaluation conditions. Keep author claims distinct from synthesis inferences.
5. Do not fill absent numbers from an abstract, a cited paper, background knowledge or arithmetic assumptions. Missingness is valid output.
6. Write the draft JSON and run `python -m slr_workbench submit`. Hand `python -m slr_workbench review` to the user. For human corrections, supply an editable full draft as --decision-file.
7. Only human-approved extraction is used in deterministic summary exports. Do not write values directly to SQLite or CSV.
