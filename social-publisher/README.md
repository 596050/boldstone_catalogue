# Boldstone background social publisher

AppleScript entry point and a Python 3.9+ standard-library supervisor for the
**existing normal Google Chrome application**, using its signed-in sessions.
Facebook and Instagram post separately through Meta Business Suite; LinkedIn
posts through Sally Price’s normal composer. Accounts, routes, exact controls
and recovery workflows are editable JSON. There are no browser-profile copies,
social API tokens, browser debugging ports or Python dependencies to install.

The second batch on 18 November 2026 published and independently read back
**five new posts on each of Facebook, Instagram and LinkedIn: 15 in total**.
Each receipt verifies the native permalink, full caption, author and loaded
photograph. Authored purchase links were checked on Facebook and LinkedIn,
and saved Commerce product associations were verified on all ten Meta posts.
The [batch review](../outputs/social-script-20261118-2/review.html) links to every
post; [execution checks](../outputs/social-script-20261118-2/execution-checks.json)
confirm one publish intent per delivery, matching original media hashes and
no observed target-window foregrounding. The completed 17 November and first
18 November batches are retained separately. The earlier 16 November Meta batch
has no Commerce tag verification.

The optional Chrome upload helper is installed in the existing signed-in
profile. It supplies reviewed original files through Chrome's public scripting
API, including detached inputs, without opening a native picker. Account,
document, job and media-hash checks precede every upload. The supervisor then
requires a matching receipt and a loaded image preview.

LinkedIn's current Editor accepts original image files in its visible media
drop area. That route checks the image hash, account and audience, loads the
preview, adds and reads back the exact alt text, then returns to the main
composer before pasting the caption. It needs no native picker or helper reload.
The older 16 November LinkedIn deliveries remain separate retained jobs; a new
batch does not release that backlog automatically.

Facebook and Instagram were checked separately in Meta Business Suite, with
Story sharing, ad-post mode, scheduling and boosting disabled. Meta's Story
confirmation uses **Don't share this post**, preserving account-wide settings.
Photo alt text was entered and read back. Rich-text captions use the site's
paste handler, with every line checked before submission.

Commerce product tags are mandatory for new Meta deliveries. The script checks
the exact product name and price in the catalogue picker, saves the tag, reopens
the photo editor to verify that selection, and checks that the composer shows
one association. The ready guard binds this evidence to the job and photo hash.
After publication, it independently verifies the native caption, author,
photograph and authored links, then checks the persisted tag count in Meta's
published editor for that exact caption and account. Meta disables editing the
photo after publication; receipts identify this persisted-count check and retain
the earlier exact-product readback. They do not claim to test every customer
shopping interface or complete a checkout.

Meta's inactive windows can retain closed confirmation nodes and leave active
menus without a completed visual transition. Story sharing is checked against
the actual switch and the exact **Don't share this post** radio choice. Product
typeahead uses DOM focus events and its option's mouse selection events, while
the Chrome window remains in the background. Instagram permalink recovery uses
the exact published Meta row and its **View Post on Instagram** link, avoiding
stale profile-grid caches.

Meta can replace a Published table row while its search is updating. Native
readback reuses the owned inventory page and matching search value when possible,
then captures the exact full-caption row in one read with bounded retries.
An ambiguous row or changed account still holds the delivery; this never retries
the Publish action.

LinkedIn's current success notification places **View post** outside alert and
status roles. Verification reads that exact native link, accepts the inspected
`/feed/foryou/` canonical feed route, and retries only reads during a publication
redirect. A redirect error never repeats the Post action.

Some LinkedIn post views use different image wrappers. Native readback also
recognises the exact authored alt text on a loaded `media.licdn.com` feedshare
image inside the matched post. This route requires an HTTPS native activity
page and the same caption and author checks. Profile pictures, other image
hosts, unloaded images and multiple post photographs still hold verification.
The native evidence records which image identification method succeeded.

