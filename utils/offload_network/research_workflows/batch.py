"""Independent candidate batches compiled to the existing immutable workflow DAG.

No candidate imports, dependency inference, source downloads or scientific pooling.
Dynamic preparation is explicit uploaded producer code with sealed input supplies.
"""

import re
from copy import deepcopy

from .common import digest, fields, name, rel

SCHEMA = "marketmaker.research_offload_batch.v1"
RUN_SCHEMA = "marketmaker.research_offload_batch.v2"
SCHEMAS = {SCHEMA, RUN_SCHEMA}
ROSTER_SCHEMA = "marketmaker.offload_candidate_roster.v1"
RUN_ROSTER_SCHEMA = "marketmaker.offload_run_roster.v1"
RESULT_SCHEMA = "marketmaker.offload_candidate_results.v1"
RUN_RESULT_SCHEMA = "marketmaker.offload_run_results.v1"
OPTIONS = {
    "runtime",
    "capsule",
    "testing",
    "inputs",
    "args",
    "outputs",
    "resources",
    "max_attempts",
    "python_environment",
    "portable_inputs",
}


def _args(values, *, own_benchmarks=False):
    if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
        raise ValueError("batch arguments must be an argv array")
    owned = ("--model", "--model-list")
    if own_benchmarks:
        owned += ("--benchmark", "--benchmark-list")
    for value in values:
        option = value.split("=", 1)[0]
        if option.startswith("--") and any(flag.startswith(option) for flag in owned):
            raise ValueError("batch owns model/comparator flags; use its explicit roster")
        path = value.split("=", 1)[1] if value.startswith("--") and "=" in value else value
        if path.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", path):
            raise ValueError("batch arguments need portable relative paths or input/output tokens")
    return values


def _models(values, *, allow_empty=False):
    if not isinstance(values, list) or not (0 if allow_empty else 1) <= len(values) <= 128:
        raise ValueError("model rosters must be arrays with 1-128 models (benchmarks may be empty)")
    for model in values:
        if not isinstance(model, str) or not model or model.startswith("-") or "{output." in model:
            raise ValueError("portable model paths are required")
        rel(re.sub(r"\{input\.[a-z][a-z0-9_-]*\}", "input", model))
    if len(set(values)) != len(values):
        raise ValueError("duplicate model within a role")
    return values


def _invocation(models, benchmarks):
    if set(models) & set(benchmarks):
        raise ValueError("candidate and comparator roles overlap within a run")
    return [
        arg
        for flag, paths in (("--model", models), ("--benchmark", benchmarks))
        for path in paths
        for arg in (flag, path)
    ]


def result_filename(workflow):
    return (
        "RUNS.json"
        if workflow.get("batch", {}).get("schema") == RUN_ROSTER_SCHEMA
        else "CANDIDATES.json"
    )


def _source(value, catalog):
    if not isinstance(value, dict) or value.get("mode") != "source_ref":
        return deepcopy(value)
    fields(value, {"mode", "source", "include"}, {"mode", "source"})
    key = name(value["source"])
    if key not in catalog:
        raise ValueError("unknown declared batch data source: " + key)
    result = deepcopy(catalog[key])
    if not isinstance(result, dict) or result.get("mode") not in {
        "bundle",
        "dataset_ref",
        "artifact_ref",
        "data_ref",
    }:
        raise ValueError("data_sources must declare bundle, dataset_ref, artifact_ref or data_ref inputs")
    if "include" in value:
        if result.get("mode") != "bundle" or "source" not in result:
            raise ValueError(
                "subset selection requires a local bundle; use a producer for remote data"
            )
        selection = value["include"]
        if not isinstance(selection, list) or not selection:
            raise ValueError("include must be a nonempty list of explicit relative paths")
        selection = [rel(p) for p in selection]
        if "include" in result and any(
            not any(p == allowed or p.startswith(allowed + "/") for allowed in result["include"])
            for p in selection
        ):
            raise ValueError("candidate selection broadens the declared data source")
        result["include"] = selection
    return result


