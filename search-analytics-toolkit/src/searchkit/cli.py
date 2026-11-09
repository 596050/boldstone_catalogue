from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from . import __version__
from .artifacts import generate
from .auth import SCOPES, Vault, authorize_google
from .core import Profile, Receipt, ToolkitError, private_json, redact, template
from .google import Google
from .http import HTTP
from .reports import periods, run_report
from .search import Bing, Cloudflare, IndexNow
from .yandex import Yandex


def plan(p, providers):
    cfg = p.data
    operations = []
    if "ga4" in providers and cfg.get("ga4", {}).get("enabled"):
        g = cfg["ga4"]
        operations += [
            {
                "provider": "ga4",
                "action": "reconcile_property_and_web_stream",
                "account_id": g.get("account_id"),
                "property_id": g.get("property_id") or p.state().get("ga4_property_id"),
                "stream_id": g.get("stream_id"),
                "create_property": g.get("create_property", False),
                "website": p.url,
                "time_zone": g["time_zone"],
                "currency": g["currency"],
                "update_existing_timezone_currency": g.get("update_property_settings", False),
            },
            {"provider": "ga4", "action": "retention", "months": g.get("retention_months", 14)},
            {"provider": "ga4", "action": "key_events", "definitions": g.get("key_events", [])},
            {
                "provider": "ga4",
                "action": "custom_dimensions",
                "definitions": g.get("custom_dimensions", []),
            },
            {"provider": "ga4", "action": "audiences", "definitions": g.get("audiences", [])},
        ]
    if "gsc" in providers and cfg.get("search_console", {}).get("enabled"):
        operations.append(
            {
                "provider": "gsc",
                "action": "add_verified_property_and_submit_sitemaps",
                "site_url": cfg["search_console"]["site_url"],
                "sitemaps": cfg["website"]["sitemaps"],
            }
        )
    if "bing" in providers and cfg.get("bing", {}).get("enabled"):
        operations.append(
            {
                "provider": "bing",
                "action": "add_site_and_submit_feeds_after_verification",
                "site_url": p.url,
                "sitemaps": cfg["website"]["sitemaps"],
            }
        )
    if "yandex" in providers and cfg.get("yandex", {}).get("enabled"):
        operations.append(
            {
                "provider": "yandex",
                "action": "add_verified_host_and_submit_sitemaps",
                "site_url": p.url,
                "sitemaps": cfg["website"]["sitemaps"],
            }
        )
    return {
        "profile": p.id,
        "website": p.url,
        "kind": "offline desired-state preview; live reads reconcile before writes",
        "operations": operations,
        "google_setup_scopes": SCOPES["setup"],
        "owner_prerequisites": [
            "Google Desktop OAuth client with required APIs enabled and account grants",
            "An existing Analytics account ID or existing property/stream IDs",
            "Google and Bing ownership proof published, or zone-scoped Cloudflare token",
            "Bing Webmaster API key; account/API terms accepted by owner",
        ],
        "separate_steps": [
            "CMS deployment and consent/conversion browser tests",
            "Social account creation and app approvals",
            "GA4/Search Console product link, advertising feature policies and account TOS",
            "Actual purchase/order reconciliation and AI mention/citation measurements",
        ],
        "live_changes": False,
    }


def audit(p, http):
    results = {
        "website": p.url,
        "source_only": True,
        "collection_or_consent_verified": False,
        "checks": {},
    }
    urls = [p.url, p.url + "robots.txt", *p.data["website"].get("sitemaps", [])]
    for url in dict.fromkeys(urls):
        try:
            result = http.call("GET", url, text=True)
            text = result["text"]
            check = {"http_status": result["http_status"], "bytes": len(text.encode())}
            if url == p.url:
                check.update(
                    google_measurement_ids=sorted(set(re.findall(r"\b(?:G|GT)-[A-Z0-9]+\b", text))),
                    meta_initializations=len(re.findall(r"fbq\s*\(\s*['\"]init['\"]", text)),
                    meta_pageview_calls=len(
                        re.findall(r"fbq\s*\(\s*['\"]track['\"]\s*,\s*['\"]PageView['\"]", text)
                    ),
                )
            elif url in p.data["website"].get("sitemaps", []):
                if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
                    raise ToolkitError("Sitemap contains a prohibited XML declaration.")
                root = ET.fromstring(text)
                check.update(
                    root_type=root.tag.split("}")[-1],
                    page_url_count=len(root.findall("{*}url/{*}loc")),
                    child_sitemap_count=len(root.findall("{*}sitemap/{*}loc")),
                    all_xml_location_count=len(root.findall(".//{*}loc")),
                )
            results["checks"][url] = check
        except (ToolkitError, ET.ParseError) as e:
            results["checks"][url] = {"status": "unavailable", "reason": str(e)}
    return results


