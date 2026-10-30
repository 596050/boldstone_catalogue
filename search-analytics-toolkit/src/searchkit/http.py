"""TLS-verified HTTP with bounded responses, safe errors, and opt-in DNS fallback."""

from __future__ import annotations

import contextlib
import ipaddress
import json
import socket
import subprocess
import threading
import urllib.error
import urllib.parse
import urllib.request

from .core import ToolkitError, redact

_DNS_LOCK = threading.RLock()


@contextlib.contextmanager
def dns_fallback(resolver):
    if not resolver:
        yield
        return
    ipaddress.ip_address(resolver)
    with _DNS_LOCK:
        original = socket.getaddrinfo

        def resolve(host, port, *args, **kwargs):
            try:
                return original(host, port, *args, **kwargs)
            except socket.gaierror:
                result = subprocess.run(
                    ["dig", "@" + resolver, host, "A", "+short"],
                    capture_output=True,
                    text=True,
                    timeout=12,
                    check=True,
                )
                for line in result.stdout.splitlines():
                    try:
                        address = ipaddress.ip_address(line)
                    except ValueError:
                        continue
                    if address.version == 4:
                        return original(str(address), port, *args, **kwargs)
                raise ToolkitError("DNS lookup failed for " + host) from None

        socket.getaddrinfo = resolve
        try:
            yield
        finally:
            socket.getaddrinfo = original


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ToolkitError("HTTP redirect blocked; verify the canonical/API endpoint.")


class APIError(ToolkitError):
    def __init__(self, status, method, url, detail):
        self.status = status
        self.detail = detail
        p = urllib.parse.urlsplit(url)
        super().__init__(f"HTTP {status}: {method} {p.hostname}{p.path}: {detail}")


class HTTP:
    def __init__(self, resolver=None, transport=None):
        self.resolver = resolver
        self.transport = transport  # Injected fake for contract tests; never a live proxy.
        self.secrets = []
        self.opener = urllib.request.build_opener(NoRedirects())

    def call(self, method, url, *, body=None, headers=None, form=None, text=False):
        p = urllib.parse.urlsplit(url)
        if p.scheme != "https" or not p.hostname or p.username or p.password:
            raise ToolkitError("Only HTTPS requests without URL credentials are allowed.")
        for key, value in (form or {}).items():
            if key in {"code", "code_verifier", "client_secret", "refresh_token"}:
                self.secrets.append(value)
        if self.transport:
            return self.transport(method, url, body=body, headers=headers, form=form, text=text)
        h = {"User-Agent": "SearchAnalyticsToolkit/0.1", **(headers or {})}
        if body is not None:
            payload = json.dumps(body).encode()
            h["Content-Type"] = "application/json"
        elif form is not None:
            payload = urllib.parse.urlencode(form).encode()
            h["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            payload = None
        request = urllib.request.Request(url, method=method, data=payload, headers=h)
        try:
            with dns_fallback(self.resolver), self.opener.open(request, timeout=30) as response:
                status = response.status
                raw = response.read(20_000_001)
        except urllib.error.HTTPError as e:
            raw = e.read(10000).decode("utf-8", "replace")
            raise APIError(e.code, method, url, redact(raw, self.secrets)) from None
        except (OSError, urllib.error.URLError, subprocess.SubprocessError) as e:
            # No automatic retries: a timed-out POST may already have created a resource.
            raise ToolkitError(
                "Network request failed; write outcome may be unknown. "
                "Inspect inventory before retrying. " + type(e).__name__
            ) from None
        if len(raw) > 20_000_000:
            raise ToolkitError("Response exceeded the 20 MB bound; partition the report.")
        value = raw.decode("utf-8")
        if text:
            return {"http_status": status, "text": value}
        try:
            data = json.loads(value) if value else {}
        except ValueError:
            raise ToolkitError("API returned a non-JSON response.") from None
        return {"http_status": status, "data": data}
