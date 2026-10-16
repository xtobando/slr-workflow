# Search scientific databases

The workflow can query real bibliographic APIs, archive their responses, and import
verified records into the existing review. It does not download subscription PDFs,
make eligibility decisions, or treat a failed search as a scientific exclusion.
No additional Python dependencies are required.

## 1. Start with public sources

Run from the project root after setup. These examples use the macOS/Linux launcher;
on Windows replace `bash workbench.sh` with `.\workbench.ps1`. With an activated
environment, `python -m slr_workbench` accepts the same subcommands.

```sh
bash workbench.sh search-providers
bash workbench.sh search-literature arxiv --query "all:software AND cat:cs.SE" --max-results 100
bash workbench.sh search-literature dblp --query "software testing" --max-results 100
bash workbench.sh search-literature crossref --query "software testing" --max-results 100
bash workbench.sh search-literature openalex --query "software testing" --max-results 100
bash workbench.sh search-literature semantic-scholar --query '"software testing"' --max-results 100
```

Start with small pilot searches. Each command prints a manifest path under
`data/searches/<generated-run-id>/`. It saves immutable record/manifest snapshots, sanitized provider response pages,
request receipts and an atomic checkpoint. `manifest.json` and `records.json`
are convenience copies of the most recently stopped snapshot. Searching alone does **not** import records,
require protocol approval, or change review decisions. To name a run yourself, add
`--run-id dblp-pilot-001`; an existing run requires an explicit `--resume`.
Historical pages and snapshots are never overwritten. The returned `manifest`
path names an immutable snapshot; retain that exact path for import retries.

In OpenCode use `/slr-search` and describe the topic and desired providers. The
updated search skill checks your protocol, translates queries for each interface,
and uses these same Python commands. Review methodological changes yourself.

| Provider ID | Interface and intended use | Access |
| --- | --- | --- |
| `arxiv` | Preprint discovery; field/Boolean syntax, offset pages sorted by submission date ascending | Public; no key; one request per three seconds |
| `dblp` | CS/SWE bibliographic discovery; CompleteSearch terms/prefixes; no abstracts | Public |
| `crossref` | DOI and bibliographic discovery across publishers; relevance query, not Boolean filtering | Public |
| `openalex` | Broad scholarly discovery; native search syntax | Anonymous first-page searches; free key for cursor paging |
| `semantic-scholar` | Bulk scholarly search; its Boolean syntax (`+`, `\|`, `-`, quotes) | Public endpoint subject to quota; optional API key |
| `ieee` | IEEE Xplore metadata via `querytext` | Approved API key |
| `scopus` | Scopus advanced query such as `TITLE-ABS-KEY(...)`, STANDARD view | API key and institutional entitlements; optional institution token |
| `wos` | Web of Science Starter, such as `TS=(...)` | API key and appropriate API plan |
| `acm` | ACM Digital Library browser search/export | Manual import; no automated ACM API/login connector |

DBLP/Crossref discovery of ACM publications is not equivalent to executing a query
in ACM Digital Library. Export from the official ACM interface and map the export
to the existing JSON/CSV format for `import-records`. RIS/BibTeX conversion is not
part of these new commands. Do not give the model an institutional password.

Provider coverage, native query syntax, quotas and access rights differ. Planned
date windows and other `protocol.yaml` limits are **not automatically applied** by
these connectors. Express supported restrictions in the provider's query, or
record a documented downstream screening step. Do not claim an identical query
has identical semantics across databases.

## 2. Plan and resume a bounded search

Planning is offline: it prints native parameters and budgets without reading
credentials, creating a run, or contacting a provider.

```sh
bash workbench.sh search-literature arxiv --query "all:software AND cat:cs.SE" --run-id arxiv-pilot-001 --max-results 1000 --max-requests 20 --dry-run
bash workbench.sh search-literature arxiv --query "all:software AND cat:cs.SE" --run-id arxiv-pilot-001 --max-results 1000 --max-requests 20
# Continue the same query after a failure, or raise an intentional pilot cap:
bash workbench.sh search-literature arxiv --query "all:software AND cat:cs.SE" --run-id arxiv-pilot-001 --max-results 2000 --max-requests 40 --resume
```

`max-results`, `max-pages` and `max-requests` bound the **whole run**, including
previous invocations. Defaults are 100 results, 100 pages and 100 physical
requests. Allowed maxima are 100,000 results, 9,999 pages and 30,000 physical
requests. Retries count against the request cap; a request intent is recorded
before network access, so a crash may conservatively consume an unused attempt.
Increase a cap explicitly on resume. The original page size stays fixed; already
archived overflow can be normalized offline when a result cap is raised.

Version-2 searches resume by replaying successful archives and requesting the
saved next cursor/offset. They also recover a complete page saved just before a
checkpoint update. They do not request previously archived successful pages again.
An invalid/repeated page stays archived and blocks continuation pending investigation.
Changing query text or provider requires a new run ID. Refining a scientific search
is a methodological change, not completion of its original query; document it and
obtain protocol approval when substantive.

