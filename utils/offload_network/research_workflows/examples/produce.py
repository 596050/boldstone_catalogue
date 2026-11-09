"""Synthetic producer/consumer example; no market data or performance claims."""

import json
import sys
from pathlib import Path

mode, source, target = sys.argv[1:]
values = json.loads(Path(source).read_text())["values"]
if mode == "prepare":
    Path(target).write_text(json.dumps({"schema": "synthetic.values.v1", "values": values}))
elif mode == "report":
    output = Path(target)
    output.mkdir(exist_ok=True)
    (output / "RESULT.json").write_text(
        json.dumps(
            {
                "schema": "synthetic.sum.v1",
                "sum": sum(values),
                "performance_qualification": "NOT_ESTABLISHED",
            }
        )
    )
    (output / "metrics.csv").write_text("metric,value\nsum," + str(sum(values)) + "\n")
    (output / "REPORT.md").write_text("Synthetic offload example. Not trading evidence.\n")
else:
    raise ValueError("unknown mode")
