#!/usr/bin/env python3
"""Publish one local HTTP service through an authenticated Cloudflare Tunnel."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import hmac
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import uuid

try:
    import aiohttp
    from aiohttp import web
    from multidict import CIMultiDict
    from yarl import URL
except ImportError:
    raise SystemExit("Install dependencies first: python -m pip install -r requirements.txt")


TOKEN_ENV = "OFFLOAD_ACCESS_TOKEN"
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{32,256}\Z")
QUICK_URL = re.compile(r"https://[a-z0-9]+(?:-[a-z0-9]+)*\.trycloudflare\.com\b")
METHODS = {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}
HOP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "proxy-connection", "te", "trailer", "transfer-encoding", "upgrade",
}
NO_CACHE = {"Cache-Control": "no-store", "Cloudflare-CDN-Cache-Control": "no-store"}


def local_url(value: str) -> str:
    """Pin the destination to loopback; request URLs can never choose a host."""
    try:
        url = URL(value)
        if url.scheme not in {"http", "https"} or not url.host or not url.port:
            raise ValueError
        if url.user is not None or url.query_string or url.fragment or url.path != "/":
            raise ValueError
        if url.host == "localhost":
            url = url.with_host("127.0.0.1")
        if not ipaddress.ip_address(url.host).is_loopback:
            raise ValueError
        return str(url.origin())
    except (ValueError, TypeError):
        raise argparse.ArgumentTypeError(
            "use a loopback HTTP(S) origin, e.g. http://127.0.0.1:8000 (no path or credentials)"
        ) from None


def positive(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be a finite positive number")
    return number


def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def port(value: str) -> int:
    number = int(value)
    if not 0 <= number <= 65535:
        raise argparse.ArgumentTypeError("must be between 0 and 65535")
    return number


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, type=local_url, help="local HTTP(S) service")
    parser.add_argument("--cloudflared", default="cloudflared", help="executable name or path")
    parser.add_argument("--proxy-port", type=port, default=0, help="loopback gateway port (0 = automatic)")
    parser.add_argument(
        "--token-file", type=Path,
        default=Path(__file__).resolve().parent / ".runtime" / "access-token.txt",
        help=f"read or create a requester token here; {TOKEN_ENV} overrides this file",
    )
    parser.add_argument(
        "--auth-header", choices=("Authorization", "X-Offload-Token"), default="Authorization",
        help="Authorization uses Bearer TOKEN; X-Offload-Token uses the raw token and preserves origin Authorization",
    )
    parser.add_argument("--max-body-mib", type=positive_int, default=16)
    parser.add_argument("--max-concurrent", type=positive_int, default=16)
    parser.add_argument("--request-timeout", type=positive, default=300, help="upload/upstream idle timeout in seconds")
    parser.add_argument("--startup-timeout", type=positive, default=120)
    parser.add_argument("--reconnect-delay", type=positive, default=5)
    parser.add_argument("--protocol", choices=("auto", "http2", "quic"), default="auto")
    parser.add_argument("--once", action="store_true", help="exit if cloudflared exits; no process restart")
    parser.add_argument("--check", action="store_true", help="check executable, settings and local TCP listener without publishing")
    named = parser.add_argument_group("optional stable hostname (locally managed tunnel)")
    named.add_argument("--tunnel-id", help="existing Cloudflare tunnel UUID")
    named.add_argument("--credentials-file", type=Path, help="that tunnel's credentials JSON")
    named.add_argument("--hostname", help="existing DNS route, e.g. worker.example.com")
    args = parser.parse_args(argv)
    if any((args.tunnel_id, args.credentials_file, args.hostname)):
        if not all((args.tunnel_id, args.credentials_file, args.hostname)):
            parser.error("--tunnel-id, --credentials-file and --hostname must be supplied together")
        try:
            args.tunnel_id = str(uuid.UUID(args.tunnel_id))
        except ValueError:
            parser.error("--tunnel-id must be a UUID")
        if len(args.hostname) > 253 or not re.fullmatch(
            r"(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+"
            r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?", args.hostname
        ):
            parser.error("--hostname must be a DNS hostname without a scheme, port or path")
        args.hostname = args.hostname.lower()
    return args


def load_token(path: Path) -> str:
    token = os.environ.get(TOKEN_ENV)
    if token is None:
        path = path.expanduser().absolute()
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(descriptor, "w", encoding="ascii") as handle:
                handle.write(secrets.token_urlsafe(32) + "\n")
        metadata = path.lstat()
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("token file must be a regular file, not a symlink")
        if os.name != "nt" and metadata.st_mode & 0o077:
            raise ValueError(f"token file must be private; run chmod 600 on {path}")
        with path.open(encoding="ascii") as handle:
            token = handle.read(258).strip()
    if not TOKEN_PATTERN.fullmatch(token):
        raise ValueError("access token must contain 32-256 letters, digits, underscores or hyphens")
    return token


def filtered_headers(headers, extra: set[str] | None = None) -> CIMultiDict:
    excluded = HOP_HEADERS | (extra or set())
    for value in headers.getall("Connection", []):
        excluded.update(part.strip().lower() for part in value.split(","))
    return CIMultiDict((key, value) for key, value in headers.items() if key.lower() not in excluded)


def error_response(status: int, message: str, **headers: str) -> web.Response:
    response = web.Response(status=status, text=message + "\n", headers={**NO_CACHE, **headers})
    response.force_close()
    return response


def create_app(
    origin: str, token: str, *, auth_header: str = "Authorization",
    max_body: int = 16 * 1024 * 1024, max_concurrent: int = 16, timeout: float = 300,
) -> web.Application:
    origin = local_url(origin)
    session = None
    active = 0
    expected = ("Bearer " + token) if auth_header == "Authorization" else token

    async def lifecycle(_app):
        nonlocal session
        async with aiohttp.ClientSession(
            auto_decompress=False, trust_env=False, cookie_jar=aiohttp.DummyCookieJar(),
            timeout=aiohttp.ClientTimeout(total=None, sock_connect=10, sock_read=timeout),
            connector=aiohttp.TCPConnector(limit=max_concurrent),
            skip_auto_headers={"Accept", "Accept-Encoding", "User-Agent", "Content-Type"},
        ) as session:
            yield

    async def forward(request: web.Request) -> web.StreamResponse:
        nonlocal active
        supplied = request.headers.getall(auth_header, [])
        if len(supplied) != 1 or not hmac.compare_digest(
            supplied[0].encode("utf-8", errors="replace"), expected.encode("ascii")
        ):
            return error_response(401, "Unauthorized", **{"WWW-Authenticate": 'Bearer realm="offload"'})
        if request.method not in METHODS:
            return error_response(405, "Method not supported", Allow=", ".join(sorted(METHODS)))
        if "Upgrade" in request.headers:
            return error_response(501, "Protocol upgrades (including WebSockets) are not supported")
        if not request.raw_path.startswith("/") or request.raw_path.startswith("//"):
            return error_response(400, "Only origin-form request paths are supported")
        if active >= max_concurrent:
            return error_response(503, "Gateway is busy", **{"Retry-After": "1"})
        if request.content_length is not None and request.content_length > max_body:
            return error_response(413, "Request body too large")
        active += 1
        response = None
        try:
            # Buffer bounded uploads so oversized/chunked bodies never partly reach the service.
            body = await asyncio.wait_for(request.read(), timeout=timeout)
            headers = filtered_headers(request.headers, {
                auth_header.lower(), "host", "content-length", "expect",
                "forwarded", "x-forwarded-for", "x-forwarded-host", "x-forwarded-proto",
            })
            # Concatenation (never URL joining) pins the destination; preserve escaped paths/query bytes.
            destination = URL(origin + request.raw_path, encoded=True)
            async with session.request(
                request.method, destination, headers=headers,
                data=body if request.can_read_body or body else None, allow_redirects=False,
            ) as upstream:
                if upstream.status == 101:
                    return error_response(502, "Unexpected protocol upgrade from local service")
                response_headers = filtered_headers(upstream.headers)
                response_headers.update(NO_CACHE)
                response = web.StreamResponse(status=upstream.status, headers=response_headers)
                await response.prepare(request)
                async for chunk in upstream.content.iter_chunked(64 * 1024):
                    await response.write(chunk)
                await response.write_eof()
                return response
        except web.HTTPRequestEntityTooLarge:
            return error_response(413, "Request body too large")
        except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError) as exc:
            if response is not None and response.prepared:
                # An incomplete body cannot be replaced by an error after sending response headers.
                if request.transport:
                    request.transport.close()
                return response
            status = 504 if isinstance(exc, asyncio.TimeoutError) else 502
            return error_response(status, "Local service timed out" if status == 504 else "Local service unavailable")
        finally:
            active -= 1

    app = web.Application(client_max_size=max_body + 1, handler_args={"auto_decompress": False})
    app.cleanup_ctx.append(lifecycle)
    app.router.add_route("*", "/{path:.*}", forward)
    return app


def child_environment() -> dict[str, str]:
    # Ambient cloudflared settings must not redirect traffic around the authentication gateway.
    return {
        key: value for key, value in os.environ.items()
        if not key.upper().startswith("TUNNEL_")
        and key.upper() not in {TOKEN_ENV, "NO_TLS_VERIFY", "NO_AUTOUPDATE"}
    }


def tunnel_config(args: argparse.Namespace, gateway: str) -> dict:
    if not args.tunnel_id:
        return {}  # Explicit empty config isolates Quick Tunnels from ~/.cloudflared/config.yml.
    return {
        "tunnel": args.tunnel_id,
        "credentials-file": str(args.credentials_file),
        "ingress": [
            {"hostname": args.hostname, "service": gateway},
            {"service": "http_status:404"},
        ],
    }


def tunnel_command(args: argparse.Namespace, executable: str, config: Path, gateway: str) -> list[str]:
    command = [
        executable, "tunnel", "--config", str(config), "--no-autoupdate",
        "--metrics", "127.0.0.1:0", "--loglevel", "info", "--output", "default",
        "--protocol", args.protocol, "--grace-period", "5s",
    ]
    if args.tunnel_id:
        return command + ["run", args.tunnel_id]
    return command + ["--url", gateway]


async def stop_process(process: asyncio.subprocess.Process) -> None:
    if process.returncode is None:
        with contextlib.suppress(ProcessLookupError):
            process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=8)
        except asyncio.TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            await process.wait()


async def supervise(args, command: list[str], token: str, stopping: asyncio.Event) -> int:
    delay = min(args.reconnect_delay, 60)
    while not stopping.is_set():
        ready = asyncio.Event()
        public_url = f"https://{args.hostname}" if args.tunnel_id else None
        started = time.monotonic()
        options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
        process = await asyncio.create_subprocess_exec(
            *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
            env=child_environment(), **options,
        )

        async def read_logs():
            nonlocal public_url
            async for raw in process.stdout:
                line = raw.decode("utf-8", errors="replace").rstrip().replace(token, "[redacted]")
                print(f"[cloudflared] {line}", file=sys.stderr, flush=True)
                if not args.tunnel_id:
                    match = QUICK_URL.search(line)
                    if match and match.group(0) != public_url:
                        public_url = match.group(0)
                        print(f"PUBLIC_URL={public_url}", flush=True)
                if "Registered tunnel connection" in line and not ready.is_set():
                    ready.set()
                    if args.tunnel_id:
                        print(f"PUBLIC_URL={public_url}", flush=True)
                    print("Tunnel connected. Requests require the access token.", flush=True)

        logs = asyncio.create_task(read_logs())
        exited = asyncio.create_task(process.wait())
        interrupted = asyncio.create_task(stopping.wait())
        connected = asyncio.create_task(ready.wait())
        try:
            done, _ = await asyncio.wait(
                {exited, interrupted, connected, logs}, timeout=args.startup_timeout,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if not done:
                print("Tunnel startup timed out. Check connectivity; try --protocol http2.", file=sys.stderr)
                return 1
            if connected in done and not stopping.is_set():
                await asyncio.wait({exited, interrupted, logs}, return_when=asyncio.FIRST_COMPLETED)
            if stopping.is_set():
                return 0
            if logs.done():
                logs.result()
        finally:
            await stop_process(process)
            for task in (logs, exited, interrupted, connected):
                if not task.done():
                    task.cancel()
            await asyncio.gather(logs, exited, interrupted, connected, return_exceptions=True)
        if args.once:
            return process.returncode or 1
        print(f"Tunnel exited ({process.returncode}); reconnecting in {delay:g}s."
              " Quick Tunnel URLs change on process restart.", file=sys.stderr, flush=True)
        try:
            await asyncio.wait_for(stopping.wait(), timeout=delay)
        except asyncio.TimeoutError:
            pass
        delay = min(args.reconnect_delay, 60) if time.monotonic() - started >= 60 else min(delay * 2, 60)
    return 0


async def check_origin(origin: str) -> None:
    url = URL(origin)
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(url.host, url.port), timeout=5)
        writer.close()
        await writer.wait_closed()
    except (OSError, asyncio.TimeoutError):
        raise ValueError(f"No reachable TCP listener at {origin}; start the local service first") from None


async def run(args, executable: str) -> int:
    await check_origin(args.url)
    if args.check:
        print(f"Checks passed: cloudflared={executable}; local TCP listener={args.url}. No public tunnel opened.")
        return 0
    token = load_token(args.token_file)
    source = TOKEN_ENV if TOKEN_ENV in os.environ else str(args.token_file.expanduser().absolute())
    print(f"Access token source: {source} (token value is not logged)", flush=True)
    stopping = asyncio.Event()
    loop = asyncio.get_running_loop()
    previous = {}
    signals = [signal.SIGINT, signal.SIGTERM]
    if hasattr(signal, "SIGBREAK"):
        signals.append(signal.SIGBREAK)
    for signum in signals:
        # Wake an idle selector/proactor too; Event.set alone does not wake its I/O wait.
        previous[signum] = signal.signal(signum, lambda *_: loop.call_soon_threadsafe(stopping.set))
    app = create_app(
        args.url, token, auth_header=args.auth_header, max_body=args.max_body_mib * 1024 * 1024,
        max_concurrent=args.max_concurrent, timeout=args.request_timeout,
    )
    runner = web.AppRunner(app, access_log=None, shutdown_timeout=5)
    try:
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", args.proxy_port)
        await site.start()
        gateway = f"http://127.0.0.1:{runner.addresses[0][1]}"
        print(f"Authenticated gateway: {gateway} -> {args.url}", flush=True)
        with tempfile.TemporaryDirectory(prefix="offload-cloudflare-") as directory:
            config = Path(directory) / "config.yml"
            # JSON is a YAML subset; quoting paths this way also works on Windows.
            config.write_text(json.dumps(tunnel_config(args, gateway)), encoding="utf-8")
            return await supervise(args, tunnel_command(args, executable, config, gateway), token, stopping)
    finally:
        await runner.cleanup()
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        candidate = os.path.expanduser(args.cloudflared)
        executable = shutil.which(candidate)
        if not executable:
            raise ValueError("cloudflared not found; install it using README.md or pass --cloudflared PATH")
        if args.tunnel_id:
            args.credentials_file = args.credentials_file.expanduser().resolve(strict=True)
            credentials = json.loads(args.credentials_file.read_text(encoding="utf-8"))
            if (not isinstance(credentials, dict) or credentials.get("TunnelID") != args.tunnel_id
                    or not credentials.get("TunnelSecret")):
                raise ValueError("credentials file does not match --tunnel-id")
        return asyncio.run(run(args, executable))
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