OpenAlex starts with `cursor=*` even anonymously, preserving the next cursor.
Anonymous queries stop after that first page. Continuing cursor paging needs a
user-configured key and explicit `--allow-credentials`. Check the current provider
plan and cost budget yourself before enabling it. No credential is read or sent
by default, even if configured. The workbench limits request counts but cannot
guarantee a monetary spending limit. For example, in your own terminal:

```sh
bash workbench.sh search-literature openalex --query "software testing" --run-id openalex-pilot-001 --max-results 100 --dry-run
# After reviewing your plan and authorizing its possible costs:
bash workbench.sh search-literature openalex --query "software testing" --run-id openalex-pilot-001 --max-results 1000 --max-requests 20 --allow-credentials
bash workbench.sh search-literature openalex --query "software testing" --run-id openalex-pilot-001 --max-results 2000 --max-requests 40 --allow-credentials --resume
```

arXiv uses one connection and at least three seconds between physical requests,
including retries, within one process. Do not run multiple arXiv harvesters on
other processes or machines concurrently; the provider rate applies collectively.
OpenAlex requests are conservatively paced at one per second. Rate limits and
transient HTTP failures have at most two retries per page; `Retry-After` above
30 seconds stops the run for later resumption. arXiv's 30,000-result offset limit
is an explicit `provider_offset_limit`, not proof of query exhaustion. Broad arXiv
queries may be better served by a formally refined query or its bulk interfaces.

Repeated cursors, response hashes and source IDs are detected. Crossref has a
historical exception: repeated stateful cursors may still advance pages, so they
produce a warning while duplicate pages/IDs still fail. Its August 2026 API update
uses changing cursors; the client always uses the last response's cursor and
retains the original query parameters. Provider indexes can change during a run;
a resumed run is not an immutable snapshot of the provider's entire index.

Inspect each run with `bash workbench.sh search-coverage`. Provider totals overlap:
do not sum them as unique papers. A capped relevance-ranked first page is not a
representative sample. A seed-sensitivity check requires a small, independently
verified relevant seed set; missing seeds can reflect index coverage, query syntax,
truncation or a failed request, not automatically poor relevance.

## 3. Configure a source before importing

Add the sources actually used to `protocol.yaml`, using the following as a snippet
inside its existing `sources` list. Keep the rest of your customized protocol.

```yaml
sources:
  - id: dblp
    name: DBLP API
    category: database
    planned_queries:
      - software testing
    limits:
      api_provider: dblp
```

The source ID may differ from the provider ID if `limits.api_provider` explicitly
maps it. Record your actual queries and limits. Adding a source changes the
scientific protocol revision: run `bash workbench.sh init`, then **you**, in a
separate interactive terminal, approve the new revision:

```sh
bash workbench.sh approve-protocol --reviewer YOUR_CONFIGURED_REVIEWER_ID
```

Past decisions remain stored and are not silently transferred to the new revision.
A pilot can precede approval, but inspect its query and scope before importing it.

## 4. Import the saved bundle

Use the exact path printed by the search command:

```sh
bash workbench.sh import-search data/searches/YOUR_RUN_ID/manifest.json --source dblp
bash workbench.sh deduplicate
bash workbench.sh records
bash workbench.sh status
```

Import verifies response/record checksums, validates the source mapping, and calls
the existing approved-protocol import service. The launcher backs up before import.
Repeating the import with the same bundle is idempotent; a different search needs a
new run ID. Exact DOI deduplication remains a separate, explicit operation.
Searches do not silently merge papers or advance screening stages.

`manifest.json` records the exact query, UTC time, public endpoint, paging parameters,
page hashes, result count, provider total/estimate, truncation and stop reason.
Credentials are removed from response archives and request parameters; headers
are not archived. The response archives are sanitized JSON, not original wire bytes.
Missing abstracts/authors/DOIs are marked in record metadata. Scopus STANDARD may
supply only the first author. API metadata is not full-text evidence; retrieve and
read the paper with `/slr-read-pdf` when needed.

Version-2 archives contain:

- `run.json`: immutable provider, exact query, initial UTC timestamp and page size.
- `request-NNNNNN.json`: append-only sanitized parameters, cursor, access mode and UTC request intent.
- `page-NNNN.json`: append-only response envelope with parameters, cursor, timestamps and response hash. arXiv includes the Atom XML plus parsed metadata.
- `checkpoint.json`: atomic progress, cumulative budgets, archived hashes and next cursor/offset.
- `records-NNNNNN.json` and `manifest-NNNNNN.json`: immutable snapshots for each stopped attempt.
- `records.json` and `manifest.json`: atomic convenience copies of the latest stopped snapshot. A running checkpoint can be newer than these copies.

