"""Build a declared, wheel-only job input; never install into a worker or host env.

Generalizes the job-local dependency preparation previously embedded in study
launchers. All versions, wheel hashes, target ABI and storage limits are inputs.
"""

import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from .common import atomic, capture_file, digest, fields, hash_id, inventory, load, no_links, positive, rel, sha

REQUEST_SCHEMA = "marketmaker.python_runtime_request.v1"
BUNDLE_SCHEMA = "marketmaker.python_runtime_bundle.v1"


def normalized_name(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value):
        raise ValueError("invalid distribution name")
    return re.sub(r"[-_.]+", "-", value).lower()


def validate(raw):
    fields(raw, {"schema", "target", "requirements", "wheels", "imports", "max_bytes", "min_free_bytes"},
           {"schema", "target", "requirements", "wheels", "max_bytes", "min_free_bytes"})
    if raw["schema"] != REQUEST_SCHEMA:
        raise ValueError("unsupported Python runtime request")
    target = raw["target"]
    fields(target, {"python", "implementation", "abi", "platforms", "system", "machine"},
           {"python", "implementation", "abi", "platforms", "system", "machine"})
    if not isinstance(target["python"], str) or not re.fullmatch(r"3\.(?:[1-9][0-9])", target["python"]):
        raise ValueError("declare Python major.minor, at least 3.10")
    if target["implementation"] != "cp" or target["system"] not in {"Linux", "Darwin", "Windows"}:
        raise ValueError("declare a supported CPython target system")
    for key in ("abi", "machine"):
        if not isinstance(target[key], str) or not re.fullmatch(r"[A-Za-z0-9_]+", target[key]):
            raise ValueError("invalid Python target " + key)
    if target["abi"] != "cp" + target["python"].replace(".", ""):
        raise ValueError("declare the regular CPython ABI matching major.minor; free-threaded builds are not supported")
    platforms = target["platforms"]
    if not isinstance(platforms, list) or not platforms or any(
        not isinstance(p, str) or not re.fullmatch(r"[A-Za-z0-9_]+", p) for p in platforms
    ) or len(set(platforms)) != len(platforms):
        raise ValueError("declare distinct target wheel platforms")
    requirements = raw["requirements"]
    if not isinstance(requirements, dict) or not requirements:
        raise ValueError("declare exact distribution versions")
    names = [normalized_name(k) for k in requirements]
    if len(set(names)) != len(names) or any(
        not isinstance(v, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.!+_-]*", v)
        for v in requirements.values()
    ):
        raise ValueError("requirements need unique names and exact versions, not ranges/URLs")
    wheels = raw["wheels"]
    if not isinstance(wheels, list) or not wheels:
        raise ValueError("declare hash-bound local wheels")
    for wheel in wheels:
        fields(wheel, {"path", "sha256"}, {"path", "sha256"})
        if not isinstance(wheel["path"], str) or not wheel["path"].endswith(".whl"):
            raise ValueError("only explicit local wheels are supported")
        hash_id(wheel["sha256"])
    imports = raw.get("imports", [])
    if not isinstance(imports, list) or len(imports) != len(set(imports)) or any(
        not isinstance(i, str) or not re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", i)
        for i in imports
    ):
        raise ValueError("imports must be distinct Python module names")
    positive(raw["max_bytes"], 1 << 40)
    if type(raw["min_free_bytes"]) is not int or raw["min_free_bytes"] < 0:
        raise ValueError("declare a nonnegative free-space reserve")
    return raw


