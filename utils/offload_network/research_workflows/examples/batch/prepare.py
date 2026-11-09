"""Synthetic offline selector/preparer; replace with declared candidate-specific code.

Preserves selected raw bytes, observation labels and hashes. No downloads or
claim to establish point-in-time provenance.
"""

import csv
import hashlib
import json
import shutil
import sys
from pathlib import Path


def main():
    mode, source, selection, destination = sys.argv[1:]
    source, destination = Path(source), Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    if mode == "select":
        requested = json.loads(Path(selection).read_text())
        relative = requested["file"]
        if (
            not isinstance(relative, str)
            or "/" in relative
            or "\\" in relative
            or relative in {".", ".."}
        ):
            raise ValueError("selection must name one supplied raw file")
        chosen = source / relative
        if chosen.is_symlink() or not chosen.is_file():
            raise ValueError(
                "BLOCKED_DATA: required raw source is not in the sealed supply: " + relative
            )
        raw = chosen.read_bytes()
        shutil.copyfile(chosen, destination / "raw.csv")
        receipt = {
            "schema": "synthetic.raw_selection.v1",
            "source_file": relative,
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "source_bytes": len(raw),
        }
        (destination / "SOURCE.json").write_text(json.dumps(receipt, sort_keys=True))
    elif mode == "cases":
        receipt = json.loads((source / "SOURCE.json").read_text())
        raw = source / "raw.csv"
        if hashlib.sha256(raw.read_bytes()).hexdigest() != receipt["source_sha256"]:
            raise ValueError("selected raw source changed")
        with raw.open(newline="") as stream, (destination / "cases.jsonl").open("w") as out:
            for row in csv.DictReader(stream):
                out.write(
                    json.dumps(
                        {
                            "input": {"observation": row["observation"], "signal": row["signal"]},
                            "target": row["target"],
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
        shutil.copyfile(raw, destination / "raw.csv")
        shutil.copyfile(source / "SOURCE.json", destination / "SOURCE.json")
    else:
        raise ValueError("unknown preparation mode")


if __name__ == "__main__":
    main()
