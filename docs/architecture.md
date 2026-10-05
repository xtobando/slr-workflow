# Architecture and scientific state

## Four layers

1. Configuration: protocol.yaml defines the review; workflow.yaml defines stages
   and prerequisites; conversion.yaml/rag.yaml configure optional adapters.
2. Mechanical services: import/archive/deduplicate/validate/export operations run
   in typed Python, independent of the current LLM provider.
3. Agent workflows: OpenCode loads the stage skill and uses its current model to
   draft recommendations, extraction and synthesis. All instructions are visible.
4. Reporting: Python projects effective human decisions into count data and tables.
   OpenCode can draft narrative methods/results with original evidence references.

## Persistence

The SQLite schema distinguishes raw search records, publications and underlying
studies. A search run records the executed query, source category, timestamp,
raw import, content hash and completeness flag. Multiple records can point to
one publication. Reports and studies are linked by human-recorded events.

Protocol/workflow versions retain their exact YAML. Their combined hash is the
revision. Proposals retain Pydantic payloads plus the submitted skill hash.
Decisions contain reviewer, choice, reasons, criteria, evidence, extracted values
and a supersedes link. Append-only triggers protect source/audit tables against
ordinary UPDATE/DELETE operations. Foreign keys are enabled on every connection.

Events include sequence, timestamp, actor type/label, payload, protocol revision,
previous hash and event hash. Their ordering, rather than wall-clock ordering,
defines history. SQLite writes use short BEGIN IMMEDIATE transactions; no model
call or human interaction holds a transaction open. WAL permits concurrent reads
but does not provide multiple concurrent writers.

Original documents live in the artifact directory and are referenced by content
hash and stable ID. Derived Markdown and structured JSON remain separate,
immutable representations. Docling conversion events record converter version,
options and input/output document IDs. Multi-page elements retain source pages
and regions rather than fabricating a single-page location for all their text.

## Effective decisions

An agent proposal changes no eligibility. Interactive review adds a human decision.
The latest entry per reviewer determines consensus. A configured minimum reviewer
count and agreement are required; quality/extraction also require matching values.
Adjudication requires prior judgments from the required reviewers and a distinct
explicit human action. Independent/blind assessment is a research procedure,
not enforced identity verification.

The report's current inclusion pathway includes valid upstream record screening.
Withdrawn upstream inclusion removes the report from corpus retrieval. Withdrawn
quality approval removes dependent extraction from summary export. Earlier data
remains auditable. Protocol changes require fresh decisions; bulk carry-forward
has not been implemented.

## Exports and retrieval

Reporting uses a consistent read transaction and a chosen event cutoff. Search
imports, decisions, retrieval and study links after the cutoff are excluded.
Counts expose pending/unclear work, non-retrieval and study-link uncertainty.
Each export records its protocol revision, sequence and event head hash. Table
bytes are hashed in a manifest. Historical projections use the currently selected
protocol revision: select the corresponding saved protocol/workflow to reproduce
an older revision; --at-sequence alone does not switch protocol versions.

Literal retrieval works without embeddings. The optional Chroma cache fingerprint
includes current protocol, selected included documents, RAG configuration and
adapter package versions. It is not the authoritative scientific database. Model
names alone do not pin remote model weights; use a frozen local embedding model
when exact weight reproducibility matters.

## Limits of guarantees

Exact quote/anchor validation checks source existence, not truth, study quality
or semantic entailment. RAG citations need human interpretation. Local triggers
and hash chains are not tamper-proof against a file owner who can replace the
database and rewrite the whole chain. Reviewer identities are audit labels;
OpenCode/terminal rules are workflow guardrails rather than secure authentication.
No credentials are handled by this project's Python code.
