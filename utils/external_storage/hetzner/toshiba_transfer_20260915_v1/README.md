# Toshiba to Hetzner transfer — 15 September 2026

The user has requested the actual move. Transfer has **not started**: no Storage Box profile/API credential is configured, and the available Hetzner browser session is at its login form. The login tab is retained for the user.

The selected folders exist and the Toshiba identity was verified again. The prior reviewed full-preservation plan remains in `REVIEWED_PLAN.json`; `TRANSFER_STATE.json` separately identifies the raw-source and provenance roots for transfer. No source files were changed or deleted.

`OPEN_FILES.json` records the live worker sparsebundle handles. This research image is separate from the identified raw-source roots and requires source-consistency handling if included in a broader backup.

After account access is available: identify the correct Box/account, perform a small live upload/restore trial, establish the source boundary, transfer, verify stored data and reconcile source coverage. The existing upload/recovery utility is `../storage_box.py`. Retain the Toshiba copies until remote integrity, recovery and source-reference handling are verified.
