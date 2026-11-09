"""Auto-bundler — translate a declarative JobSpec into a v2 SealedManifest.

This is the bridge between the spec/batch layer (v2/spec.py) and the
existing v2 sealed-bundle machinery (v2/seal.py, v2/manifest.py). It
makes "add a new workflow" a 1-file-per-job declarative change instead
of a Python coding task.

Inputs
------
- A `JobSpec` (parsed from JSON/YAML)
- A `roots` dict (from BatchSpec) for $VAR substitution in src/env/args
- An `upstream_state` dict: name → ResolvedUpstream(host, remote_workdir)
  populated by the batch executor as jobs complete. Empty for the first
  layer.
- A `bundle_out_dir` to stage the seal under
- A `hosts` config dict (same shape as hosts.json) — used to pick a host
  when JobSpec.host.alias is unset AND no affinity is declared

Output
------
A v2 `SealedManifest` ready for `v2.submit.submit_one`, plus the OutputsSpec
(returned alongside so the batch executor can do post-pull file moves to
the declared `to:` destinations).
"""
from __future__ import annotations

import json
import pathlib
import re
from dataclasses import dataclass
from typing import Optional

from .spec import (
    JobSpec, BundleEntry, RemoteRef, OutputsSpec,
    SpecError, _resolve_vars,
)
from .defaults import remote_workdir_default


_HERE = pathlib.Path(__file__).resolve().parent
_ORCH_ROOT = _HERE.parent                           # utils/offload_network/
_REPO_ROOT = _ORCH_ROOT.parent.parent               # fleet-offload/

# libemd.dll is bundled in every seal (stateless-host architecture,
# 2026-06-07). Drivers find it at workdir/blobs/native/libemd.dll;
# c_emd.python.emd_c also expects it at blobs/code/c_emd/build/libemd.dll.
_LIBEMD_WIN_DLL = _REPO_ROOT / "c_emd" / "build" / "windows" / "libemd.dll"


@dataclass
class ResolvedUpstream:
    """What the batch executor records about a completed upstream job
    so its downstream jobs can resolve remote_refs + affinity."""
    name: str
    host_alias: str
    remote_workdir: str            # eg. "<remote-root>/v2-cache.naturalgas-..."
    v2_job_id: str
    bundle_dir_local: pathlib.Path  # for fallback_local lookups


def _placeholder_re():
    return re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


def _substitute_vars(s: str, vars_: dict[str, str]) -> str:
    """Replace `{{var}}` placeholders. Missing var → SpecError."""
    pat = _placeholder_re()

    def _sub(m):
        name = m.group(1)
        if name not in vars_:
            raise SpecError(f"unresolved placeholder {{{{{name}}}}} in {s!r}; "
                            f"known vars: {sorted(vars_)}")
        return vars_[name]
    return pat.sub(_sub, s)


def _blob_rel_path(as_path: str) -> str:
    """Path stored under the seal archive's top-level blobs/ directory."""
    norm = as_path.replace("\\", "/").lstrip("/")
    return norm[len("blobs/"):] if norm.startswith("blobs/") else norm


def _runtime_blob_path(as_path: str) -> str:
    """Workdir-relative runtime path for a bundled artifact."""
    return f"blobs/{_blob_rel_path(as_path)}"


def _set_dotted_path(doc, path: str, value) -> None:
    """Set `doc[<path>]` where path is a dotted key chain, creating
    intermediate dicts if needed. List indices are supported via numeric
    components (``arr.0.field``). Used by Fix-4 cache-config rewriting.
    """
    parts = path.split(".")
    cur = doc
    for k in parts[:-1]:
        if isinstance(cur, list):
            cur = cur[int(k)]
        elif isinstance(cur, dict):
            if k not in cur:
                cur[k] = {}
            cur = cur[k]
        else:
            raise SpecError(
                f"rewrite_json path {path!r}: can't traverse into {type(cur).__name__} at {k!r}"
            )
    last = parts[-1]
    if isinstance(cur, list):
        cur[int(last)] = value
    elif isinstance(cur, dict):
        cur[last] = value
    else:
        raise SpecError(
            f"rewrite_json path {path!r}: can't assign into {type(cur).__name__} at {last!r}"
        )


