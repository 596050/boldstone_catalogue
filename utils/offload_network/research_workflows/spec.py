"""Pure workflow/output planning: no plugin imports, downloads or execution."""

import re
from copy import deepcopy

from .common import canonical, digest, fields, hash_id, name, positive, rel

SCHEMA = "marketmaker.research_offload_workflow.v1"
STAGES = (
    "contracts",
    "data",
    "models",
    "causality",
    "replay",
    "metrics",
    "comparison",
    "statistics",
    "execution",
    "prospective",
)
TERMINAL = {"succeeded", "failed", "interrupted", "cancelled", "blocked_dependency"}
RESOURCE_KEYS = {"cpus", "memory_mb", "pids", "timeout_s", "max_work_mb", "max_output_mb"}
TOKEN = re.compile(r"\{(input|output)\.([a-z][a-z0-9_-]{0,62})\}")


def output_spec(raw):
    fields(
        raw,
        {"path", "type", "schema", "required", "delivery", "requires", "rows"},
        {"path", "type"},
    )
    value = {"required": True, "delivery": "return", "requires": [], **raw}
    path = rel(value["path"])
    if not path.startswith("artifacts/") or path == "artifacts":
        raise ValueError("output paths must be below artifacts/")
    if value["type"] not in {"file", "json", "jsonl", "csv", "tree"}:
        raise ValueError("unsupported output type")
    if type(value["required"]) is not bool or value["delivery"] not in {"return", "remote"}:
        raise ValueError("invalid output policy")
    if "schema" in value and (value["type"] != "json" or not isinstance(value["schema"], str)):
        raise ValueError("schema identifiers require JSON output")
    if not isinstance(value["requires"], list) or any(
        not isinstance(x, str) for x in value["requires"]
    ):
        raise ValueError("output requires must be an array of port references")
    if "rows" in value:
        if (
            value["type"] not in {"jsonl", "csv"}
            or type(value["rows"]) is not int
            or value["rows"] < 0
        ):
            raise ValueError("row count applies only to JSONL/CSV")
    return value


