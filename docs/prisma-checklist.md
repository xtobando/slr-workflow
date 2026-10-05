# Reporting coverage and methodological references

PRISMA 2020 is a reporting guideline. Kitchenham/Charters guides software-engineering
review planning, conduct and synthesis. Software supports transparent records;
it does not make a review rigorous by itself.

| Reporting area | Project evidence | Human work still needed |
| --- | --- | --- |
| Rationale/questions and eligibility | Approved protocol snapshots | Validate scientific scope and operational criteria |
| Sources/search strategies | Recorded queries, timestamps, raw imports, truncation flags | Verify completeness, exact interfaces, dates, update searches and PRISMA-S detail |
| Selection/data collection | Proposals, reviewer decisions, evidence, skill/protocol hashes | Report actual reviewer independence, disagreements and automation validation |
| Quality/risk of bias | Configured checklist and reviewed values | Choose justified study-specific instruments and interpret their limitations |
| Selection results | Counts by record/report/study, retrieval status, primary exclusion reasons | Resolve pending work and choose the appropriate official flow template |
| Synthesis | Approved extraction and configurable synthesis plan | Perform a justified analysis, assess comparability/uncertainty and review conclusions |
| Discussion/limitations | Synthesis skill instructions | Describe primary evidence and review-process limitations honestly |
| Protocol/access/amendments | Approval reasons and exact protocol/workflow versions | Publish/access the protocol where appropriate and explain deviations |
| Support/conflicts/data availability | Protocol extensions and exported manifests | Supply actual funding, competing-interest and availability statements |

This iteration's JSON is count data for a new review. It records source categories,
but does not render the official multi-branch diagram or handle studies carried
over from a previous review. Search-derived records follow title/abstract screening
in this starter; document your actual pathway if other-source identification differs.

## Count semantics

- Records identified preserve each source search result. A retry with the same
  run identity does not add records again.
- Exact same-publication record duplicates are preserved and marked removed.
- Records screened require an effective human decision. Unclear judgments are
  separately visible and remain unresolved; they are not exclusions.
- Reports sought/retrieved/not retrieved are distinct from eligibility outcomes.
- Full-text exclusion reasons use the first recorded criterion as the primary reason.
- Included reports and included underlying studies are separate counts. Missing
  human-confirmed study links make the study count provisional.
- Automatic pre-screen ineligibility is zero in this iteration: agents only propose.
- Multi-reviewer disagreements remain pending until consensus/adjudication.

## Primary references

- [Kitchenham and Charters, 2007, EBSE-2007-01, version 2.3](https://homepages.dcc.ufmg.br/~figueiredo/disciplinas/papers/guidelines-kitchenham.pdf)
- [PRISMA 2020 statement/checklists](https://www.prisma-statement.org/prisma-2020)
- [Expanded PRISMA 2020 checklist](https://www.prisma-statement.org/s/PRISMA_2020_expanded_checklist-yc78.pdf)
- [Official flow templates](https://www.prisma-statement.org/prisma-2020-flow-diagram)
- [PRISMA-S search reporting](https://link.springer.com/article/10.1186/s13643-020-01542-z)