def _resolve_local_src(src: str, roots: dict[str, str]) -> pathlib.Path:
    """Resolve a bundle entry's `src` against the batch roots + repo root.

    Resolution order:
      1. Apply $VAR substitution from roots / os.environ
      2. If the result is absolute, use as-is
      3. Else treat as relative to the repo root (fleet-offload/)
    """
    resolved = _resolve_vars(src, roots)
    p = pathlib.Path(resolved)
    if not p.is_absolute():
        p = _REPO_ROOT / p
    return p


def _pick_host_from_pool(hosts: dict, exclude: set[str] | None = None) -> str:
    """Default host picker — most-cored remote host that's bootstrapped.

    "Bootstrapped" means ``has_msys64=True`` (host can load libemd's
    runtime deps). libemd.dll itself ships IN the seal — hosts no
    longer need ``has_libemd``; that flag is still respected if set,
    but absence is no longer disqualifying.

    Pre-2026-06-07 hosts.json entries used ``has_libemd`` as the
    bootstrap flag; treat it as an alias for ``has_msys64`` when the
    new flag is missing, so the picker keeps working on legacy configs.
    """
    exclude = exclude or set()

    def _bootstrapped(cfg: dict) -> bool:
        if cfg.get("type") == "local":
            return False
        if "has_msys64" in cfg:
            return bool(cfg["has_msys64"])
        # Legacy: has_libemd was the only bootstrap flag.
        return bool(cfg.get("has_libemd"))

    candidates = sorted(
        (h for h, cfg in hosts.items()
         if _bootstrapped(cfg) and h not in exclude),
        key=lambda h: hosts[h].get("cores", 0), reverse=True,
    )
    if not candidates:
        raise SpecError(
            "no eligible bootstrapped remote host available "
            "(need has_msys64=true or legacy has_libemd=true)"
        )
    return candidates[0]


def _is_host_reachable(host_alias: str, timeout_s: int = 10) -> bool:
    """Probe a host with a 1-line SSH echo. Used to test affinity-host
    liveness before pinning a downstream job to it. Returns True iff the
    host responds within timeout.

    Lazy import of transport so this module stays importable without
    pulling rsync etc.
    """
    try:
        from .transport import remote_run
        r = remote_run(
            host_alias=host_alias,
            powershell_script="Write-Output PONG",
            timeout=timeout_s,
        )
        return r.returncode == 0 and "PONG" in (r.stdout or "")
    except Exception:
        return False


def _resolve_host_alias(
    spec: JobSpec,
    hosts: dict,
    upstream_state: dict[str, ResolvedUpstream],
    *,
    probe_affinity_host: bool = False,
    host_pool: list[str] | None = None,
) -> tuple[str, dict, bool]:
    """Pick the host this job should run on. Returns (alias, hcfg, affinity_alive).

    `host_pool`, when provided, restricts the picker to ONLY those host
    aliases — used by the batch executor to honour policy.host_pool. An
    explicit ``spec.host.alias`` overrides the pool (operator-set is
    sticky); affinity also overrides (downstream follows its upstream
    even if the upstream isn't in the pool).

    `affinity_alive` is True iff the job was placed on an affinity host
    AND that host responded to the liveness probe (or probing was off).
    A False here while spec.host.affinity is set means the affinity host
    was unreachable and we fell back to a pool pick — callers may then
    need to switch any matching ``remote_refs`` over to their
    ``fallback_local`` paths (handled in build_manifest_from_spec).
    """
    if spec.host.alias:
        if spec.host.alias not in hosts:
            raise SpecError(f"job {spec.name!r} host.alias={spec.host.alias!r} not in hosts.json")
        return spec.host.alias, hosts[spec.host.alias], True
    # Construct the eligible-hosts view: full hosts.json minus anything
    # the pool excludes (when a pool is set).
    eligible_hosts = (
        {h: cfg for h, cfg in hosts.items() if h in host_pool}
        if host_pool else hosts
    )
    if spec.host.affinity:
        up = upstream_state.get(spec.host.affinity)
        if up is None:
            raise SpecError(
                f"job {spec.name!r} affinity={spec.host.affinity!r} not yet completed "
                f"(batch executor invoked autobundle out of order)"
            )
        if up.host_alias not in hosts:
            raise SpecError(
                f"affinity-resolved host {up.host_alias!r} not in hosts.json"
            )
        if probe_affinity_host and not _is_host_reachable(up.host_alias):
            # Affinity host is down → fall back to a pool pick. The caller
            # will look for remote_refs with fallback="bundle_from_local"
            # and swap them to local-bundle blobs.
            pool_alias = _pick_host_from_pool(eligible_hosts, exclude={up.host_alias})
            return pool_alias, hosts[pool_alias], False
        return up.host_alias, hosts[up.host_alias], True
    # No alias / no affinity → pick the most-cored idle libemd host
    # from the eligible pool.
    alias = _pick_host_from_pool(eligible_hosts)
    return alias, hosts[alias], True


