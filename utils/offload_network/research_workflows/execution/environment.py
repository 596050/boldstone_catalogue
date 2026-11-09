"""Stdlib-only runtime check executed inside the admitted job, never on the host."""

import hashlib
import importlib
import importlib.metadata
import json
import os
import platform
import re
import site
import sys
import sysconfig
from pathlib import Path


def machine(value):
    return {"amd64": "x86_64", "arm64": "aarch64"}.get(value.lower(), value.lower())


def verify(root):
    root = Path(root)
    record = json.loads((root / "PYTHON_RUNTIME.json").read_text())
    if record.get("schema") != "marketmaker.python_runtime_bundle.v1" or record.get("site") != "site-packages":
        raise ValueError("unsupported runtime bundle")
    target = record["target"]
    actual = {"python": f"{sys.version_info.major}.{sys.version_info.minor}",
              "abi": "cp" + str(sys.version_info.major) + str(sys.version_info.minor),
              "implementation": "cp" if platform.python_implementation() == "CPython" else platform.python_implementation(),
              "system": platform.system(), "machine": platform.machine()}
    if (sysconfig.get_config_var("Py_GIL_DISABLED") or
            any(actual[key] != target[key] for key in ("python", "abi", "implementation", "system"))
            or machine(actual["machine"]) != machine(target["machine"])):
        raise ValueError("job interpreter/platform differs from the runtime bundle target: " + json.dumps(actual))
    directory = root / "site-packages"
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("runtime site directory is absent or linked")
    observed = {}
    for parent, dirs, leaves in os.walk(directory):
        for name in dirs + leaves:
            path = Path(parent) / name
            if path.is_symlink():
                raise ValueError("linked runtime member")
        for name in leaves:
            path = Path(parent) / name
            if not path.is_file():
                raise ValueError("nonregular runtime member")
            value = hashlib.sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1 << 20), b""):
                    value.update(block)
            observed[path.relative_to(directory).as_posix()] = {"bytes": path.stat().st_size, "sha256": value.hexdigest()}
    if observed != record["files"]:
        raise ValueError("runtime files differ from the bound manifest")
    normalize = lambda value: re.sub(r"[-_.]+", "-", value).lower()
    installed = {}
    for distribution in importlib.metadata.distributions(path=[str(directory)]):
        key = normalize(distribution.metadata["Name"])
        if key in installed:
            raise ValueError("duplicate runtime distribution")
        installed[key] = distribution.version
    expected = {normalize(key): value for key, value in record["requirements"].items()}
    if installed != expected:
        raise ValueError("installed distributions differ from exact declared requirements")
    # Verification and platform checks happen before executing any target package
    # initialization. .pth and imports are trusted job code within Docker isolation.
    sys.path.insert(0, str(directory))
    site.addsitedir(str(directory))
    imports = {}
    for name in record["imports"]:
        module = importlib.import_module(name)
        origin = getattr(module, "__file__", None)
        locations = [origin] if origin is not None else list(getattr(module, "__path__", []))
        if not locations or any(not Path(path).resolve().is_relative_to(directory.resolve()) for path in locations):
            raise ValueError("runtime import resolved outside the declared site: " + name)
        imports[name] = origin
    return {"schema": "marketmaker.job_runtime_validation.v1", "status": "PASS", "actual": actual,
            "requirements": installed, "imports": imports, "files_verified": len(observed),
            "bundle_manifest_sha256": hashlib.sha256((root / "PYTHON_RUNTIME.json").read_bytes()).hexdigest(),
            "scope": "Job interpreter, exact library bytes and declared imports; not workload correctness or performance."}


def main():
    root, output = map(Path, sys.argv[1:])
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        record = verify(root)
    except Exception as error:
        record = {"schema": "marketmaker.job_runtime_validation.v1", "status": "FAIL", "error": str(error)}
    with output.open("x") as stream:
        json.dump(record, stream, sort_keys=True)
    return 0 if record["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
