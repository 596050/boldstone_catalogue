-- Logical standalone schema for FLAT-20261015. Do not overwrite an old database.
PRAGMA foreign_keys = ON;
CREATE TABLE schema_versions (version TEXT PRIMARY KEY, installed_utc TEXT NOT NULL);
CREATE TABLE runs (
 run_id TEXT PRIMARY KEY, account_id TEXT NOT NULL, root_id TEXT NOT NULL,
 root_context_json TEXT NOT NULL, input_digest TEXT NOT NULL,
 started_utc TEXT NOT NULL, ended_utc TEXT, status TEXT NOT NULL
);
CREATE TABLE source_records (
 source_key TEXT PRIMARY KEY, filename TEXT NOT NULL, file_sha256 TEXT NOT NULL,
 source_row INTEGER, source_date TEXT, raw_json TEXT NOT NULL
);
CREATE TABLE routing_rules (
 rule_id TEXT PRIMARY KEY, source_key TEXT REFERENCES source_records(source_key),
 source_folder_id TEXT NOT NULL COLLATE BINARY, action TEXT NOT NULL,
 family_id TEXT NOT NULL COLLATE BINARY, target_relative TEXT,
 direct_files_only INTEGER NOT NULL CHECK(direct_files_only IN (0,1)),
 UNIQUE(source_folder_id, action)
);
CREATE TABLE snapshots (
 snapshot_id TEXT PRIMARY KEY, run_id TEXT REFERENCES runs(run_id),
 account_id TEXT NOT NULL, root_context_json TEXT NOT NULL,
 started_utc TEXT NOT NULL, finished_utc TEXT, is_complete INTEGER NOT NULL DEFAULT 0,
 cursor_ref TEXT, evidence_sha256 TEXT
);
CREATE TABLE observations (
 observation_id TEXT PRIMARY KEY, snapshot_id TEXT REFERENCES snapshots(snapshot_id),
 object_id TEXT NOT NULL COLLATE BINARY, object_kind TEXT NOT NULL,
 parent_id TEXT COLLATE BINARY, family_id TEXT COLLATE BINARY,
 path_display TEXT NOT NULL, path_key TEXT NOT NULL, name TEXT NOT NULL,
 revision TEXT, size_bytes INTEGER, dropbox_hash TEXT,
 client_modified TEXT, server_modified TEXT, observed_utc TEXT NOT NULL,
 access_json TEXT, evidence_ref TEXT NOT NULL,
 UNIQUE(snapshot_id, object_id)
);
CREATE TABLE protections (
 protection_id TEXT PRIMARY KEY, object_id TEXT NOT NULL COLLATE BINARY,
 action_scope TEXT NOT NULL, reason TEXT NOT NULL, source_key TEXT,
 active INTEGER NOT NULL CHECK(active IN (0,1)), cleared_by TEXT, clearance_evidence TEXT
);
CREATE TABLE storage_decisions (
 decision_id TEXT PRIMARY KEY, target_relative TEXT NOT NULL, target_version TEXT NOT NULL,
 decision TEXT NOT NULL, identity_status TEXT NOT NULL,
 decided_by TEXT NOT NULL, decided_utc TEXT NOT NULL, evidence_ref TEXT NOT NULL,
 supersedes TEXT REFERENCES storage_decisions(decision_id)
);
CREATE TABLE backups (
 backup_id TEXT PRIMARY KEY, object_id TEXT NOT NULL COLLATE BINARY,
 revision TEXT NOT NULL, bytes INTEGER NOT NULL, dropbox_hash TEXT NOT NULL,
 local_sha256 TEXT NOT NULL, local_path TEXT NOT NULL, verified_utc TEXT NOT NULL
);
CREATE TABLE manifests (
 manifest_id TEXT PRIMARY KEY, run_id TEXT REFERENCES runs(run_id),
 version INTEGER NOT NULL, manifest_sha256 TEXT NOT NULL UNIQUE,
 contents_json TEXT NOT NULL, created_utc TEXT NOT NULL
);
CREATE TABLE approvals (
 approval_id TEXT PRIMARY KEY, manifest_id TEXT NOT NULL REFERENCES manifests(manifest_id),
 manifest_sha256 TEXT NOT NULL, approved_by TEXT NOT NULL,
 approved_utc TEXT NOT NULL, authorization_evidence TEXT NOT NULL,
 revoked_utc TEXT
);
CREATE TABLE operations (
 operation_id TEXT PRIMARY KEY, operation_key TEXT NOT NULL UNIQUE,
 run_id TEXT NOT NULL REFERENCES runs(run_id), family_batch_id TEXT NOT NULL,
 child_batch_id TEXT NOT NULL, manifest_id TEXT NOT NULL REFERENCES manifests(manifest_id),
 action TEXT NOT NULL, source_id TEXT COLLATE BINARY,
 expected_before_json TEXT NOT NULL, intended_after_json TEXT NOT NULL,
 backup_id TEXT REFERENCES backups(backup_id), approval_id TEXT REFERENCES approvals(approval_id),
 state TEXT NOT NULL, submitted_utc TEXT, verified_utc TEXT,
 job_id TEXT, result_json TEXT, verification_json TEXT
);
CREATE TABLE dependencies (
 operation_id TEXT NOT NULL REFERENCES operations(operation_id),
 depends_on TEXT NOT NULL REFERENCES operations(operation_id),
 PRIMARY KEY(operation_id, depends_on), CHECK(operation_id <> depends_on)
);
CREATE TABLE asset_provenance (
 asset_id TEXT PRIMARY KEY COLLATE BINARY, original_parent_id TEXT COLLATE BINARY,
 original_name TEXT NOT NULL, original_path TEXT NOT NULL,
 source_context_json TEXT NOT NULL, identity_status TEXT NOT NULL,
 provenance_evidence_ref TEXT, current_observation_id TEXT REFERENCES observations(observation_id)
);
CREATE TABLE relations (
 relation_id TEXT PRIMARY KEY, subject_id TEXT NOT NULL COLLATE BINARY,
 predicate TEXT NOT NULL, object_id TEXT NOT NULL COLLATE BINARY,
 evidence_ref TEXT NOT NULL, status TEXT NOT NULL
);
CREATE TABLE events (
 sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE,
 run_id TEXT NOT NULL REFERENCES runs(run_id), operation_id TEXT REFERENCES operations(operation_id),
 recorded_utc TEXT NOT NULL, event_type TEXT NOT NULL, payload_json TEXT NOT NULL
);
CREATE TRIGGER immutable_events_update BEFORE UPDATE ON events
 BEGIN SELECT RAISE(ABORT,'Events are append-only'); END;
CREATE TRIGGER immutable_events_delete BEFORE DELETE ON events
 BEGIN SELECT RAISE(ABORT,'Events are append-only'); END;
CREATE TABLE export_outbox (
 sequence INTEGER PRIMARY KEY REFERENCES events(sequence), exported_utc TEXT, output_ref TEXT
);
CREATE TABLE exceptions (
 exception_id TEXT PRIMARY KEY, run_id TEXT REFERENCES runs(run_id),
 object_id TEXT COLLATE BINARY, category TEXT NOT NULL, evidence_json TEXT NOT NULL,
 status TEXT NOT NULL, resolution_event_id TEXT REFERENCES events(event_id)
);
CREATE INDEX observations_object ON observations(object_id, observed_utc);
CREATE INDEX operations_status ON operations(run_id, state);
