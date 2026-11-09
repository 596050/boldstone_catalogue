"""Declarative job-spec layer for v2.

A "job spec" is a JSON/YAML file that DECLARES what a job needs (inputs,
outputs, entry-point, dependencies) instead of HAND-WRITING a manifest
builder in Python. The autobundler (v2/autobundle.py) reads a spec and
emits a v2 SealedManifest; the batch executor (v2/batch.py) reads a
batch.json (a list of spec files + policy) and runs the resulting DAG.

This file owns just the SCHEMA + parsing + validation. Nothing here
touches a remote or builds a manifest — those live in autobundle.py
and batch.py.

Spec example (a cache build for the retro_last_week_cutoff batch):

    {
      "name": "cache.naturalgas",
      "phase": "cache",
      "host": {"alias": "cdec"},
      "entry": {
        "kind": "script",
        "path": "model_research/implementations/build_cutoff_emd_cache.py"
      },
  "args": ["--config", "{{config_file}}"],
  "env": {
    "FAMOUS_MODEL_WORK_ROOT": "{{remote_workdir}}/{{job_id}}/work"
  },
      "inputs": {
        "bundle": [
          {"src": "trading_common", "as": "code/trading_common"},
          {"src": "c_emd/python", "as": "code/c_emd/python"},
          {"src": "c_emd/__init__.py", "as": "code/c_emd/__init__.py"},
          {"src": "model_research/implementations",
           "as": "code/model_research/implementations"},
          {"src": "$RUN/configs/cache_jobs/naturalgas.json",
           "as": "config/naturalgas.json",
           "var": "config_file"}
        ],
        "remote_refs": []
      },
      "outputs": {
        "pull": [
          {"remote": "outputs/cache/*.mat",
           "to": "$CACHE_ROOT/naturalgas_260117_1000_aa2/"},
          {"remote": "outputs/cache_builds/*.log",
           "to": "$RUN/logs/cache_builds/"}
        ]
      },
      "deps": []
    }

The {{job_id}} / {{config_file}} placeholders are resolved by
autobundle.py at build time. $RUN / $CACHE_ROOT are resolved against the
batch's `roots` map (or os.environ as a fallback).
"""
from __future__ import annotations

import dataclasses
import json
import pathlib
import re
from dataclasses import dataclass, field
from typing import Any, Optional


class SpecError(Exception):
    """Raised on invalid spec files (bad schema, cycles, unknown deps)."""


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class EntrySpec:
    """How the wrapped python is invoked.

    ``kind="module"`` → ``python -m <path>``.
    ``kind="script"`` → ``python <script>``; the script is auto-bundled
    from its `src` (defaults to ``path``) into ``code/`` inside the seal.
    """
    kind: str                     # "module" | "script"
    path: str                     # dotted module name OR script path
    src: Optional[str] = None     # script source (defaults to `path` for scripts)

    def validate(self) -> None:
        if self.kind not in ("module", "script"):
            raise SpecError(f"entry.kind must be 'module' or 'script', got {self.kind!r}")
        if not self.path:
            raise SpecError("entry.path is required")
        if self.kind == "module" and "/" in self.path:
            raise SpecError(f"entry.kind=module path should be dotted, not a filesystem path: {self.path!r}")


@dataclass
class BundleEntry:
    """One file/directory to ship inside the seal.

    `src` may be absolute or relative-to-repo-root (resolution happens in
    autobundle.py against the batch's `roots`). `as_` is the rel_path
    inside the seal's blobs/ tree. `var` (optional) gives this entry a
    name that can be referenced as ``{{var}}`` in args/env — the
    substitution resolves to the bundle-internal path (eg.
    ``blobs/config/naturalgas.json``).

    `rewrite_json` (optional, Fix-4) lets the autobundler patch dotted
    paths inside a JSON config file BEFORE sealing it, so paths that are
    Mac-side on disk become bundle-internal on the remote. Each rule:

      {"path": "data.tick_archive", "value": "blobs/data/ng_ticks.json"}

    `value` strings may contain ``{{var}}`` placeholders that resolve
    against the autobundler's var map (job_id, other bundle entries'
    vars). Useful for shipping cache configs whose original `data:` /
    `output:` paths point to Mac-side `/Volumes/...` paths.
    """
    src: str
    as_: str
    var: Optional[str] = None
    rewrite_json: list[dict] = field(default_factory=list)

    def validate(self) -> None:
        if not self.src:
            raise SpecError("bundle entry .src is required")
        if not self.as_:
            raise SpecError(f"bundle entry .as is required for src={self.src!r}")
        if self.as_.startswith("/") or "\\" in self.as_:
            raise SpecError(f"bundle entry .as must be a forward-slash rel path, got {self.as_!r}")
        for r in self.rewrite_json:
            if not isinstance(r, dict) or "path" not in r or "value" not in r:
                raise SpecError(
                    f"bundle entry rewrite_json rule must have 'path' and 'value' keys; got {r!r}"
                )
            if not isinstance(r["path"], str) or not isinstance(r["value"], str):
                raise SpecError(
                    f"bundle entry rewrite_json rule path/value must be strings; got {r!r}"
                )


