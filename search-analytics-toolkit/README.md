# Search Analytics Toolkit

A reusable local project for setting up a website's search and analytics accounts through supported APIs. Each website has its own JSON profile, credential namespace, state and dated evidence archive. The supplied Boldstone profile targets the existing property; it does not create a replacement.

The CLI and virtual environment are installed in this directory. Start here:

```sh
cd /Users/tprice/Documents/boldstone/search-analytics-toolkit
bin/searchctl doctor
bin/searchctl plan
bin/searchctl capabilities
```

`plan` and `setup` without `--apply` are offline previews. API mutations require `--apply`. Successful API responses and independent readbacks are recorded separately. Public-source checks, account configuration, event collection and business outcomes remain separate evidence.

## What it implements

| Provider | Implemented |
| --- | --- |
| Google authentication | Desktop OAuth with PKCE, loopback callback, state checking, expected-account checking, offline refresh; separate reporting/setup scopes |
| Google Analytics 4 | Reuse or explicitly create a property in an existing account; web stream; retention; key-event counting; event dimensions; optional public-host lead audience; reporting |
| Search Console | Property registration; DNS/META verification tokens; ownership confirmation; sitemap submission/readback; URL inspection; paginated performance exports |
| Bing Webmaster | JSON REST site registration; XML/META ownership assets; verification; sitemap feeds; search/crawl exports |
| Yandex Webmaster | Optional site registration, META ownership proof/confirmation and sitemap submission/readback with owner-issued OAuth token |
| IndexNow | Persistent proof-file generation, public proof validation, changed-URL notifications to the shared participating-engine endpoint |
| Cloudflare | Optional append-only Google verification TXT deployment, with exact zone/domain checks; does not change existing DNS records |
| Website/social presence | Organization `sameAs` structured data, social campaign links, robots sitemap lines, reviewed deployment assets and an AEO recording template |
| Reporting | Dated raw JSON/CSV, comparison periods, public-host GA4 scope, identifiable AI referrals, indexing and collection-access failures, local launchd/cron schedule generation |

See [capabilities and boundaries](docs/CAPABILITIES.md) and [authentication](docs/AUTHENTICATION.md). Social account signup/API approval, website publication, policy acknowledgements and browser consent/conversion tests remain their own steps. The project does not create social accounts or launch advertisements.

## One-time credentials

1. Create an owner-controlled Google Cloud project, enable Analytics Admin, Analytics Data, Search Console and Site Verification APIs, and download a **Desktop OAuth client** JSON. Keep it outside this checkout. Add your Google account as a test user if the OAuth app requires that.
2. Start the local grant, then approve Google's consent screen yourself:

```sh
bin/searchctl auth google --mode setup \
  --client-file "$HOME/.config/searchkit/google-desktop-client.json"
bin/searchctl inventory --providers google
```

Setup requests `analytics.edit`, `analytics.readonly`, `webmasters`, `siteverification.verify_only`, and identity scopes. Reporting-only grants are available with `--mode report`. The setup grant can configure Google Analytics resources accessible to the account; the code restricts operations to the profile's target IDs and hostname. It does not request Analytics user-management access.

3. Obtain your Bing Webmaster API key from the owner account and store it with hidden input:

```sh
bin/searchctl secret bing_api_key
bin/searchctl inventory --providers bing
```

The default credential backend is the OS Keychain. If it is unavailable, choose `--credential-store file` explicitly on each command. Private files then live under `~/.local/state/searchkit/<profile>/credentials/` with mode `0600`. There is no silent fallback and no global gcloud/ADC overwrite.

```sh
bin/searchctl --credential-store file auth google --mode setup \
  --client-file "$HOME/.config/searchkit/google-desktop-client.json"
```

The project currently has **no live provider credentials**. Existing browser sessions and connected GSC Wizard tokens are not imported. A Cloud Platform gcloud token without Analytics scopes is insufficient.

On this computer, the final Keychain read check returned macOS error `-50`. The explicit private-file backend passed its tests and is available now. For this local installation, use it consistently, including on scheduled commands:

```sh
bin/searchctl --credential-store file doctor
bin/searchctl --credential-store file auth google --mode setup \
  --client-file "$HOME/.config/searchkit/google-desktop-client.json"
bin/searchctl --credential-store file secret bing_api_key
bin/searchctl --credential-store file inventory
bin/searchctl --credential-store file setup --apply
```

These commands require the owner-supplied client and credentials. No credentials were saved during installation. The default remains Keychain for other installations; the toolkit never falls back automatically.

## Use Boldstone's existing configuration

`profiles/boldstone.json` includes account `234700920`, property `546648922`, web stream `15303377002`, `G-DYE31M1PWM`, currency GBP and fixed UTC timezone `Etc/GMT`. It preserves the native Squarespace installation, existing audiences and timezone/currency. It requests the three enquiry dimensions and the existing event-counting definitions.

```sh
bin/searchctl plan --providers ga4,gsc,bing
# After the dedicated grants and inventory checks:
bin/searchctl setup --providers ga4,gsc,bing --apply
bin/searchctl generate
```

This reconciles existing resources rather than deleting/rebuilding them. No live provisioning was executed during project installation. Existing tested Boldstone tracking code is not replaced by the generated assets.

## Set up another website

```sh
bin/searchctl init --id example --name "Example Company" \
  --url https://example.com/ --output profiles/my-site.json
bin/searchctl --profile profiles/my-site.json plan
```

