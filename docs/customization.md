# Customization and extension contracts

All files are user-owned and editable. There is no compiled workflow or hosted
service hiding the scientific rules. Defaults are explicit and can be changed.

| Change | Edit | Consequence |
| --- | --- | --- |
| Research questions and eligibility | protocol.yaml | Register and approve a revision; revisit decisions |
| Sources, search window and limits | protocol.yaml | Limits are planned/search-reported settings, not silent automatic filters on manual imports |
| Extraction variables and quality answers | protocol.yaml | Runtime validation changes after registering a revision |
| Reviewer count and procedure | protocol.yaml | Consensus projection changes for the new revision |
| Stage order, IDs, labels and prerequisites | workflow.yaml | Update criteria stage references and semantic role mappings; register a revision |
| LLM instructions | .opencode/skills/*/SKILL.md and AGENTS.md | New submissions record the skill hash; pilot changed behavior |
| Slash commands and model overrides | .opencode/commands/*.md | Use provider/model IDs available in your OpenCode session |
| Provider and permissions | opencode.json | Keep V1/V2 field/action names distinct |
| OCR, table and formula conversion | conversion.yaml | Options are validated by the installed Docling pipeline and recorded on conversion |
| Embeddings and chunking | rag.yaml | Rebuild the fingerprinted local index; use a frozen local model path if exact weight reproducibility is needed |
| Validation/persistence/reporting | src/slr_workbench/ | Run invariants and document any methodological changes |
| Database layout | new versioned migration plus database.py | Implement a non-destructive upgrade; do not rewrite used migrations |

## Add a workflow stage

1. Add its id, name, skill, entity, choices, requires and optional extensions to
   workflow.yaml. The prerequisite graph must remain acyclic.
2. Create `.opencode/skills/<skill>/SKILL.md` with name/description frontmatter.
   Use the same portable lowercase kebab-case name in the folder and metadata.
3. Add `.opencode/commands/<skill>.md`, using an inherited model unless you want
   an explicit override. Tell the model to load the native skill and follow it.
4. Register a new configuration revision with `slr init`, and approve it.
5. Use generic draft submission for choices/evidence. For a new kind of values,
   cross-entity prerequisite or reporting milestone, extend the service validator,
   resolver and projection. Merely changing a prompt does not extend the database
   semantics.

The roles map points to record-screening, report-screening, quality and extraction
milestones. Renaming their IDs is supported when their role and criterion links
are updated. Their PRISMA meanings remain explicit. Review-stage prerequisites
can identify protocol approval using extensions.gate = protocol_approval.

## Replace or add integrations

- Metadata adapters should produce RecordInput entries and a documented search
  run. Call import_records; keep query/source/interface/time/limits and completeness.
- A converter should preserve original bytes and produce elements with id, text,
  page and optional bbox. Use attach to archive representations; retain a converter
  version/options record in your adapter metadata. The supplied adapter is Docling.
- A retrieval adapter should return report_id, document_id, element_id, page and
  exact source text. Rebuild derived indexes when source/configuration changes.
- Reporting extensions should use a consistent event cutoff and human-effective
  decisions. Never ask an LLM to supply counts or overwrite approved data.

## Policy changes

Human-only commands and evidence checks are defaults, not a restriction on your
ability to modify your own software. If you introduce automated final decisions,
add a distinct actor type and PRISMA projection instead of labeling them human.
Changing safeguards/approval rules needs a documented protocol amendment and
appropriate validation before drawing scientific conclusions.

OpenCode permissions and terminal checks are guardrails, not a security sandbox
against an agent or person with unrestricted Python/SQLite/file access. Avoid
approving arbitrary commands that bypass the intended services. The user can
modify any of these rules, with the methodological implications made explicit.
