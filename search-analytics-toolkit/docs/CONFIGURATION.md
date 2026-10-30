# Website configuration

Use `init` to create a profile, then edit the JSON. `profiles/example.json` is a generic starting point. It intentionally has no guessed account IDs or credentials. `profiles/boldstone.json` contains the existing Boldstone target information.

| Input | Purpose |
| --- | --- |
| `id` | Unique lowercase profile slug; determines local state/credential namespace; keep stable for this site |
| `website.url` | Canonical HTTPS origin, including trailing slash; public GA4 hostname filter derives from this |
| `website.domain` | Exact DNS domain used for Domain-property ownership; for `www.example.com`, normally `example.com` |
| `website.sitemaps` | Same-host absolute sitemap/index URLs maintained by the website |
| `website.priority_urls` | Canonical URLs for repeatable URL Inspection checks |
| `organization.name`, `.type` | Real organization/person name and schema type; `Organization`, `LocalBusiness` or `Person` |
| `social_profiles` | Map of platform name to actual public profile URL; generates `sameAs` and campaign links, not accounts |
| `google.expected_email` | Optional verified-account pin; recommended |
| `ga4.account_id` | Existing Google Analytics account numeric ID; not the Google Cloud project ID |
| `ga4.property_id`, `.stream_id` | Existing target IDs, or null for a new site's setup |
| `ga4.create_property` | Explicit permission for this CLI to create a property when no target is pinned or remembered |
| `ga4.display_name` | Property name; a same-named existing property blocks automatic creation until you pin its ID |
| `ga4.time_zone`, `.currency` | Intended IANA timezone and ISO 4217 currency; existing differences block changes unless explicitly allowed |
| `ga4.update_property_settings` | Opt-in to changing an existing timezone/currency; default false to preserve reporting comparability |
| `ga4.retention_months` | Standard-property retention: 2 or 14 months; external exports are separate |
| `ga4.native_installation` | True when the CMS already installs GA4; suppresses generation of a second tag loader |
| `ga4.key_events` | Explicit event names and ONCE_PER_EVENT/ONCE_PER_SESSION counting definitions; no assumed monetary values |
| `ga4.custom_dimensions` | EVENT-scope parameter names, display names and descriptions; registration does not backfill historical reports |
| `ga4.audiences` | Optional `{name,event,days}` public-host audience definitions; immutable filter differences block reuse |
| `ga4.allow_shared_property` | Explicit opt-in to property-level configuration when other websites/streams share the property; retention and key-event definitions affect the whole property |
| `search_console.site_url` | Exact `sc-domain:example.com` or canonical URL-prefix property |
| `bing.enabled`, `yandex.enabled` | Enable a provider; credentials remain outside this file |
| `cloudflare.zone_id` | Optional exact zone ID for Google TXT deployment; the zone/domain must match |
| `network.dns_fallback` | Optional resolver IP for process-local fallback when normal DNS fails; TLS remains verified |
| `reporting.ai_referral_hosts` | Optional exact source hostname allowlist for identifiable AI referrals; normal Google/Bing search is not classified as AI |
| `aeo.platforms`, `.prompts` | Fixed platform/prompt IDs and exact texts for a comparable manual baseline template |

The runtime checks URLs, property/stream numeric IDs, timezone, dimensions, counting methods and cross-host targets before requests. Each profile is locked during setup/reporting. Created property IDs are saved immediately so a later failure does not silently create another property. Unknown write outcomes are retained in the receipt; inspect live inventory before retrying.

Avoid multiple definitions with the same event name, parameter name or audience name. A newsletter subscription should not be named `generate_lead` unless it truly meets the business's enquiry definition. Changing a GA4 definition alone does not implement website tracking.

Add new provider adapters behind the existing HTTP/Vault/Receipt interfaces. Implement exact site guards, read-before-write behavior and verified readback. Document unsupported actions and test uncertain-write recovery before claiming a provider is supported.
