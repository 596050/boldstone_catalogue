"""Read-only returned-artifact resolution, without rewriting native receipts."""

from pathlib import Path

from .client import verify_collection
from .common import load, rel


def resolve(directory, port, relative=None, *, native_path=None, max_bytes=1 << 30):
    directory = Path(directory).resolve()
    verify_collection(directory, max_bytes=max_bytes)
    index = load(directory / "INDEX.json")
    if port not in index:
        delivery = load(directory / "DELIVERY.json", max_bytes=16 << 20)["manifest"]
        node_id, separator, output_name = port.partition(".")
        node = next((n for n in delivery["status"]["nodes"] if n["id"] == node_id), None)
        declared = delivery.get("output_plan", {}).get("jobs", {}).get(node_id, {})
        envelope = (node or {}).get("outputs") or {}
        if (separator and output_name in declared and node is not None
                and node["state"] in {"failed", "cancelled", "interrupted", "blocked_dependency"}
                and (not envelope or envelope.get("output_status") == "NOT_PRODUCED")
                and port not in delivery.get("remote_only", {})):
            reason = node.get("error") or "the producer did not publish an output"
            raise ValueError("OUTPUT_NOT_PRODUCED: requested port is absent locally; "
                             f"node {node_id!r} ended {node['state']}: {reason}")
        raise ValueError(
            "BLOCKED_DATA: requested port is absent locally; retrieve its exact remote object"
        )
    root = directory / index[port]
    if (root.parent / "ARCHIVE_ONLY.json").is_file() and not root.is_dir():
        raise ValueError("artifact is retained compressed; use research-offload origin with its "
                         "project config/record for bounded verified materialization")
    if native_path is not None:
        if relative is not None or not port.endswith(".research_evidence"):
            raise ValueError("native paths require a research_evidence port and no relative path")
        delivery = load(directory / "DELIVERY.json", max_bytes=16 << 20)["manifest"]
        node = next(n for n in delivery["status"]["nodes"] if n["id"] == port.split(".")[0])
        prefix = (node["outputs"].get("native_result") or {}).get("native_output_prefix")
        if not prefix or not native_path.startswith(prefix + "/"):
            raise ValueError("native path is not part of this job's returned evidence")
        relative = native_path[len(prefix) + 1 :]
    target = root / rel(relative) if relative is not None else root
    if (
        not target.exists()
        or target.is_symlink()
        or not target.resolve().is_relative_to(root.resolve())
    ):
        raise ValueError("BLOCKED_DATA: artifact path is absent or unsafe")
    return target
