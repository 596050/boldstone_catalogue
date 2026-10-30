# Search Analytics Toolkit

Keep this standalone project separate from the adjacent Dropbox application and migration evidence. Generic website behavior belongs in `src/searchkit`; website-specific IDs and public metadata belong in `profiles`.

Before changing a provider adapter, check its current official API reference. Do not invent endpoints or substitute browser cookies/session tokens. Secrets stay in the OS credential store or explicitly chosen private state files, outside the checkout. Do not import global ADC or change gcloud's active account.

Keep offline plans free of network calls and live writes behind explicit CLI apply flags. Reconcile before creating resources, check exact account/domain/stream identity, and preserve durable intent/readback receipts. Do not automatically retry uncertain creates. Keep public-host business metrics separate from property-wide diagnostics and unavailable data separate from zero.

Do not delete account data, delegate owners, accept feature policies, launch ads or publish CMS changes as incidental setup. Document unsupported steps in the capability guide. Do not claim browser collection/consent/ecommerce behavior from API configuration or contract tests.

Required checks for code changes: `.venv/bin/ruff check src tests` and `.venv/bin/pytest`. Provider/security/pagination changes need meaningful contract tests; never use live mutating tests. The optional public audit is read-only and its receipt must say source-only.
