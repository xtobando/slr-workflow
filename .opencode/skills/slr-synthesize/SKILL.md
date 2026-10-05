---
name: slr-synthesize
description: Draft a Kitchenham-style synthesis from human-approved extracted data,
  respecting comparability, quality, missingness and threats to validity.
---

# Workflow

Read `../../../AGENTS.md` and `../../../docs/draft-contract.md` when producing structured drafts. Resolve executable commands from the project root, with the environment activated.

1. Generate a current export with `slr report`; read its manifest, summary.csv, count warnings and approved extraction evidence.
2. Follow the protocol synthesis plan and research-question mappings. Group findings by configured variables.
3. Do not mix draft extraction with approved data. Use publication and underlying-study identities to avoid double-counting evidence.
4. Keep non-comparable datasets, units and evaluation conditions separate. Do not produce a meta-analysis without a justified protocol and a implemented statistical method.
5. Write an editable English draft under data/synthesis/ citing report/document anchors and stating missing evidence, contradictions and quality limitations.
6. Distinguish limitations of primary studies from limitations of the review process, including searches, extraction/conversion and LLM assistance.
7. Hand substantive conclusions and manuscript wording to the user for review. This skill does not constitute automatic publication approval.
