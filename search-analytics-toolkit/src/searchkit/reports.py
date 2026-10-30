"""Dated JSON/CSV archives with source-specific periods and truthful availability."""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json

from .core import ToolkitError, csv_safe, now, private_json
from .google import ADMIN, GSC, GSC_READ, q


def periods(mode, today=None, lag=3):
    today = today or dt.datetime.now(dt.timezone.utc).date()
    cutoff = today - dt.timedelta(days=lag)
    if mode == "weekly":
        end = cutoff - dt.timedelta(days=(cutoff.weekday() + 1) % 7)
        start = end - dt.timedelta(days=6)
        previous_end = start - dt.timedelta(days=1)
        previous_start = previous_end - dt.timedelta(days=6)
    elif mode == "monthly":
        end = today.replace(day=1) - dt.timedelta(days=1)
        if end > cutoff:
            end = end.replace(day=1) - dt.timedelta(days=1)
        start = end.replace(day=1)
        previous_end = start - dt.timedelta(days=1)
        previous_start = previous_end.replace(day=1)
    else:
        end = cutoff
        start = end - dt.timedelta(days=27)
        previous_end = start - dt.timedelta(days=1)
        previous_start = previous_end - dt.timedelta(days=27)
    return (start.isoformat(), end.isoformat()), (
        previous_start.isoformat(),
        previous_end.isoformat(),
    )


def csv_rows(path, rows):
    if not rows:
        path.write_text("")
        return
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fields)
        writer.writeheader()
        writer.writerows(
            {
                k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else csv_safe(v)
                for k, v in row.items()
            }
            for row in rows
        )


def flatten_ga4(result):
    req = result["request"]
    dimensions = [d["name"] for d in req["dimensions"]]
    metrics = [m["name"] for m in req["metrics"]]
    rows = []
    for row in result["rows"]:
        flat = {k: v["value"] for k, v in zip(dimensions, row.get("dimensionValues", []))}
        flat.update({k: v["value"] for k, v in zip(metrics, row.get("metricValues", []))})
        rows.append(flat)
    return rows


def gsc_summary(rows):
    clicks = sum(r["clicks"] for r in rows)
    impressions = sum(r["impressions"] for r in rows)
    return {
        "clicks": clicks,
        "impressions": impressions,
        "ctr": clicks / impressions if impressions else None,
        "position": sum(r["position"] * r["impressions"] for r in rows) / impressions
        if impressions
        else None,
    }


