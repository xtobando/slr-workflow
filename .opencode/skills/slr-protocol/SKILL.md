---
name: slr-protocol
description: Design or amend a Kitchenham-style review protocol, questions, criteria,
  quality checklist, extraction form and synthesis plan.
---

# Workflow

Read `../../../AGENTS.md` and `../../../docs/draft-contract.md` when producing structured drafts. Resolve executable commands from the project root, with the environment activated.

1. Read the existing protocol and workflow at the project root. Identify rationale, scope, research questions, sources, search strategies, eligibility, reviewer procedures, quality assessment, extraction and synthesis.
2. Ask for topic-specific information needed to make criteria operational; use the example only as a template.
3. Draft edits in English. Assign stable IDs and map extraction variables to research questions. Quote YAML strings such as "yes" and "no".
4. Pilot criteria and extraction forms against representative studies. Describe uncertainty and protocol limitations.
5. Run `python -m slr_workbench init` after edits. Explain the amendment, its reason and the review stage.
6. Hand `python -m slr_workbench approve-protocol --reviewer <identity>` to the user. Do not approve or carry forward earlier decisions yourself.
