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
bash workbench.sh search-literature dblp --query "software testing" --max-results 100
bash workbench.sh search-literature crossref --query "software testing" --max-results 100
bash workbench.sh search-literature openalex --query "software testing" --max-results 100
bash workbench.sh search-literature semantic-scholar --query '"software testing"' --max-results 100
```

Start with small pilot searches. Each command prints a manifest path under
`data/searches/<generated-run-id>/`. It saves `records.json`, sanitized provider
response pages and `manifest.json`. Searching alone does **not** import records,
require protocol approval, or change review decisions. To name a run yourself, add
`--run-id dblp-pilot-001`; an existing directory is never overwritten.

In OpenCode use `/slr-search` and describe the topic and desired providers. The
updated search skill checks your protocol, translates queries for each interface,
and uses these same Python commands. Review methodological changes yourself.

| Provider ID | Interface and intended use | Access |
| --- | --- | --- |
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

## 2. Configure a source before importing

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

## 3. Import the saved bundle

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

The default result cap is 100, configurable from 1 to 10,000; there is also a
100-page ceiling. Semantic Scholar may return a larger page than the requested
local cap; the full sanitized page is archived and the selected subset is marked
truncated. An anonymous OpenAlex search stops after its first page. Check
`truncated` and `stop_reason` before claiming completeness. Exhausting an API query
is not proof of exhaustive SLR coverage, and provider indexes change over time.

Failed/interrupted searches preserve available partial evidence and are rejected
by `import-search`. Retry the API search with a **new** run ID after resolving the
problem. A completed but capped search can be imported and retains its truncation
flag. A retry of an already completed **import** uses the original bundle offline.
Checksums detect accidental modification; they are not digital signatures.
A process kill, full disk or hardware failure may leave an unfinished bundle;
never infer success from files alone. See [backup guidance](recovery.md).

## 4. Optional credentials, outside the project

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

- [DBLP search API](https://dblp.org/faq/How+to+use+the+dblp+search+API.html)
- [Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/)
- [OpenAlex authentication and paging](https://help.openalex.org/api/authentication/)
- [Semantic Scholar API](https://api.semanticscholar.org/api-docs/)
- [IEEE metadata search](https://developer.ieee.org/docs/read/Searching_the_IEEE_Xplore_Metadata_API)
- [Scopus search API](https://dev.elsevier.com/documentation/SCOPUSSearchAPI.wadl)
- [Web of Science Starter](https://github.com/clarivate/wosstarter_python_client)

Automated tests use synthetic responses for all seven API connectors, including
pagination, truncation, credential redaction, failed searches and import integrity.
Restricted connectors have **not** been tested with subscription credentials.

Public smoke checks on 2026-10-15 returned real metadata from Crossref, OpenAlex
and Semantic Scholar. DBLP returned an HTML anti-bot challenge (HTTP 202) from this
network, so its live integration could not be verified here. The client reports
this failure and does not bypass the challenge. Use another public source or a
manual export if this occurs. These checks do not guarantee ongoing availability.