def validate(raw):
    fields(
        raw,
        {"schema", "submission_id", "workflow", "jobs", "return_policy", "metadata", "batch"},
        {"schema", "submission_id", "jobs"},
    )
    value = deepcopy(raw)
    if value["schema"] != SCHEMA or value.get("workflow", "research") != "research":
        raise ValueError("only the versioned research workflow is supported")
    name(value["submission_id"])
    value["workflow"] = "research"
    value.setdefault("metadata", {})
    if not isinstance(value["metadata"], dict):
        raise ValueError("metadata must be an object")
    policy = {
        "profile": "full_results",
        "ports": [],
        "include_inputs": False,
        "require_local": [],
        **value.get("return_policy", {}),
    }
    fields(policy, {"profile", "ports", "include_inputs", "require_local"})
    if type(policy["include_inputs"]) is not bool:
        raise ValueError("include_inputs must be explicit boolean export authorization")
    if not isinstance(policy["require_local"], list) or any(
        not isinstance(x, str) for x in policy["require_local"]
    ):
        raise ValueError("require_local must name output ports")
    if policy["profile"] not in {"full_results", "summary_and_refs", "selected"}:
        raise ValueError("invalid return profile")
    if not isinstance(policy["ports"], list) or any(
        not isinstance(x, str) for x in policy["ports"]
    ):
        raise ValueError("selected ports must be strings")
    if (policy["profile"] == "selected") != bool(policy["ports"]):
        raise ValueError("only selected return profile takes a nonempty ports list")
    value["return_policy"] = policy
    if not isinstance(value["jobs"], list) or not 1 <= len(value["jobs"]) <= 128:
        raise ValueError("a workflow needs 1-128 jobs")
    jobs = {}
    for raw_job in value["jobs"]:
        fields(
            raw_job,
            {
                "id",
                "kind",
                "runtime",
                "capsule",
                "entrypoint",
                "args",
                "inputs",
                "outputs",
                "depends_on",
                "resources",
                "testing",
                "max_attempts",
                "condition",
                "python_environment",
                "portable_inputs",
            },
            {"id", "kind", "runtime", "capsule"},
        )
        job = raw_job
        key = name(job["id"])
        if key in jobs:
            raise ValueError("duplicate node ID")
        jobs[key] = job
        name(job["runtime"])
        hash_id(job["capsule"])
        if job["kind"] not in {"producer", "testing", "testing_stage", "report"}:
            raise ValueError("unsupported node kind")
        job.setdefault("args", [])
        if (
            not isinstance(job["args"], list)
            or len(job["args"]) > 256
            or any(not isinstance(x, str) or len(x) > 8192 or "\0" in x for x in job["args"])
        ):
            raise ValueError("invalid argument vector")
        job.setdefault("depends_on", [])
        deps = job["depends_on"]
        if (
            not isinstance(deps, list)
            or any(not isinstance(d, str) for d in deps)
            or len(set(deps)) != len(deps)
        ):
            raise ValueError("dependencies must be unique names")
        for dep in deps:
            name(dep)
        job.setdefault("condition", "success")
        if job["condition"] not in {"success", "all_terminal"}:
            raise ValueError("unsupported dependency condition")
        if job["condition"] == "all_terminal" and job["kind"] != "report":
            raise ValueError("only report nodes may use all_terminal")
        job.setdefault("max_attempts", 1)
        positive(job["max_attempts"], 3)
        job.setdefault("inputs", {})
        if not isinstance(job["inputs"], dict) or len(job["inputs"]) > 64:
            raise ValueError("invalid input ports")
        for port, source in job["inputs"].items():
            name(port)
            mode = source.get("mode") if isinstance(source, dict) else None
            if mode == "bundle":
                fields(source, {"mode", "object_sha256"}, {"mode", "object_sha256"})
                hash_id(source["object_sha256"])
            elif mode == "data_ref":
                from .data_references import validate_reference

                validate_reference(source)
            elif mode == "dataset_ref":
                fields(
                    source,
                    {"mode", "dataset_id", "version", "object_sha256"},
                    {"mode", "dataset_id", "version", "object_sha256"},
                )
                name(source["dataset_id"])
                name(source["version"])
                hash_id(source["object_sha256"])
            elif mode == "artifact_ref":
                fields(source, {"mode", "job", "output"}, {"mode", "job", "output"})
                name(source["job"])
                name(source["output"])
                if source["job"] not in deps:
                    raise ValueError("artifact reference requires an explicit dependency")
            else:
                raise ValueError("unknown input mode")
        if "portable_inputs" in job:
            ports = job["portable_inputs"]
            if (not isinstance(ports, list) or not ports or any(not isinstance(p, str) for p in ports)
                    or len(set(ports)) != len(ports) or set(ports) - set(job["inputs"])):
                raise ValueError("portable_inputs must name distinct declared inputs")
            port = {"type": "tree", "path": "artifacts/inputs"}
            supplied = job.setdefault("outputs", {}).get("input_relocation")
            if supplied is not None and output_spec(supplied) != output_spec(port):
                raise ValueError("input relocation output is adapter-owned")
            job["outputs"]["input_relocation"] = port
        if "python_environment" in job:
            environment = job["python_environment"]
            fields(environment, {"input"}, {"input"})
            if environment["input"] not in job["inputs"]:
                raise ValueError("Python environment must name a declared input")
            if environment["input"] in job.get("portable_inputs", []):
                raise ValueError("runtime input cannot also be a relocated document input")
            port = {"type": "json", "path": "artifacts/runtime/VALIDATION.json",
                    "schema": "marketmaker.job_runtime_validation.v1"}
            supplied = job.setdefault("outputs", {}).get("runtime_validation")
            if supplied is not None and output_spec(supplied) != output_spec(port):
                raise ValueError("runtime validation output is adapter-owned")
            job["outputs"]["runtime_validation"] = port
        if job["kind"] in {"testing", "testing_stage"}:
            if "entrypoint" in job:
                raise ValueError("testing nodes use the canonical testing entrypoint")
            testing = {"repository": "repo", "through": "metrics", **job.get("testing", {})}
            fields(testing, {"repository", "through", "stop_after", "resume_input"})
            rel(testing["repository"])
            if testing["through"] not in STAGES:
                raise ValueError("unknown testing endpoint")
            if job["kind"] == "testing":
                if set(testing) & {"stop_after", "resume_input"}:
                    raise ValueError("checkpoint controls require testing_stage")
            else:
                testing.setdefault("stop_after", testing["through"])
                if testing["stop_after"] not in STAGES or STAGES.index(
                    testing["stop_after"]
                ) > STAGES.index(testing["through"]):
                    raise ValueError("invalid checkpoint boundary")
                if testing.get("resume_input") not in {None, *job["inputs"]}:
                    raise ValueError("checkpoint input is missing")
            job["testing"] = testing
            # These are adapter-owned. Reject explicit overrides, including = forms.
            protected = (
                "--output",
                "--workflow",
                "--data-refresh",
                "--through",
                "--cache-dir",
                "--cache-mode",
            )
            if any(token.split("=", 1)[0] in protected for token in job["args"]):
                raise ValueError(
                    "output/workflow/freshness/endpoint/cache are owned by the testing adapter"
                )
            defaults = {
                "research_result": {
                    "path": "artifacts/testing/RESULT.json",
                    "type": "json",
                    "schema": "marketmaker.progressive_gate_result.v1",
                },
                "research_evidence": {"path": "artifacts/testing", "type": "tree"},
            }
            if job["kind"] == "testing_stage" and testing["stop_after"] != testing["through"]:
                defaults["checkpoint"] = {"path": "artifacts/checkpoint", "type": "tree"}
            supplied = job.get("outputs", {})
            for port in set(supplied) & set(defaults):
                if output_spec(supplied[port]) != output_spec(defaults[port]):
                    raise ValueError("testing output ports are adapter-owned")
            job["outputs"] = {**supplied, **defaults}
        else:
            rel(job.get("entrypoint"))
            if not job["entrypoint"].endswith(".py") or "testing" in job:
                raise ValueError("producer/report needs a Python entrypoint, not testing options")
        if (
            not isinstance(job.get("outputs"), dict)
            or not job["outputs"]
            or len(job["outputs"]) > 64
        ):
            raise ValueError("declare at least one bounded output port")
        job["outputs"] = {name(k): output_spec(v) for k, v in job["outputs"].items()}
        for text in job["args"]:
            for match in TOKEN.finditer(text):
                group = job["inputs"] if match[1] == "input" else job["outputs"]
                if match[2] not in group:
                    raise ValueError("argument refers to an unknown input/output")
        resources = job.setdefault("resources", {})
        fields(resources, RESOURCE_KEYS)
        for key, amount in resources.items():
            positive(amount, 1048576, integer=key != "cpus" and key != "timeout_s")
    for job in jobs.values():
        if job["id"] in job["depends_on"] or set(job["depends_on"]) - set(jobs):
            raise ValueError("unknown/self dependency")
        for source in job["inputs"].values():
            if source["mode"] == "artifact_ref":
                parent = jobs[source["job"]]
                if (
                    source["output"] not in parent["outputs"]
                    or not parent["outputs"][source["output"]]["required"]
                ):
                    raise ValueError("downstream inputs require an existing mandatory output")
                if parent["kind"] == "report" and job["kind"] != "report":
                    raise ValueError("report-only outputs cannot advance computation")
        resume = job.get("testing", {}).get("resume_input")
        if resume and (resume in job.get("portable_inputs", [])
                       or resume == job.get("python_environment", {}).get("input")):
            raise ValueError("checkpoint input cannot also be relocated or used as a Python environment")
        if resume and job["inputs"][resume]["mode"] == "artifact_ref":
            ref = job["inputs"][resume]
            parent = jobs[ref["job"]]
            if (
                parent["kind"] != "testing_stage"
                or ref["output"] != "checkpoint"
                or parent["testing"]["through"] != job["testing"]["through"]
                or STAGES.index(parent["testing"]["stop_after"])
                >= STAGES.index(job["testing"]["stop_after"])
                or any(parent[k] != job[k] for k in ("capsule", "runtime", "args", "resources"))
                or any(parent.get(k) != job.get(k) for k in ("python_environment", "portable_inputs"))
            ):
                raise ValueError(
                    "checkpoint continuation must preserve identity and advance the gate boundary"
                )
    layers, completed = [], set()
    while len(completed) < len(jobs):
        ready = [
            j["id"]
            for j in jobs.values()
            if j["id"] not in completed and set(j["depends_on"]) <= completed
        ]
        if not ready:
            raise ValueError("dependency cycle")
        layers.append(ready)
        completed.update(ready)
    from .batch import validate_roster

    validate_roster(value)
    # Validate dependency closure of output selections without executing anything.
    ports = {j["id"] + "." + p: v for j in jobs.values() for p, v in j["outputs"].items()}
    for port, spec in ports.items():
        for required in spec["requires"]:
            if required not in ports or required == port:
                raise ValueError("unknown/self output dependency")
    visiting, seen = set(), set()

    def visit(port):
        if port in visiting:
            raise ValueError("output dependency cycle")
        if port in seen:
            return
        visiting.add(port)
        for required in ports[port]["requires"]:
            visit(required)
        visiting.remove(port)
        seen.add(port)

    for port in ports:
        visit(port)
    if set(policy["ports"]) - set(ports):
        raise ValueError("unknown selected output port")
    if set(policy["require_local"]) - set(selected_ports(value)):
        raise ValueError("return selection does not satisfy required local continuation inputs")
    if len(canonical(value).encode()) > 1 << 20:
        raise ValueError("workflow exceeds 1 MiB")
    return value


