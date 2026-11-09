"""Source-owned configuration and mount-checked, shared bulk evidence storage."""

import importlib.util
import shutil
from pathlib import Path

from lib.live_files import live_tree_bytes

from .common import atomic, canonical, digest, fields, load, name, no_links, positive, rel
from .operation_timing import phase


class StorageUnavailable(RuntimeError):
    """A transient local storage condition: leave queued work intact."""


class Project:
    def __init__(self, config):
        self.config_path = Path(config).resolve()
        raw = load(self.config_path)
        fields(
            raw,
            {
                "schema",
                "project_id",
                "project_root",
                "state_directory",
                "evidence",
                "workers",
                "recovery",
                "storage",
            },
            {
                "schema",
                "project_id",
                "project_root",
                "state_directory",
                "evidence",
                "workers",
                "recovery",
                "storage",
            },
        )
        if raw["schema"] != "marketmaker.offload_project.v1":
            raise ValueError("unsupported project configuration")
        self.id = name(raw["project_id"])
        self.root = (self.config_path.parent / raw["project_root"]).resolve(strict=True)
        if not (self.root / "research").is_dir():
            raise ValueError("project must have an existing research directory")
        self.state = no_links(self.root / rel(raw["state_directory"]), self.root)
        if self.state.is_relative_to(self.root / "research"):
            raise ValueError("queue state belongs outside the research record")
        self.evidence = raw["evidence"]
        fields(self.evidence, {"registry", "directory", "relative"}, {"relative"})
        if ("registry" in self.evidence) == ("directory" in self.evidence):
            raise ValueError("choose a registry location or an existing storage directory")
        rel(self.evidence["relative"])
        self.workers = raw["workers"]
        if not isinstance(self.workers, dict):
            raise ValueError("workers must be an object")
        for key, worker in self.workers.items():
            name(key)
            fields(worker, {"url", "token_file", "retired_reason"}, {"url", "token_file"})
            if "retired_reason" in worker and (not isinstance(worker["retired_reason"], str)
                                               or not worker["retired_reason"].strip()):
                raise ValueError("retired workers require a nonempty reason")
            from .client import Client

            Client(worker["url"], "x" * 43)  # Validate transport, without reading credentials.
        self.recovery, self.storage = raw["recovery"], raw["storage"]
        fields(
            self.recovery,
            {
                "poll_seconds",
                "backoff_initial_seconds",
                "backoff_max_seconds",
                "request_timeout_seconds",
                "resume_interrupted",
                "max_pending",
                "default_max_attempts",
                "collect_completed_nodes",
                "collection_lock_scope",
            },
            {
                "poll_seconds",
                "backoff_initial_seconds",
                "backoff_max_seconds",
                "request_timeout_seconds",
                "resume_interrupted",
                "max_pending",
                "default_max_attempts",
            },
        )
        for key, value in self.recovery.items():
            if key == "collection_lock_scope":
                if type(value) is not str or value not in {"queue", "separate"}:
                    raise ValueError('collection_lock_scope must be queue or separate')
            elif key in {"resume_interrupted", "collect_completed_nodes"}:
                if type(value) is not bool:
                    raise ValueError(key + " must be boolean")
            else:
                positive(
                    value,
                    3 if key == "default_max_attempts" else 86400,
                    integer=key in {"max_pending", "default_max_attempts"},
                )
        if self.recovery["backoff_max_seconds"] < self.recovery["backoff_initial_seconds"]:
            raise ValueError("backoff maximum is below initial delay")
        fields(
            self.storage,
            {
                "max_store_mb",
                "min_free_mb",
                "max_collection_mb",
                "max_local_state_mb",
                "local_min_free_mb",
                "release_outbox",
            },
            {
                "max_store_mb",
                "min_free_mb",
                "max_collection_mb",
                "max_local_state_mb",
                "local_min_free_mb",
                "release_outbox",
            },
        )
        for key, value in self.storage.items():
            if key == "release_outbox":
                if type(value) is not bool:
                    raise ValueError("release_outbox must be boolean")
            else:
                positive(value, 10485760)
        self.raw = raw

    def worker(self, key):
        if key not in self.workers:
            raise ValueError("worker is not configured in the central project configuration")
        profile = self.workers[key]
        return {
            "id": key,
            "url": profile["url"],
            "token_file": str((self.config_path.parent / profile["token_file"]).absolute()),
        }

    def require_active_worker(self, key):
        self.worker(key)  # Preserve and validate the original immutable binding.
        if self.workers[key].get('retired_reason'):
            raise ValueError('worker is retired: ' + self.workers[key]['retired_reason'])

    def bulk(self, *, create=True):
        try:
            if "registry" in self.evidence:
                # The project-owned resolver, not a capsule or remote-supplied module.
                path = self.root / "utils/data_paths.py"
                spec = importlib.util.spec_from_file_location("_offload_project_data_paths", path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                module.ensure_external_storage(force=True)
                base = module.resolve_source_location(
                    self.evidence["registry"], require_exists=True
                )
            else:
                base = (self.root / self.evidence["directory"]).absolute()
                if not base.is_dir() or base.is_symlink():
                    raise StorageUnavailable("configured bulk storage directory is unavailable")
            root = no_links(base / rel(self.evidence["relative"]), base)
            if root.is_relative_to(self.root / "research"):
                raise ValueError(
                    "bulk evidence must not live inside candidate research directories"
                )
            marker = {"schema": "marketmaker.offload_repository.v1", "project_id": self.id}
            if create:
                root.mkdir(parents=True, exist_ok=True)
                if not (root / "REPOSITORY.json").exists():
                    atomic(root / "REPOSITORY.json", marker)
            if root.exists() and load(root / "REPOSITORY.json") != marker:
                raise ValueError("bulk repository belongs to another project")
            return root
        except (OSError, RuntimeError) as exc:
            raise StorageUnavailable(str(exc)) from exc

    def capacity(self, additional=0):
        with phase('storage.capacity', additional_bytes=additional) as details:
            with phase('storage.locate_bulk'):
                root = self.bulk()
            with phase('storage.scan_bulk_tree'):
                used = live_tree_bytes(root)
            with phase('storage.read_bulk_free_space'):
                free = shutil.disk_usage(root).free
            limit = self.storage["max_store_mb"] * (1 << 20)
            required = additional + self.storage["min_free_mb"] * (1 << 20)
            details.update(stored_bytes=used, free_bytes=free,
                           store_limit_bytes=limit, required_free_bytes=required)
            if used + additional > limit or free < required:
                raise StorageUnavailable(
                    "bulk evidence capacity/free-space reserve exhausted: "
                    f"stored_bytes={used}, additional_bytes={additional}, "
                    f"store_limit_bytes={limit}, free_bytes={free}, "
                    f"required_free_bytes={required}, "
                    f"store_excess_bytes={max(0, used + additional - limit)}, "
                    f"free_shortfall_bytes={max(0, required - free)}"
                )
            with phase('storage.local_capacity'):
                self.local_capacity()
            return root

    def local_capacity(self):
        """Bound source metadata writes without walking the bulk evidence store.

        Remote status reconciliation only writes this small local queue. New
        remote admissions, interrupted retries and bulk writes call capacity().
        """
        if self.state.exists() and live_tree_bytes(self.state) > self.storage[
            "max_local_state_mb"
        ] * (1 << 20):
            raise StorageUnavailable("local queue metadata capacity exhausted")
        if shutil.disk_usage(self.root).free < self.storage["local_min_free_mb"] * (1 << 20):
            raise StorageUnavailable("local research/queue free-space reserve exhausted")

    def origins(self, workflow, mapping):
        """Source-only explicit job ownership, frozen before any external request."""
        jobs = {j["id"]: j for j in workflow["jobs"]}
        required = {j["id"] for j in workflow["jobs"] if j["kind"] in {"testing", "testing_stage"}}
        if (
            not isinstance(mapping, dict)
            or not mapping
            or set(mapping) - set(jobs)
            or required - set(mapping)
        ):
            raise ValueError("origins must map every testing node and only declared jobs")
        checked = {}
        for key, values in sorted(mapping.items()):
            if (
                not isinstance(values, list)
                or not 1 <= len(values) <= 128
                or any(not isinstance(v, str) for v in values)
                or len(values) != len(set(values))
            ):
                raise ValueError("each job needs distinct origin directory paths")
            for value in values:
                self.origin(value)
            checked[key] = sorted(values)
        if (
            sum(len(v) for v in checked.values()) > 1024
            or len(canonical(checked).encode()) > 128 << 10
        ):
            raise ValueError("origin mapping exceeds the local record budget")
        return checked

    def origin(self, relative):
        rel(relative)
        parts = Path(relative).parts
        if not (
            len(parts) == 4
            and parts[:2] == ("research", "candidates")
            or len(parts) == 3
            and parts[:2] == ("research", "all_research_candidates_not_harness_frameworks")
        ):
            raise ValueError("origin must be an existing candidate directory, not a framework/root")
        path = no_links(self.root / relative, self.root)
        if not path.is_dir():
            raise StorageUnavailable("origin directory is unavailable: " + relative)
        return path

    def binding(self, workflow, origins):
        return {
            "schema": "marketmaker.offload_origin_binding.v1",
            "project_id": self.id,
            "workflow_id": workflow["submission_id"],
            "workflow_sha256": digest(workflow),
            "origins": self.origins(workflow, origins),
            "storage": self.evidence,
        }