def expand(request):
    """Produce independently isolated testing runs, with namespaced producers.

    v1 retains exactly one candidate per run. v2 explicitly binds model/comparator
    sets; a model may play different roles in different runs, never both in one run.
    """
    from .spec import SCHEMA as WORKFLOW_SCHEMA

    grouped = request.get("schema") == RUN_SCHEMA
    entries = "runs" if grouped else "candidates"
    fields(
        request,
        {
            "schema",
            "submission_id",
            "defaults",
            "data_sources",
            "jobs",
            entries,
            "return_policy",
            "metadata",
        },
        {"schema", "submission_id", entries},
    )
    if request["schema"] not in SCHEMAS:
        raise ValueError("unsupported candidate batch schema")
    defaults = deepcopy(request.get("defaults", {}))
    fields(defaults, OPTIONS | ({"benchmarks"} if grouped else set()))
    if grouped and "benchmarks" in defaults:
        _models(defaults["benchmarks"], allow_empty=True)
    catalog = request.get("data_sources", {})
    if not isinstance(catalog, dict):
        raise ValueError("data_sources must be an object")
    for key in catalog:
        name(key)
    candidates = request[entries]
    if not isinstance(candidates, list) or not 1 <= len(candidates) <= 128:
        raise ValueError("a batch needs 1-128 candidates within the 128-node workflow limit")
    jobs = deepcopy(request.get("jobs", []))
    if not isinstance(jobs, list):
        raise ValueError("shared jobs must be an array")
    for job in jobs:
        if not isinstance(job, dict) or job.get("kind") not in {"producer", "report"}:
            raise ValueError("shared batch jobs may only be producers or reports")
    roster, seen = [], set()

    def inputs(job, local):
        values = job.get("inputs", {})
        if not isinstance(values, dict):
            raise ValueError("candidate inputs must be an object")
        job["inputs"] = {name(k): _source(v, catalog) for k, v in values.items()}
        dependencies = job.get("depends_on", [])
        if not isinstance(dependencies, list):
            raise ValueError("preparation dependencies must be an array")
        dependencies = [local.get(d, d) for d in dependencies]
        for value in job["inputs"].values():
            if isinstance(value, dict) and value.get("mode") == "artifact_ref":
                value["job"] = local.get(value["job"], value["job"])
                dependencies.append(value["job"])
        job["depends_on"] = list(dict.fromkeys(dependencies))
        for output in job.get("outputs", {}).values():
            if "requires" in output:
                references = []
                for port in output["requires"]:
                    if not isinstance(port, str) or port.count(".") != 1:
                        raise ValueError("output dependencies must name node.port")
                    node, leaf = port.split(".")
                    references.append(local.get(node, node) + "." + leaf)
                output["requires"] = references

    for job in jobs:
        inputs(job, {})
    for candidate in candidates:
        fields(
            candidate,
            OPTIONS | ({"models", "benchmarks"} if grouped else {"model"}) | {"id", "prepare"},
            {"id", "models" if grouped else "model"},
        )
        key = name(candidate["id"])
        if key in seen:
            raise ValueError("duplicate candidate ID")
        seen.add(key)
        models = _models(candidate["models"] if grouped else [candidate["model"]])
        benchmarks = (
            _models(candidate.get("benchmarks", defaults.get("benchmarks", [])), allow_empty=True)
            if grouped
            else []
        )
        merged = {
            **{k: v for k, v in defaults.items() if k in OPTIONS},
            **{k: v for k, v in candidate.items() if k in OPTIONS},
        }
        for field in ("inputs", "outputs", "testing", "resources"):
            first, second = defaults.get(field, {}), candidate.get(field, {})
            if not isinstance(first, dict) or not isinstance(second, dict):
                raise ValueError(field + " must be an object")
            merged[field] = {**deepcopy(first), **deepcopy(second)}
        arguments = _args(defaults.get("args", []), own_benchmarks=grouped) + _args(
            candidate.get("args", []), own_benchmarks=grouped
        )
        merged.update(id=key, kind="testing", args=[*_invocation(models, benchmarks), *arguments])
        preparation = deepcopy(candidate.get("prepare", []))
        if not isinstance(preparation, list):
            raise ValueError("prepare must be an array of explicit producer jobs")
        local = {}
        for step in preparation:
            if not isinstance(step, dict):
                raise ValueError("preparation steps must be objects")
            step_id = name(step.get("id"))
            if step_id in local or step_id == key:
                raise ValueError("duplicate or ambiguous preparation ID")
            local[step_id] = name(key + "--" + step_id)
        for step in preparation:
            step["id"] = local[step["id"]]
            step.setdefault("kind", "producer")
            if step["kind"] != "producer":
                raise ValueError("candidate preparation steps must be producers")
            for field in ("capsule", "runtime"):
                if field not in step and field in merged:
                    step[field] = deepcopy(merged[field])
            inputs(step, local)
            jobs.append(step)
        inputs(merged, local)
        # Every declared preparation step is part of this candidate's contract.
        merged["depends_on"] = list(dict.fromkeys([*merged["depends_on"], *local.values()]))
        jobs.append(merged)
        roster.append(
            {
                "id": key,
                "job_id": key,
                "preparation_jobs": list(local.values()),
                **(
                    {
                        "models": models,
                        "benchmarks": benchmarks,
                        "comparison_policy": "each_model_vs_each_benchmark",
                    }
                    if grouped
                    else {"model": models[0]}
                ),
            }
        )
    if len(jobs) > 128:
        raise ValueError("batch exceeds the 128-node workflow limit including preparation jobs")
    return {
        "schema": WORKFLOW_SCHEMA,
        "submission_id": request["submission_id"],
        "jobs": jobs,
        "batch": {"schema": RUN_ROSTER_SCHEMA if grouped else ROSTER_SCHEMA, entries: roster},
        **{k: deepcopy(request[k]) for k in ("return_policy", "metadata") if k in request},
    }