@dataclass
class RemoteRef:
    """Reference to an output of an upstream job that lives on the remote
    host. No data is shipped — just an interpolated path string.

    Implies a host-affinity constraint: the consuming job MUST run on the
    same host the upstream ran on (enforced by batch.py). Fallback policy
    lets a spec opt into "if affinity host is unreachable, ship a local
    copy instead" — typically used when the upstream's output was ALSO
    pulled to a Mac-side canonical path.
    """
    from_: str                    # upstream job name
    remote_path: str              # path RELATIVE to upstream's workdir
    var: str                      # name for {{var}} interpolation
    fallback: str = "fail"        # "fail" | "bundle_from_local"
    fallback_local: Optional[str] = None  # local path used if fallback="bundle_from_local"

    def validate(self) -> None:
        if not self.from_:
            raise SpecError("remote_ref .from is required")
        if not self.remote_path:
            raise SpecError(f"remote_ref .remote_path is required (from={self.from_!r})")
        if not self.var:
            raise SpecError(f"remote_ref .var is required (from={self.from_!r})")
        if self.fallback not in ("fail", "bundle_from_local"):
            raise SpecError(f"remote_ref .fallback must be 'fail' or 'bundle_from_local', got {self.fallback!r}")
        if self.fallback == "bundle_from_local" and not self.fallback_local:
            raise SpecError(
                f"remote_ref(from={self.from_!r}) has fallback='bundle_from_local' "
                f"but no fallback_local path"
            )


@dataclass
class InputsSpec:
    bundle: list[BundleEntry] = field(default_factory=list)
    remote_refs: list[RemoteRef] = field(default_factory=list)

    def validate(self) -> None:
        for b in self.bundle:
            b.validate()
        for r in self.remote_refs:
            r.validate()
        # vars must be unique across bundle + remote_refs
        seen: dict[str, str] = {}
        for b in self.bundle:
            if b.var:
                if b.var in seen:
                    raise SpecError(f"duplicate var {b.var!r} in inputs")
                seen[b.var] = f"bundle({b.src})"
        for r in self.remote_refs:
            if r.var in seen:
                raise SpecError(
                    f"duplicate var {r.var!r}: {seen[r.var]} vs remote_ref({r.from_})"
                )
            seen[r.var] = f"remote_ref({r.from_})"


@dataclass
class OutputPull:
    """One post-run rsync from remote workdir back to a Mac-side location."""
    remote: str           # relative to workdir's outputs/ (may include glob)
    to: str               # Mac-side dir (must end with / for dir) or file path

    def validate(self) -> None:
        if not self.remote:
            raise SpecError("outputs.pull .remote is required")
        if not self.to:
            raise SpecError("outputs.pull .to is required")


@dataclass
class OutputsSpec:
    pull: list[OutputPull] = field(default_factory=list)

    def validate(self) -> None:
        for p in self.pull:
            p.validate()


@dataclass
class HostSpec:
    """Where this job runs. Either explicit (alias) or constrained
    (affinity to an upstream job's resolved host). Mutually exclusive."""
    alias: Optional[str] = None
    affinity: Optional[str] = None       # upstream job name

    def validate(self) -> None:
        if self.alias and self.affinity:
            raise SpecError("host.alias and host.affinity are mutually exclusive")
        # Either or neither is OK — dispatcher picks an idle host with libemd
        # when both are unset.