Fill in the required inputs in [the configuration guide](docs/CONFIGURATION.md). Set the Analytics account ID, either pin an existing property/stream or explicitly allow a new property, and provide the intended timezone, currency, sitemaps, genuine conversion events and public social-profile URLs. Credentials are stored separately for each profile ID. Reusing a profile ID for another site is rejected.

Then authenticate and run inventory with that profile:

```sh
bin/searchctl --profile profiles/my-site.json auth google --mode setup \
  --client-file "$HOME/.config/searchkit/google-desktop-client.json"
bin/searchctl --profile profiles/my-site.json secret bing_api_key
bin/searchctl --profile profiles/my-site.json inventory
```

### Ownership verification

```sh
bin/searchctl --profile profiles/my-site.json verification prepare google
bin/searchctl --profile profiles/my-site.json verification prepare bing --apply
```

Generated proof instructions appear in `generated/<profile>/`. Publish Google's DNS TXT or META proof and Bing's XML or META proof. The project can publish the Google TXT with a zone-scoped Cloudflare token:

```sh
bin/searchctl --profile profiles/my-site.json secret cloudflare_api_token
# Set cloudflare.zone_id in the profile; the zone name must match website.domain.
bin/searchctl --profile profiles/my-site.json verification deploy-google-dns google --apply
bin/searchctl --profile profiles/my-site.json verification confirm google --apply
bin/searchctl --profile profiles/my-site.json verification confirm bing --apply
bin/searchctl --profile profiles/my-site.json setup --apply
```

DNS propagation, sitemap processing and indexing can remain pending after submission. Their status is recorded without pretending the operation completed.

### Yandex and other participating search engines

Yandex is optional. Add `"yandex": {"enabled": true}` to the profile, obtain an owner-issued OAuth token with the Webmaster rights described in the authentication guide, and run:

```sh
bin/searchctl --profile profiles/my-site.json secret yandex_oauth_token
bin/searchctl --profile profiles/my-site.json inventory --providers yandex
bin/searchctl --profile profiles/my-site.json verification prepare yandex --apply
# Publish generated/yoursite/yandex-verification-meta.html in the homepage head.
bin/searchctl --profile profiles/my-site.json verification confirm yandex --apply
bin/searchctl --profile profiles/my-site.json setup --providers yandex --apply
```

For IndexNow, generate and publish the text key file at the canonical site root. This requires suitable hosting/CDN access; Squarespace does not provide arbitrary root-file hosting through its normal page editor. Existing Cloudflare Crawler Hints can be a separate deployment path and must be checked in that account.

```sh
bin/searchctl --profile profiles/my-site.json indexnow prepare
# Publish generated/<profile>/public/<key>.txt at https://example.com/<key>.txt.
# changed-urls.txt contains one changed canonical URL per line.
bin/searchctl --profile profiles/my-site.json indexnow submit \
  --urls-file changed-urls.txt --apply
```

Google is not an IndexNow destination. No obsolete Google/Bing sitemap-ping endpoints are used. Notification receipt does not prove indexing.

## Repeatable reporting

```sh
bin/searchctl report --period weekly
bin/searchctl report --period monthly
bin/searchctl report --start 2026-09-15 --end 2026-10-12 \
  --comparison-start 2026-08-18 --comparison-end 2026-09-14
bin/searchctl schedule --period weekly
bin/searchctl schedule --period monthly
```

Reports are retained under `reports/<profile>/<timestamp>-report/`. Source-specific dates, filters, raw metadata, pagination limits and retrieval failures are preserved. Default periods use a three-day buffer; explicit dates can include provisional data. GSC uses Pacific dates; GA4 uses the property's verified reporting timezone. Bing's API-selected date window is archived separately. Thresholding/sampling flags remain in raw GA4 responses. Missing data is not zero.

Weekly mode chooses the latest complete Monday–Sunday week whose Sunday is within the buffered cutoff. Monthly mode chooses the latest fully completed calendar month within that cutoff. CSV exports prefix formula-like text for spreadsheet safety; raw JSON retains original values.

Weekly search-impression alerts require both a 50% fall and at least 100 fewer impressions. Priority URL alerts compare saved URL Inspection verdicts. These are local report alerts, not emails. The CLI does not assume that registered key events have validated collection or business outcomes.

`schedule` writes launchd and cron definitions without installing them. Use the returned `launchctl bootstrap` command to enable a macOS schedule. Schedules use the computer's timezone and run when that computer/user session is available; they are not a cloud service. Run a report manually and check the first actual scheduled receipt before treating automation as verified.

## Development and validation

Python 3.11+ on macOS/Linux. The installed local environment was tested with Python 3.14. The API client uses the standard library; OS credential storage is an optional `keychain` extra.

```sh
uv sync --extra keychain --extra dev
.venv/bin/pytest
.venv/bin/ruff check src tests
```

Use `uv sync --offline --extra keychain --extra dev` when dependencies are already cached. The Boldstone profile enables process-local DNS fallback to `1.1.1.1` for this environment's broken normal lookup. It preserves TLS hostname/certificate checks and does not change system network settings. Disable it or choose your resolver for another environment.

Tests exercise provider contracts with fake transports, state/OAuth checks, idempotency, pagination, wrong-target rejection and secret redaction. They do not establish live provider permissions. The public `audit` command was also run against Boldstone; it checks HTTP/source only and does not test browser consent or collection.
