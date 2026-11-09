"""Scenario runner — the engine behind v2/tests/test_scenarios.py.

Each scenario lives in its own directory:
  v2/tests/scenarios/<name>/
    scenario.json           ← INPUT  (workflow, args, fake hosts)
    expected_manifest.json  ← GOLDEN (normalised manifest)
    expected_summary.json   ← OPTIONAL (live-mode result expectations)

The runner:
  1. Reads scenario.json
  2. Calls the right v2.fleet_adapter._build_X_manifest() based on workflow
  3. Normalises the produced manifest (strips timestamps, sha256s, abs paths,
     bundle_out_dir, etc. — anything that varies run-to-run)
  4. In CHECK mode (default): diffs against expected_manifest.json
     In UPDATE mode (env UPDATE_GOLDEN=1): rewrites expected_manifest.json
  5. In LIVE mode (env V2_LIVE_TESTS=1 + scenario.live=true): also runs
     the manifest on a real remote and diffs the result summary

Why config-driven: adding a new test scenario is now a 1-file change
(scenario.json + first-run goldens). No Python test code to write.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import sys
import tempfile
from typing import Any, Optional

if str(pathlib.Path(__file__).resolve().parents[3]) not in sys.path:
    sys.path.insert(
        0, str(pathlib.Path(__file__).resolve().parents[3]),
    )
from fleet.paths import fleet_dir


HERE = pathlib.Path(__file__).resolve().parent          # v2/tests/scenarios/
V2_DIR = HERE.parent.parent                              # v2/
ORCH_ROOT = V2_DIR.parent                                # utils/offload_network/
REPO_ROOT = ORCH_ROOT.parent.parent                      # fleet-offload/

# Volatile fields that vary run-to-run and must be normalised before diffing.
# Each maps to its placeholder value in the golden snapshot.
NORMALISE_PLACEHOLDERS = {
    "created_at":       "<TIMESTAMP>",
    "seal_sha256":      "<SEAL_SHA>",
    "seal_size_bytes":  "<SEAL_SIZE>",
    "seal_path_local":  "<SEAL_PATH>",
    "status":           "<STATUS>",
    "last_error":       "<NONE>",
}

# Absolute path prefixes we substitute with portable tokens. Order matters —
# longer prefixes first so they match before shorter ones.
PATH_TOKENS = [
    (str(REPO_ROOT), "<REPO>"),
    (str(fleet_dir() / "v2_bundles"), "<BUNDLES>"),
    (str(fleet_dir()), "<FLEET_STATE>"),
    (str(pathlib.Path.home()), "<HOME>"),
    (tempfile.gettempdir(), "<TMP>"),
]


def discover_scenarios() -> list[pathlib.Path]:
    """Return every subdirectory of v2/tests/scenarios/ that contains a
    scenario.json file. Sorted for deterministic test ordering."""
    return sorted(
        d for d in HERE.iterdir()
        if d.is_dir() and (d / "scenario.json").is_file()
    )


def load_scenario(scenario_dir: pathlib.Path) -> dict:
    """Read scenario.json + validate the minimum schema."""
    sj = json.loads((scenario_dir / "scenario.json").read_text())
    required = ("name", "workflow", "args", "hosts")
    missing = [k for k in required if k not in sj]
    if missing:
        raise ValueError(f"{scenario_dir.name}/scenario.json missing keys: {missing}")
    # Stash the scenario's own dir for from_spec relative-path resolution.
    sj["__scenario_dir__"] = str(scenario_dir)
    return sj


def normalise_manifest(m: dict) -> dict:
    """Strip + canonicalise volatile fields so two runs at different times
    produce byte-identical output.

    What this normalises:
      - top-level seal_*, created_at, status, last_error → placeholders
      - blob sha256 + size_bytes → placeholders (size is data-dependent but
        we want goldens that survive minor code edits)
      - any absolute path → portable token (<REPO>, <HOME>, <TMP>, etc.)
      - job_id → keep the prefix but strip any wall-clock-influenced suffix
      - timestamps inside metadata → <TIMESTAMP>
    """
    import copy
    n = copy.deepcopy(m)

    # Top-level placeholders
    for k, placeholder in NORMALISE_PLACEHOLDERS.items():
        if k in n:
            n[k] = placeholder

    # Per-blob: sha256 + size → placeholders, absolute paths → tokens
    for b in n.get("blobs", []):
        b["sha256"] = "<BLOB_SHA>"
        b["size_bytes"] = "<BLOB_SIZE>"
        if "local_src" in b:
            b["local_src"] = _replace_paths(b["local_src"])

    # result.local_dir is per-bundle absolute → token
    res = n.get("result", {})
    if "local_dir" in res:
        res["local_dir"] = _replace_paths(res["local_dir"])

    # job_id pattern often embeds an integer fleet_job_id + hostname; keep
    # as-is since the scenario picks both deterministically.
    return n


_TMP_RAND_RE = re.compile(r"<TMP>/v2sc_[a-zA-Z0-9_]+")


def _replace_paths(s: str) -> str:
    """Apply PATH_TOKENS to a single string, then normalise the per-run
    random tempdir name so goldens are stable across runs.

    tempfile.mkdtemp(prefix='v2sc_') produces eg. 'v2sc_c4m0x325' — that
    8-char suffix changes every run. Collapse to '<TMP>/<RAND>'.
    """
    for prefix, token in PATH_TOKENS:
        if s.startswith(prefix):
            tail = s[len(prefix):].replace("\\", "/")
            s = token + tail
            break
    s = _TMP_RAND_RE.sub("<TMP>/<RAND>", s)
    return s


# Workflow → builder dispatch table.
def build_manifest_for_scenario(scenario: dict, fake_bundle_dir: pathlib.Path):
    """Call the right v2.fleet_adapter._build_*_manifest() based on scenario['workflow'].

    Returns the produced SealedManifest as a normalised dict.
    """
    sys.path.insert(0, str(ORCH_ROOT))
    from v2 import fleet_adapter as fa

    wf = scenario["workflow"]
    args = scenario["args"]
    hosts = scenario["hosts"]

    # Resolve the host config the scenario points at.
    host_alias = args.get("host")
    if host_alias and host_alias not in hosts:
        raise ValueError(f"scenario host {host_alias!r} not in scenario hosts dict")
    hcfg = hosts.get(host_alias, {}) if host_alias else {}
    common = dict(
        host_alias=hcfg.get("ssh_alias", host_alias or "fakehost"),
        remote_workdir=hcfg.get("v2_remote_workdir", "C:/sealed/jobs"),
        rsync_path=hcfg.get("rsync_path"),
        host_repo=hcfg.get("repo", "C:/Users/fake/Downloads/fleet-offload"),
        bundle_out_dir=fake_bundle_dir,
    )
    job_id = scenario.get("job_id", 1)

    # NEW: `from_spec` — load a declarative JobSpec file and run the
    # autobundler. Lets the spec layer get the same golden-file regression
    # testing as the per-workflow manifest builders.
    if wf == "from_spec":
        from v2.spec import JobSpec, _resolve_vars
        from v2 import autobundle
        spec_path = args["spec_path"]
        # spec_path may itself reference $VAR via the scenario's roots
        roots = dict(args.get("roots") or {})
        spec_path = _resolve_vars(spec_path, roots) if "$" in spec_path else spec_path
        sp = pathlib.Path(spec_path)
        if not sp.is_absolute():
            # Resolve relative to scenario's own directory.
            sp = (pathlib.Path(scenario["__scenario_dir__"]) / sp).resolve()
        spec = JobSpec.from_path(sp)
        upstream = args.get("upstream_state", {})
        upstream_resolved = {
            name: autobundle.ResolvedUpstream(
                name=name,
                host_alias=v["host_alias"],
                remote_workdir=v["remote_workdir"],
                v2_job_id=v.get("v2_job_id", "<UPSTREAM>"),
                bundle_dir_local=pathlib.Path(v.get("bundle_dir_local", "/tmp")),
            )
            for name, v in upstream.items()
        }
        m, _outs = autobundle.build_manifest_from_spec(
            spec,
            job_id=job_id,
            bundle_out_dir=fake_bundle_dir,
            hosts=hosts,
            roots=roots,
            upstream_state=upstream_resolved,
        )
        return normalise_manifest(m.to_dict())

    if wf == "random_windows":
        m = fa._build_random_windows_manifest(
            job_id=job_id,
            cohort=args["cohort"],
            pipeline_args=args.get("pipeline_args") or "",
            host_results_root=f'{common["host_repo"]}/c_emd/results',
            **common,
        )
    elif wf == "emd_cache_replay":
        # The cache blob is fake — we just need a file that exists for the
        # local_src so the builder doesn't blow up on path validation.
        fake_cache = fake_bundle_dir / "fake_cache.mat"
        fake_cache.write_bytes(b"x" * 1024)
        m = fa._build_emd_cache_replay_manifest(
            job_id=job_id,
            instrument=args["instrument"],
            cache_path=str(fake_cache),
            cadence_rows=args.get("cadence_rows", 30),
            extra_args=args.get("extra_args", []),
            **common,
        )
    elif wf == "ig_trading":
        m = fa._build_ig_trading_manifest(
            job_id=job_id,
            submodule=args["submodule"],
            extra_args=args.get("extra_args", []),
            **common,
        )
    elif wf == "generic":
        # Direct call to the generic-manifest builder for arbitrary modules.
        m = fa._build_generic_manifest(
            job_id=job_id,
            workflow=args.get("workflow_tag", "generic"),
            module=args["module"],
            pass_args=args.get("pass_args", []),
            host_results_root=args.get("host_results_root"),
            extra_blobs=[],
            **common,
        )
    else:
        raise ValueError(f"unknown workflow {wf!r}; supported: "
                         "random_windows, emd_cache_replay, ig_trading, generic")

    return normalise_manifest(m.to_dict())


def diff_manifest(actual: dict, expected: dict) -> Optional[str]:
    """Return None if equal, else a unified-diff-style string."""
    actual_s = json.dumps(actual, indent=2, sort_keys=True, default=str)
    expected_s = json.dumps(expected, indent=2, sort_keys=True, default=str)
    if actual_s == expected_s:
        return None
    import difflib
    return "\n".join(difflib.unified_diff(
        expected_s.splitlines(), actual_s.splitlines(),
        fromfile="expected", tofile="actual", n=3,
    ))


def golden_path(scenario_dir: pathlib.Path) -> pathlib.Path:
    return scenario_dir / "expected_manifest.json"


def update_golden(scenario_dir: pathlib.Path, actual: dict) -> None:
    """Rewrite expected_manifest.json with the actual normalised manifest.

    Used in UPDATE_GOLDEN=1 mode after an intentional API change.
    """
    path = golden_path(scenario_dir)
    path.write_text(json.dumps(actual, indent=2, sort_keys=True, default=str) + "\n")


def in_update_mode() -> bool:
    return os.environ.get("UPDATE_GOLDEN", "").strip() not in ("", "0", "false", "False")


def in_live_mode() -> bool:
    return os.environ.get("V2_LIVE_TESTS", "").strip() not in ("", "0", "false", "False")


# ---------------------------------------------------------------------------
# Windows build-artifact test hermeticity
# ---------------------------------------------------------------------------
# c_emd/build/windows/{libemd.dll, emd_cache_gen.exe} are gitignored Windows
# build artifacts the v2 fleet bundles into every sealed code bundle
# ("stateless-host" architecture: libemd.dll for engine=c, emd_cache_gen.exe for
# engine=exe). On a non-Windows dev box or CI runner they aren't built, so the
# builder — correctly, and by explicit design (see autobundle.py / fleet_adapter
# "Skip silently if the local checkout doesn't have it built") — omits those
# blobs. The scenario goldens were generated where the artifacts existed, so
# without them every code-bundling scenario drifts. To make the manifest-check
# phase hermetic we drop tiny placeholders at the real paths for the duration of
# the suite. We NEVER overwrite a real artifact (so a genuine staged build is
# used as-is), and NEVER stub in live mode (a fake would be pushed to a real host
# and break the run).
_WINDOWS_ARTIFACT_STUBS = (
    REPO_ROOT / "c_emd" / "build" / "windows" / "libemd.dll",
    REPO_ROOT / "c_emd" / "build" / "windows" / "emd_cache_gen.exe",
)
_stub_created_files: list = []
_stub_created_dirs: list = []


def install_libemd_stub() -> None:
    """Create placeholder Windows build artifacts (libemd.dll + emd_cache_gen.exe)
    so scenario manifests deterministically include the blobs the goldens expect.
    Idempotent; skips any artifact already present (never clobbers a real build)
    and is a no-op when running live (V2_LIVE_TESTS)."""
    global _stub_created_files, _stub_created_dirs
    if in_live_mode():
        return
    for path in _WINDOWS_ARTIFACT_STUBS:
        if path.exists():
            continue
        # Record the parent dirs we have to create so teardown removes exactly
        # what we made and nothing pre-existing.
        p = path.parent
        while not p.exists():
            _stub_created_dirs.append(p)
            p = p.parent
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"MZ\x00placeholder-for-scenario-manifest-tests")
        _stub_created_files.append(path)


def remove_libemd_stub() -> None:
    """Undo install_libemd_stub(), removing only what we created."""
    global _stub_created_files, _stub_created_dirs
    for path in _stub_created_files:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    _stub_created_files = []
    # Remove created dirs deepest-first (dedup: both artifacts share a parent).
    for d in sorted(set(_stub_created_dirs), key=lambda x: len(str(x)), reverse=True):
        try:
            d.rmdir()  # only succeeds if empty → never nukes a real tree
        except OSError:
            pass
    _stub_created_dirs = []


def run_scenario_check(scenario_dir: pathlib.Path) -> Optional[str]:
    """Run a single scenario in CHECK or UPDATE mode. Returns None on
    success, a diff/error string on failure.

    Live mode is handled separately (run_scenario_live) so the unit-level
    test parametrization is fast even when V2_LIVE_TESTS is set.
    """
    scenario = load_scenario(scenario_dir)
    with tempfile.TemporaryDirectory(prefix="v2sc_") as td:
        bundle_dir = pathlib.Path(td)
        try:
            actual = build_manifest_for_scenario(scenario, bundle_dir)
        except Exception as e:
            return f"build_manifest failed: {type(e).__name__}: {e}"

    if in_update_mode():
        update_golden(scenario_dir, actual)
        return None  # treated as pass in update mode

    gp = golden_path(scenario_dir)
    if not gp.exists():
        # First-time scenario: write the golden so the next run is a real check.
        update_golden(scenario_dir, actual)
        return (
            f"golden didn't exist; wrote initial expected_manifest.json. "
            f"Re-run to verify it's stable. (Inspect the file first if "
            f"this scenario is new.)"
        )

    expected = json.loads(gp.read_text())
    return diff_manifest(actual, expected)


# ---------------------------------------------------------------------------
# Live-remote mode — actually run the manifest on a real host and check the
# returned result summary against the scenario's expected_summary.json.
# ---------------------------------------------------------------------------

def expected_summary_path(scenario_dir: pathlib.Path) -> pathlib.Path:
    return scenario_dir / "expected_summary.json"


def _normalise_summary(summary: dict) -> dict:
    """Strip volatile fields (wall-clock times, sha256s, byte counts that
    vary by host/network) from a live result summary before comparing
    against the golden. We only require the SEMANTIC bits to match.
    """
    import copy
    n = copy.deepcopy(summary)
    # Top-level run wrapper
    for k in ("started_at", "finished_at", "run_started_at",
              "run_finished_at", "elapsed_s", "wall_clock_s"):
        if k in n:
            n[k] = f"<{k.upper()}>"
    return n


def run_scenario_live(scenario_dir: pathlib.Path) -> Optional[str]:
    """Execute the scenario on a real remote and diff the result summary
    against expected_summary.json. Returns None on success, a diff/error
    string on failure.

    Skips silently when:
      - V2_LIVE_TESTS is not set
      - scenario.json doesn't declare ``"live": true``
      - the scenario's host isn't reachable
    """
    if not in_live_mode():
        return None
    scenario = load_scenario(scenario_dir)
    if not scenario.get("live"):
        return None

    # Build the manifest against a real host config. For live mode the
    # caller's hosts dict must reflect the REAL ssh_alias / rsync_path /
    # remote_workdir of the host they want to hit.
    sys.path.insert(0, str(ORCH_ROOT))
    from v2 import fleet_adapter as fa
    from v2 import submit as v2submit

    bundle_dir = pathlib.Path(tempfile.mkdtemp(prefix="v2_live_"))
    try:
        # Build the manifest (don't normalise — we need the real paths).
        sys.path.insert(0, str(ORCH_ROOT))
        from v2 import fleet_adapter as fa_live
        scenario_no_norm = scenario
        # Reuse build_manifest_for_scenario logic but skip normalise step
        # — we want to actually submit, not snapshot.
        wf = scenario["workflow"]
        args = scenario["args"]
        hcfg = scenario["hosts"][args["host"]]
        common = dict(
            host_alias=hcfg["ssh_alias"],
            remote_workdir=hcfg.get("v2_remote_workdir", "C:/sealed/jobs"),
            rsync_path=hcfg.get("rsync_path"),
            host_repo=hcfg["repo"],
            bundle_out_dir=bundle_dir,
        )
        if wf == "random_windows":
            m = fa_live._build_random_windows_manifest(
                job_id=scenario.get("job_id", 1), cohort=args["cohort"],
                pipeline_args=args.get("pipeline_args") or "",
                host_results_root=f'{common["host_repo"]}/c_emd/results',
                **common,
            )
        elif wf == "emd_cache_replay":
            m = fa_live._build_emd_cache_replay_manifest(
                job_id=scenario.get("job_id", 1), instrument=args["instrument"],
                cache_path=args["cache_path"],     # MUST be supplied for live mode
                cadence_rows=args.get("cadence_rows", 30),
                extra_args=args.get("extra_args", []),
                **common,
            )
        elif wf == "ig_trading":
            m = fa_live._build_ig_trading_manifest(
                job_id=scenario.get("job_id", 1), submodule=args["submodule"],
                extra_args=args.get("extra_args", []),
                **common,
            )
        elif wf == "generic":
            m = fa_live._build_generic_manifest(
                job_id=scenario.get("job_id", 1),
                workflow=args.get("workflow_tag", "generic-live"),
                module=args["module"],
                pass_args=args.get("pass_args", []),
                host_results_root=args.get("host_results_root"),
                extra_blobs=[],
                **common,
            )
        else:
            return f"live mode: unknown workflow {wf!r}"

        # Submit synchronously. submit_one builds, pushes, runs, polls, pulls.
        result = v2submit.submit_one(
            m, bundle_out_dir=bundle_dir,
            poll_interval_s=10.0,
        )

        # Extract the bits we want to lock down: exit code, decisions/count
        # if present, pulled n_files.
        status = result.get("status", {}) or {}
        summary = {
            "rc":                status.get("exit_code"),
            "phase":             status.get("phase"),
            "pulled_n_files":    (result.get("result", {}) or {}).get("n_files"),
            "remote_elapsed_s":  (result.get("timings", {}) or {}).get("remote_elapsed_s"),
            # Some workflows write a report.json into outputs/ — bubble its
            # key fields up if present.
        }
        # Walk pulled tree for a report.json (workflow-dependent summary)
        pulled = pathlib.Path(result.get("result", {}).get("extracted_to", ""))
        report_p = pulled / "outputs" / "report.json"
        if report_p.exists():
            try:
                summary["report"] = json.loads(report_p.read_text())
            except Exception as e:
                summary["report_err"] = str(e)

        sp = expected_summary_path(scenario_dir)
        if in_update_mode() or not sp.exists():
            sp.write_text(json.dumps(_normalise_summary(summary), indent=2, sort_keys=True) + "\n")
            return None
        expected = json.loads(sp.read_text())
        actual = _normalise_summary(summary)
        return diff_manifest(actual, expected)
    finally:
        import shutil as _sh
        _sh.rmtree(bundle_dir, ignore_errors=True)
