# Authentication and access

## Google

This project uses its own Google Desktop OAuth client. It does not copy browser session tokens, GSC Wizard tokens or another project's gcloud/ADC credentials.

Owner prerequisites:

1. Choose an owner-controlled Google Cloud project.
2. Enable `analyticsadmin.googleapis.com`, `analyticsdata.googleapis.com`, `searchconsole.googleapis.com` and `siteverification.googleapis.com`.
3. Configure the OAuth consent app and allowed test users as appropriate. Create a Desktop client and download its JSON outside the repository, for example `~/.config/searchkit/google-desktop-client.json`.
4. Run `auth google --mode setup --client-file ...` and complete Google's consent screen. `--no-browser` displays the authorization URL without opening it; the loopback callback still has to reach this computer.
5. Run `inventory`. Possessing a token is separate from having access to the intended Analytics account and Search Console property.

| Mode | Requested rights |
| --- | --- |
| report | `openid`, `email`, `analytics.readonly`, `webmasters.readonly` |
| setup | `openid`, `email`, `analytics.readonly`, `analytics.edit`, `webmasters`, `siteverification.verify_only` |

Analytics edit authorization can affect the Analytics resources the signed-in user can edit; it is not a Google property-specific OAuth scope. The adapter verifies the configured account, property and public web-stream identity before settings changes. `google.expected_email` pins the expected verified account. Analytics user-management scopes are not requested. Google ownership confirmation uses only the authenticated user; the tool does not delegate owners.

The flow uses PKCE S256, a random state, a `127.0.0.1` callback bound to an ephemeral port, and verified Google user-info identity. Callback URLs and authorization codes are not logged. Offline refresh uses the saved refresh token without requesting broader scopes. Refresh grants in a testing OAuth app can have limited lifetimes; review Google's publishing/grant rules before relying on unattended reporting.

A local gcloud Cloud Platform login does not imply Analytics permissions. This was the source of the earlier `ACCESS_TOKEN_SCOPE_INSUFFICIENT` result. The CLI's explicit setup grant addresses that scope requirement once the owner supplies the Desktop client and completes consent.

## Credential storage

Default: OS Keychain via Python keyring, service `SearchAnalyticsToolkit`, account `<profile-id>:<credential-name>`. A saved value is read back before success is reported. An unavailable Keychain is an error, not permission to store plaintext elsewhere.

Explicit alternative: `--credential-store file`. Credentials live in `~/.local/state/searchkit/<profile-id>/credentials/`, outside the checkout, with private directories and `0600` files. Symlinks and files accessible by other users are rejected. `SEARCHKIT_STATE_DIR` can select a private local state location. Set it consistently for scheduled commands as well.

Secrets are entered with hidden terminal input using `secret`, not command-line arguments. The public profile contains IDs, domains and desired settings only. Generated ownership proofs are intentionally deployable assets; restrict access to the generated folder until you publish the chosen proof. Keep client JSON, credentials and reports out of public version control.

## Bing

The implemented Bing adapter uses the supported JSON REST API and an owner-generated API key. Sign up/accept API terms in Bing Webmaster Tools, verify at least the necessary account/site prerequisites and obtain the key in API Access. Store it with `secret bing_api_key`. A Bing API key is account-wide; the tool sends only the configured site URL for mutations.

Bing requires the API key as a query argument for this authentication mode. The client never prints authenticated URLs; errors, stdout and receipts redact the key. Bing OAuth app registration/refresh is not implemented by this version. Legacy SOAP/POX are not used.

## Cloudflare

Optional: a narrowly scoped API token with Zone Read and DNS Edit for the intended zone. Store it with `secret cloudflare_api_token` and set `cloudflare.zone_id`. The code reads the zone and verifies `zone.name == website.domain` before adding the exact prepared Google TXT value. It never deletes or overwrites DNS records. DNS visibility/Google confirmation still require subsequent verification.

## Yandex

Optional owner-issued OAuth token. Follow Yandex Webmaster's app registration instructions, requesting `webmaster:hostinfo` and `webmaster:verify` as needed. Store with `secret yandex_oauth_token`. The adapter sends the token through `Authorization: OAuth ...`, discovers the token owner's user ID, and targets the exact configured site URL. This version consumes the issued token; Yandex OAuth app registration/refresh remains an owner step. Pending ownership verification is reported as pending.

## Official references

- [Analytics Admin API](https://developers.google.com/analytics/devguides/config/admin/v1)
- [Google installed-app OAuth](https://developers.google.com/identity/protocols/oauth2/native-app)
- [Search Console authorization](https://developers.google.com/webmaster-tools/v1/how-tos/authorizing)
- [Google Site Verification tokens](https://developers.google.com/site-verification/v1/webResource/getToken)
- [Bing API access](https://learn.microsoft.com/en-us/bingwebmaster/getting-access)
- [Bing JSON REST protocol](https://learn.microsoft.com/en-us/bingwebmaster/api-protocols)
- [Yandex authorization](https://yandex.com/dev/webmaster/doc/ru/tasks/how-to-get-oauth)