@dataclass
class JobSpec:
    """One job in a batch. Parsed from a JSON/YAML file."""
    name: str
    phase: str = "default"
    host: HostSpec = field(default_factory=HostSpec)
    entry: EntrySpec = None  # type: ignore[assignment]
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    inputs: InputsSpec = field(default_factory=InputsSpec)
    outputs: OutputsSpec = field(default_factory=OutputsSpec)
    deps: list[str] = field(default_factory=list)
    # Free-form per-job metadata — passed through to manifest.metadata.
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.name:
            raise SpecError("job .name is required")
        if "/" in self.name or " " in self.name:
            raise SpecError(f"job .name must be path-safe (no '/' or spaces): {self.name!r}")
        self.host.validate()
        if self.entry is None:
            raise SpecError(f"job {self.name!r} missing entry")
        self.entry.validate()
        self.inputs.validate()
        self.outputs.validate()
        for d in self.deps:
            if not d or " " in d:
                raise SpecError(f"job {self.name!r} has bad dep {d!r}")

    @classmethod
    def from_dict(cls, d: dict) -> "JobSpec":
        return cls(
            name=d["name"],
            phase=d.get("phase", "default"),
            host=_host_from_dict(d.get("host", {})),
            entry=_entry_from_dict(d["entry"]),
            args=list(d.get("args", [])),
            env=dict(d.get("env", {})),
            inputs=_inputs_from_dict(d.get("inputs", {})),
            outputs=_outputs_from_dict(d.get("outputs", {})),
            deps=list(d.get("deps", [])),
            metadata=dict(d.get("metadata", {})),
        )

    @classmethod
    def from_path(cls, p: str | pathlib.Path) -> "JobSpec":
        return _load_spec(pathlib.Path(p), cls)


@dataclass
class BatchSpec:
    """A batch = a named collection of jobs (resolved via globs) +
    runtime policy (parallelism caps, failure handling, host pool).
    """
    batch: str                              # human label
    jobs: list[JobSpec] = field(default_factory=list)
    roots: dict[str, str] = field(default_factory=dict)    # $VAR substitution table
    policy: dict[str, Any] = field(default_factory=dict)
    # Loaded source paths (one per job spec file) — kept for debug/state.
    job_source_paths: list[pathlib.Path] = field(default_factory=list)

    def validate(self) -> None:
        if not self.batch:
            raise SpecError("batch .batch label is required")
        if not self.jobs:
            raise SpecError("batch has no jobs")
        # Names must be unique
        names = [j.name for j in self.jobs]
        dups = {n for n in names if names.count(n) > 1}
        if dups:
            raise SpecError(f"duplicate job names: {sorted(dups)}")
        # All deps + affinities must resolve to a job name in this batch
        name_set = set(names)
        for j in self.jobs:
            for d in j.deps:
                if d not in name_set:
                    raise SpecError(
                        f"job {j.name!r} has dep {d!r} but no job by that name in the batch"
                    )
            if j.host.affinity and j.host.affinity not in name_set:
                raise SpecError(
                    f"job {j.name!r} has affinity to {j.host.affinity!r} but no such job in the batch"
                )
            # affinity ⇒ dep (you can't pin to something whose host you don't know)
            if j.host.affinity and j.host.affinity not in j.deps:
                raise SpecError(
                    f"job {j.name!r}: affinity to {j.host.affinity!r} requires a corresponding entry in deps"
                )
        # No cycles
        _detect_cycles(self.jobs)
        for j in self.jobs:
            j.validate()

    @classmethod
    def from_path(cls, p: str | pathlib.Path) -> "BatchSpec":
        """Load a batch.json. `jobs` may contain globs which are expanded
        against the batch file's directory. Roots are resolved via the
        batch's `roots` map (with $VAR fallback to os.environ).
        """
        import os, glob
        p = pathlib.Path(p).resolve()
        d = json.loads(p.read_text())
        roots = dict(d.get("roots", {}))
        # Expand $VAR refs in roots themselves (eg. CACHE_ROOT may reference $RUN)
        for k, v in list(roots.items()):
            roots[k] = _resolve_vars(v, roots)
        job_specs: list[JobSpec] = []
        source_paths: list[pathlib.Path] = []
        for jpat in d.get("jobs", []):
            expanded = _resolve_vars(jpat, roots)
            # If path contains a glob, expand from the batch file's dir
            base = p.parent
            if any(c in expanded for c in "*?["):
                matches = sorted(pathlib.Path(g) for g in glob.glob(str(base / expanded)))
                if not matches:
                    raise SpecError(f"job glob {expanded!r} matched no files (from batch {p})")
                for m in matches:
                    job_specs.append(JobSpec.from_path(m))
                    source_paths.append(m)
            else:
                jpath = base / expanded if not pathlib.Path(expanded).is_absolute() else pathlib.Path(expanded)
                job_specs.append(JobSpec.from_path(jpath))
                source_paths.append(jpath)
        bs = cls(
            batch=d["batch"],
            jobs=job_specs,
            roots=roots,
            policy=dict(d.get("policy", {})),
            job_source_paths=source_paths,
        )
        bs.validate()
        return bs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _host_from_dict(d: dict) -> HostSpec:
    return HostSpec(alias=d.get("alias"), affinity=d.get("affinity"))