def doctor(p, vault):
    found = {}
    for name in ["google", "bing_api_key", "cloudflare_api_token", "yandex_oauth_token"]:
        try:
            value = vault.get(name, required=False)
            found[name] = {"present": value is not None}
            if name == "google" and value:
                found[name].update(email=value.get("email"), scopes=value.get("scopes", []))
        except ToolkitError as e:
            found[name] = {"present": "unknown", "error": str(e)}
    return {
        "version": __version__,
        "profile": p.id,
        "website": p.url,
        "state_folder": str(p.state_path.parent),
        "credential_store": vault.backend,
        "credentials": found,
        "network_dns_fallback": p.data.get("network", {}).get("dns_fallback"),
        "live_permissions_checked": False,
        "note": "Presence is not permission verification; run inventory before setup.",
    }


def parser():
    ap = argparse.ArgumentParser(
        description="Website search and analytics setup through supported APIs."
    )
    ap.add_argument("--version", action="version", version=__version__)
    ap.add_argument(
        "--profile", default=str(Path(__file__).resolve().parents[2] / "profiles/boldstone.json")
    )
    ap.add_argument("--credential-store", choices=["keychain", "file"], default="keychain")
    ap.add_argument("--reports-dir", default="reports")
    ap.add_argument("--generated-dir", default="generated")
    sub = ap.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="Create a profile for another website; refuses overwrite.")
    init.add_argument("--url", required=True)
    init.add_argument("--name", required=True)
    init.add_argument("--id", required=True)
    init.add_argument("--output", required=True)
    sub.add_parser("doctor")
    sub.add_parser("capabilities")
    sub.add_parser("audit")
    for name in ["plan", "setup"]:
        cmd = sub.add_parser(name)
        cmd.add_argument("--providers", default="ga4,gsc,bing")
        if name == "setup":
            cmd.add_argument("--apply", action="store_true")
    inv = sub.add_parser("inventory")
    inv.add_argument("--providers", default="google,bing")
    auth = sub.add_parser("auth")
    auth.add_argument("provider", choices=["google"])
    auth.add_argument("--client-file", required=True)
    auth.add_argument("--mode", choices=["report", "setup"], default="report")
    auth.add_argument("--no-browser", action="store_true")
    secret = sub.add_parser("secret")
    secret.add_argument(
        "name", choices=["bing_api_key", "cloudflare_api_token", "yandex_oauth_token"]
    )
    verification = sub.add_parser("verification")
    verification.add_argument("action", choices=["prepare", "confirm", "deploy-google-dns"])
    verification.add_argument("provider", choices=["google", "bing", "yandex"])
    verification.add_argument("--apply", action="store_true")
    sub.add_parser("generate")
    index = sub.add_parser("indexnow")
    index.add_argument("action", choices=["prepare", "submit"])
    index.add_argument("--urls-file")
    index.add_argument("--apply", action="store_true")
    report = sub.add_parser("report")
    report.add_argument("--period", choices=["weekly", "monthly", "rolling"], default="rolling")
    report.add_argument("--start")
    report.add_argument("--end")
    report.add_argument("--comparison-start")
    report.add_argument("--comparison-end")
    schedule = sub.add_parser("schedule")
    schedule.add_argument("--period", choices=["weekly", "monthly"], required=True)
    return ap


def require_apply(args):
    if not args.apply:
        raise ToolkitError(
            "This operation can change provider state. Inspect plan, then add --apply to execute."
        )


def schedule(profile, args):
    import plistlib
    import shlex

    executable = str(Path(sys.executable).absolute())
    project = str(Path.cwd().resolve())
    base = [
        executable,
        "-m",
        "searchkit",
        "--profile",
        str(profile.path),
        "--credential-store",
        args.credential_store,
        "--reports-dir",
        str(Path(args.reports_dir).expanduser().resolve()),
        "report",
        "--period",
        args.period,
    ]
    interval = (
        {"Weekday": 1, "Hour": 9, "Minute": 0}
        if args.period == "weekly"
        else {"Day": 5, "Hour": 10, "Minute": 0}
    )
    dest = Path(args.generated_dir).expanduser() / profile.id
    dest.mkdir(parents=True, exist_ok=True)
    environment = {"PYTHONPATH": str(Path(__file__).resolve().parents[1])}
    if os.environ.get("SEARCHKIT_STATE_DIR"):
        environment["SEARCHKIT_STATE_DIR"] = str(profile.state_dir)
    payload = {
        "Label": "local.searchkit." + profile.id + "." + args.period,
        "ProgramArguments": base,
        "WorkingDirectory": project,
        "StartCalendarInterval": interval,
        "EnvironmentVariables": environment,
        "StandardOutPath": str((dest / (args.period + ".stdout.log")).resolve()),
        "StandardErrorPath": str((dest / (args.period + ".stderr.log")).resolve()),
    }
    path = dest / (payload["Label"] + ".plist")
    path.write_bytes(plistlib.dumps(payload))
    (dest / (args.period + "-cron-command.txt")).write_text(
        ("0 9 * * 1 " if args.period == "weekly" else "0 10 5 * * ")
        + "cd "
        + shlex.quote(project)
        + " && "
        + shlex.join(["env", *(f"{key}={value}" for key, value in environment.items()), *base])
        + "\n"
    )
    return {
        "launchd_plist": str(path.resolve()),
        "installed": False,
        "timezone": "Local machine timezone; explicit source reporting timezones retained in reports",
        "launchd_install": "launchctl bootstrap gui/$(id -u) " + shlex.quote(str(path.resolve())),
    }


