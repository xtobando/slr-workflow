# Human review and the pilot checkpoint

The starter protocol and example papers are synthetic. Generating a queue or
passing tests does not complete a real screening pilot. Connect the actual review
configuration and artifacts before interpreting its progress. The software never
infers prosthesis, EMG or robotics evidence streams from a title: stream filters
use only explicit imported `metadata.evidence_stream` or
`metadata.evidence_streams` labels. Unlabelled records remain unlabelled.

## Inspect before drafting more

Run from the project root after setup. The launcher finds the project environment.
On Windows replace `bash workbench.sh` with `.\workbench.ps1`.

```sh
bash workbench.sh pending-review --reviewer REVIEWER_ID
bash workbench.sh review-sheet --reviewer REVIEWER_ID
bash workbench.sh pilot-evaluation
```

Use a reviewer identity configured in `protocol.yaml`. These commands are read-only
projections. They do not initialize a missing review database, approve a protocol,
submit proposals, retrieve papers or record decisions. A missing database is an
explicit blocker, not an empty completed review.

`review-sheet` creates a fresh directory under `data/review-packages/` containing:

- `review.md`: numbered source/evidence summary, unresolved questions and individual
  command handoffs for macOS/Linux and Windows PowerShell.
- `review.json`: the same snapshot with machine-readable judgments, blockers and
  proposal identifiers.
- `manifest.json`: file hashes, protocol revision and audit snapshot sequence/hash.

Existing packages are never overwritten. Treat them as point-in-time derived
exports: rerun after decisions or configuration changes, and retain the original
research artifacts independently. `data/` is ignored by Git and is not uploaded
when software changes are pushed.

## Keep batches manageable

The pending view and review sheet default to at most 25 targets. Start smaller if
the pilot has many boundary cases or the reviewer has limited capacity. The output
reports total matching targets, pending targets and those remaining after the
sheet. After an individual human decision, rerun the queue: completed targets are
omitted automatically. Explicit offsets page one snapshot; do not increment an
offset while simultaneously removing completed targets, because that skips work.

Filters use the actual configured stage ID, exact search-run/proposal/entity IDs
or imported metadata batch labels. Consult `--help` for the exposed options.
Never assume the example stage IDs or research variables remain unchanged.

For a selected reviewer, an unresolved consensus may remain visible after their
judgment. Check the latest reviewer labels and the configured disagreement
procedure; another LLM recommendation is not the missing independent reviewer.
The service's existing individual decision command remains the only approval path.

## Human decisions and independence

Open the generated sheet. Check the cited source, criterion and physical page or
element anchor. Execute each provided `review` command yourself in a separate
interactive terminal. Accept, modify or defer individually. The agent must not
run those commands, pipe confirmations, or approve its own recommendation.

When `reviewers.independent` is true, initial sheets hide recommendations,
rationale, evidence selections, extracted values and other human judgments. The
sheet gives a neutral `packet` command and a review command with
`--decision-file data/drafts/human-PROPOSAL_ID.json`. Read the packet and sources,
prepare your own complete schema-valid decision JSON, then run that command. The
existing review interface displays your supplied decision file; running it without
a decision file would display the original proposal before your assessment.

Use explicit human `--unblind` only when it is methodologically appropriate to
reveal recommendations. Uncertainty filtering is refused on blind sheets because
membership would disclose a recommendation. Reviewer labels are audit labels,
not authenticated accounts or proof of research independence.

## Evaluate the pilot

`pilot-evaluation` distinguishes draft recommendations from effective current
human judgments. It uses the latest judgment for each reviewer and the existing
consensus/adjudication rules. Quality/extraction comparisons include statuses and
values, not only the approval label. Missingness remains explicit.

A decision referring to an older proposal remains stored and visible; a newer
proposal does not silently supersede it. Agreement totals include only comparisons
on the current displayed proposal with satisfied current prerequisites. Historical
revision targets are separate, never get current review commands, and are not
silently carried forward. Include them explicitly for inspection when useful.

Descriptive agreement is not model accuracy or scientific validation. Inspect
recurring boundary cases, omitted abstracts, unclear relevance, disagreement and
required-field burden. For each unresolved case, the queue gives a precise
question, the evidence needed, and the next permitted action. Do not infer absence
of a method or numerical result merely from an unsuccessful text search.
Operational interpretations must follow the approved protocol. Substantive changes
to eligibility, gates, required fields or evidence rules require a protocol/workflow
amendment, `init`, and separate human approval before reevaluation.

## Full-text pilot checkpoint

The evaluation includes report pathways with the actual configured stage IDs,
record-screening inclusion, attached-document kinds and prerequisite blockers.
Document presence alone does not prove successful retrieval, readable text or
scientific eligibility. The list is diagnostic; it does not select representative
papers or manufacture evidence-stream coverage.

For actual eligible candidates, follow this order:

1. Verify bibliographic identity and attempt permitted public-source discovery.
   Respect API/access restrictions and do not request credentials in chat.
2. Preserve original PDF and hashes. Use `/slr-read-pdf` or `read-pdf` to inspect
   Markdown conversion without changing review state. Check physical page anchors,
   tables and missing text against the original.
3. Follow the configured screening prerequisites before formal attachment and
   full-text drafting. Hand retrieval-status decisions to the human terminal.
4. Submit full-text eligibility drafts through `submit`; await required human
   decisions. Then draft quality; await its required approval. Only then extract
   where the configured dependencies require it.
5. Keep direct prosthesis evidence, supporting EMG evidence, robotic manipulation,
   simulation, offline recordings and intact-limb/user populations distinct when
   those distinctions are actually defined by the review. Transfer evidence does
   not establish clinical efficacy.
6. Evaluate extraction burden and missingness on representative real candidates.
   Propose amendments rather than dropping required fields silently.

Missing abstract, inaccessible PDF, conversion failure and unresolved eligibility
are separate states. None is an automatic exclusion. An empty package contains no
real pilot progress; the next step is to restore/configure the actual review, not
to invent papers, approve a demonstration protocol, or submit placeholder drafts.