def output_plan(workflow):
    return {
        "schema": "marketmaker.research_output_plan.v1",
        "submission_id": workflow["submission_id"],
        "jobs": {j["id"]: j["outputs"] for j in workflow["jobs"]},
        "return_policy": workflow["return_policy"],
        "automatic_delete": False,
        "estimated_bytes": None,
        "note": "Estimates unknown until output production; profile limits are enforced.",
    }


def selected_ports(workflow):
    ports = {j["id"] + "." + k: v for j in workflow["jobs"] for k, v in j["outputs"].items()}
    policy = workflow["return_policy"]
    if policy["profile"] == "full_results":
        chosen = {p for p, spec in ports.items() if spec["delivery"] == "return"}
    elif policy["profile"] == "selected":
        chosen = set(policy["ports"])
    else:
        chosen = {
            p
            for p, spec in ports.items()
            if spec["delivery"] == "return" and spec["type"] in {"json", "csv"}
        }
    # Summary-only deliberately retains unresolved bulk dependencies as references.
    if policy["profile"] != "summary_and_refs":
        pending = list(chosen)
        while pending:
            for required in ports[pending.pop()]["requires"]:
                if required not in chosen:
                    chosen.add(required)
                    pending.append(required)
    return sorted(chosen)


def identity(workflow):
    return digest(workflow)
