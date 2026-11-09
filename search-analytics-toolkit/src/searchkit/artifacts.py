"""Generate local deployment assets. Never publishes or overwrites website code."""

from __future__ import annotations

import csv
import html
import json
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from xml.sax.saxutils import escape

from .core import ToolkitError, csv_safe, private_json


def campaign_url(url, source, campaign, medium="organic_social"):
    p = urlsplit(url)
    args = dict(parse_qsl(p.query, keep_blank_values=True))
    args.update(utm_source=source.lower(), utm_medium=medium.lower(), utm_campaign=campaign.lower())
    return urlunsplit(p._replace(query=urlencode(args)))


def generate(profile, output):
    root = Path(output) / profile.id
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    org = profile.data["organization"]
    schema = {
        "@context": "https://schema.org",
        "@type": org.get("type", "Organization"),
        "@id": profile.url + "#organization",
        "name": org["name"],
        "url": profile.url,
        "sameAs": list(profile.data.get("social_profiles", {}).values()),
    }
    if org.get("logo_url"):
        schema["logo"] = org["logo_url"]
    if org.get("description"):
        schema["description"] = org["description"]
    private_json(root / "organization.jsonld", schema)
    encoded = json.dumps(schema, indent=2, ensure_ascii=False).replace("<", "\\u003c")
    (root / "organization-schema.html").write_text(
        '<script type="application/ld+json">\n' + encoded + "\n</script>\n"
    )
    (root / "robots-sitemap-lines.txt").write_text(
        "\n".join("Sitemap: " + x for x in profile.data["website"].get("sitemaps", [])) + "\n"
    )
    with (root / "social-campaign-links.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["platform", "profile_url", "website_campaign_link"])
        for platform, url in profile.data.get("social_profiles", {}).items():
            writer.writerow(
                [csv_safe(platform), url, campaign_url(profile.url, platform, "profile_link")]
            )
    state = profile.state()
    measurement = state.get("ga4_measurement_id") or profile.data.get("ga4", {}).get(
        "measurement_id"
    )
    native = profile.data.get("ga4", {}).get("native_installation")
    if native or not measurement:
        (root / "ga4-consent-loader.html").unlink(missing_ok=True)
    if not native:
        (root / "analytics-installation.txt").unlink(missing_ok=True)
    if native:
        (root / "analytics-installation.txt").write_text(
            "Use the CMS's existing native GA4 integration. Do not add a second Google configuration.\n"
            + "Expected measurement ID: "
            + str(measurement or "run GA4 setup/inventory")
            + "\n"
            + "Test actual requests and consent in a clean browser; API configuration is not collection proof.\n"
        )
    elif measurement:
        if not __import__("re").fullmatch(r"G-[A-Z0-9]+", measurement):
            raise ToolkitError("Invalid GA4 measurement ID.")
        snippet = """<!-- Connect websiteAnalyticsConsent to your actual cookie manager. -->
<script>
window.dataLayer = window.dataLayer || [];
window.gtag = window.gtag || function(){dataLayer.push(arguments);};
gtag('consent','default',{analytics_storage:'denied',ad_storage:'denied',ad_user_data:'denied',ad_personalization:'denied'});
(function(){
  var loaded=false;
  window.websiteAnalyticsConsent=function(choice){
    var analytics=choice.analytics===true, advertising=choice.advertising===true;
    gtag('consent','update',{analytics_storage:analytics?'granted':'denied',ad_storage:advertising?'granted':'denied',ad_user_data:advertising?'granted':'denied',ad_personalization:advertising?'granted':'denied'});
    if(analytics && !loaded){
      loaded=true;
      var script=document.createElement('script');script.async=true;
      script.src='https://www.googletagmanager.com/gtag/js?id=MEASUREMENT';
      document.head.appendChild(script);gtag('js',new Date());gtag('config','MEASUREMENT');
    }
  };
})();
</script>
""".replace("MEASUREMENT", measurement)
        (root / "ga4-consent-loader.html").write_text(snippet)
    v = state.get("google_verification")
    if v:
        private_json(root / "google-verification.json", v)
        if v["verificationMethod"] == "META":
            # getToken(META) returns the complete meta element, not just its content.
            (root / "google-verification-meta.html").write_text(v["token"] + "\n")
        else:
            (root / "google-verification-dns.txt").write_text(
                "Type: TXT\nName: " + v["site"]["identifier"] + "\nValue: " + v["token"] + "\n"
            )
    b = state.get("bing_verification")
    if b:
        code = b["AuthenticationCode"]
        (root / "bing-verification-meta.html").write_text(
            '<meta name="msvalidate.01" content="' + html.escape(code, quote=True) + '" />\n'
        )
        public = root / "public"
        public.mkdir(exist_ok=True)
        (public / "BingSiteAuth.xml").write_text(
            '<?xml version="1.0"?>\n<users><user>' + escape(code) + "</user></users>\n"
        )
    if state.get("indexnow_key"):
        public = root / "public"
        public.mkdir(exist_ok=True)
        key = state["indexnow_key"]
        (public / (key + ".txt")).write_text(key + "\n")
    y = state.get("yandex_verification")
    if y:
        code = str(y["verification_uin"])
        (root / "yandex-verification-meta.html").write_text(
            '<meta name="yandex-verification" content="' + html.escape(code, quote=True) + '" />\n'
        )
    prompts = profile.data.get("aeo", {}).get("prompts", [])
    with (root / "aeo-baseline-template.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "prompt_id",
                "prompt",
                "platform",
                "model",
                "search_mode",
                "timestamp_utc",
                "brand_mentioned",
                "site_cited",
                "cited_urls",
                "raw_response_file",
                "status",
            ]
        )
        for prompt in prompts:
            for platform in profile.data.get("aeo", {}).get(
                "platforms", ["ChatGPT", "Gemini", "Perplexity"]
            ):
                writer.writerow(
                    [
                        csv_safe(prompt["id"]),
                        csv_safe(prompt["text"]),
                        csv_safe(platform),
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "unmeasured",
                    ]
                )
    checklist = """# Deployment and validation

1. Review the generated organization schema against existing CMS/schema output; merge one authoritative entity and preserve the `@id`.
2. Merge Sitemap lines into the existing robots.txt. Do not replace its crawler/access rules.
3. Publish the requested ownership proof (Google TXT/META; Bing XML or META). Then run verification confirm and inspect the saved receipt.
4. Publish the IndexNow text file at the canonical root and run indexnow submit only for changed URLs. Receipt acceptance is separate from indexing.
5. Use the native CMS GA4 integration when configured. Otherwise connect the generated loader to the real cookie manager before deploying it.
6. Before optional consent, after each choice, and after withdrawal, inspect actual cookies and requests. The sample loader controls loading/consent signals; the CMP must persist preferences and remove optional cookies on withdrawal.
7. Implement real success-confirmed enquiry/purchase events in the website/backend. Creating a GA4 key event does not implement it. Test success, failure, validation errors and duplicate prevention. Never include email, phone or message text in event parameters.
8. Reconcile purchases with actual orders and separate controlled test traffic. Inspect internal/developer exclusions in Testing before activating them.
9. Social account creation, verified ownership, business-profile approval and platform-specific API app grants are separate owner steps. Generated profile links and schema do not create or verify accounts.
10. GA4/Search Console linking, Google Ads linking, custom insights, Google signals/UPD policy acknowledgements and any Measurement Protocol secret require their own supported setup/review; this project does not acknowledge policies or create persistent backend secrets automatically.
11. Capture fresh AI-platform responses for the AEO CSV protocol. No model response or citation is fabricated by this tool.
"""
    (root / "DEPLOYMENT.md").write_text(checklist)
    return {
        "folder": str(root.resolve()),
        "files": sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()),
        "published": False,
    }