def validate_roster(workflow):
    """Bind all roles to actual invocations and prohibit cross-run private edges."""
    if "batch" not in workflow:
        return
    roster = workflow["batch"]
    if not isinstance(roster, dict):
        raise ValueError("batch roster must be an object")
    grouped = roster.get("schema") == RUN_ROSTER_SCHEMA
    entries = "runs" if grouped else "candidates"
    fields(roster, {"schema", entries}, {"schema", entries})
    if (
        roster["schema"] not in {ROSTER_SCHEMA, RUN_ROSTER_SCHEMA}
        or not isinstance(roster[entries], list)
        or not roster[entries]
    ):
        raise ValueError("invalid independent-candidate roster")
    jobs = {j["id"]: j for j in workflow["jobs"]}
    owners, seen, tests = {}, set(), set()
    for candidate in roster[entries]:
        keys = {"id", "job_id", "preparation_jobs"} | (
            {"models", "benchmarks", "comparison_policy"} if grouped else {"model"}
        )
        fields(
            candidate,
            keys,
            keys,
        )
        key = name(candidate["id"])
        if key in seen or candidate["job_id"] not in jobs:
            raise ValueError("duplicate candidate or missing testing node")
        seen.add(key)
        job = jobs[candidate["job_id"]]
        tests.add(job["id"])
        models = _models(candidate["models"] if grouped else [candidate["model"]])
        benchmarks = _models(candidate["benchmarks"], allow_empty=True) if grouped else []
        if grouped and candidate["comparison_policy"] != "each_model_vs_each_benchmark":
            raise ValueError("unsupported comparison policy")
        invocation = _invocation(models, benchmarks)
        if job["kind"] != "testing" or job["args"][: len(invocation)] != invocation:
            raise ValueError("candidate roster differs from its testing invocation")
        _args(job["args"][len(invocation) :], own_benchmarks=grouped)
        preparation = candidate["preparation_jobs"]
        if not isinstance(preparation, list) or len(set(preparation)) != len(preparation):
            raise ValueError("invalid preparation roster")
        for ident in [job["id"], *preparation]:
            if ident in owners or ident not in jobs:
                raise ValueError("candidate job ownership is ambiguous")
            owners[ident] = key
        if any(jobs[p]["kind"] != "producer" or p not in job["depends_on"] for p in preparation):
            raise ValueError("preparation must be a required producer dependency")
    if tests != {j["id"] for j in jobs.values() if j["kind"] in {"testing", "testing_stage"}}:
        raise ValueError("batch roster must cover every testing node")
    for ident, owner in owners.items():
        pending, visited = list(jobs[ident]["depends_on"]), set()
        while pending:
            parent = pending.pop()
            if parent in visited:
                continue
            visited.add(parent)
            if parent in owners and owners[parent] != owner:
                raise ValueError("independent candidates cannot depend on another candidate")
            pending.extend(jobs[parent]["depends_on"])


def candidate_results(manifest, index):
    """Deterministic local view; preserve failures and reference immutable evidence."""
    workflow = manifest["workflow"]
    if "batch" not in workflow:
        return None
    validate_roster(workflow)
    grouped = workflow["batch"]["schema"] == RUN_ROSTER_SCHEMA
    entries = "runs" if grouped else "candidates"
    nodes = {n["id"]: n for n in manifest["status"]["nodes"]}
    jobs = {j["id"]: j for j in workflow["jobs"]}
    candidates = []
    for entry in workflow["batch"][entries]:
        node = nodes[entry["job_id"]]
        envelope = node["outputs"] or {}
        ports = {}
        for ident in [entry["job_id"], *entry["preparation_jobs"]]:
            for port, details in (nodes[ident]["outputs"] or {}).get("ports", {}).items():
                key = ident + "." + port
                ports[key] = {**details, "local_directory": index.get(key)}
            diagnostic = ident + ".__diagnostics__"
            if diagnostic in index:
                ports[diagnostic] = {"local_directory": index[diagnostic]}
        candidates.append(
            {
                **entry,
                "job_spec_sha256": digest(jobs[entry["job_id"]]),
                "state": node["state"],
                "attempt": node["attempt"],
                "error": node["error"],
                "input_objects": envelope.get("input_objects", {}),
                "native_result": envelope.get("native_result"),
                "preparation": [
                    {k: nodes[p][k] for k in ("id", "state", "attempt", "error")}
                    for p in entry["preparation_jobs"]
                ],
                "ports": ports,
            }
        )
    return {
        "schema": RUN_RESULT_SCHEMA if grouped else RESULT_SCHEMA,
        "workflow_id": manifest["status"]["workflow_id"],
        "workflow_sha256": manifest["status"]["workflow_sha256"],
        "final": manifest["final"],
        entries: candidates,
        "scientific_family_aggregation": "NOT_PERFORMED",
        "performance_qualification": "NOT_ESTABLISHED",
    }