Chrome's native AppleScript URL setter activates its window on this Mac. The
bridge uses an owned page's `location.assign` instead, checks focus, and retains
an exact pending URL for recovery. Runtime publishing does not activate an app,
change the user's active tab, use the system clipboard or open a file picker.
A user switching between other windows is allowed; using the reserved tab holds
that delivery. Stable window and tab IDs avoid index shifts during tab changes.

## Start here

From this directory:

```sh
/usr/bin/osascript Run.applescript doctor --probe
/usr/bin/osascript Run.applescript status
```

The entry point defaults to `doctor`. Its two editable path properties point to
this directory and `/usr/bin/python3`. The launcher does not activate Terminal,
Chrome or Script Editor. The equivalent command is:

```sh
/usr/bin/python3 publisher.py doctor --probe
```

`state/health.json` records the live diagnostic. `state/status.html` and
`state/status.json` show each delivery separately. The 30 verified deliveries
from **14 and 15 November 2026** have been imported as `HISTORICAL_VERIFIED`
duplicate guards. They are historical receipts, not new publications or fresh
live verifications.

## Install the background photo helper once

Prepare the local, reviewable bundle without installing anything:

```sh
/usr/bin/python3 publisher.py helper-build
```

The bundle is `state/chrome-uploader-extension/`. Its manifest and source hashes
are listed in `state/upload-helper-review.json`. It asks for `scripting`,
`alarms` and `storage`, with access to exactly these origins:

- `https://business.facebook.com/*` for both Meta destinations.
- `https://www.linkedin.com/*` for the LinkedIn composer.
- `http://127.0.0.1/*` for the local bridge, fixed to port 8768 by default.

After explicit approval for this new extension access and the one-time Chrome
setup, open `chrome://extensions`, enable Developer mode if necessary, choose
**Load unpacked**, and select the bundle. Use the existing signed-in Chrome
profile. The stable extension ID is recorded in the review file. Return to the
user's own application before testing any upload. Runtime posting does not
activate a window or open a file picker.

The helper cannot enqueue a new file or invoke a publish action. Its authenticated
loopback server exposes only existing requests, exact hashed media, leases and
receipts. HTTP callers cannot supply arbitrary file paths or URLs. Each request
checks its normal background tab, URL, tab owner, current job, selected account
and media hash. A lost file event/result remains uncertain and is never replayed.
An unclaimed request is cancelled when its supervising client closes. A later
preparation can requeue an expired unclaimed request or a retained failure that
proves no file event started. Running or uncertain file events are never replayed.

The local connection token is generated per installation and kept under private
`state/`; it is not a social account credential. Keep the bundle and its config
private. No service is installed. `run` starts and closes its own loopback server
when needed. For a connection check without publishing:

```sh
/usr/bin/python3 publisher.py helper-serve
# In another terminal, or from the helper popup:
/usr/bin/python3 publisher.py helper-status
```