def _entry_from_dict(d: dict) -> EntrySpec:
    return EntrySpec(kind=d["kind"], path=d["path"], src=d.get("src"))


def _inputs_from_dict(d: dict) -> InputsSpec:
    bundle = [
        BundleEntry(
            src=e["src"], as_=e["as"], var=e.get("var"),
            rewrite_json=list(e.get("rewrite_json", [])),
        )
        for e in d.get("bundle", [])
    ]
    remote_refs = [
        RemoteRef(
            from_=e["from"], remote_path=e["remote_path"], var=e["var"],
            fallback=e.get("fallback", "fail"),
            fallback_local=e.get("fallback_local"),
        )
        for e in d.get("remote_refs", [])
    ]
    return InputsSpec(bundle=bundle, remote_refs=remote_refs)


def _outputs_from_dict(d: dict) -> OutputsSpec:
    return OutputsSpec(
        pull=[OutputPull(remote=e["remote"], to=e["to"]) for e in d.get("pull", [])]
    )


def _load_spec(p: pathlib.Path, cls):
    """Load a single JobSpec from a JSON file. (YAML support is opt-in:
    if the path ends with .yaml/.yml and PyYAML is importable, we use it;
    else we fall back to expecting JSON in any case.)
    """
    p = p.resolve()
    text = p.read_text()
    suffix = p.suffix.lower()
    data: dict
    if suffix in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore
            data = yaml.safe_load(text)
        except ImportError:
            raise SpecError(
                f"spec {p} is YAML but PyYAML is not installed. "
                f"Either `pip install pyyaml` or rewrite as JSON."
            )
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        raise SpecError(f"spec {p} must be a JSON/YAML object")
    return cls.from_dict(data)


_VAR_RE = re.compile(r"\$([A-Z_][A-Z0-9_]*)")


def _resolve_vars(s: str, roots: dict[str, str]) -> str:
    """Substitute $VAR refs from the roots map (falling back to env)."""
    import os

    def _sub(m):
        name = m.group(1)
        if name in roots:
            return roots[name]
        if name in os.environ:
            return os.environ[name]
        raise SpecError(f"unresolved $-variable {name!r} (not in roots, not in env)")
    return _VAR_RE.sub(_sub, s)


def _detect_cycles(jobs: list["JobSpec"]) -> None:
    """Raise SpecError on any cycle in the dep DAG (Kahn's algorithm)."""
    by_name = {j.name: j for j in jobs}
    in_degree = {j.name: 0 for j in jobs}
    for j in jobs:
        for d in j.deps:
            if d in by_name:
                in_degree[j.name] += 1
    queue = [n for n, d in in_degree.items() if d == 0]
    visited = 0
    while queue:
        n = queue.pop()
        visited += 1
        # Decrement in-degrees of n's dependents
        for j in jobs:
            if n in j.deps:
                in_degree[j.name] -= 1
                if in_degree[j.name] == 0:
                    queue.append(j.name)
    if visited != len(jobs):
        cycle_members = [n for n, d in in_degree.items() if d > 0]
        raise SpecError(f"dependency cycle detected involving: {sorted(cycle_members)}")


def topological_layers(jobs: list[JobSpec]) -> list[list[JobSpec]]:
    """Return jobs grouped into layers: layer K can start once layer K-1
    is fully complete. Inside a layer there are no inter-job dependencies.

    This is the unit the batch executor dispatches per round.
    """
    remaining = {j.name: j for j in jobs}
    done: set[str] = set()
    layers: list[list[JobSpec]] = []
    while remaining:
        ready = [
            j for j in remaining.values()
            if all(d in done or d not in {k.name for k in jobs}
                   for d in j.deps)
            and not any(d in remaining for d in j.deps)
        ]
        if not ready:
            raise SpecError(
                f"could not advance topological sort; remaining={sorted(remaining)}"
            )
        layers.append(sorted(ready, key=lambda j: j.name))
        for j in ready:
            done.add(j.name)
            del remaining[j.name]
    return layers
