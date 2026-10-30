CREATE TABLE IF NOT EXISTS source_provenance (
  source_path TEXT NOT NULL REFERENCES sources(source_path),
  row_number INTEGER NOT NULL,
  source_date TEXT,
  original_observation_date TEXT,
  original_execution_date TEXT,
  original_source_id TEXT,
  representation TEXT NOT NULL,
  evidence_json TEXT NOT NULL,
  PRIMARY KEY(source_path,row_number)
);
CREATE TABLE IF NOT EXISTS root_bindings (
  binding_sha256 TEXT PRIMARY KEY,
  confirmed_utc TEXT NOT NULL,
  account_id TEXT NOT NULL,
  namespace_id TEXT NOT NULL,
  root_folder_id TEXT NOT NULL COLLATE BINARY,
  sentinel_ids_json TEXT NOT NULL,
  evidence_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS inventory_entries (
  scan_id TEXT NOT NULL REFERENCES scans(scan_id),
  asset_id TEXT NOT NULL COLLATE BINARY,
  metadata_json TEXT NOT NULL,
  PRIMARY KEY(scan_id,asset_id)
);
CREATE TABLE IF NOT EXISTS current_assets (
  asset_id TEXT PRIMARY KEY COLLATE BINARY,
  namespace_id TEXT NOT NULL,
  account_id TEXT NOT NULL,
  root_folder_id TEXT NOT NULL COLLATE BINARY,
  path_lower TEXT,
  path_display TEXT,
  parent_folder_id TEXT COLLATE BINARY,
  revision TEXT,
  content_hash TEXT,
  byte_size INTEGER,
  kind TEXT NOT NULL,
  status TEXT NOT NULL,
  latest_scan_id TEXT,
  metadata_json TEXT NOT NULL,
  updated_utc TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS current_assets_path ON current_assets(namespace_id,path_lower);
CREATE TABLE IF NOT EXISTS cursor_tracks (
  binding_sha256 TEXT PRIMARY KEY REFERENCES root_bindings(binding_sha256),
  cursor TEXT NOT NULL,
  scan_id TEXT NOT NULL REFERENCES scans(scan_id),
  updated_utc TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scan_details (
  scan_id TEXT PRIMARY KEY REFERENCES scans(scan_id),
  scan_kind TEXT NOT NULL,
  state TEXT NOT NULL,
  binding_sha256 TEXT NOT NULL,
  warnings_json TEXT NOT NULL DEFAULT '[]',
  reconciliation_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS binary_checks (
  binary_check_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(run_id),
  asset_id TEXT NOT NULL COLLATE BINARY,
  revision TEXT NOT NULL,
  checked_utc TEXT NOT NULL,
  cache_path TEXT,
  sha256 TEXT,
  dropbox_content_hash TEXT,
  byte_size INTEGER,
  outcome TEXT NOT NULL,
  evidence_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS review_results (
  attempt_id TEXT NOT NULL REFERENCES attempts(attempt_id),
  row_number INTEGER NOT NULL,
  asset_id TEXT COLLATE BINARY,
  outcome TEXT NOT NULL,
  evidence_json TEXT NOT NULL,
  PRIMARY KEY(attempt_id,row_number)
);
CREATE TABLE IF NOT EXISTS issue_relations (
  from_issue_id TEXT NOT NULL REFERENCES identity_cases(issue_id),
  to_issue_id TEXT NOT NULL REFERENCES identity_cases(issue_id),
  relation TEXT NOT NULL,
  evidence_json TEXT NOT NULL,
  PRIMARY KEY(from_issue_id,to_issue_id,relation)
);
CREATE TABLE IF NOT EXISTS change_invalidations (
  invalidation_id TEXT PRIMARY KEY,
  scan_id TEXT NOT NULL REFERENCES scans(scan_id),
  asset_id TEXT COLLATE BINARY,
  reason TEXT NOT NULL,
  observed_utc TEXT NOT NULL,
  evidence_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS manifest_invalidations (
  manifest_sha256 TEXT NOT NULL REFERENCES manifests(manifest_sha256),
  invalidation_id TEXT NOT NULL REFERENCES change_invalidations(invalidation_id),
  PRIMARY KEY(manifest_sha256,invalidation_id)
);
CREATE TRIGGER IF NOT EXISTS sources_no_update BEFORE UPDATE ON sources BEGIN SELECT RAISE(ABORT,'immutable source'); END;
CREATE TRIGGER IF NOT EXISTS sources_no_delete BEFORE DELETE ON sources BEGIN SELECT RAISE(ABORT,'immutable source'); END;
CREATE TRIGGER IF NOT EXISTS provenance_no_update BEFORE UPDATE ON source_provenance BEGIN SELECT RAISE(ABORT,'immutable source provenance'); END;
CREATE TRIGGER IF NOT EXISTS provenance_no_delete BEFORE DELETE ON source_provenance BEGIN SELECT RAISE(ABORT,'immutable source provenance'); END;
CREATE TRIGGER IF NOT EXISTS batch_history_no_update BEFORE UPDATE OF original_order,workstream,family_or_scope,item_count,unit,manifest_path,manifest_sha256,saved_status,saved_completed_utc,original_plan_status,imported_row_json ON batches BEGIN SELECT RAISE(ABORT,'immutable historical batch'); END;
CREATE TRIGGER IF NOT EXISTS batches_no_delete BEFORE DELETE ON batches BEGIN SELECT RAISE(ABORT,'immutable batch'); END;
CREATE TRIGGER IF NOT EXISTS protections_no_update BEFORE UPDATE ON protections BEGIN SELECT RAISE(ABORT,'immutable protection'); END;
CREATE TRIGGER IF NOT EXISTS protections_no_delete BEFORE DELETE ON protections BEGIN SELECT RAISE(ABORT,'immutable protection'); END;
CREATE TRIGGER IF NOT EXISTS exclusions_no_update BEFORE UPDATE ON exclusions BEGIN SELECT RAISE(ABORT,'immutable exclusion'); END;
CREATE TRIGGER IF NOT EXISTS exclusions_no_delete BEFORE DELETE ON exclusions BEGIN SELECT RAISE(ABORT,'immutable exclusion'); END;
CREATE TRIGGER IF NOT EXISTS review_results_no_update BEFORE UPDATE ON review_results BEGIN SELECT RAISE(ABORT,'immutable review result'); END;
CREATE TRIGGER IF NOT EXISTS review_results_no_delete BEFORE DELETE ON review_results BEGIN SELECT RAISE(ABORT,'immutable review result'); END;
CREATE TRIGGER IF NOT EXISTS binary_checks_no_update BEFORE UPDATE ON binary_checks BEGIN SELECT RAISE(ABORT,'immutable binary result'); END;
CREATE TRIGGER IF NOT EXISTS binary_checks_no_delete BEFORE DELETE ON binary_checks BEGIN SELECT RAISE(ABORT,'immutable binary result'); END;
CREATE TRIGGER IF NOT EXISTS root_bindings_no_update BEFORE UPDATE ON root_bindings BEGIN SELECT RAISE(ABORT,'immutable root confirmation'); END;
CREATE TRIGGER IF NOT EXISTS root_bindings_no_delete BEFORE DELETE ON root_bindings BEGIN SELECT RAISE(ABORT,'immutable root confirmation'); END;