Stop a manually started server with Ctrl-C. `helper-status` reports the last
helper contact; a running server or a heartbeat alone does not prove upload or
publication. Chrome may suspend the helper between its 30-second alarm checks.
The supervisor allows time for it to wake without bringing Chrome forward.
During the one-time setup, start `helper-serve`, open the extension popup and
click **Connect local uploader**. If Chrome requests local companion/loopback
access, approve it as part of that setup. The worker stays idle until this
authenticated connection succeeds. This follows Chrome's
[local connection permission guidance](https://developer.chrome.com/docs/modern-web-guidance/guides/security/local-network-access).

## Reserve tabs once

Chrome’s AppleScript `make new tab` selects the new tab. Opening a new window also
shows it. To preserve the user’s focus, this runner **never creates tabs or
windows**. Set aside four normal Chrome tabs once, in the existing signed-in
browser profile. Open the two Meta composer URLs and the LinkedIn composer URL
from `profiles.json`, plus an `about:blank` tab for shared verification. Return
to your own tab before binding the reserved tabs.
They can live in a separate existing Chrome window. No window needs to be
frontmost for posting.

`doctor --probe` lists social tab IDs and their window IDs. Bind only the tabs
that were deliberately set aside, using the current IDs from that output:

```sh
/usr/bin/python3 publisher.py bind --profile boldstone_facebook --window WINDOW_ID --tab FACEBOOK_TAB_ID
/usr/bin/python3 publisher.py bind --profile boldstone_instagram --window WINDOW_ID --tab INSTAGRAM_TAB_ID
/usr/bin/python3 publisher.py bind --profile sally_linkedin --window WINDOW_ID --tab LINKEDIN_TAB_ID
/usr/bin/python3 publisher.py bind --profile verification --window WINDOW_ID --tab VERIFICATION_TAB_ID
```

Run each `inspect` command to save the current public controls, label text,
file-input attributes and useful selector hints. Adjust the matching workflow
file when the site’s current labels or markup differ:

```sh
/usr/bin/python3 publisher.py inspect --profile boldstone_facebook
/usr/bin/python3 publisher.py inspect --profile boldstone_instagram
/usr/bin/python3 publisher.py inspect --profile sally_linkedin
```

The shared verification tab opens native post links and Published inventories
without leaving an unfinished composer. A browser-wide unsaved-changes dialog
can otherwise interrupt the user even when its source tab is in the background.
After verification, the composer is reused only when its own fields and uploaded
preview read back as empty or absent. A stale form is retained for inspection.

Tab IDs are stable for a browser session. If a tab closes, Chrome exits, the user
navigates a reserved tab elsewhere or starts using it, the runner holds rather
than taking over. Bind a deliberately reserved replacement to resume. After an
uncertain submission, rebinding enables **reconciliation only** for that job.

Chrome must already allow JavaScript from Apple Events and macOS must permit
this runner to send Apple events to Chrome. Both transport capabilities worked
in the development read-only check. The tool does not change these permissions,
read passwords or handle authentication challenges. It does not need macOS
Accessibility access or System Events.

## Prepare and publish a new batch

Use `examples/batch.example.json` as the schema. Each sculpture has independent
target captions and a hash of its reviewed original photograph. A five-sculpture,
three-profile manifest creates 15 independently tracked deliveries. There is no
automatic extra crosspost. The destination must read back as the intended
platform alone. Ad-post mode, Story sharing, scheduling and boost controls are
checked before upload and again before publication when exposed by the composer.

The 17 November Commerce audit found that the 16 November batch omitted shopping
tags. Its native publication receipts prove captions, authors and photographs;
they do not prove Commerce tags. `policy.require_meta_product_tags` is now true:
Facebook and Instagram need an explicit `product_tag` regardless of caption
wording. Website and bio links cannot satisfy that requirement. The builder
carries the native Commerce name and price onto both Meta targets. Preparation
also checks existing queued jobs and refuses adapters without selected-tag and
native-tag checks. Both Meta workflows now include the calibrated selection,
save/reopen and published-association checks described above.

The existing-post desktop editors inspected in this account disabled media
editing; Instagram's own web editor exposed people tags but no product tags.
Commerce Manager showed both channels active and all five matching White items
eligible. No Commerce edits, replacement publications or deletions were applied
by this audit. Evidence and the review are in
`../outputs/commerce-tag-repair-20261117/`.

The existing Boldstone prepared-post format can be converted:

```sh
/usr/bin/python3 build_manifest.py /path/to/NEW/prepared-posts.json --output /path/to/new-batch.json --batch-id component-sculptures-YYYYMMDD
```

The builder refuses rows containing existing publication receipts. Every new
Facebook or Instagram target needs
`native_commerce_title` and `native_commerce_price_text` from the actual Commerce
picker. It does not invent the product’s native name. The generated manifest
defaults to `publish_authorized: false`; set it to true for a batch whose exact
publication is authorized, or pass `--authorize` to the builder when that
authorization is already in place. No per-post confirmation dialog is used.

```sh
/usr/bin/python3 publisher.py validate /path/to/new-batch.json
/usr/bin/python3 publisher.py enqueue /path/to/new-batch.json
/usr/bin/osascript Run.applescript run
```

`run` processes due jobs once. `watch` resumes due work with bounded backoff:

```sh
/usr/bin/osascript Run.applescript watch
```

No scheduler or login item is installed. `Ctrl-C` or process termination retains
the journal. Runtime success requires a verified native permalink, complete
caption, expected author and one loaded post photograph. Caption URLs must
also appear in the native links or have a verified LinkedIn shortlink landing
destination. The original image is SHA-256 checked both locally and in Chrome
before the file input receives it. Alternate text is entered and read back in
the composer; the native receipt does not claim a separate accessibility audit.
Promised product tags require an additional native tag readback.

Meta and LinkedIn change their interface. Rich text or synthetic file-input
events may be rejected by a particular site revision. An input value or a
success toast alone cannot mark the delivery as published. The native post
readback is mandatory.

## Recovery behavior

| Situation | Behavior |
|---|---|
| Slow page or temporarily missing control before submission | Resume the saved preparation step, with exponential backoff; at most four automatic preparation attempts. |
| Known selector changed | Try the next exact, unique locator in the workflow; ambiguous matches hold immediately. |
| Account, destination, caption or original changed | Hold before submission. |
| User is using the reserved tab | Pause; no global keyboard, mouse or clipboard operation is attempted. |
| Crash or timeout during submission | Keep `OUTCOME_UNKNOWN`; search for the native post and verify it. Never automatically click Publish again. |
| Published caption missing, wrong author, absent photo or bad link | Keep the delivery unconfirmed. Other independent jobs retain their own status. |
| Restart during reversible preparation | Resume from its checkpoint in the same owned job. Unclaimed uploads may be prepared again; a running/lost upload lease is reconciliation-only. |
| Helper returns file events but no loaded photo appears | Retain the draft and input receipt; do not publish or upload the file again automatically. |
| SQLite restored to an older backup | Replay the independent intent ledger before considering any queued work. |
| Corrupt or torn intent ledger | Hold; preserve the evidence. Do not erase the ambiguous record. |
| Login, checkpoint, permission prompt or removed browser tab | Hold for that account/tab to be restored; no attempt to bypass it. |

After eight automatic native reconciliation attempts, the record remains
`OUTCOME_UNKNOWN` and is available for explicit reconciliation. The precise
error and its delivery ID appear in `status`:

```sh
/usr/bin/python3 publisher.py reconcile --job DELIVERY_ID --url 'EXACT_NATIVE_POST_URL'
```

This command verifies the actual post and writes a receipt. It cannot submit a
post. If publication never happened after an intent was written, the record
still cannot be reset automatically: that tradeoff prevents a duplicate after
a lost response. Inspect the native platform before deliberately creating any
replacement delivery.

Fix a pre-submission issue, then resume that job:

```sh
/usr/bin/python3 publisher.py resume --job DELIVERY_ID
```

If a profile name, handle, URL or workflow is edited, queued jobs hold on their
old fingerprint. For the same stable destination account, inspect the corrected
reserved composer, then explicitly adopt the change:

```sh
/usr/bin/python3 publisher.py adopt-profile-change --job DELIVERY_ID
```

This also updates an existing reserved binding's workflow fingerprint and
restarts its preparation checks while preserving its owner and retained draft.
Reserve and bind a replacement only if the original tab is unavailable.

Changing the actual account requires a new profile with a new `channel_key`.
After submission, the original profile/workflow configuration must remain
available for reconciliation; do not replace it with a different destination.
Queued manifests retain the profile/workflow snapshots for review.

## Keep the recovery directory

`state/` is private, ignored by Git and contains no copied browser credentials:

| File | Purpose |
|---|---|
| `outbox.sqlite3` | Per-account product/content uniqueness, retries and delivery states. |
| `intent-ledger.jsonl` | Fsynced hash-chained intents written before every possible publish click, plus verified outcomes and imported history. |
| `outbox-backup.sqlite3` | Independently integrity-checked SQLite backup. |
| `bindings.json` | Explicitly reserved window/tab IDs, ownership token and preparation checkpoint. |
| `evidence/` | Ready-state and complete native post readbacks with hashes. |
| `focus-audit.jsonl` | Focus and active-tab IDs sampled before and after DOM mutations. Concurrent user changes pause work; their focus is never restored by the runner. |
| `upload-helper.json`, `chrome-uploader-extension/` | Private helper pairing token, public extension key and generated bundle. |
| `upload-requests/` | Durable upload states, single leases and document receipts. Unknown file events are never requeued. |
| `status.json`, `status.html`, `health.json` | Reviewable status, receipt links and current diagnostics. |

Retain the **whole state directory**, especially the independent ledger and
evidence, with backups. Losing both the database and the ledger cannot be
automatically distinguished from a new installation. Imported history covers
the recorded batches; it is not a complete scan of every manually created post.

Explicit recovery from a good backup:

```sh
/usr/bin/python3 publisher.py recover-db --backup /absolute/path/to/good-outbox.sqlite3
```

The existing database is preserved before restoration. The intent ledger stays
in place and is replayed. Never delete a journal or change a delivery ID as a
way to retry an uncertain submission.

## Add platforms and change account details

Edit `profiles.json` for public account names, handles, stable channel IDs,
approved HTTPS origins, composer/inventory URLs and workflow paths. Keep a
profile’s stable `channel_key` through display-name changes so its duplicate
history stays attached to the same account. Profile metadata is configuration;
this tool does not edit the live account’s bio or other public details.

Add a new profile and a workflow JSON to support another ordinary web composer.
If it needs the photo helper, its new origin also requires a reviewed manifest
change and approval of the additional Chrome site access.
The generic driver supports exact unique CSS/accessible-label locators, waits,
text entry, checkbox selection, direct file inputs, alt text, guarded submission,
native permalink discovery and readback. Every workflow must have account,
complete-caption and photograph guards. A native permalink pattern, author
selector and scoped post-photo selector are also required. Optional recovery
steps can search that account’s native Published inventory. All jobs share the
same durable state machine and duplicate guards.

Do not loosen selectors to a whole page, remove readiness guards, add a native
file-picker click or retry a guarded submission to accommodate a UI change.
Use `inspect` and update the smallest exact locator instead. If a new platform
cannot accept a DOM file upload in a background tab, it needs a separate
background-capable adapter before unattended publishing is supported.

## Verification

```sh
/usr/bin/python3 verify.py
/usr/bin/python3 verify.py --live-probe
```

Node is used only for the DOM-driver tests. Python recovery tests use temporary
databases and a fake remote publisher; DOM tests use an isolated Node fixture.
AppleScripts are compiled into temporary files. The optional live test performs
read-only Apple events against the existing default Chrome, without reserving,
navigating or posting in any tab. Results and source hashes go to
`verification.json`. This separates offline recovery coverage, live transport
checks and the still-required first live publication validation.

Chrome’s tab-creation and isolated-world behavior was checked against its
[window scripting implementation](https://raw.githubusercontent.com/chromium/chromium/main/chrome/browser/ui/cocoa/applescript/window_applescript.mm)
and [tab scripting implementation](https://raw.githubusercontent.com/chromium/chromium/main/chrome/browser/ui/cocoa/applescript/tab_applescript.mm).
Chrome’s treatment of unsaved-page dialogs is documented in its
[dialog manager implementation](https://raw.githubusercontent.com/chromium/chromium/main/components/javascript_dialogs/tab_modal_dialog_manager.cc).
The native file-input mechanism is defined by the
[HTML file input specification](https://html.spec.whatwg.org/multipage/input.html#dom-input-files).