def main(argv=None):
    args = parser().parse_args(argv)
    receipt = None
    try:
        if args.command == "init":
            path = Path(args.output).expanduser()
            if path.exists() or path.is_symlink():
                raise ToolkitError("Refusing to overwrite an existing profile.")
            data = template(args.url, args.name, args.id)
            Profile.validate_data(data)
            private_json(path, data, exclusive=True)
            print(
                json.dumps(
                    {"profile": str(path.resolve()), "configure_account_and_auth_next": True},
                    indent=2,
                )
            )
            return 0
        p = Profile(args.profile)
        http = HTTP(p.data.get("network", {}).get("dns_fallback"))
        vault = Vault(p, args.credential_store)
        if args.command == "doctor":
            print(json.dumps(doctor(p, vault), indent=2))
            return 0
        if args.command == "capabilities":
            print(
                json.dumps(
                    {
                        "implemented": [
                            "Google Desktop OAuth PKCE and refresh",
                            "GA4 properties, web streams, retention, key events, event dimensions, optional lead audiences",
                            "Search Console site ownership tokens, verification, sites, sitemaps, URL inspection, search reports",
                            "Bing JSON REST sites, ownership proofs/verification, feeds, reports",
                            "Optional Yandex Webmaster sites, META verification and sitemaps",
                            "IndexNow proof files and changed URL submission",
                            "Cloudflare append-only Google verification TXT",
                            "Social sameAs schema, campaign links, deployment assets",
                            "JSON/CSV reporting and local schedule generation",
                        ],
                        "owner_or_platform_steps": [
                            "Account signup, terms and OAuth consent",
                            "CMS deployment and browser validation",
                            "Social API app approvals and account creation",
                            "GA4 product linking and unsupported dashboard settings",
                            "Google signals/UPD/Measurement Protocol policy decisions",
                            "Fresh AI-platform mention/citation responses",
                        ],
                    },
                    indent=2,
                )
            )
            return 0
        if args.command == "plan" or (args.command == "setup" and not args.apply):
            providers = args.providers.split(",")
            if set(providers) - {"ga4", "gsc", "bing", "yandex"}:
                raise ToolkitError("Providers must be ga4,gsc,bing,yandex.")
            print(json.dumps(plan(p, providers), indent=2))
            return 0
        if args.command == "auth":
            with p.lock():
                result = authorize_google(
                    p, vault, http, args.client_file, args.mode, open_browser=not args.no_browser
                )
            print(json.dumps(result, indent=2))
            return 0
        if args.command == "secret":
            vault.prompt_secret(args.name)
            print(
                json.dumps(
                    {"credential": args.name, "stored_in": vault.backend, "verified_readback": True}
                )
            )
            return 0
        if args.command == "schedule":
            print(json.dumps(schedule(p, args), indent=2))
            return 0
        with p.lock():
            receipt = Receipt(p, args.command, args.reports_dir)
            google, bing = Google(p, http, vault, receipt), Bing(p, http, vault, receipt)
            yandex = Yandex(p, http, vault, receipt)
            if args.command == "inventory":
                results = {}
                for provider in args.providers.split(","):
                    try:
                        if provider not in ["google", "bing", "yandex"]:
                            raise ToolkitError("Inventory providers must be google,bing,yandex.")
                        results[provider] = {
                            "google": google.inventory,
                            "bing": bing.sites,
                            "yandex": yandex.inventory,
                        }[provider]()
                    except ToolkitError as e:
                        results[provider] = {"status": "unavailable", "reason": str(e)}
                result = redact(results)
                receipt.export("inventory", result)
                status = (
                    "partial"
                    if any(
                        isinstance(v, dict) and v.get("status") == "unavailable"
                        for v in results.values()
                    )
                    else "complete"
                )
            elif args.command == "setup":
                providers = args.providers.split(",")
                if set(providers) - {"ga4", "gsc", "bing", "yandex"}:
                    raise ToolkitError("Providers must be ga4,gsc,bing,yandex.")
                receipt.export("desired-state", plan(p, providers))
                result = {}
                for provider in providers:
                    key = "search_console" if provider == "gsc" else provider
                    if not p.data.get(key, {}).get("enabled"):
                        result[provider] = {"status": "disabled"}
                        continue
                    try:
                        value = {
                            "ga4": google.setup_ga4,
                            "gsc": google.setup_gsc,
                            "bing": bing.setup,
                            "yandex": yandex.setup,
                        }[provider]()
                        result[provider] = {"status": "configured", "result": redact(value)}
                    except ToolkitError as e:
                        result[provider] = {"status": "blocked", "reason": str(e)}
                        receipt.add(provider, "blocked", str(e))
                status = (
                    "partial"
                    if any(v["status"] == "blocked" for v in result.values())
                    else "complete"
                )
            elif args.command == "verification":
                if args.action in ["confirm", "deploy-google-dns"] or args.provider in [
                    "bing",
                    "yandex",
                ]:
                    require_apply(args)
                if args.action == "deploy-google-dns":
                    if args.provider != "google":
                        raise ToolkitError(
                            "This adapter deploys only the prepared Google TXT record."
                        )
                    result = Cloudflare(p, http, vault, receipt).deploy_google_txt()
                else:
                    adapter = {"google": google, "bing": bing, "yandex": yandex}[args.provider]
                    result = (
                        adapter.prepare_verification()
                        if args.action == "prepare"
                        else adapter.confirm_verification()
                    )
                    if args.action == "prepare":
                        result = {
                            "provider": args.provider,
                            "proof_prepared": True,
                            "verified": False,
                            "assets": generate(p, args.generated_dir),
                        }
                status = (
                    "partial"
                    if args.action == "confirm" and result.get("verified") is False
                    else "complete"
                )
            elif args.command == "indexnow":
                adapter = IndexNow(p, http, receipt)
                if args.action == "prepare":
                    adapter.prepare()
                    result = generate(p, args.generated_dir)
                else:
                    require_apply(args)
                    if not args.urls_file:
                        raise ToolkitError("Supply --urls-file with changed canonical URLs.")
                    urls = [
                        s.strip()
                        for s in Path(args.urls_file).read_text().splitlines()
                        if s.strip()
                    ]
                    result = adapter.submit(urls)
                status = "complete"
            elif args.command == "generate":
                result = generate(p, args.generated_dir)
                status = "complete"
            elif args.command == "audit":
                result = audit(p, http)
                status = (
                    "partial"
                    if any(c.get("status") == "unavailable" for c in result["checks"].values())
                    else "complete"
                )
            elif args.command == "report":
                if bool(args.start) != bool(args.end) or bool(args.comparison_start) != bool(
                    args.comparison_end
                ):
                    raise ToolkitError("Provide both dates for each explicit period.")
                if args.start:
                    current = (args.start, args.end)
                    start, end = map(dt.date.fromisoformat, current)
                    if end < start:
                        raise ToolkitError("End date precedes start date.")
                    previous = (
                        (args.comparison_start, args.comparison_end)
                        if args.comparison_start
                        else (
                            (start - (end - start) - dt.timedelta(days=1)).isoformat(),
                            (start - dt.timedelta(days=1)).isoformat(),
                        )
                    )
                else:
                    if args.comparison_start:
                        raise ToolkitError(
                            "Explicit comparison dates require explicit current dates."
                        )
                    current, previous = periods(args.period)
                if dt.date.fromisoformat(previous[1]) < dt.date.fromisoformat(previous[0]):
                    raise ToolkitError("Comparison end precedes start.")
                today = dt.datetime.now(dt.timezone.utc).date()
                if any(dt.date.fromisoformat(end) > today for end in [current[1], previous[1]]):
                    raise ToolkitError("Future reporting dates are not supported.")
                result = run_report(p, google, bing, receipt, current, previous)
                status = (
                    "partial"
                    if any(
                        "available" != v and not v.startswith("available;")
                        for v in result["availability"].values()
                    )
                    else "complete"
                )
            else:
                raise ToolkitError("Unsupported command.")
            receipt.export("result", redact(result, http.secrets))
            receipt.finish(status)
            print(
                json.dumps(
                    {
                        "status": status,
                        "receipt": str(receipt.path.resolve()),
                        "result": redact(result, http.secrets),
                    },
                    indent=2,
                )
            )
            return 0 if status == "complete" else 2
    except (ToolkitError, OSError, ValueError, KeyError) as e:
        if receipt:
            receipt.add("command", "failed", str(e))
            receipt.finish("failed")
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error": str(e),
                    "receipt": str(receipt.path.resolve()) if receipt else None,
                }
            ),
            file=sys.stderr,
        )
        return 1