def _result_spec_for(spec: JobSpec, *, ResultSpec, bundle_out_dir: pathlib.Path,
                     v2_job_id: str):
    """Pick the sealed result archive policy for a job.

    Cache jobs can legitimately create tens-of-GB ``outputs/cache/*.mat``
    files. Those must not go into the sealed result tarball; the batch
    layer pulls them explicitly with direct rsync when outputs.pull asks
    for them, and cache-stage jobs keep them on the remote for downstream
    affinity consumers.
    """
    subkind = str(spec.metadata.get("phase_subkind") or "")
    is_cache_artifact_job = spec.phase == "cache" or subkind in {
        "cache_build", "cache_stage",
    }
    if is_cache_artifact_job:
        return ResultSpec(
            local_dir=str(bundle_out_dir / "pulled" / v2_job_id),
            include_patterns=[
                "outputs/report.json",
                "outputs/metadata/**",
                "outputs/cache_builds/**",
                "report.json",
                "status.json",
                "run.log",
                "bootstrap.log",
            ],
            exclude_patterns=[
                "outputs/cache/**",
                "*.tmp",
                ".rsync-partial/",
            ],
            archive_format="tar.gz",
            max_size_mb=512,
        )
    return ResultSpec(
        local_dir=str(bundle_out_dir / "pulled" / v2_job_id),
        include_patterns=[
            "outputs/**",
            "report.json",
            "status.json",
            "run.log",
            "bootstrap.log",
        ],
        exclude_patterns=["*.tmp", ".rsync-partial/"],
        archive_format="tar.gz",
        max_size_mb=4096,
    )


