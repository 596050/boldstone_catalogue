"""Compile, run and collect opt-in isolated research workflows."""

import argparse
import json
import sys
from pathlib import Path

from .client import Client, verify_collection
from .common import atomic, load


def parser():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    orchestrate = sub.add_parser("orchestrate", help="coordinate the durable queue and serve a live loopback monitor")
    orchestrate.add_argument("--config", type=Path, required=True)
    orchestrate.add_argument("--port", type=int, default=8766)
    orchestrate.add_argument("--poll-seconds", type=float, default=3)
    orchestrate.add_argument("--transfers", type=int, default=2)
    orchestrate.add_argument("--observers", type=int, default=4)
    orchestrate.add_argument("--request-timeout", type=float, default=3)
    orchestrate.add_argument("--local-worker", action="append", default=[], metavar="ID=CONFIG", help="optional read-only adapter for an older local worker")
    for command in ("schedule", "admit-scheduled", "retry-scheduled", "cancel-scheduled"):
        item = sub.add_parser(command, help="retain and service a sealed plan while bulk storage is unavailable")
        item.add_argument("--config", type=Path, required=True)
        if command == "schedule":
            item.add_argument("--plan", type=Path, required=True)
            item.add_argument("--worker", required=True)
            item.add_argument("--origins", type=Path, required=True)
        else:
            item.add_argument("--workflow", required=True)
    for command in ("enqueue", "sync", "queue", "retry-transfer", "origin", "publish"):
        item = sub.add_parser(command, help="source-owned durable research return and recovery")
        item.add_argument("--config", type=Path, required=True, help="central project.json")
        if command == "enqueue":
            item.add_argument("--plan", type=Path, required=True)
            item.add_argument("--worker", required=True)
            item.add_argument("--receipt", type=Path, help="export an immutable source-queue acknowledgement")
            item.add_argument("--lock-timeout", type=float, default=0, help="bounded retry of the source queue ownership lock only")
        if command in {"enqueue", "publish"}:
            item.add_argument("--origins", type=Path, required=True, help="job ID to origin directories JSON")
        if command == "publish":
            item.add_argument("--result", type=Path, required=True, help="existing verified collection to retain")
            item.add_argument("--timing-output", type=Path,
                              help="optional new diagnostic JSON for publication/capacity phases; no result identity changes")
        if command == "retry-transfer":
            item.add_argument("--workflow", required=True)
        if command == "sync":
            item.add_argument("--watch", action="store_true", help="foreground reconnect loop; supervisor can restart it")
            item.add_argument("--now", action="store_true", help="ignore backoff once, not integrity errors")
            item.add_argument("--workflow", action="append", help="service only this existing workflow; repeat for more IDs")
        if command == "origin":
            item.add_argument("--record", type=Path, required=True)
            item.add_argument("--port", required=True)
            item.add_argument("--relative")
    for command in ("plan", "plan-batch"):
        plan = sub.add_parser(
            command, help="freeze declared sources without importing candidate code"
        )
        plan.add_argument("--request", type=Path, required=True)
        plan.add_argument("--out", type=Path, required=True)
        plan.add_argument("--max-object-mb", type=int, default=1024)
        plan.add_argument("--capsule-staging-directory", type=Path,
                          help="existing, separately budgeted directory for temporary code snapshots; data and objects stay under --out")
        plan.add_argument("--project-config", type=Path,
                          help="freeze central default retry budget (explicit per-job limits win)")
    for command in ("prepare-runtime", "prepare-input"):
        item = sub.add_parser(command, help="prepare a fresh hash-bound job input from a declarative request")
        item.add_argument("--request", type=Path, required=True)
        item.add_argument("--out", type=Path, required=True)
    relocate = sub.add_parser("relocate-input", help="verify a portable input and materialize declared JSON path strings")
    relocate.add_argument("--bundle", type=Path, required=True)
    relocate.add_argument("--out", type=Path, required=True)
    retention = sub.add_parser("retain-local", help="inspect explicit completed-local-job retention targets; execution is opt-in")
    retention.add_argument("--request", type=Path, required=True)
    retention.add_argument("--out", type=Path, help="separate, retained recovery directory (required to execute)")
    retention.add_argument("--execute", action="store_true", help="archive, restore-verify, then remove only selected redundant bytes")
    restore = sub.add_parser("restore-retention", help="restore and verify one retained attempt into a fresh directory")
    restore.add_argument("--record", type=Path, required=True)
    restore.add_argument("--attempt", required=True)
    restore.add_argument("--out", type=Path, required=True)
    restore.add_argument("--max-object-mb", type=int, default=1024)
    capsule = sub.add_parser(
        "pack-research", help="snapshot selected research code and explicit dependencies"
    )
    capsule.add_argument("--repo", type=Path, required=True)
    capsule.add_argument("--include", action="append", default=[])
    capsule.add_argument("--out", type=Path, required=True, help="new capsule directory")
    init = sub.add_parser("init-worker")
    init.add_argument("--dir", type=Path, required=True)
    init.add_argument("--image", default="python:3.12-slim")
    dataset = sub.add_parser(
        "register-dataset", help="operator-local snapshot; stop the worker first"
    )
    dataset.add_argument("--config", type=Path, required=True)
    dataset.add_argument("--id", required=True)
    dataset.add_argument("--version", required=True)
    dataset.add_argument("--source", type=Path, required=True)
    dataset.add_argument("--expected-object")
    reference = sub.add_parser("prepare-data-reference", help="seal raw files and create a location-independent data_ref; does not publish data")
    reference.add_argument("--source", type=Path, required=True)
    reference.add_argument("--source-name", required=True, help="operator-approved source name on the worker")
    reference.add_argument("--key", required=True, help="relative archive key under that source")
    reference.add_argument("--out", type=Path, required=True)
    reference.add_argument("--max-object-mb", type=int, default=1024)
    verify = sub.add_parser("verify")
    verify.add_argument("--result", type=Path, required=True)
    verify.add_argument("--max-return-mb", type=int, default=1024)
    candidates = sub.add_parser("candidates", help="show independently returned candidate results")
    candidates.add_argument("--result", type=Path, required=True)
    candidates.add_argument("--candidate", help="one candidate ID; defaults to the complete roster")
    candidates.add_argument("--max-return-mb", type=int, default=1024)
    runs = sub.add_parser("runs", help="show verified multi-model batch results")
    runs.add_argument("--result", type=Path, required=True)
    runs.add_argument("--run", help="one run ID; defaults to the complete roster")
    runs.add_argument("--max-return-mb", type=int, default=1024)
    local = sub.add_parser("local", help="run a compiled plan on an owned loopback Docker worker")
    local.add_argument("--plan", type=Path, required=True)
    local.add_argument(
        "--dir", type=Path, required=True, help="new retained worker/result directory"
    )
    local.add_argument("--image", required=True, help="prebuilt interpreter image; dependencies may use declared job-local runtime inputs")
    local.add_argument("--runtime", default="python")
    local.add_argument("--deadline", type=float, default=900)
    local.add_argument("--concurrency", type=int, default=2)
    local.add_argument("--runtime-resources", type=Path,
                       help="JSON object of explicit CPU, memory, time, input, work and output limits")
    local.add_argument("--min-free-mb", type=int, default=256,
                       help="required free-space reserve for the owned local worker")
    local.add_argument("--max-object-mb", type=int, default=256,
                       help="maximum compressed and expanded bytes per verified object, in MiB")
    local.add_argument("--max-return-mb", type=int, default=1024,
                       help="maximum total verified return bytes, in MiB; budget retained output explicitly")
    local.add_argument("--input-transport", choices=("bind", "docker-volume"), default="bind",
                       help="read-only input mounts; Docker volumes use verified temporary copies")
    resolve = sub.add_parser(
        "resolve", help="resolve a verified local artifact; never executes its code"
    )
    resolve.add_argument("--result", type=Path, required=True)
    resolve.add_argument("--port", required=True)
    paths = resolve.add_mutually_exclusive_group()
    paths.add_argument("--relative")
    paths.add_argument("--native-path")
    simulation = sub.add_parser(
        "simulate", help="synthetic loopback workflows; automatically cleans temporary state"
    )
    simulation.add_argument("--docker", action="store_true")
    simulation.add_argument(
        "--report", type=Path, help="optional retained summary, never bulk test state"
    )
    for command in (
        "validate",
        "submit",
        "status",
        "wait",
        "resume",
        "cancel",
        "revoke",
        "revocation",
        "collect",
        "capabilities",
    ):
        item = sub.add_parser(command)
        item.add_argument("--url", required=True)
        item.add_argument("--token-file", type=Path, required=True)
        if command in {"validate", "submit"}:
            item.add_argument("--plan", type=Path, required=True, help="compiled plan directory")
        elif command != "capabilities":
            item.add_argument("--workflow", required=True)
        if command in {"wait", "submit"}:
            item.add_argument("--deadline", type=float, default=3600)
        if command == "revoke":
            item.add_argument("--workflow-sha256", required=True,
                              help="exact compiled identity; prevents late admission and cancels matching admitted work")
        item.add_argument(
            "--request-timeout",
            type=float,
            default=30,
            help="HTTP timeout in seconds for each worker request, including object commit",
        )
        if command in {"collect", "submit"}:
            item.add_argument(
                "--out",
                type=Path,
                required=command == "collect",
                help="submit: wait and automatically collect into this fresh directory",
            )
            item.add_argument("--max-return-mb", type=int, default=1024)
        if command == "collect":
            item.add_argument(
                "--partial",
                action="store_true",
                help="immutable nonfinal snapshot into a fresh directory",
            )
    return parser


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "orchestrate":
            from .orchestrator import run

            local_workers = {}
            for value in args.local_worker:
                key, separator, path = value.partition("=")
                if not separator or not key or not path or key in local_workers:
                    raise ValueError("local-worker must be a unique ID=CONFIG mapping")
                local_workers[key] = Path(path)
            run(args.config, port=args.port, poll_seconds=args.poll_seconds,
                transfers=args.transfers, observers=args.observers,
                request_timeout=args.request_timeout, local_workers=local_workers)
            return 0
        elif args.command in {"schedule", "admit-scheduled", "retry-scheduled", "cancel-scheduled"}:
            from .prepared_queue import schedule, service, reset

            if args.command == "schedule":
                result = schedule(args.config, args.plan, args.worker, load(args.origins))
            elif args.command == "admit-scheduled":
                result = service(args.config, args.workflow)
            else:
                result = reset(args.config, args.workflow, cancel=args.command == "cancel-scheduled")
        elif args.command in {"enqueue", "sync", "queue", "retry-transfer"}:
            from .project_queue import ProjectQueue

            with ProjectQueue(args.config) as queue:
                if args.command == "enqueue":
                    receipt = queue.enqueue_receipt(args.plan, args.worker, load(args.origins),
                                                    output=args.receipt, lock_timeout=args.lock_timeout)
                    result = receipt if args.receipt else queue.status()
                elif args.command == "retry-transfer":
                    queue.retry(args.workflow)
                    result = queue.status()
                elif args.command == "queue":
                    result = queue.status()
                else:
                    import threading

                    stop = threading.Event()
                    previous = None
                    while True:
                        result = queue.sync(now=args.now, workflows=args.workflow)
                        args.now = False
                        if not args.watch:
                            break
                        if result != previous:
                            print(json.dumps(result, sort_keys=True), flush=True)
                            previous = result
                        stop.wait(min(30, queue.project.recovery["poll_seconds"]))
        elif args.command == "origin":
            from .project_storage import Project
            from .publication import resolve_record

            result = {"path": str(resolve_record(Project(args.config), args.record, args.port,
                                                  args.relative)), "executed": False}
        elif args.command == "publish":
            from .project_storage import Project
            from .publication import import_collection

            if args.timing_output:
                from .operation_timing import record_to

                with record_to(args.timing_output, 'publication.import_collection'):
                    result = import_collection(Project(args.config), args.result, load(args.origins))
            else:
                result = import_collection(Project(args.config), args.result, load(args.origins))
        elif args.command in {"plan", "plan-batch"}:
            from .planner import from_file

            if args.command == "plan-batch":
                from .batch import SCHEMAS

                if load(args.request).get("schema") not in SCHEMAS:
                    raise ValueError("plan-batch requires the independent-candidate batch schema")
            attempts = None
            if args.project_config:
                from .project_storage import Project

                attempts = Project(args.project_config).recovery["default_max_attempts"]
            result = from_file(args.request, args.out, max_object_mb=args.max_object_mb,
                               default_max_attempts=attempts,
                               capsule_staging_directory=args.capsule_staging_directory)
        elif args.command in {"prepare-runtime", "prepare-input"}:
            if args.command == "prepare-runtime":
                from .python_runtime import from_file
            else:
                from .input_bundle import from_file
            result = from_file(args.request, args.out)
        elif args.command == "relocate-input":
            from .execution.portable import materialize
            result = {"directory": str(materialize(args.bundle, args.out)), "source_bytes_modified": False}
        elif args.command == "retain-local":
            from .retention import retain
            result = retain(load(args.request), args.out, base=args.request.resolve().parent, execute=args.execute)
        elif args.command == "restore-retention":
            from .common import positive
            from .retention import restore
            positive(args.max_object_mb, 1 << 20)
            result = restore(args.record, args.attempt, args.out, max_bytes=args.max_object_mb << 20)
        elif args.command == "local":
            from .local import run

            result = run(
                args.plan,
                args.dir,
                image=args.image,
                runtime=args.runtime,
                deadline=args.deadline,
                concurrency=args.concurrency,
                runtime_resources=load(args.runtime_resources) if args.runtime_resources else None,
                min_free_mb=args.min_free_mb,
                max_object_mb=args.max_object_mb,
                max_return_mb=args.max_return_mb,
                input_transport=args.input_transport,
            )
        elif args.command == "pack-research":
            from .capsule import research_selection, snapshot

            args.out.mkdir(parents=True, exist_ok=False)
            result = snapshot(
                args.repo,
                args.out / "repo",
                include=research_selection(args.repo, args.include),
                resolve_code_links=True,
            )
            atomic(args.out.parent / (args.out.name + ".snapshot.json"), result)
        elif args.command == "init-worker":
            from offload_service.cli import initialize

            config = initialize(args.dir, args.image)
            raw = load(config)
            raw["concurrency"] = 2
            raw["max_pending"] = 512  # Admit a full 128-node DAG plus bounded queued batches.
            raw["workflows"] = {
                "enabled": True,
                "runtimes": {
                    "python": {
                        "image": args.image,
                        "memory_mb": 512,
                        "cpus": 1,
                        "pids": 128,
                        "timeout_s": 300,
                        "max_work_mb": 512,
                        "max_output_mb": 128,
                    }
                },
                "capacity": {"cpus": 2, "memory_mb": 2048, "pids": 512, "max_work_mb": 2048},
                "max_object_mb": 1024,
                "max_store_mb": 10240,
                "min_free_mb": 128,
            }
            atomic(config, raw)
            result = {
                "config": str(config),
                "code_submission": "explicitly_enabled",
                "note": "Jobs need a prebuilt interpreter image; declare image dependencies or a verified python_environment input.",
            }
        elif args.command == "prepare-data-reference":
            from .common import positive
            from .data_references import prepare_reference

            positive(args.max_object_mb, 1048576)
            result = prepare_reference(args.source, args.out, source=args.source_name,
                                       object_key=args.key, max_bytes=args.max_object_mb << 20)
        elif args.command == "register-dataset":
            from lib.file_lock import file_lock
            from offload_service.cli import load_config

            from .objects import ObjectStore

            raw, _, base = load_config(args.config)
            root = (base / raw["root"]).resolve()
            root.mkdir(parents=True, exist_ok=True)
            with file_lock(root / "worker.lock", timeout=0):
                config = raw["workflows"]
                store = ObjectStore(
                    root / "workflows",
                    **{
                        k: config[k]
                        for k in ("max_object_mb", "max_store_mb", "min_free_mb")
                        if k in config
                    },
                )
                result = store.register_dataset(
                    args.id, args.version, args.source, expected_object=args.expected_object
                )
        elif args.command == "verify":
            result = verify_collection(args.result, max_bytes=args.max_return_mb * (1 << 20))
        elif args.command in {"candidates", "runs"}:
            verify_collection(args.result, max_bytes=args.max_return_mb * (1 << 20))
            result = load(
                args.result / ("RUNS.json" if args.command == "runs" else "CANDIDATES.json")
            )
            selected = args.run if args.command == "runs" else args.candidate
            if selected:
                matches = [c for c in result[args.command] if c["id"] == selected]
                if not matches:
                    raise ValueError("candidate is not in this returned batch")
                result = matches[0]
        elif args.command == "resolve":
            from .resolver import resolve

            result = {
                "path": str(
                    resolve(args.result, args.port, args.relative, native_path=args.native_path)
                ),
                "executed": False,
            }
        elif args.command == "simulate":
            from .simulation import run

            result = run(docker=args.docker)
            if args.report:
                if args.report.exists():
                    raise FileExistsError("simulation report already exists")
                atomic(args.report, result)
        else:
            client = Client(
                args.url,
                args.token_file.read_text().strip(),
                timeout=getattr(args, "request_timeout", 30),
            )
            if args.command == "capabilities":
                result = client.request("/v2/capabilities")
            elif args.command in {"validate", "submit"}:
                result = client.submit_plan(args.plan, validate_only=args.command == "validate")
                if args.command == "submit" and args.out:
                    workflow = result["workflow_id"]
                    client.wait_workflow(workflow, deadline=args.deadline)
                    result = client.collect(
                        workflow, args.out, max_bytes=args.max_return_mb * (1 << 20)
                    )
            elif args.command == "status":
                result = client.workflow_status(args.workflow)
            elif args.command == "revoke":
                result = client.revoke_workflow(args.workflow, args.workflow_sha256)
            elif args.command == "revocation":
                result = client.workflow_revocation(args.workflow)
            elif args.command == "wait":
                result = client.wait_workflow(args.workflow, deadline=args.deadline)
            elif args.command == "collect":
                result = client.collect(
                    args.workflow,
                    args.out,
                    max_bytes=args.max_return_mb * (1 << 20),
                    partial=args.partial,
                )
            else:
                result = client.request("/v2/workflows/" + args.workflow + "/" + args.command, {})
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, OSError, RuntimeError, KeyError) as error:
        print(json.dumps({"status": "ERROR", "reason": str(error)}, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
