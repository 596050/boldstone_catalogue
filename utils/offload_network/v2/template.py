"""Spec generator for v2 batches.

Reads a `workload.json` describing instruments × cadences × phases and
emits the per-job spec files plus a top-level `batch.json`. See
v2/templates/README.md for the operator workflow.

The generator is intentionally dumb: it substitutes a fixed set of
placeholders in the canonical templates under v2/templates/ and writes
them out. No conditional logic in the templates themselves — anything
workload-specific belongs in the workload.json.

CLI:
    python3 -m v2.template generate --workload workload.json --out <dir>

Library:
    from v2.template import generate_batch
    generate_batch(workload_path, out_dir)
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import os
from typing import Any


_HERE = pathlib.Path(__file__).resolve().parent             # v2/
_TEMPLATES = _HERE / "templates"


# Template name → relative filename under v2/templates/
PHASE_TEMPLATE = {
    "cache":       "cache.template.json",
    "cache_stage": "cache_stage.template.json",
    "replay":      "replay.template.json",
    "diagnostics": "diagnostics.template.json",
}


def _append_extra_args(spec: dict, extra: list[str]) -> None:
    """Append workload-provided extra args to a spec's ``args`` list.

    Used by Fix-3 plumbing to flow workload-level ``cache_args`` /
    ``cache_stage_args`` / ``replay_args`` / ``diagnostics_args`` into
    every spec of that phase. Extra args land at the END of the
    template's args so they can override earlier flag/value pairs in a
    follow-up (operators sometimes pre-pend a `--` and then everything
    after is forwarded literally; we don't enforce that, just append).
    """
    if not extra:
        return
    spec.setdefault("args", []).extend(extra)


def _append_per_inst_replay_args(spec: dict, inst: dict) -> None:
    """Fix-3 per-instrument: every replay needs --trade-cost + --best-config,
    and those vary per instrument. Pull from the instrument entry."""
    if "trade_cost" in inst:
        spec["args"].extend(["--trade-cost", str(inst["trade_cost"])])
    if "best_config" in inst:
        spec["args"].extend(["--best-config", str(inst["best_config"])])


def _wire_cache_build_paths(spec: dict, inst: dict, *, iqfeed_root: str | None) -> None:
    """Fix-2 + Fix-4: rewrite the bundled cache config so all the Mac
    paths (source_dir, source_path, output_dir, cache_path, metadata_path)
    point at seal-bundled or workdir-relative locations on the remote.
    Also add a bundle entry shipping the IQFeed source data (12-19MB
    per instrument — small enough to seal-bundle).

    Required instrument fields:
      iqfeed_subdir   the subdir under $IQFEED to ship (eg "naturalgas_ig_production")
      iqfeed_file     filename inside that subdir (eg "QNG#C.txt")

    The cache config's existing keys are rewritten in-place via
    BundleEntry.rewrite_json — the original Mac-side config stays
    untouched (the rewritten copy materialises under bundle_out_dir).
    """
    iqfeed_subdir = inst.get("iqfeed_subdir")
    iqfeed_file = inst.get("iqfeed_file")
    if not iqfeed_subdir or not iqfeed_file:
        # Operator chose to leave cache build wiring manual.
        return
    if not iqfeed_root:
        raise ValueError(
            f"instrument {inst['key']!r} has iqfeed_subdir but workload "
            f"is missing roots.IQFEED — set it to the local IQFeed root "
            f"(eg /Volumes/Untitled/offload_data/live_data/iqfeed_data)"
        )

    inst_id = inst["id"]
    inst_key = inst["key"]
    cache_basename = f"{inst_id}_live_emd_cache.mat"

    # Add the source-data bundle entry (gets var "source_dir" → blobs/data/source).
    spec["inputs"]["bundle"].append({
        "src": f"$IQFEED/{iqfeed_subdir}",
        "as":  "data/source",
        "var": "source_dir",
    })

    # Find the existing config bundle entry (the one with var="config_file")
    # and attach the rewrite rules.
    cfg_entry = next(
        (b for b in spec["inputs"]["bundle"] if b.get("var") == "config_file"),
        None,
    )
    if cfg_entry is None:
        raise ValueError(
            f"cache template for {inst_key!r} has no bundle entry with "
            f"var=config_file — Fix-4 path-rewriting expects one"
        )
    cfg_entry["rewrite_json"] = [
        {"path": "source_dir",    "value": "{{source_dir}}"},
        {"path": "source_path",   "value": f"{{{{source_dir}}}}/{iqfeed_file}"},
        {"path": "output_dir",    "value": "outputs/cache"},
        {"path": "cache_path",    "value": f"outputs/cache/{cache_basename}"},
        {"path": "metadata_path", "value": f"outputs/metadata/{inst_key}.json"},
    ]


def _load_template(phase: str) -> str:
    """Return the raw text of a phase template (placeholders intact)."""
    tp = _TEMPLATES / PHASE_TEMPLATE[phase]
    if not tp.is_file():
        raise FileNotFoundError(f"missing template: {tp}")
    return tp.read_text()


def _substitute(template_text: str, *, inst_key: str, inst_id: str,
                cad_key: str = "", cad_rows: int = 0,
                batch_name: str = "",
                prestaged_cache_root: str = "C:/sealed/prestaged_caches") -> dict:
    """Apply <<INST_KEY>>, <<INST_ID>>, <<CAD_KEY>>, <<CAD_ROWS>> substitutions
    and parse the result as JSON.

    Substitutions are done on the raw text so the result is guaranteed
    to be JSON-valid (the templates are themselves valid JSON pre-sub).
    Numeric placeholders (<<CAD_ROWS>>) are inserted as bare numerals so
    `"cadence_rows": <<CAD_ROWS>>` ends up as `"cadence_rows": 30` (int).
    """
    text = template_text
    text = text.replace("<<INST_KEY>>", inst_key)
    text = text.replace("<<INST_ID>>", inst_id)
    text = text.replace("<<CAD_KEY>>", cad_key)
    text = text.replace("<<CAD_ROWS>>", str(cad_rows))
    text = text.replace("<<BATCH_NAME>>", batch_name)
    text = text.replace("<<PRESTAGED_CACHE_ROOT>>", prestaged_cache_root)
    return json.loads(text)


def generate_batch(workload_path: str | pathlib.Path,
                   out_dir: str | pathlib.Path,
                   *, overwrite: bool = False) -> dict:
    """Materialise a full batch from a workload config. Returns a summary
    dict {n_specs, n_per_phase, batch_path, specs_dir}.
    """
    workload_path = pathlib.Path(workload_path).resolve()
    out_dir = pathlib.Path(out_dir).resolve()
    jobs_dir = out_dir / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)

    wl = json.loads(workload_path.read_text())

    name = wl["name"]
    roots = wl.get("roots", {})
    instruments = wl["instruments"]
    cadences = wl.get("cadences", [])
    phases = wl.get("phases", ["cache", "replay", "diagnostics"])
    skip_cache_for = set(wl.get("skip_cache_for", []))
    prestaged_cache_root = (
        wl.get("roots", {}).get("PRESTAGED_CACHE_ROOT")
        or os.environ.get("V2_PRESTAGED_CACHE_ROOT", "C:/sealed/prestaged_caches")
    )

    # Fix-3: workload-level extra args flow into every spec of the
    # named phase. These are appended verbatim to the spec's args list
    # (after the template's own args), so proof-critical replay/cache
    # flags don't need to be hand-edited into every generated spec.
    extra_cache_args       = list(wl.get("cache_args", []))
    extra_cache_stage_args = list(wl.get("cache_stage_args", []))
    extra_replay_args      = list(wl.get("replay_args", []))
    extra_diagnostics_args = list(wl.get("diagnostics_args", []))

    # cache_stage is a sub-phase of "cache": when instruments are in
    # skip_cache_for AND the workload includes the "cache" phase, we
    # emit cache_stage jobs (ship existing .mat) so the downstream
    # replay's affinity + remote_refs still resolve to a real upstream.
    # Counter goes under "cache" so the operator sees the total.
    n_per_phase = {ph: 0 for ph in phases}
    if "cache" in phases and skip_cache_for:
        n_per_phase.setdefault("cache_stage", 0)

    def _write(path: pathlib.Path, obj: dict) -> None:
        if path.exists() and not overwrite:
            raise FileExistsError(
                f"{path} already exists. Pass overwrite=True or delete first."
            )
        path.write_text(json.dumps(obj, indent=2) + "\n")

    # cache phase: full rebuild for non-skipped instruments, cache_stage
    # (ship existing .mat) for the skipped ones. Both share the cache.*
    # name so the replay phase's deps/affinity resolves uniformly.
    if "cache" in phases:
        cache_tpl = _load_template("cache")
        stage_tpl = _load_template("cache_stage")
        host_pool = wl.get("host_pool") or []
        iqfeed_root = wl.get("roots", {}).get("IQFEED")
        for i, inst in enumerate(instruments):
            if inst["key"] in skip_cache_for:
                spec = _substitute(
                    stage_tpl, inst_key=inst["key"], inst_id=inst["id"],
                    batch_name=name,
                    prestaged_cache_root=prestaged_cache_root,
                )
                _append_extra_args(spec, extra_cache_stage_args)
                if host_pool:
                    spec["host"] = {"alias": host_pool[i % len(host_pool)]}
                _write(jobs_dir / f"cache.{inst['key']}.json", spec)
                n_per_phase["cache_stage"] = n_per_phase.get("cache_stage", 0) + 1
                continue
            spec = _substitute(
                cache_tpl, inst_key=inst["key"], inst_id=inst["id"],
                batch_name=name,
            )
            _append_extra_args(spec, extra_cache_args)
            # Fix-2/Fix-4: cache-build needs source IQFeed data + rewritten
            # config paths so the Windows remote doesn't try to read Mac
            # /Volumes/... paths. The instrument dict supplies the source
            # subdir + filename; we (a) add a bundle entry shipping the
            # source dir, and (b) attach rewrite_json rules that point the
            # config at the bundle-internal source + outputs/-relative
            # output paths.
            _wire_cache_build_paths(spec, inst, iqfeed_root=iqfeed_root)
            # Round-robin distribute cache builds across the host pool so
            # one host doesn't take all the cache work; replays/diagnostics
            # inherit placement via affinity.
            if host_pool:
                spec["host"] = {"alias": host_pool[i % len(host_pool)]}
            _write(jobs_dir / f"cache.{inst['key']}.json", spec)
            n_per_phase["cache"] += 1

    # replay phase
    if "replay" in phases:
        tpl = _load_template("replay")
        for inst in instruments:
            for cad in cadences:
                spec = _substitute(tpl,
                                   inst_key=inst["key"], inst_id=inst["id"],
                                   cad_key=cad["key"], cad_rows=cad["rows"],
                                   batch_name=name)
                _append_extra_args(spec, extra_replay_args)
                # Fix-3: per-instrument proof-critical replay flags
                # (trade_cost + best_config vary per instrument; the
                # workload's flat replay_args covers the cross-instrument
                # ones like warmup-rows / decision-delay-bars).
                _append_per_inst_replay_args(spec, inst)
                _write(jobs_dir / f"replay.{inst['key']}.{cad['key']}.json", spec)
                n_per_phase["replay"] += 1

    # diagnostics phase
    if "diagnostics" in phases:
        tpl = _load_template("diagnostics")
        for inst in instruments:
            for cad in cadences:
                spec = _substitute(tpl,
                                   inst_key=inst["key"], inst_id=inst["id"],
                                   cad_key=cad["key"], cad_rows=cad["rows"],
                                   batch_name=name)
                _append_extra_args(spec, extra_diagnostics_args)
                _write(jobs_dir / f"diagnostics.{inst['key']}.{cad['key']}.json", spec)
                n_per_phase["diagnostics"] += 1

    # batch.json: globs over the jobs/ dir
    batch_obj = {
        "batch": name,
        "roots": roots,
        "jobs": ["jobs/*.json"],
        "policy": {
            "max_parallel_per_host": wl.get("max_parallel_per_host", 2),
            "max_parallel_total":    wl.get("max_parallel_total", 8),
            "on_failure":            wl.get("on_failure", "skip_dependents"),
            "host_pool":             wl.get("host_pool"),
        },
    }
    batch_path = out_dir / "batch.json"
    _write(batch_path, batch_obj)

    return {
        "batch_path": str(batch_path),
        "specs_dir":  str(jobs_dir),
        "n_specs":    sum(n_per_phase.values()),
        "n_per_phase": n_per_phase,
    }


# ---------------------------------------------------------------------------
# CLI: python3 -m v2.template generate ...
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="v2.template",
        description="Generate v2 batch specs from a workload config",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="emit per-job specs + batch.json")
    g.add_argument("--workload", required=True, help="path to workload.json")
    g.add_argument("--out", required=True,
                   help="output dir (will hold batch.json + jobs/)")
    g.add_argument("--overwrite", action="store_true",
                   help="overwrite existing files (default: refuse)")

    ns = p.parse_args(argv)
    if ns.cmd == "generate":
        summary = generate_batch(ns.workload, ns.out, overwrite=ns.overwrite)
        print(json.dumps(summary, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