def build_manifest_from_spec(
    spec: JobSpec,
    *,
    job_id: int,
    bundle_out_dir: pathlib.Path,
    hosts: dict,
    roots: dict[str, str] | None = None,
    upstream_state: dict[str, ResolvedUpstream] | None = None,
    probe_affinity_host: bool = False,
    host_pool: list[str] | None = None,
):
    """The main entry point — produces a v2 SealedManifest from a spec.

    Returns (manifest, outputs_spec). The outputs_spec is returned
    alongside so the batch executor knows what to rsync back AFTER the
    submit's own result-pull (the manifest's result.include_patterns
    catches everything in outputs/, and the post-pull step then moves
    specific files to their declared `to:` destinations on the Mac).

    When ``probe_affinity_host=True``, a job with ``host.affinity`` is
    only pinned to its upstream's host if that host responds to a
    liveness probe; if the affinity host is down, the job is migrated
    to a fresh pool pick AND any remote_refs with
    fallback="bundle_from_local" have their referenced files bundled
    into the seal instead.
    """
    # Lazy import to keep this module light.
    from .manifest import SealedManifest, SealedBlob, HostSpec, ResultSpec

    roots = dict(roots or {})
    upstream_state = dict(upstream_state or {})
    spec.validate()

    host_alias, hcfg, affinity_alive = _resolve_host_alias(
        spec, hosts, upstream_state,
        probe_affinity_host=probe_affinity_host,
        host_pool=host_pool,
    )
    # When affinity is BROKEN (host down), we'll swap any matching
    # remote_refs to their fallback_local blobs. Track this so the right
    # vars get the right substitution.
    affinity_broken_for: set[str] = (
        {spec.host.affinity} if (spec.host.affinity and not affinity_alive)
        else set()
    )

    # Build the bundle: one SealedBlob per inputs.bundle entry, plus the
    # generic driver. Track interpolation vars as we go.
    work_root = remote_workdir_default(hcfg).rstrip("/\\")
    vars_: dict[str, str] = {
        "job_id": str(job_id),
        "remote_workdir": work_root,
    }
    blobs: list = []

    # The generic driver always goes in at code/generic.py.
    driver_src = str(_HERE / "drivers" / "generic.py")
    blobs.append(SealedBlob(
        name="driver",
        local_src=driver_src,
        rel_path="code/generic.py",
        is_dir=False,
    ))

    # libemd.dll ships in EVERY seal so remote hosts can run cold
    # (only need SSH+rsync+python+msys64). Drivers find it at
    # workdir/blobs/native/libemd.dll. rel_path is "native/libemd.dll"
    # because the runner places blobs at workdir/blobs/{rel_path}.
    # Skip silently if the local checkout doesn't have it built (e.g.
    # running from a Mac without a Windows cross-build); the driver's
    # host-repo fallback covers that case for bootstrapped hosts.
    if _LIBEMD_WIN_DLL.is_file():
        blobs.append(SealedBlob(
            name="libemd_dll",
            local_src=str(_LIBEMD_WIN_DLL),
            rel_path="native/libemd.dll",
            is_dir=False,
        ))
        blobs.append(SealedBlob(
            name="libemd_dll_c_emd_build",
            local_src=str(_LIBEMD_WIN_DLL),
            rel_path="code/c_emd/build/libemd.dll",
            is_dir=False,
        ))

    # If entry.kind == script and entry.src is set (or path is bundle-relative),
    # auto-bundle the script. If kind == module, no extra script blob.
    script_relpath: Optional[str] = None
    if spec.entry.kind == "script":
        script_src = spec.entry.src or spec.entry.path
        # Determine the rel_path the script lives under inside the seal.
        # If user didn't bundle it explicitly via inputs.bundle, we put it
        # at code/<basename>.
        explicit_bundle = next(
            (b for b in spec.inputs.bundle
             if _resolve_local_src(b.src, roots) == _resolve_local_src(script_src, roots)),
            None,
        )
        if explicit_bundle:
            script_relpath = explicit_bundle.as_
        else:
            local = _resolve_local_src(script_src, roots)
            script_relpath = f"code/{local.name}"
            blobs.append(SealedBlob(
                name="entry_script",
                local_src=str(local),
                rel_path=script_relpath,
                is_dir=local.is_dir(),
            ))

    # User-declared bundle entries. Two-pass: first establish vars for
    # entries WITHOUT rewrite_json so rewrite rules can reference them
    # via {{var}}, then process rewrites in a second pass.
    rewrite_pending: list[tuple[int, BundleEntry, pathlib.Path]] = []
    for i, b in enumerate(spec.inputs.bundle):
        b.validate()
        local = _resolve_local_src(b.src, roots)
        if not local.exists():
            raise SpecError(
                f"job {spec.name!r}: bundle entry .src={b.src!r} → {local} "
                f"does not exist on the Mac"
            )
        if b.var:
            # Path INSIDE the seal workdir, NOT a Mac path. The driver runs
            # cwd=workdir so "blobs/<as_>" is the right reference.
            vars_[b.var] = _runtime_blob_path(b.as_)
        if b.rewrite_json:
            # Defer adding the SealedBlob until pass 2 — we need to write
            # the rewritten JSON to a tmp file and bundle THAT instead.
            rewrite_pending.append((i, b, local))
            continue
        blobs.append(SealedBlob(
            name=f"bundle_{i}_{pathlib.Path(b.src).name}",
            local_src=str(local),
            rel_path=_blob_rel_path(b.as_),
            is_dir=local.is_dir(),
        ))

    # Pass 2 — rewrite_json. We materialise the rewritten file under
    # bundle_out_dir/_rewritten/<spec.name>/<as_> so the original Mac-side
    # config stays untouched. The seal's blob points at the rewritten copy.
    if rewrite_pending:
        rewrite_root = bundle_out_dir / "_rewritten" / spec.name
        rewrite_root.mkdir(parents=True, exist_ok=True)
        for i, b, local in rewrite_pending:
            if not local.is_file():
                raise SpecError(
                    f"job {spec.name!r}: rewrite_json requires a regular file, "
                    f"got dir/missing: {local}"
                )
            try:
                doc = json.loads(local.read_text())
            except json.JSONDecodeError as e:
                raise SpecError(
                    f"job {spec.name!r}: bundle entry {b.src!r} has rewrite_json "
                    f"but isn't valid JSON: {e}"
                )
            for rule in b.rewrite_json:
                value = _substitute_vars(rule["value"], vars_)
                _set_dotted_path(doc, rule["path"], value)
            patched = rewrite_root / pathlib.Path(b.as_).name
            patched.write_text(json.dumps(doc, indent=2))
            blobs.append(SealedBlob(
                name=f"bundle_{i}_{pathlib.Path(b.src).name}",
                local_src=str(patched),
                rel_path=_blob_rel_path(b.as_),
                is_dir=False,
            ))

    # Remote refs: resolve each to its upstream's <remote_workdir>/<remote_path>
    # UNLESS the affinity host is down + fallback_local is set — in which
    # case ship the local copy as an extra blob and resolve the var to that.
    n_fallback_blobs = 0
    for r in spec.inputs.remote_refs:
        up = upstream_state.get(r.from_)
        if up is None:
            raise SpecError(
                f"job {spec.name!r}: remote_ref from={r.from_!r} but upstream not yet completed "
                f"(batch executor invoked autobundle out of order)"
            )
        if r.from_ in affinity_broken_for and r.fallback == "bundle_from_local":
            # Ship the local copy as a blob, resolve var to bundle-internal path.
            local = _resolve_local_src(r.fallback_local, roots)
            if not local.exists():
                raise SpecError(
                    f"job {spec.name!r}: affinity host {up.host_alias!r} unreachable; "
                    f"fallback_local={r.fallback_local!r} → {local} does not exist on Mac"
                )
            rel = f"fallback/{r.from_}/{local.name}"
            blobs.append(SealedBlob(
                name=f"fallback_{n_fallback_blobs}_{local.name}",
                local_src=str(local),
                rel_path=rel,
                is_dir=local.is_dir(),
            ))
            n_fallback_blobs += 1
            vars_[r.var] = f"blobs/{rel}"
        else:
            vars_[r.var] = f"{up.remote_workdir.rstrip('/')}/{r.remote_path.lstrip('/')}"

    # Interpolate args + env. Each {{var}} comes from vars_.
    interpolated_args = [_substitute_vars(a, vars_) for a in spec.args]
    interpolated_env = {k: _substitute_vars(v, vars_) for k, v in spec.env.items()}
    # Ensure PYTHONIOENCODING for Windows safety (matches existing builders).
    interpolated_env.setdefault("PYTHONIOENCODING", "utf-8")

    # Construct the driver call. Generic driver takes --module M or --script S
    # plus --pass-args-shlex "..." for the wrapped command's args.
    import shlex as _shlex
    if spec.entry.kind == "module":
        run_args = ["--module", spec.entry.path]
    else:
        # --script expects a path relative to blobs/code/, but our generic
        # driver resolves --script as relative to blobs/code/ already.
        # script_relpath is "code/<name>" or "blobs/<...>" → trim the leading
        # "blobs/" if present and the "code/" since the driver prepends it.
        rp = script_relpath or ""
        if rp.startswith("blobs/"):
            rp = rp[len("blobs/"):]
        if rp.startswith("code/"):
            rp = rp[len("code/"):]
        run_args = ["--script", rp]
    if interpolated_args:
        run_args += ["--pass-args-shlex", _shlex.join(interpolated_args)]

    # Build the per-job v2 job_id; keep it path-safe (no slashes/spaces).
    safe_jobname = spec.name.replace("/", "-").replace(".", "_")
    v2_job_id = f"v2-spec-{job_id}-{safe_jobname}-{host_alias}"

    manifest = SealedManifest(
        job_id=v2_job_id,
        host=HostSpec(
            ssh_alias=hcfg.get("ssh_alias", host_alias),
            remote_workdir=work_root,
            platform=hcfg.get("platform", "windows"),
            user=hcfg.get("user"),
            rsync_path=hcfg.get("rsync_path"),
            python_executable=hcfg.get(
                "python_executable",
                "python3" if hcfg.get("platform") in {"linux", "macos"} else "python",
            ),
        ),
        blobs=blobs,
        entrypoint_rel="code/generic.py",
        run_args=run_args,
        env=interpolated_env,
        extra_pythonpath=[],
        result=_result_spec_for(
            spec, ResultSpec=ResultSpec, bundle_out_dir=bundle_out_dir,
            v2_job_id=v2_job_id,
        ),
        archive_format="tar.gz",
        metadata={
            "task_type": f"spec_v2_{spec.phase}",
            "spec_name": spec.name,
            "spec_phase": spec.phase,
            "fleet_job_id": job_id,
            "via": "v2",
            "affinity_failed_over": bool(affinity_broken_for),
            **spec.metadata,
        },
    )
    return manifest, spec.outputs


def expected_remote_workdir(manifest) -> str:
    """Helper: the workdir path on the remote where this manifest's
    bundle will live after extraction. Needed when recording
    ResolvedUpstream after the job completes."""
    base = manifest.host.remote_workdir.rstrip("/\\")
    return f"{base}/{manifest.job_id}"