def run_report(profile, google, bing, receipt, current, previous):
    summary = {
        "generated_at": now(),
        "website": profile.url,
        "current": current,
        "previous": previous,
        "ga4_hostname_filter": profile.host,
        "gsc_date_basis": "America/Los_Angeles",
        "settlement": "Three-day buffer by default; API metadata is retained, not a guarantee that late events are final.",
        "availability": {},
        "alerts": [],
    }
    gsc_totals = {}

    def save(name, result, rows):
        receipt.export(name, result)
        csv_rows(receipt.folder / (name + ".csv"), rows)

    for label, dates in [("current", current), ("previous", previous)]:
        if profile.data.get("search_console", {}).get("enabled"):
            try:
                for dimension in ["date", "query", "page", "country", "device"]:
                    result = google.search_report(*dates, [dimension])
                    save("gsc-" + label + "-" + dimension, result, result["rows"])
                    if dimension == "date":
                        gsc_totals[label] = gsc_summary(result["rows"])
                summary["availability"]["gsc_" + label] = "available"
            except ToolkitError as e:
                summary["availability"]["gsc_" + label] = str(e)
                receipt.add("report.gsc." + label, "unavailable", str(e))
        if profile.data.get("ga4", {}).get("enabled"):
            try:
                metrics = [
                    "sessions",
                    "activeUsers",
                    "screenPageViews",
                    "engagementRate",
                    "eventCount",
                    "keyEvents",
                    "ecommercePurchases",
                    "totalRevenue",
                ]
                result = google.ga4_report(*dates, [], metrics)
                save("ga4-" + label + "-totals", result, flatten_ga4(result))
                for dimension in [
                    "date",
                    "sessionSourceMedium",
                    "pagePath",
                    "landingPage",
                    "country",
                    "deviceCategory",
                    "eventName",
                ]:
                    event_metrics = (
                        ["eventCount", "keyEvents"]
                        if dimension == "eventName"
                        else ["sessions", "screenPageViews", "keyEvents"]
                    )
                    result = google.ga4_report(*dates, [dimension], event_metrics)
                    flat = flatten_ga4(result)
                    save("ga4-" + label + "-" + dimension, result, flat)
                    if dimension == "sessionSourceMedium":
                        hosts = set(
                            profile.data.get("reporting", {}).get(
                                "ai_referral_hosts",
                                [
                                    "chatgpt.com",
                                    "perplexity.ai",
                                    "claude.ai",
                                    "gemini.google.com",
                                    "copilot.microsoft.com",
                                ],
                            )
                        )
                        sources = [
                            r["sessionSourceMedium"]
                            for r in flat
                            if r["sessionSourceMedium"].split(" / ")[0].removeprefix("www.")
                            in hosts
                        ]
                        if sources:
                            ai = google.ga4_report(
                                *dates,
                                ["sessionSourceMedium"],
                                metrics,
                                extra_filter={
                                    "filter": {
                                        "fieldName": "sessionSourceMedium",
                                        "inListFilter": {"values": sources},
                                    }
                                },
                            )
                            save("ga4-" + label + "-ai-referrals", ai, flatten_ga4(ai))
                        summary["ai_referral_sources_" + label] = sources
                summary["availability"]["ga4_" + label] = "available"
            except ToolkitError as e:
                summary["availability"]["ga4_" + label] = str(e)
                receipt.add("report.ga4." + label, "unavailable", str(e))
    summary["gsc"] = gsc_totals
    if "current" in gsc_totals and "previous" in gsc_totals:
        before, after = gsc_totals["previous"]["impressions"], gsc_totals["current"]["impressions"]
        if before and before - after >= 100 and after <= before * 0.5:
            summary["alerts"].append(
                {"type": "gsc_impression_drop", "previous": before, "current": after}
            )
    if profile.data.get("ga4", {}).get("enabled"):
        try:
            pid = profile.data["ga4"].get("property_id") or profile.state().get("ga4_property_id")
            if not pid:
                raise ToolkitError("No GA4 property is configured.")
            resource = google.request("GET", ADMIN + "v1beta/properties/" + str(pid))
            summary["ga4_time_zone"] = resource.get("timeZone")
            summary["ga4_currency"] = resource.get("currencyCode")
            receipt.export("ga4-property-settings", resource)
        except ToolkitError as e:
            summary["ga4_settings"] = str(e)
    if profile.data.get("search_console", {}).get("enabled"):
        try:
            receipt.export(
                "gsc-sitemaps",
                google.request(
                    "GET", GSC + "sites/" + q(google.site_url()) + "/sitemaps", scope=GSC_READ
                ),
            )
            previous_index = profile.state().get("priority_index_verdicts", {})
            current_index = {}
            for index, url in enumerate(profile.data["website"].get("priority_urls", [])):
                result = google.inspect_url(url)
                receipt.export("gsc-inspection-" + str(index), result)
                verdict = (
                    result.get("inspectionResult", {})
                    .get("indexStatusResult", {})
                    .get("verdict", "UNKNOWN")
                )
                if verdict != "UNKNOWN":
                    current_index[url] = verdict
                if previous_index.get(url) == "PASS" and verdict not in ("PASS", "UNKNOWN"):
                    summary["alerts"].append(
                        {"type": "priority_url_no_longer_pass", "url": url, "verdict": verdict}
                    )
            profile.save_state(priority_index_verdicts={**previous_index, **current_index})
        except ToolkitError as e:
            summary["indexing_status"] = str(e)
    if profile.data.get("bing", {}).get("enabled"):
        try:
            result = bing.report()
            receipt.export("bing-native-api-window", result)
            for name, rows in result.items():
                if isinstance(rows, list):
                    csv_rows(receipt.folder / ("bing-" + name + ".csv"), rows)
            summary["availability"]["bing"] = (
                "available; provider-selected dates, separate from GA4/GSC periods"
            )
        except ToolkitError as e:
            summary["availability"]["bing"] = str(e)
    receipt.export("summary", summary)
    manifest = [
        {
            "file": p.name,
            "bytes": p.stat().st_size,
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
        }
        for p in sorted(receipt.folder.iterdir())
        if p.is_file() and p.name not in ("receipt.json", "manifest.json")
    ]
    private_json(receipt.folder / "manifest.json", {"files": manifest})
    return summary