API headers and credentials are not archived. Page files contain sanitized response
evidence, not original wire bytes; arXiv XML has been decoded as UTF-8. Original
response evidence and prior failed/capped snapshots remain available after resume.
Checksums detect accidental modification; they are not digital signatures. Keep
independent backups for disk loss or hardware failure; see [backup guidance](recovery.md).

A failed/interrupted snapshot cannot be imported. A completed capped snapshot can
be imported but retains its truncation flag. An API page ending before the stated
total stays truncated unless the interface has a documented terminal signal.
Semantic Scholar totals are estimates; token exhaustion governs its completeness.
Exhausting an interface query still does not establish exhaustive SLR coverage.

Finish the intended search before importing it. Re-importing the same immutable
snapshot is idempotent. If a run was already imported, an extended snapshot with
changed records is deliberately rejected under the same run ID by the existing
import service; preserve the original receipt and plan a separately identified
new search round rather than silently changing imported evidence. Importing a
new round can create cross-run duplicates; run explicit deduplication afterward.

Legacy version-1 bundles remain verifiable and importable through their original
`manifest.json` and `records.json`, but cannot be resumed in place. Preserve those
pilots and use a new stable run ID for a new retrieval round. No historical files
are upgraded or rewritten automatically.

## 5. Optional credentials, outside the project

Use only official API credentials; browser passwords and institutional SSO sessions
are not supported. API access and full-text subscriptions are separate permissions.
You do not need subscription keys to start with public sources.

In your own interactive terminal (the prompt hides input):

```sh
bash workbench.sh credentials openalex set
bash workbench.sh credentials openalex status
bash workbench.sh credentials openalex delete
# When you have the corresponding API entitlements:
bash workbench.sh credentials ieee set
bash workbench.sh credentials scopus set
bash workbench.sh credentials scopus set --field insttoken
bash workbench.sh credentials wos set
```

The default file is `~/.config/slr-workbench/scientific-credentials.json`, outside
the repository. It is **unencrypted**. POSIX files are owner-only; on Windows use a
private user folder with appropriate Windows permissions. You can select another
external private path with `SLR_CREDENTIALS_FILE`. Paths inside a workbench checkout
are rejected. Project backups and Git do not include the default credential file.
Protect or recreate credentials separately; never paste them into prompts, config,
tracked files, command arguments, screenshots or support messages.

Searches only read either source after `--allow-credentials`; API keys are not
used automatically. Check access conditions and possible costs first.
Environment variables override stored values. Useful for a trusted shell or a CI
secret store; do not put real values in README commands or shell history:

| Provider | Environment variables |
| --- | --- |
| OpenAlex | `SLR_OPENALEX_API_KEY` |
| Semantic Scholar | `SLR_SEMANTIC_SCHOLAR_API_KEY` |
| IEEE | `SLR_IEEE_API_KEY` |
| Scopus | `SLR_SCOPUS_API_KEY`, optional `SLR_SCOPUS_INSTTOKEN` |
| Web of Science | `SLR_WOS_API_KEY` |

`credentials status` prints only presence flags. `delete` removes a stored value,
not an overriding environment variable or the provider-side key. Requests use fixed
HTTPS endpoints, reject redirects and retry rate-limit/transient errors at most
twice. Long provider retry delays stop the search instead of blocking indefinitely.

## Official API documentation and validation

- [arXiv manual](https://info.arxiv.org/help/api/user-manual.html) and [rate/access terms](https://info.arxiv.org/help/api/tou.html)
- [Crossref cursor changes](https://community.crossref.org/t/changes-to-cursors-filtering-and-sorting-in-the-rest-api/16246)
- [DBLP search API](https://dblp.org/faq/How+to+use+the+dblp+search+API.html)
- [Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/)
- [OpenAlex authentication](https://help.openalex.org/api/authentication/) and [cursor paging](https://help.openalex.org/api/paging/)
- [Semantic Scholar API](https://api.semanticscholar.org/api-docs/)
- [IEEE metadata search](https://developer.ieee.org/docs/read/Searching_the_IEEE_Xplore_Metadata_API)
- [Scopus search API](https://dev.elsevier.com/documentation/SCOPUSSearchAPI.wadl)
- [Web of Science Starter](https://github.com/clarivate/wosstarter_python_client)

Automated tests use synthetic responses for all eight API connectors, including
OpenAlex cursor continuation, arXiv Atom and offset paging, checkpoint recovery,
physical-request budgets, repeated pages/cursors/IDs, credential redaction,
legacy imports and immutable snapshot integrity. No live API calls were used to
validate this resumable-search implementation; arXiv remains fixture-tested only.
Restricted connectors have **not** been tested with subscription credentials.

Historical public smoke checks on 2026-10-15 returned real metadata from Crossref, OpenAlex
and Semantic Scholar. DBLP returned an HTML anti-bot challenge (HTTP 202) from this
network, so its live integration could not be verified here. The client reports
this failure and does not bypass the challenge. Use another public source or a
manual export if this occurs. These checks do not guarantee ongoing availability.
