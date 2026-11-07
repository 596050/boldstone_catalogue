**We offer three levels of service:**

- **Made to Order:** Choose from our existing collections, handcrafted in your preferred size and finish where available.
- **Customised Designs:** Adapt an existing sculpture with bespoke colours, dimensions, materials or finishes.
- **Completely Bespoke:** Commission an original design created specifically for your home, garden, business or interior design project.

We work with private collectors, homeowners, interior designers, architects, garden designers and commercial clients in the UK and internationally.











Most of it is now done, but Google approval, Marketplace and complete conversion tracking remain unfinished.

| Request | Verified status |
|---|---|
| Retail names | Separate catalogue names added and used across all 176 public listings. |
| Product descriptions | Design and inspiration copy added. Underlying material names and Royal Mail details removed; outdoor suitability and keyhole/French-cleat wording included. |
| Images | All selected listing and in situ photographs are now in the main carousel. The separate “In a setting” sections are removed. |
| Homepage | All 176 listings appear with their current primary photographs. |
| Dropbox catalogue | Updated and verified on 31 October at 17:49, covering all 181 component records, image links, descriptions and current prices. Labour is zero; manufacturing excludes labour. |
| Facebook/Instagram | All 176 wall sculptures are in the catalogue. I published a dedicated Wall Sculptures shop collection and checked both platform previews. |
| Google Merchant Center | Correct account connected; 176 updated records matched without feed errors. Product approval remains pending. |
| Facebook Marketplace | Not published. The inspected integrations do not automatically publish the shop catalogue to Marketplace. |
| Analytics | GA4, Meta pixel and consent handling are configured. Recent Meta product views exist, but cart, purchase and attribution verification is not complete. Checkout rendered blank in this browser during the latest test. |

Open the updated Dropbox catalogue (https://www.dropbox.com/preview/BOLDSTONE%20MASTER/Products/01%20Wall%20Sculptures/_Documents_Catalogue/catalogue_wall_sculptures.xlsx).

Photography exception: 27 listings have fewer than two selected in situ photographs—12 have none and 15 have one. All currently selected photographs have been included.

Squarespace’s main feeds sync automatically. The supplementary Google/Meta uploads I added need refreshing after future relevant catalogue changes.

The platforms serve different purposes:

| Platform | What it does |
|---|---|
| Meta Commerce Manager | The management system for your product catalogue, collections and shop settings. |
| Facebook Shop / Instagram Shopping | Customer-facing browsing and product tagging using that shared catalogue. Your new collection provides one place to browse the wall sculptures. Meta guidance (https://www.facebookblueprint.com/student/activity/489413-use-shops-to-help-increase-your-sales) |
| Facebook Marketplace | Separate buying-and-selling listings. Publishing a Shop collection does not create Marketplace listings. Meta’s new bulk-selling app launched for US users; that does not establish availability for your UK account. Meta announcement (https://about.fb.com/news/2026/07/introducing-seller-app-facebook-marketplace/) |
| Threads | Product posts and links to your catalogue. Threads supports profile links and link-performance insights; I have not connected a native product shop there. Threads features (https://about.fb.com/news/2025/03/new-threads-features-more-personalized-experience-you-control/) |
| Google Merchant Center | Supplies eligible products to free listings across Search, Shopping, Images, Lens, Maps and other Google surfaces. Upload acceptance does not guarantee approval or display. Google guidance (https://support.google.com/merchants/answer/13889434?hl=en-GB) |

Additional useful routes are Facebook/Instagram product tags, your Google Business Profile’s product module where eligible, and tracked catalogue links on Threads. Paid catalogue advertising is a separate step.

The remaining practical work is Google approval, the 27 photography gaps, Marketplace publishing, and a successful checkout/conversion test. The GSC Wizard reporting connector also currently requires an active subscription.

Updated main product carousel

Meta confirms publication to Facebook and Instagram




------------------------------------------------------------------------------------------------------------
------------------------------------------------------------------------------------------------------------
------------------------------------------------------------------------------------------------------------
------------------------------------------------------------------------------------------------------------




# Boldstone catalogue tools

Source code for the local Boldstone sculpture catalogue, image review room,
Dropbox organisation tools and supporting catalogue workflows.

## Projects

- `catalogue-review/` - local review application, galleries, component and
  specification editing, image roles, pricing, exports and background jobs.
- `application/` - read-only Dropbox inventory/audit application and the shared
  Python environment used by the review app's authenticated workers.
- `image-processing/` - Dropbox authorisation and image conversion tools.
- `sculpture-catalogue/` - catalogue reconciliation, publication, review and
  verification scripts, including retained historical source versions.
- `search-analytics-toolkit/` - search/analytics utilities, with its own setup.
- `SquareSpace product upload/`, `dropbox resolution/` and
  `boldstone_flat_migration_local_2026-10-15/` - platform and migration tools.
- `reports/` and `outputs/` - source scripts from earlier reviews and audits;
  the generated records, photographs and results are deliberately excluded.

This is a source repository, not a copy of the private catalogue or Dropbox.
Historical scripts may reference local datasets and absolute paths. They are
retained for traceability and are not automatic startup or migration commands.
Read each project's instructions before running it.

## Review application

Use Python 3.11-3.14 for the shared environment (the current Mac uses 3.13).
Install the Dropbox SDK, Pillow and Keyring in the
existing `application/.venv` environment (the dependency ranges are in
`application/pyproject.toml`). On a new checkout, create that environment and
install the application package:

```sh
python3.13 -m venv application/.venv
application/.venv/bin/python -m pip install -e './application[dev]'
python3 catalogue-review/launch.py
```

The app opens at `http://127.0.0.1:8767`. It requires the separately retained
private catalogue publication, including `sculpture-catalogue/current-master.json`
and the register/database named by that pointer. Review decisions and runtime
state are stored outside this repository under
`~/Library/Application Support/BoldstoneReview/`. Existing Dropbox credentials
remain in macOS Keychain; they are not distributed by this repository.

Gallery thumbnails are cached with a 256 MiB limit. Full Dropbox originals are
read on demand through the local server. Background inventory checks do not
download galleries. See `catalogue-review/README.md` for the workflows and
data-preservation rules.

## Tests

The review application's fake-adapter tests do not need Dropbox credentials:

```sh
application/.venv/bin/python -m unittest discover -s catalogue-review/tests -p 'test_*.py'
node --test catalogue-review/tests/ui-*.cjs
```

Some browser and historical verification scripts explicitly require the local
catalogue, browser tooling or a live read connection. They are separate from
the fake-adapter suite. Never use test execution to authorise Dropbox changes.

## Local files excluded from Git

The allowlist in `.gitignore` includes code across the workspace while excluding
photographs, downloaded originals, exports, workbook/catalogue data, SQLite
databases, JSON snapshots, logs, archives, installed dependencies and secrets.
Those files continue to exist locally or in their verified archives/Dropbox.
Source scripts and required static application HTML are included. A generated
JavaScript inventory containing private image records is explicitly excluded.
