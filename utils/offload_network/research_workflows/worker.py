"""Worker-side workflow execution; Docker remains the sole production boundary."""

import json
import shutil
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from offload_service.core import Template, Worker

from .common import fields, hash_id, positive, rel


@dataclass(frozen=True)
class MountedTemplate(Template):
    mounts: tuple = ()


class WorkflowWorker(Worker):
    def __init__(self, root, templates, *, workflow_config, **kwargs):
        fields(
            workflow_config,
            {"enabled", "runtimes", "capacity", "max_object_mb", "max_store_mb", "min_free_mb", "input_transport", "recover_completed", "data_sources"},
            {"enabled", "runtimes", "capacity"},
        )
        if workflow_config["enabled"] is not True:
            raise ValueError("workflow code submission requires explicit enabled=true")
        from .finished_recovery import recovery_ids

        self.completed_recovery_ids = recovery_ids(workflow_config.get("recover_completed", []))
        self.input_transport = workflow_config.get("input_transport", "bind")
        if self.input_transport not in ("bind", "docker-volume"):
            raise ValueError("workflow input_transport must be bind or docker-volume")
        if self.input_transport == "docker-volume" and kwargs.get("backend", "docker") != "docker":
            raise ValueError("Docker volume inputs require the Docker backend")
        self.input_volume_lock = threading.Lock()
        fields(
            workflow_config["capacity"],
            {"cpus", "memory_mb", "pids", "max_work_mb"},
            {"cpus", "memory_mb", "pids", "max_work_mb"},
        )
        self.capacity = dict(workflow_config["capacity"])
        for key, value in self.capacity.items():
            positive(value, 10485760, integer=key != "cpus")
        runtime_root = Path(__file__).parent / "execution"
        self.profiles = {}
        for name, raw in workflow_config["runtimes"].items():
            from .common import name as valid_name

            valid_name(name)
            fields(
                raw,
                {
                    "image",
                    "timeout_s",
                    "memory_mb",
                    "cpus",
                    "pids",
                    "max_output_mb",
                    "max_work_mb",
                    "max_input_mb",
                },
                {"image"},
            )
            profile = Template.load(
                "workflow-" + name,
                {"entrypoint": str(runtime_root / "run.py"), "code_dir": str(runtime_root), **raw},
                runtime_root,
            )
            if any(getattr(profile, key) > limit for key, limit in self.capacity.items()):
                raise ValueError("runtime profile exceeds aggregate workflow capacity")
            self.profiles[name] = profile
        if not self.profiles:
            raise ValueError("configure at least one workflow runtime")
        if any(t.name.startswith("workflow-") for t in templates):
            raise ValueError("workflow- template namespace is reserved")
        if any(getattr(t, key) > limit for t in templates for key, limit in self.capacity.items()):
            raise ValueError("legacy template exceeds aggregate worker capacity")
        super().__init__(root, [*templates, *self.profiles.values()], **kwargs)
        try:
            from .scheduler import Coordinator

            self.workflows = Coordinator(self, workflow_config)
            if self.completed_recovery_ids:
                from .finished_recovery import finish

                finish(self, self.completed_recovery_pending)
        except BaseException:
            super().close()
            raise

    def _recover(self):
        if not self.completed_recovery_ids:
            return super()._recover()
        from .finished_recovery import pending

        # The base constructor owns the kernel lock. Defer byte verification
        # until the workflow object store has also been initialized.
        self.completed_recovery_pending = pending(self, self.completed_recovery_ids)

    def submit(self, request, *, template_override=None, admission_check=None):
        if template_override is None and (
            str(request.get("job_id", "")).startswith("wf-")
            or str(request.get("template", "")).startswith("workflow-")
        ):
            raise ValueError("use the workflow endpoint for workflow jobs")
        return super().submit(request, template_override=template_override, admission_check=admission_check)

    def _prepare(self, job_id, template, args, metadata):
        result = super()._prepare(job_id, template, args, metadata)
        if isinstance(template, MountedTemplate):
            result["workflow_mounts"] = list(template.mounts)
            result["workflow_input_transport"] = self.input_transport
            # image was bound on workflow admission, not when a dependency finishes.
            result["image_id"] = metadata["workflow_image_id"]
        return result

    def _mount_references(self, payload):
        for mount in payload.get("workflow_mounts", []):
            fields(mount, {"object_sha256", "target"}, {"object_sha256", "target"})
            target = rel(mount["target"])
            if target != "capsule" and not target.startswith("inputs/"):
                raise ValueError("invalid workflow mount target")
            yield hash_id(mount["object_sha256"]), target

    def _checked_mounts(self, payload):
        verified = {}
        for identity, target in self._mount_references(payload):
            # Multiple ports may name the same object. Verify its bytes once
            # within this boundary, while retaining every distinct mount path.
            # This local map is discarded before the next execution boundary.
            if identity not in verified:
                root, _ = self.workflows.objects.get(identity)
                verified[identity] = root / "data"
            yield verified[identity], target

    def prepare_extra_inputs(self, work, payload):
        mounts = (self._mount_references(payload) if payload["backend"] == "docker"
                  else self._checked_mounts(payload))
        for source, target in mounts:
            destination = work / "blobs" / target
            if destination.exists() or destination.is_symlink():
                raise ValueError("workflow mount target already exists")
            # These mounts have separate immutable object identities, bound in
            # the sealed job.json. They are not empty blobs in the seal manifest.
            destination.mkdir(parents=True)
            if payload["backend"] == "trusted-local":
                # Simulation only: no host isolation or cross-attempt canonical path.
                shutil.copytree(source, destination, dirs_exist_ok=True)
            # Docker has not consumed any mounted data yet. docker_command does
            # the complete pre-execution verification immediately before create;
            # verify_extra_inputs performs a second full check after execution.

    def verify_extra_inputs(self, payload):
        list(self._checked_mounts(payload))

    def docker_command(self, work, attempt, payload):
        command = super().docker_command(work, attempt, payload)
        extra = []
        references = list(self._mount_references(payload))
        if payload.get("workflow_input_transport", "bind") == "docker-volume" and references:
            from .input_volumes import stage

            mounts = stage(self, work, attempt, payload, references)
            for volume, target in mounts:
                extra += ["--mount", f"type=volume,source={volume},target=/work/blobs/{target},readonly"]
        else:
            for source, target in self._checked_mounts(payload):
                extra += ["--mount", f"type=bind,source={source},target=/work/blobs/{target},readonly"]
        index = command.index("--workdir")
        command[index:index] = extra
        return command

    def _remove_container(self, name):
        super()._remove_container(name)
        with self.db_lock:
            row = self.db.execute("SELECT payload FROM jobs WHERE attempt=?", (name,)).fetchone()
        if row and json.loads(row[0] or "{}").get("workflow_input_transport") == "docker-volume":
            from .input_volumes import cleanup

            cleanup(self, name)

    def _finish(self, job_id, attempt, state, receipt, *, db=None):
        if attempt:
            from .input_volumes import directory

            path = directory(self, attempt) / "TRANSPORT.json"
            if path.exists():
                receipt = {**receipt, "workflow_input_transport": json.loads(path.read_text())}
        return super()._finish(job_id, attempt, state, receipt, db=db)

    def _claim(self):
        if self.stop.is_set():
            return None
        from .input_capacity import observe
        # Queued jobs retain their original transport across worker restarts,
        # even when the current default has changed to bind mounts.
        volume_capacity = observe(self)
        free_bytes = shutil.disk_usage(self.root).free
        # One atomic admission budget spans legacy and workflow jobs in this store.
        with self.transaction() as db:
            if self.stop.is_set():
                return None
            used = {key: 0 for key in self.capacity}
            for row in db.execute("SELECT payload FROM jobs WHERE state='running'"):
                template = json.loads(row[0])["template"]
                for key in used:
                    used[key] += template[key]
            for row in db.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY sequence"):
                payload = json.loads(row["payload"])
                if any(
                    used[key] + payload["template"][key] > limit
                    for key, limit in self.capacity.items()
                ):
                    continue
                if not self._storage_claim_allowed(db, payload, free_bytes):
                    continue
                if volume_capacity is not None and not volume_capacity.allows(self, db, payload, free_bytes):
                    continue
                attempt = "offload-" + uuid.uuid4().hex
                db.execute(
                    "UPDATE jobs SET state='running',attempt=?,updated=? WHERE id=? AND state='queued'",
                    (attempt, time.time(), row["id"]),
                )
                return row["id"], attempt, payload
        return None

    def start(self):
        super().start()
        self.workflows.start()

    def close(self):
        if hasattr(self, "workflows"):
            self.workflows.close()
        super().close()
