---
name: slr-screen
description: Draft title/abstract eligibility recommendations for retained records,
  using protocol criteria and exact source quotations, pending human confirmation.
---

# Workflow

Read `../../../AGENTS.md` and `../../../docs/draft-contract.md` when producing structured drafts. Resolve executable commands from the project root, with the environment activated.

1. Read `slr workflow` and locate the record_screening role. Obtain retained record IDs from `slr records`/`slr status`.
2. Run `slr packet <record-screening-stage> <record-id> --output data/drafts/packet.json` and read it.
3. Evaluate only applicable protocol criteria. Distinguish include, exclude and unclear. Missing abstract or uncertain relevance is not an automatic exclusion.
4. Write a JSON draft matching schemas/draft.schema.json and the packet revision/target. Cite exact title/abstract quotations. For exclusion, list criterion IDs with the primary reason first.
5. Record known provider/model/session information; use null for unavailable identifiers. Keep the rationale concise and observable.
6. Run `slr submit <draft.json>`. Fix structural or evidence errors rather than weakening validation.
7. Hand the returned proposal ID and `slr review <proposal-id> --reviewer <identity>` to the user. Offer a blind initial human evaluation when required by the protocol.
