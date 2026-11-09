"""Record identities and confirm that the handoff wheel matches runtime source."""
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    wheel = HERE / "fleet_offload_orchestration-0.2.0-py3-none-any.whl"
    files = list(ROOT.glob("*.py")) + [ROOT / "pyproject.toml", ROOT / "README.md"]
    for package in ("offload_service", "v2", "fleet", "lib", "trading_common", "external_machine_connect", "tests"):
        files.extend(p for p in (ROOT / package).rglob("*")
                     if p.is_file() and p.suffix in {".py", ".json", ".md"}
                     and not any(part in {".venv", ".runtime", "__pycache__"} for part in p.parts))
    identity = {str(p.relative_to(ROOT)): digest(p) for p in sorted(set(files))}
    mismatches = []
    with zipfile.ZipFile(wheel) as archive:
        for name in archive.namelist():
            if any(part in {".runtime", ".venv", "access-token"} for part in name.split("/")):
                raise AssertionError(f"private runtime path in wheel: {name}")
            if name.endswith(".py") and (ROOT / name).is_file():
                if hashlib.sha256(archive.read(name)).hexdigest() != digest(ROOT / name):
                    mismatches.append(name)
        required = {"offload_service/core.py", "offload_service/smoke_test.py", "simulator.py",
                    "v2/templates/cache.template.json", "fleet/hosts.example.json",
                    "trading_common/data_storage/external_queue.py",
                    "external_machine_connect/cloudflare/connect.py"}
        assert required.issubset(set(archive.namelist()))
    assert not mismatches, mismatches
    result = {"head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "wheel_sha256": digest(wheel), "wheel_source_mismatches": mismatches,
              "files": identity}
    (HERE / "SOURCE_MANIFEST.json").write_text(json.dumps(result, indent=2, sort_keys=True))
    print(json.dumps({"head": result["head"], "files": len(identity),
                      "wheel_sha256": result["wheel_sha256"], "wheel_source_mismatches": mismatches}))


if __name__ == "__main__":
    main()
