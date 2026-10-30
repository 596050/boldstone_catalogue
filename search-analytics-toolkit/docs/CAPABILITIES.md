# Capability boundaries

| Area | Available here | Separate requirement |
| --- | --- | --- |
| Google Cloud APIs/OAuth | Dedicated Desktop OAuth PKCE flow and scoped provider calls | Owner creates/enables the Cloud project/client and approves the Google grant |
| GA4 | Existing-account property/stream creation or reuse, retention, key events, dimensions, optional lead audiences, Data API reports | Account/TOS creation; GA4/GSC link and unsupported dashboard controls; website event implementation and browser proof |
| Google Search Console | Add property, generate verification token, confirm ownership, submit/read sitemaps, URL Inspection and performance exports | Publish ownership proof; Google's processing/indexing decisions |
| Bing Webmaster | Site registration, proof assets, confirmation, feeds and available search/crawl reports | Owner account/API key, terms, proof publication; Bing processing |
| Yandex Webmaster | Optional site registration, META proof/confirmation and sitemap management | Owner OAuth app/token and publication of proof |
| Other IndexNow participants | Shared changed-URL notification protocol | Public key file/CDN integration; individual portals/analytics require their own accounts |
| DuckDuckGo/other engines | Public sitemap/robots assets and applicable shared discovery paths | No fabricated universal webmaster-registration API; use each engine's actual supported process |
| Meta/Instagram, LinkedIn, X, TikTok, YouTube, Pinterest, Houzz | Profile inventory, `sameAs` JSON-LD, UTM campaign links | Account creation, ownership, app approval and platform-specific publishing/advertising APIs; those adapters are not implemented |
| Google/Apple business profiles | Organization inputs can be retained in website schema | Business identity/location eligibility and approved account/API access; no listing is created automatically |
| Consent/conversions/ecommerce | Deployment checklist, consent-gated loader for new non-native GA4 sites, key-event definitions | Real CMP persistence/withdrawal cleanup, success-confirmed events, real order fields/deduplication/reconciliation |
| AEO | Fixed CSV measurement protocol | Fresh actual platform/model responses, mentions and citations; no invented scores |
| Reporting/alerts | Raw JSON/CSV archives, comparison periods, local alerts and schedule files | Live credentials, first scheduled-run verification, always-on computer or owner-managed cloud scheduling |

No deletion, broad user-permission management, billing, advertising launch, automatic policy acknowledgement or automatic privacy-policy publication is implemented. The toolkit reports unsupported/blocked steps instead of marking them complete.

Audience management uses Google's optional v1alpha API, which can change independently of the beta configuration endpoints.

The public audit reads source/HTTP only. More than one Google configuration does not by itself prove duplicate GA4 collection. A sitemap submission/readback is separate from successful processing. HTTP 200/202 IndexNow acknowledgement is separate from indexing.

Provider schemas were reviewed against these official references on 15 October 2026:

- [GA4 Admin API](https://developers.google.com/analytics/devguides/config/admin/v1)
- [GA4 Data API](https://developers.google.com/analytics/devguides/reporting/data/v1)
- [Search Console sites](https://developers.google.com/webmaster-tools/v1/sites/add), [sitemaps](https://developers.google.com/webmaster-tools/v1/sitemaps/submit), [URL Inspection](https://developers.google.com/webmaster-tools/v1/urlInspection.index/inspect)
- [Site Verification](https://developers.google.com/site-verification/v1/webResource/insert)
- [Bing JSON REST](https://learn.microsoft.com/en-us/bingwebmaster/api-protocols), [site list/proofs](https://learn.microsoft.com/en-us/dotnet/api/microsoft.bing.webmaster.api.interfaces.iwebmasterapi.getusersites?view=bing-webmaster-dotnet), [feeds](https://learn.microsoft.com/en-us/dotnet/api/microsoft.bing.webmaster.api.interfaces.iwebmasterapi.submitfeed?view=bing-webmaster-dotnet)
- [IndexNow](https://www.indexnow.org/documentation)
- [Yandex site management](https://yandex.com/dev/webmaster/doc/en/reference/hosts-add-site), [verification](https://yandex.com/dev/webmaster/doc/en/concepts/verification), [sitemaps](https://yandex.com/dev/webmaster/doc/en/reference/host-user-added-sitemaps-post)
