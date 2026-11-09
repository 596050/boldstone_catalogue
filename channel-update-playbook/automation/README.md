# Meta posting automation

`meta_posting.py` supervises short AppleScript operations. Every AppleScript call has
an internal five-second limit and an external nine-second wall-clock timeout. It
does not restart Chrome, alter permissions or interact with protected macOS prompts.

Run `python3 meta_posting.py preflight` before starting. A blocked preflight is a
stop condition. A person must clear any permission prompt and decide whether to
grant the runner the requested macOS access. These scripts do not grant it.

The 8 November queue contains five reviewed photographs and captions at
`outputs/instagram-marketplace-next-channels-20261107-1324/instagram-five-posts.json`.
None was published during preparation of this automation.
That preparation manifest is historical: all five were subsequently published
through the native browser on 8 November. Reconcile against
`outputs/product-social-approval-20261108/instagram-publication-receipts.json`;
do not replay the original preparation queue.

The reusable operations are `inspect`, `click`, `choose-file`, `caption`, `publish`
and `reconcile`. Pass the exact currently observed Meta tab URL. The destination
is restricted to business 2380586078685156 and Page 103781478537396. Each media
file must still match its recorded SHA-256.

For each post:

1. Search all published content for the exact sculpture/caption. Record a fresh
   `duplicate_search_verified_utc` and `duplicate_search_result: "NO_MATCH"`.
2. Open the Instagram composer and verify `boldstonesculpture` is selected.
   Use `inspect` to obtain the currently visible controls. `click --name` accepts
   an exact, unique visible control name. It cannot click Publish.
3. Click the observed upload control, then run `choose-file` for the manifest
   item. Verify the photo is the reviewed original. Run `caption` and read it back.
4. Select the exact existing Meta Commerce product. Inspect its selected-tag
   summary and uploaded-media preview. Save a per-item profile with
   `catalogue_id`, `sku`, `tag_selector`, `tag_text`, `media_selector` and the
   duplicate-search fields. Selectors must come from current visible DOM, not
   guesses. The caption alone is never evidence of a selected product tag.
5. `publish` requires that profile and a persistent `--journal`. It checks the
   exact caption, one uploaded preview, selected product tag, correct business
   and enabled Publish control. It saves a durable intent before clicking once.
6. Inspect the actual native post. `reconcile --permalink` requires its complete
   caption and Instagram permalink to be visible in Meta. Only then is it
   recorded as published and eligible for a master-catalogue post URL.

A timeout after Publish means **uncertain**, not failed. Never delete the journal
or click Publish again to recover. Inspect Meta content and reconcile first.
Concurrent runs cannot publish the same reviewed item. Script execution alone is
not evidence that a product tag or post is live.

This source checkout does not contain `meta_browser.applescript` or
`meta_choose_file.applescript`, and no retained copy was found in the workspace.
The standalone runner reports the exact missing helper and stops before calling
it. Restore the reviewed sources separately; the offline tests do not supply or
certify replacement publishing automation. Existing account and macOS permission
checks still apply.

Local artifact checks run without browser or account access:

```sh
python -m unittest discover -s channel-update-playbook/automation -p 'test_*.py'
node channel-update-playbook/automation/test_pinterest_tag.cjs
```

The tracking builder validates the complete 176-product mapping even under
optimized Python, refuses any existing prepared artifact, safely embeds JSON
inside HTML, and removes new partial files if a write fails. Its receipt describes
only the prepared files, with no live website changes. The workbook preflight
follows actual worksheet relationships (including custom filenames and strict
SpreadsheetML), hashes the inspected snapshot and holds incomplete packages.
An optional report cannot overwrite its source workbook or a hardlink to it.

Verification on 8 November: seven supervisor/journal tests pass. Both AppleScripts
compile. The actual Mac preflight stops on the protected permission prompt and
missing Accessibility permission. A successful live end-to-end posting test is
still required; this is not yet an unattended batch uploader.

Live browser verification later on 8 November found that macOS Accessibility was
still unavailable to the standalone runner, but the existing Computer Use browser
controls worked. Do not require that runner to use those existing controls.

Meta's rich-text caption editor did not persist text entered through native AX
`setValue`, even though the entire caption appeared in its accessibility value.
The first post's photo was published without its caption. It was repaired on the
same native post ID, 18425817283154355, by focusing the caption editor and using
normal keyboard paste, then publishing the edit and reading the complete saved
caption back from its native Feed preview. Never treat an editor value alone as
proof of a saved caption. Native plain-text search fields did accept `setValue`.

For image pickers, open Go to Folder, wait for its `PathTextField`, set the exact
path, verify it, then press Return and verify the selected filename before Open.
Pasting immediately after opening the Go to Folder sheet raced with its focus
change and selected a previously used path. The identity checks prevented upload.

The exact native Commerce tag name may omit the catalogue's word `Finish`, such
as `Frozen Fish Relief - Verdigris`. Verify its finish and current price against
the component and record the actual native name separately. Do not select the
White or Terracotta variant, or change a live product title as part of tagging.
### 8 November native publication readback

The five queued Instagram posts and ten LinkedIn posts are now published; exact
native receipts are in `outputs/product-social-approval-20261108/`. This does not
validate the standalone AppleScript runner or grant its missing macOS access.

Meta navigation is asynchronous. After Publish, retain the exclusive intent file
and reconcile the native Published inventory before any retry. A completion
dialog and a stale unsaved-composer warning can coexist after a successful
submission. Resolve only the agent-created stale composer, reload the inventory
and find the exact caption opening and native post ID. Do not click Publish a
second time because an immediate snapshot still shows the composer or because
the insights page has not finished loading.

For full caption readback, scope to the native Feed preview and join its text
nodes before normalising whitespace. Raw accessibility indices can appear
between wrapped lines. Wait for the actual preview heading and text; an unloaded
insights page is not evidence that the caption was lost. Store the canonical
Instagram URL after decoding the visible View Post on Instagram link.
