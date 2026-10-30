-- Proposed application schema v1. bootstrap.py seeds historical data only.
-- SQLite file must be outside a synchronized working folder.
PRAGMA foreign_keys=ON;
PRAGMA journal_mode=WAL;
PRAGMA synchronous=FULL;

CREATE TABLE IF NOT EXISTS schema_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sources (
  source_path TEXT PRIMARY KEY,
  sha256 TEXT NOT NULL,
  byte_size INTEGER NOT NULL CHECK(byte_size >= 0),
  imported_utc TEXT NOT NULL,
  representation TEXT NOT NULL,
  evidence_level TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS source_rows (
  source_path TEXT NOT NULL REFERENCES sources(source_path),
  row_number INTEGER NOT NULL CHECK(row_number > 0),
  row_sha256 TEXT NOT NULL,
  row_json TEXT NOT NULL,
  PRIMARY KEY(source_path,row_number)
);
CREATE TABLE IF NOT EXISTS assets (
  asset_id TEXT PRIMARY KEY COLLATE BINARY,
  kind TEXT NOT NULL CHECK(kind IN ('file','folder','unresolved')),
  baseline_family TEXT,
  baseline_relative_path TEXT,
  baseline_bytes INTEGER,
  baseline_extension TEXT,
  source_path TEXT REFERENCES sources(source_path),
  source_row_number INTEGER,
  imported_only INTEGER NOT NULL DEFAULT 1 CHECK(imported_only IN (0,1))
);
CREATE TABLE IF NOT EXISTS batches (
  batch_id TEXT PRIMARY KEY,
  original_order INTEGER UNIQUE, -- NULL for dynamically created child/supplemental batches
  workstream TEXT NOT NULL,
  family_or_scope TEXT NOT NULL,
  item_count INTEGER NOT NULL,
  unit TEXT NOT NULL,
  manifest_path TEXT NOT NULL REFERENCES sources(source_path),
  manifest_sha256 TEXT NOT NULL,
  saved_status TEXT NOT NULL,
  saved_completed_utc TEXT,
  original_plan_status TEXT,
  imported_row_json TEXT NOT NULL,
  local_objective_state TEXT NOT NULL DEFAULT 'HISTORICAL_ONLY',
  parent_batch_id TEXT REFERENCES batches(batch_id)
);
CREATE TABLE IF NOT EXISTS batch_members (
  batch_id TEXT NOT NULL REFERENCES batches(batch_id),
  row_number INTEGER NOT NULL,
  primary_object_id TEXT COLLATE BINARY,
  secondary_object_id TEXT COLLATE BINARY,
  row_sha256 TEXT NOT NULL,
  row_json TEXT NOT NULL,
  PRIMARY KEY(batch_id,row_number)
);
CREATE INDEX IF NOT EXISTS batch_members_object ON batch_members(primary_object_id);
CREATE TABLE IF NOT EXISTS protections (
  asset_id TEXT NOT NULL COLLATE BINARY,
  protection_role TEXT NOT NULL,
  reason TEXT NOT NULL,
  source_path TEXT NOT NULL REFERENCES sources(source_path),
  PRIMARY KEY(asset_id,protection_role,source_path)
);
CREATE TABLE IF NOT EXISTS exclusions (
  asset_id TEXT NOT NULL COLLATE BINARY,
  exclusion_kind TEXT NOT NULL,
  source_path TEXT NOT NULL REFERENCES sources(source_path),
  row_json TEXT NOT NULL,
  PRIMARY KEY(asset_id,exclusion_kind,source_path)
);
CREATE TABLE IF NOT EXISTS holds (
  hold_id TEXT PRIMARY KEY,
  asset_id TEXT NOT NULL COLLATE BINARY,
  hold_kind TEXT NOT NULL,
  reason TEXT NOT NULL,
  active INTEGER NOT NULL CHECK(active IN (0,1)),
  source_path TEXT NOT NULL REFERENCES sources(source_path),
  release_event_id INTEGER
);
CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  started_utc TEXT NOT NULL,
  ended_utc TEXT,
  code_version TEXT NOT NULL,
  configuration_sha256 TEXT NOT NULL,
  account_id TEXT,
  namespace_id TEXT,
  root_folder_id TEXT COLLATE BINARY,
  mode TEXT NOT NULL CHECK(mode IN ('offline_import','read_only','sandbox','apply')),
  environment_json TEXT NOT NULL,
  result TEXT
);
CREATE TABLE IF NOT EXISTS attempts (
  attempt_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(run_id),
  batch_id TEXT NOT NULL REFERENCES batches(batch_id),
  started_utc TEXT NOT NULL,
  ended_utc TEXT,
  objective_completed_utc TEXT,
  attempt_state TEXT NOT NULL,
  objective_outcome TEXT,
  counts_json TEXT NOT NULL DEFAULT '{}',
  evidence_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS observations (
  observation_id TEXT PRIMARY KEY,
  run_id TEXT REFERENCES runs(run_id),
  asset_id TEXT COLLATE BINARY,
  observed_utc TEXT NOT NULL,
  endpoint TEXT NOT NULL,
  account_id TEXT,
  namespace_id TEXT,
  parent_folder_id TEXT COLLATE BINARY,
  path_display TEXT,
  path_lower TEXT,
  name TEXT,
  revision TEXT,
  byte_size INTEGER,
  dropbox_content_hash TEXT,
  observation_outcome TEXT NOT NULL,
  raw_evidence_path TEXT,
  raw_evidence_sha256 TEXT,
  response_json TEXT NOT NULL,
  request_id TEXT,
  is_historical INTEGER NOT NULL DEFAULT 0 CHECK(is_historical IN (0,1))
);
CREATE INDEX IF NOT EXISTS observations_by_asset ON observations(asset_id,observed_utc);
CREATE TABLE IF NOT EXISTS scans (
  scan_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(run_id),
  root_folder_id TEXT NOT NULL COLLATE BINARY,
  namespace_id TEXT NOT NULL,
  started_utc TEXT NOT NULL,
  ended_utc TEXT,
  current_cursor TEXT,
  enumeration_exhausted INTEGER NOT NULL DEFAULT 0,
  scope_complete INTEGER NOT NULL DEFAULT 0,
  concurrent_changes_observed INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS cursor_pages (
  scan_id TEXT NOT NULL REFERENCES scans(scan_id),
  page_number INTEGER NOT NULL,
  request_cursor_sha256 TEXT,
  returned_cursor TEXT,
  response_sha256 TEXT NOT NULL,
  raw_evidence_path TEXT NOT NULL,
  has_more INTEGER NOT NULL,
  ingested_utc TEXT NOT NULL,
  PRIMARY KEY(scan_id,page_number)
);
CREATE TABLE IF NOT EXISTS work_items (
  work_id TEXT PRIMARY KEY,
  batch_id TEXT NOT NULL REFERENCES batches(batch_id),
  asset_id TEXT COLLATE BINARY,
  related_asset_id TEXT COLLATE BINARY,
  action_kind TEXT NOT NULL,
  state TEXT NOT NULL,
  policy_version TEXT NOT NULL,
  source_row_number INTEGER,
  details_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS manifests (
  manifest_id TEXT PRIMARY KEY,
  batch_id TEXT NOT NULL REFERENCES batches(batch_id),
  action_kind TEXT NOT NULL,
  manifest_sha256 TEXT UNIQUE NOT NULL,
  created_utc TEXT NOT NULL,
  policy_version TEXT NOT NULL,
  json_payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS approvals (
  approval_id TEXT PRIMARY KEY,
  manifest_sha256 TEXT NOT NULL REFERENCES manifests(manifest_sha256),
  approving_identity TEXT NOT NULL,
  approved_utc TEXT NOT NULL,
  authority_basis TEXT NOT NULL,
  decision TEXT NOT NULL CHECK(decision IN ('approve','reject','withdraw')),
  evidence_path TEXT,
  evidence_sha256 TEXT
);
CREATE TABLE IF NOT EXISTS operations (
  operation_id TEXT PRIMARY KEY,
  idempotency_key TEXT UNIQUE NOT NULL,
  work_id TEXT REFERENCES work_items(work_id),
  manifest_id TEXT NOT NULL REFERENCES manifests(manifest_id),
  approval_id TEXT NOT NULL REFERENCES approvals(approval_id),
  action_kind TEXT NOT NULL,
  source_id TEXT COLLATE BINARY,
  keeper_id TEXT COLLATE BINARY,
  replacement_id TEXT COLLATE BINARY,
  expected_source_revision TEXT,
  expected_source_hash TEXT,
  expected_keeper_revision TEXT,
  expected_keeper_hash TEXT,
  expected_bytes INTEGER,
  old_path TEXT,
  intended_new_path TEXT,
  state TEXT NOT NULL,
  intent_committed_utc TEXT NOT NULL,
  submitted_utc TEXT,
  async_job_id TEXT,
  request_id TEXT,
  receipt_path TEXT,
  receipt_sha256 TEXT,
  verified_utc TEXT,
  attribution TEXT,
  inverse_of_operation_id TEXT REFERENCES operations(operation_id)
);
CREATE TABLE IF NOT EXISTS checks (
  check_id TEXT PRIMARY KEY,
  work_id TEXT REFERENCES work_items(work_id),
  operation_id TEXT REFERENCES operations(operation_id),
  check_type TEXT NOT NULL,
  result TEXT NOT NULL CHECK(result IN ('pass','fail','unknown','not_applicable')),
  checked_utc TEXT NOT NULL,
  evidence_json TEXT NOT NULL,
  policy_version TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS backups (
  backup_id TEXT PRIMARY KEY,
  asset_id TEXT NOT NULL COLLATE BINARY,
  revision TEXT NOT NULL,
  local_path TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  dropbox_content_hash TEXT NOT NULL,
  byte_size INTEGER NOT NULL,
  verified_utc TEXT NOT NULL,
  restore_test_result TEXT NOT NULL,
  metadata_evidence_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lineage (
  edge_id TEXT PRIMARY KEY,
  from_asset_id TEXT NOT NULL COLLATE BINARY,
  to_asset_id TEXT NOT NULL COLLATE BINARY,
  relation TEXT NOT NULL CHECK(relation IN ('duplicate_of','converted_to','recovered_as','reuploaded_as')),
  source_revision TEXT,
  successor_revision TEXT,
  evidence_level TEXT NOT NULL,
  operation_id TEXT REFERENCES operations(operation_id),
  source_path TEXT REFERENCES sources(source_path),
  evidence_json TEXT NOT NULL,
  accepted_utc TEXT,
  CHECK(from_asset_id <> to_asset_id)
);
CREATE TABLE IF NOT EXISTS identity_cases (
  issue_id TEXT PRIMARY KEY,
  question TEXT NOT NULL,
  folder_id TEXT COLLATE BINARY,
  issue_scope_json TEXT NOT NULL,
  state TEXT NOT NULL,
  decision_json TEXT,
  reviewer TEXT,
  decision_utc TEXT
);
CREATE TABLE IF NOT EXISTS identity_source_links (
  issue_id TEXT NOT NULL REFERENCES identity_cases(issue_id),
  source_path TEXT NOT NULL REFERENCES sources(source_path),
  source_row_number INTEGER NOT NULL,
  link_reason TEXT NOT NULL,
  PRIMARY KEY(issue_id,source_path,source_row_number)
);
CREATE TABLE IF NOT EXISTS visual_observations (
  visual_id TEXT PRIMARY KEY,
  asset_id TEXT NOT NULL COLLATE BINARY,
  revision TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  batch_id TEXT REFERENCES batches(batch_id),
  reviewer_kind TEXT NOT NULL CHECK(reviewer_kind IN ('human','model','imported_historical')),
  reviewer_identity TEXT NOT NULL,
  model_and_prompt_json TEXT,
  reviewed_utc TEXT NOT NULL,
  video_ranges_json TEXT,
  observation_json TEXT NOT NULL,
  decision_state TEXT NOT NULL CHECK(decision_state IN ('suggested','accepted','rejected','unresolved','historical')),
  provenance_evidence_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
  sequence INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id TEXT UNIQUE NOT NULL,
  run_id TEXT REFERENCES runs(run_id),
  event_utc TEXT NOT NULL,
  entity_kind TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  previous_event_hash TEXT,
  event_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS leases (
  resource_key TEXT PRIMARY KEY,
  holder_run_id TEXT NOT NULL REFERENCES runs(run_id),
  acquired_utc TEXT NOT NULL,
  expires_utc TEXT NOT NULL,
  details_json TEXT NOT NULL
);

-- Append-only protections. Deliberate controlled migrations must be separately audited.
CREATE TRIGGER IF NOT EXISTS source_rows_no_update BEFORE UPDATE ON source_rows BEGIN SELECT RAISE(ABORT,'immutable historical source row'); END;
CREATE TRIGGER IF NOT EXISTS source_rows_no_delete BEFORE DELETE ON source_rows BEGIN SELECT RAISE(ABORT,'immutable historical source row'); END;
CREATE TRIGGER IF NOT EXISTS batch_members_no_update BEFORE UPDATE ON batch_members BEGIN SELECT RAISE(ABORT,'immutable batch membership'); END;
CREATE TRIGGER IF NOT EXISTS batch_members_no_delete BEFORE DELETE ON batch_members BEGIN SELECT RAISE(ABORT,'immutable batch membership'); END;
CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT,'append-only event ledger'); END;
CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT,'append-only event ledger'); END;
CREATE TRIGGER IF NOT EXISTS observations_no_update BEFORE UPDATE ON observations BEGIN SELECT RAISE(ABORT,'append-only observation'); END;
CREATE TRIGGER IF NOT EXISTS observations_no_delete BEFORE DELETE ON observations BEGIN SELECT RAISE(ABORT,'append-only observation'); END;
CREATE TRIGGER IF NOT EXISTS manifests_no_update BEFORE UPDATE ON manifests BEGIN SELECT RAISE(ABORT,'immutable approval manifest'); END;
CREATE TRIGGER IF NOT EXISTS manifests_no_delete BEFORE DELETE ON manifests BEGIN SELECT RAISE(ABORT,'immutable approval manifest'); END;
CREATE TRIGGER IF NOT EXISTS approvals_no_update BEFORE UPDATE ON approvals BEGIN SELECT RAISE(ABORT,'append-only approval decision'); END;
CREATE TRIGGER IF NOT EXISTS approvals_no_delete BEFORE DELETE ON approvals BEGIN SELECT RAISE(ABORT,'append-only approval decision'); END;
