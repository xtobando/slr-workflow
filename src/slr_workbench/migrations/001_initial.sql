-- Immutable source entities and append-only scientific decisions.
CREATE TABLE IF NOT EXISTS protocol_versions (
  revision TEXT PRIMARY KEY, review_id TEXT NOT NULL,
  protocol_yaml TEXT NOT NULL, workflow_yaml TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS search_runs (
  id TEXT PRIMARY KEY, source_id TEXT NOT NULL,
  category TEXT NOT NULL CHECK(category IN ('database','register','other')),
  query TEXT NOT NULL, searched_at TEXT NOT NULL, protocol_revision TEXT NOT NULL,
  import_sha256 TEXT NOT NULL, raw_import TEXT NOT NULL,
  truncated INTEGER NOT NULL CHECK(truncated IN (0,1)),
  FOREIGN KEY(protocol_revision) REFERENCES protocol_versions(revision)
);
CREATE TABLE IF NOT EXISTS reports (
  id TEXT PRIMARY KEY, doi TEXT, title TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS reports_doi ON reports(doi) WHERE doi IS NOT NULL;
CREATE TABLE IF NOT EXISTS records (
  id TEXT PRIMARY KEY, search_run_id TEXT NOT NULL, source_record_id TEXT NOT NULL,
  report_id TEXT NOT NULL, title TEXT NOT NULL, abstract TEXT NOT NULL,
  year INTEGER, raw_metadata TEXT NOT NULL,
  FOREIGN KEY(search_run_id) REFERENCES search_runs(id),
  FOREIGN KEY(report_id) REFERENCES reports(id),
  UNIQUE(search_run_id, source_record_id)
);
CREATE INDEX IF NOT EXISTS records_report ON records(report_id);
CREATE TABLE IF NOT EXISTS studies (
  id TEXT PRIMARY KEY, label TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY, report_id TEXT NOT NULL,
  kind TEXT NOT NULL CHECK(kind IN ('pdf','markdown','docling_json')),
  sha256 TEXT NOT NULL, local_path TEXT NOT NULL,
  text_content TEXT, elements_json TEXT NOT NULL, created_at TEXT NOT NULL,
  FOREIGN KEY(report_id) REFERENCES reports(id), UNIQUE(report_id,kind,sha256)
);
CREATE TABLE IF NOT EXISTS proposals (
  id TEXT PRIMARY KEY, protocol_revision TEXT NOT NULL,
  entity_type TEXT NOT NULL CHECK(entity_type IN ('review','record','report','study')),
  entity_id TEXT NOT NULL, stage TEXT NOT NULL, payload TEXT NOT NULL,
  skill_sha256 TEXT, created_at TEXT NOT NULL,
  FOREIGN KEY(protocol_revision) REFERENCES protocol_versions(revision)
);
CREATE TABLE IF NOT EXISTS decisions (
  id TEXT PRIMARY KEY, protocol_revision TEXT NOT NULL,
  entity_type TEXT NOT NULL CHECK(entity_type IN ('review','record','report','study')),
  entity_id TEXT NOT NULL, stage TEXT NOT NULL, reviewer TEXT NOT NULL,
  choice TEXT NOT NULL, rationale TEXT NOT NULL, criteria_json TEXT NOT NULL,
  evidence_json TEXT NOT NULL, values_json TEXT NOT NULL,
  proposal_id TEXT, adjudication INTEGER NOT NULL DEFAULT 0 CHECK(adjudication IN (0,1)),
  supersedes TEXT, created_at TEXT NOT NULL,
  FOREIGN KEY(protocol_revision) REFERENCES protocol_versions(revision),
  FOREIGN KEY(proposal_id) REFERENCES proposals(id),
  FOREIGN KEY(supersedes) REFERENCES decisions(id)
);
CREATE INDEX IF NOT EXISTS decisions_scope ON decisions(protocol_revision,entity_type,entity_id,stage);
CREATE TABLE IF NOT EXISTS events (
  sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE,
  protocol_revision TEXT NOT NULL, event_type TEXT NOT NULL,
  entity_type TEXT NOT NULL, entity_id TEXT NOT NULL,
  actor_type TEXT NOT NULL CHECK(actor_type IN ('human','mechanical','agent')),
  actor_id TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL,
  previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL UNIQUE,
  FOREIGN KEY(protocol_revision) REFERENCES protocol_versions(revision)
);
-- rowid ordering is local insertion order. Scientific state is reconstructed from these entries.
CREATE VIEW IF NOT EXISTS latest_reviewer_decisions AS
SELECT d.* FROM decisions d WHERE NOT EXISTS (
 SELECT 1 FROM decisions newer
 WHERE newer.protocol_revision=d.protocol_revision AND newer.entity_type=d.entity_type
 AND newer.entity_id=d.entity_id AND newer.stage=d.stage AND newer.reviewer=d.reviewer
 AND newer.rowid>d.rowid
);
PRAGMA user_version = 1;