def prepare(request, destination, *, base=None, python=None):
    """Install only supplied, hash-verified wheels into a fresh bounded directory.

    No network, dependency resolution, source builds or import probes on the
    requester. The selected worker validates compatibility before executing code.
    Failed preparations remain inspectable and cannot be reused as ready bundles.
    """
    request = validate(request)
    base, destination = Path(base or ".").resolve(), Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(destination)
    wheels, compressed = [], 0
    for row in request["wheels"]:
        path = (base / row["path"]).absolute()
        if path.is_symlink() or not path.is_file():
            raise ValueError("runtime wheel is not a regular local file")
        compressed += path.stat().st_size
        if compressed > request["max_bytes"]:
            raise ValueError("compressed wheel staging exceeds the runtime byte budget")
        if sha(path) != row["sha256"]:
            raise ValueError("runtime wheel differs from declared bytes")
        wheels.append(path)
    names = [rel(p.name).casefold() for p in wheels]
    if len(set(names)) != len(names):
        raise ValueError("ambiguous wheel filenames")
    expanded, members = 0, 0
    for wheel in wheels:
        with zipfile.ZipFile(wheel) as archive:
            seen = set()
            for member in archive.infolist():
                name = rel(member.filename.rstrip("/")).casefold()
                if name in seen or (member.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError("wheel contains ambiguous or linked members")
                seen.add(name)
                expanded += member.file_size
                members += 1
                if expanded > request["max_bytes"] or members > 100000:
                    raise ValueError("wheel expansion exceeds its byte/count budget")
    # Leave room for pip's generated metadata/activation before invoking pip.
    if expanded + (1 << 20) + members * 512 > request["max_bytes"]:
        raise ValueError("runtime byte budget lacks installation metadata headroom")
    no_links(destination, destination.parent)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Wheel staging plus installation and a full verification reserve. Filesystem
    # accounting is checked again afterward; this does not reserve other writers.
    required = request["min_free_bytes"] + request["max_bytes"] + expanded + sum(p.stat().st_size for p in wheels)
    if shutil.disk_usage(destination.parent).free < required:
        raise ValueError("insufficient runtime preparation space above the declared reserve")
    destination.mkdir()
    atomic(destination / "REQUEST.json", request)
    staging = destination / "wheels"
    staging.mkdir()
    try:
        for original, row in zip(wheels, request["wheels"]):
            capture_file(original, staging / original.name, expected_sha256=row["sha256"],
                         max_bytes=original.stat().st_size)
        target = request["target"]
        site = destination / "site-packages"
        command = [str(python or sys.executable), "-B", "-m", "pip", "--isolated", "install",
                   "--no-index", "--find-links", str(staging), "--only-binary=:all:",
                   "--no-deps", "--no-cache-dir", "--no-compile", "--disable-pip-version-check",
                   "--python-version", target["python"], "--implementation", target["implementation"],
                   "--abi", target["abi"], "--target", str(site)]
        for platform in target["platforms"]:
            command += ["--platform", platform]
        command += [key + "==" + value for key, value in sorted(request["requirements"].items())]
        with (destination / "INSTALL.log").open("x") as log:
            process = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
        if process.returncode:
            raise RuntimeError("wheel installation failed; inspect retained INSTALL.log")
        # Activated only in the job interpreter. Never execute wheel .pth files
        # or import target-platform binary extensions in this requester process.
        activation = site / "sitecustomize.py"
        if activation.exists():
            raise ValueError("a distribution owns reserved runtime activation file")
        activation.write_text("import os, site\nsite.addsitedir(os.path.dirname(__file__))\n")
        files = inventory(site, max_bytes=request["max_bytes"])
        if shutil.disk_usage(destination).free < request["min_free_bytes"]:
            raise ValueError("runtime preparation consumed its declared free-space reserve")
        result = {"schema": BUNDLE_SCHEMA, "target": target, "requirements": request["requirements"],
                  "imports": request.get("imports", []), "site": "site-packages", "files": files,
                  "request_sha256": digest(request), "status": "PREPARED_NOT_WORKER_VALIDATED",
                  "worker_configuration_changed": False, "global_packages_changed": False}
        atomic(destination / "PYTHON_RUNTIME.json", result)
        return result
    except BaseException as error:
        atomic(destination / "FAILURE.json", {"status": "PREPARATION_FAILED", "error": str(error),
                                              "request_sha256": digest(request)})
        raise


def from_file(request, destination, **kwargs):
    request = Path(request).resolve()
    return prepare(load(request), destination, base=request.parent, **kwargs)
