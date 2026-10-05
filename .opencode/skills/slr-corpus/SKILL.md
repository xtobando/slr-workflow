---
name: slr-corpus
description: Retrieve and answer questions about included review evidence with verified
  publication/document anchors, using literal search or optional local Chroma.
---

# Workflow

Read `../../../AGENTS.md` and `../../../docs/draft-contract.md` when producing structured drafts. Resolve executable commands from the project root, with the environment activated.

1. Use `slr status` to confirm included publications. Answer numerical workflow/decision questions from SQLite-derived CLI output.
2. For evidence queries, use `slr search-corpus <literal phrase>` or, after optional dependency installation, `slr index-corpus` and `slr retrieve <query>`.
3. Inspect retrieved snippets and their report_id, document_id, element_id and page. A vector distance is not calibrated relevance probability.
4. Cite each supported factual claim to its actual retrieved document/anchor. Read additional context when the fragment cannot establish the interpretation.
5. Label synthesis inferences explicitly; preserve contradictions and say when evidence is insufficient. A citation's existence does not prove entailment.
6. Keep tables/experimental conditions together when possible. The initial Chroma adapter uses configurable character windows, so evaluate retrieval quality before relying on it.
7. Changing the protocol, corpus or RAG config creates a different index fingerprint. Re-index instead of silently querying stale evidence. Do not change eligibility from chat.
