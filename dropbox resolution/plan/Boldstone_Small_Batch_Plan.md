# Boldstone: smaller, resumable work batches

**Planning checkpoint: 14 October 2026. No live Dropbox reads or changes were performed to create this plan.**

There are 350 explicitly allocated control/review batches, with exact record membership in the `batches` folder. They are not 350 approved mutation jobs.
Additional execution and visual-review child batches are defined by the rules below; their counts depend on verified remaining work.

The complete starting file-ID census and the 203 completed filename-only moves remain historical completed checkpoints. Rechecking a changed file before an operation is not permission to replay its earlier operation.

## Workstream list

| Workstream | References | Recorded scope | Batch rule |
|---|---|---|---|
| Setup | S01 | 1 control task | Lock checkpoint, exclusions, protected keeper IDs and evidence ledger. |
| Capability test | S02 | 2 files | One BMP plus one existing JPG; read/decode only. |
| Blocked review | H01 | 7 held target/keeper pairs | Review the native block. Keep unresolved restrictions held. |
| Existing JPG QA | J001 to J003 | 13 JPG/source associations | Batches of 5, 5 and 3; verify existing outputs, not new conversion work. |
| Identity consolidation | I00 | 1 consolidated queue | Combine earlier identity issues before asserting a total. |
| Metadata review | M001 to M122 | 8,377 snapshot IDs | At most 100 IDs per batch; no batch crosses a baseline family boundary. |
| Folder review | F001 to F017 | 423 previously recorded folder IDs | At most 25 per batch; this is an earlier folder inventory, not a new live count. |
| Duplicate review | D001 to D110 | 2,015 historical target/keeper pairs | At most 25 targets per batch. Presence is not authorization to delete. |
| BMP source review | B001 to B085 | 642 present baseline-BMP IDs | At most 10 source IDs per review batch; actual conversion queue is determined later. |
| Known identity case | I001 to I009 | 9 known folder-label cases | One flagged folder case each, using visual sub-batches for large cases. Not the entire identity queue. |

Counts are workstream scopes and overlap. The 642 BMP entries are baseline-BMP IDs still present, not a confirmed count of remaining conversions.
Six of the seven blocked candidates overlap the 2,015 historical present targets. The seventh is an additional candidate preserved from the earlier checkpoint. H01 is restriction review, not a second deletion queue.
The 423 folder IDs come from the earlier folder checkpoint, which predates the final file-only census. The nine label flags are not a new total for all identity ambiguities.

## How to run small batches

Start with S01. Run the read-only S02 byte-retrieval test once; a failure should be recorded, not repeatedly retried through alternate restricted routes. Continue metadata and other non-binary work while binary-dependent work is blocked.
Process the M batches in manageable units. Each M batch assesses a maximum of 100 fixed IDs within one baseline family. An already approved correct name is a no-op, not another rename.
D batches validate up to 25 historical target/keeper pairs. They do not delete anything. Only a separately authorized X child batch can remove a freshly validated subset.
B batches review up to 10 source IDs. Convert at most five retained sources in each C child batch, and remove originals only in a separate Q batch after replacement verification.
Related folder or identity changes must be resolved before dependent filename actions; after a folder change, refresh and rebase all affected child paths.
There is no requirement to finish all 350 reviews before completing a small validated family subset. Follow the relevant dependencies and save a checkpoint after every batch. Avoid simultaneous overlapping file/folder jobs.

## Gated child batches

| Prefix | Work | Maximum | Unit | Allocation / boundary |
|---|---|---:|---|---|
| R | Filename changes | 25 | approved files | Create R-{parent M batch}-{sequence} only from the outstanding approved subset. Not allocated: remaining approved rename count is not yet known. |
| X | Duplicate deletion | 25 | approved extra copies | Create X-{parent D batch}-{sequence} from freshly validated, authorized targets only. Not allocated: 2,015 presence-matched proposals are not 2,015 approved deletions. |
| C | BMP conversion and upload | 5 | retained sources | Create C-{parent B batch}-{sequence} after duplicate disposition and applicable approval. Capability dependent. Do not report a renamed extension as a conversion. |
| Q | Verified BMP retirement | 5 | source BMPs | Create Q-{parent C batch}-{sequence} only after replacements have passed verification. Separate from C: upload success alone never authorizes source removal. |
| G | Folder naming changes | 1 | approved folder | Create G-{parent F or I batch}-{sequence} only after naming/identity approval. Never rename a folder solely to replace a word such as diptych without evidence. |
| V | Visual component and in-situ review | 25 | retained media assets | Create V-{family code}-{sequence} from the post-cleanup retained/replacement asset set. Dynamic count. Review every retained asset needed for exhaustive coverage; no filename-only coverage claims. |
| T | Family close-out checks | 100 | retained IDs per sub-batch | Create T-{family code}-{sequence}; repeat until that family's retained-ID and exception sets are exhausted. Repeat for all 64 baseline family scopes; do not assume their current locations. |
| Z01 | Final whole-library reconciliation | Paginated | paginated final snapshot | One closing task after all family checks, using paginated reads and saved checkpoints. A final fresh inventory is needed; the completed starting census is not replayed as unfinished work. |

Visual child batches must ultimately cover all relevant retained media and source-to-replacement lineage. Distinguish actual installations, group-only scenes, generated visualisations, details, process assets and uncertainty. A folder label is never sufficient visual evidence.
The final closing census is a new end-state check, not a claim that the completed starting census was unfinished.

## Exact batch list

| Batch ID | Workstream | Family or case | Items | Unit | Initial status |
|---|---|---|---:|---|---|
| S01 | Setup | Checkpoint controls | 1 | control task | Planned |
| S02 | Capability test | One BMP and one JPG | 2 | files | Capability dependent |
| H01 | Blocked review | Seven held duplicate candidates | 7 | target/keeper pairs | Held |
| J001 | Existing JPG QA | Cup Ring and Spiral | 5 | JPG/source associations | Capability dependent |
| J002 | Existing JPG QA | Cup Ring and Spiral | 5 | JPG/source associations | Capability dependent |
| J003 | Existing JPG QA | Cup Ring and Spiral | 3 | JPG/source associations | Capability dependent |
| I00 | Identity consolidation | All historical identity registers | 1 | register task | Planned |
| M001 | Metadata review | Abstract Cave Paintings | 13 | current-snapshot IDs | Planned |
| M002 | Metadata review | Acanthus | 81 | current-snapshot IDs | Planned |
| M003 | Metadata review | Ammonite | 100 | current-snapshot IDs | Planned |
| M004 | Metadata review | Ammonite | 100 | current-snapshot IDs | Planned |
| M005 | Metadata review | Ammonite | 56 | current-snapshot IDs | Planned |
| M006 | Metadata review | Barbados Wave | 34 | current-snapshot IDs | Planned |
| M007 | Metadata review | Bone Spiral | 100 | current-snapshot IDs | Planned |
| M008 | Metadata review | Bone Spiral | 62 | current-snapshot IDs | Planned |
| M009 | Metadata review | Bone Water Spiral | 41 | current-snapshot IDs | Planned |
| M010 | Metadata review | Brancusi | 100 | current-snapshot IDs | Planned |
| M011 | Metadata review | Brancusi | 100 | current-snapshot IDs | Planned |
| M012 | Metadata review | Brancusi | 100 | current-snapshot IDs | Planned |
| M013 | Metadata review | Brancusi | 92 | current-snapshot IDs | Planned |
| M014 | Metadata review | Brancusi Totem | 17 | current-snapshot IDs | Planned |
| M015 | Metadata review | Chelsea Moonwave | 15 | current-snapshot IDs | Planned |
| M016 | Metadata review | Chiswick Moon | 21 | current-snapshot IDs | Planned |
| M017 | Metadata review | Collection Together | 100 | current-snapshot IDs | Planned |
| M018 | Metadata review | Collection Together | 88 | current-snapshot IDs | Planned |
| M019 | Metadata review | Concave Moon | 24 | current-snapshot IDs | Planned |
| M020 | Metadata review | Coral Spiral | 17 | current-snapshot IDs | Planned |
| M021 | Metadata review | Cup Ring and Spiral | 30 | current-snapshot IDs | Planned |
| M022 | Metadata review | Deco Dune Ripple | 100 | current-snapshot IDs | Planned |
| M023 | Metadata review | Deco Dune Ripple | 100 | current-snapshot IDs | Planned |
| M024 | Metadata review | Deco Dune Ripple | 25 | current-snapshot IDs | Planned |
| M025 | Metadata review | Deco Palm and Spiral | 100 | current-snapshot IDs | Planned |
| M026 | Metadata review | Deco Palm and Spiral | 100 | current-snapshot IDs | Planned |
| M027 | Metadata review | Deco Palm and Spiral | 100 | current-snapshot IDs | Planned |
| M028 | Metadata review | Deco Palm and Spiral | 100 | current-snapshot IDs | Planned |
| M029 | Metadata review | Deco Palm and Spiral | 100 | current-snapshot IDs | Planned |
| M030 | Metadata review | Deco Palm and Spiral | 100 | current-snapshot IDs | Planned |
| M031 | Metadata review | Deco Palm and Spiral | 100 | current-snapshot IDs | Planned |
| M032 | Metadata review | Deco Palm and Spiral | 100 | current-snapshot IDs | Planned |
| M033 | Metadata review | Deco Palm and Spiral | 100 | current-snapshot IDs | Planned |
| M034 | Metadata review | Deco Palm and Spiral | 78 | current-snapshot IDs | Planned |
| M035 | Metadata review | Decowaves | 100 | current-snapshot IDs | Planned |
| M036 | Metadata review | Decowaves | 53 | current-snapshot IDs | Planned |
| M037 | Metadata review | Dune Ripple | 100 | current-snapshot IDs | Planned |
| M038 | Metadata review | Dune Ripple | 100 | current-snapshot IDs | Planned |
| M039 | Metadata review | Dune Ripple | 100 | current-snapshot IDs | Planned |
| M040 | Metadata review | Dune Ripple | 100 | current-snapshot IDs | Planned |
| M041 | Metadata review | Dune Ripple | 53 | current-snapshot IDs | Planned |
| M042 | Metadata review | Echo Sound | 100 | current-snapshot IDs | Planned |
| M043 | Metadata review | Echo Sound | 100 | current-snapshot IDs | Planned |
| M044 | Metadata review | Echo Sound | 3 | current-snapshot IDs | Planned |
| M045 | Metadata review | Egyptian Two Palms | 100 | current-snapshot IDs | Planned |
| M046 | Metadata review | Egyptian Two Palms | 100 | current-snapshot IDs | Planned |
| M047 | Metadata review | Egyptian Two Palms | 100 | current-snapshot IDs | Planned |
| M048 | Metadata review | Egyptian Two Palms | 78 | current-snapshot IDs | Planned |
| M049 | Metadata review | Embedded Shells | 11 | current-snapshot IDs | Planned |
| M050 | Metadata review | Faceted Mound | 13 | current-snapshot IDs | Planned |
| M051 | Metadata review | Fan Folds | 100 | current-snapshot IDs | Planned |
| M052 | Metadata review | Fan Folds | 100 | current-snapshot IDs | Planned |
| M053 | Metadata review | Fan Folds | 100 | current-snapshot IDs | Planned |
| M054 | Metadata review | Fan Folds | 100 | current-snapshot IDs | Planned |
| M055 | Metadata review | Fan Folds | 100 | current-snapshot IDs | Planned |
| M056 | Metadata review | Fan Folds | 100 | current-snapshot IDs | Planned |
| M057 | Metadata review | Fan Folds | 100 | current-snapshot IDs | Planned |
| M058 | Metadata review | Fan Folds | 100 | current-snapshot IDs | Planned |
| M059 | Metadata review | Fan Folds | 40 | current-snapshot IDs | Planned |
| M060 | Metadata review | Fingerprint | 94 | current-snapshot IDs | Planned |
| M061 | Metadata review | Fish and Wave | 6 | current-snapshot IDs | Planned |
| M062 | Metadata review | Fountain Palm | 100 | current-snapshot IDs | Planned |
| M063 | Metadata review | Fountain Palm | 100 | current-snapshot IDs | Planned |
| M064 | Metadata review | Fountain Palm | 95 | current-snapshot IDs | Planned |
| M065 | Metadata review | Frozen Fish | 94 | current-snapshot IDs | Planned |
| M066 | Metadata review | Gleneagles Vine and Tendril | 12 | current-snapshot IDs | Planned |
| M067 | Metadata review | Knightsbridge Fountain | 20 | current-snapshot IDs | Planned |
| M068 | Metadata review | Lava Moon | 7 | current-snapshot IDs | Planned |
| M069 | Metadata review | Leaf curve | 100 | current-snapshot IDs | Planned |
| M070 | Metadata review | Leaf curve | 62 | current-snapshot IDs | Planned |
| M071 | Metadata review | Leaf Form | 100 | current-snapshot IDs | Planned |
| M072 | Metadata review | Leaf Form | 100 | current-snapshot IDs | Planned |
| M073 | Metadata review | Leaf Form | 17 | current-snapshot IDs | Planned |
| M074 | Metadata review | Leaf Growth | 100 | current-snapshot IDs | Planned |
| M075 | Metadata review | Leaf Growth | 100 | current-snapshot IDs | Planned |
| M076 | Metadata review | Leaf Growth | 3 | current-snapshot IDs | Planned |
| M077 | Metadata review | Moon & Shellwave | 100 | current-snapshot IDs | Planned |
| M078 | Metadata review | Moon & Shellwave | 80 | current-snapshot IDs | Planned |
| M079 | Metadata review | Moon Crater Phase | 100 | current-snapshot IDs | Planned |
| M080 | Metadata review | Moon Crater Phase | 95 | current-snapshot IDs | Planned |
| M081 | Metadata review | Moon Crater Wide Lip | 9 | current-snapshot IDs | Planned |
| M082 | Metadata review | Moon Fishwave | 100 | current-snapshot IDs | Planned |
| M083 | Metadata review | Moon Fishwave | 87 | current-snapshot IDs | Planned |
| M084 | Metadata review | Moon Ring | 8 | current-snapshot IDs | Planned |
| M085 | Metadata review | Moon Ripple | 17 | current-snapshot IDs | Planned |
| M086 | Metadata review | Mooncrater | 25 | current-snapshot IDs | Planned |
| M087 | Metadata review | Moonphases | 100 | current-snapshot IDs | Planned |
| M088 | Metadata review | Moonphases | 100 | current-snapshot IDs | Planned |
| M089 | Metadata review | Moonphases | 100 | current-snapshot IDs | Planned |
| M090 | Metadata review | Moonphases | 50 | current-snapshot IDs | Planned |
| M091 | Metadata review | Moonshell Lava | 15 | current-snapshot IDs | Planned |
| M092 | Metadata review | Moonshell Lava Corner Curve | 7 | current-snapshot IDs | Planned |
| M093 | Metadata review | Moonspirals | 100 | current-snapshot IDs | Planned |
| M094 | Metadata review | Moonspirals | 75 | current-snapshot IDs | Planned |
| M095 | Metadata review | Moonwater catcher | 100 | current-snapshot IDs | Planned |
| M096 | Metadata review | Moonwater catcher | 6 | current-snapshot IDs | Planned |
| M097 | Metadata review | Moonwave | 100 | current-snapshot IDs | Planned |
| M098 | Metadata review | Moonwave | 85 | current-snapshot IDs | Planned |
| M099 | Metadata review | Panel Curves | 58 | current-snapshot IDs | Planned |
| M100 | Metadata review | Plant Form | 7 | current-snapshot IDs | Planned |
| M101 | Metadata review | Raked Spiral | 100 | current-snapshot IDs | Planned |
| M102 | Metadata review | Raked Spiral | 33 | current-snapshot IDs | Planned |
| M103 | Metadata review | Riyadh Shell Spiral and Wave | 64 | current-snapshot IDs | Planned |
| M104 | Metadata review | Rust and Verdigris Panel | 34 | current-snapshot IDs | Planned |
| M105 | Metadata review | Sally With Sculptures | 1 | current-snapshot IDs | Planned |
| M106 | Metadata review | Seaweed Ripple | 100 | current-snapshot IDs | Planned |
| M107 | Metadata review | Seaweed Ripple | 85 | current-snapshot IDs | Planned |
| M108 | Metadata review | Shellmoon | 100 | current-snapshot IDs | Planned |
| M109 | Metadata review | Shellmoon | 20 | current-snapshot IDs | Planned |
| M110 | Metadata review | Soundwave | 9 | current-snapshot IDs | Planned |
| M111 | Metadata review | Spice Texture | 3 | current-snapshot IDs | Planned |
| M112 | Metadata review | Spiralfish Wave & Tide | 76 | current-snapshot IDs | Planned |
| M113 | Metadata review | Spiralmoon | 100 | current-snapshot IDs | Planned |
| M114 | Metadata review | Spiralmoon | 8 | current-snapshot IDs | Planned |
| M115 | Metadata review | Strata | 20 | current-snapshot IDs | Planned |
| M116 | Metadata review | Textured panels | 100 | current-snapshot IDs | Planned |
| M117 | Metadata review | Textured panels | 32 | current-snapshot IDs | Planned |
| M118 | Metadata review | Videos Of Sculpture Making | 1 | current-snapshot IDs | Planned |
| M119 | Metadata review | Wall Circle | 100 | current-snapshot IDs | Planned |
| M120 | Metadata review | Wall Circle | 72 | current-snapshot IDs | Planned |
| M121 | Metadata review | Wall Panel Azure Blue Marble | 43 | current-snapshot IDs | Planned |
| M122 | Metadata review | Wave and Moon Shadow | 97 | current-snapshot IDs | Planned |
| F001 | Folder review | Earlier folder inventory | 25 | recorded folder IDs | Planned |
| F002 | Folder review | Earlier folder inventory | 25 | recorded folder IDs | Planned |
| F003 | Folder review | Earlier folder inventory | 25 | recorded folder IDs | Planned |
| F004 | Folder review | Earlier folder inventory | 25 | recorded folder IDs | Planned |
| F005 | Folder review | Earlier folder inventory | 25 | recorded folder IDs | Planned |
| F006 | Folder review | Earlier folder inventory | 25 | recorded folder IDs | Planned |
| F007 | Folder review | Earlier folder inventory | 25 | recorded folder IDs | Planned |
| F008 | Folder review | Earlier folder inventory | 25 | recorded folder IDs | Planned |
| F009 | Folder review | Earlier folder inventory | 25 | recorded folder IDs | Planned |
| F010 | Folder review | Earlier folder inventory | 25 | recorded folder IDs | Planned |
| F011 | Folder review | Earlier folder inventory | 25 | recorded folder IDs | Planned |
| F012 | Folder review | Earlier folder inventory | 25 | recorded folder IDs | Planned |
| F013 | Folder review | Earlier folder inventory | 25 | recorded folder IDs | Planned |
| F014 | Folder review | Earlier folder inventory | 25 | recorded folder IDs | Planned |
| F015 | Folder review | Earlier folder inventory | 25 | recorded folder IDs | Planned |
| F016 | Folder review | Earlier folder inventory | 25 | recorded folder IDs | Planned |
| F017 | Folder review | Earlier folder inventory | 23 | recorded folder IDs | Planned |
| D001 | Duplicate review | Ammonite | 6 | historical target/keeper pairs | Held |
| D002 | Duplicate review | Barbados Wave | 11 | historical target/keeper pairs | Planned |
| D003 | Duplicate review | Bone Spiral | 22 | historical target/keeper pairs | Planned |
| D004 | Duplicate review | Bone Water Spiral | 19 | historical target/keeper pairs | Planned |
| D005 | Duplicate review | Brancusi | 25 | historical target/keeper pairs | Planned |
| D006 | Duplicate review | Brancusi | 25 | historical target/keeper pairs | Planned |
| D007 | Duplicate review | Brancusi | 25 | historical target/keeper pairs | Planned |
| D008 | Duplicate review | Brancusi | 25 | historical target/keeper pairs | Planned |
| D009 | Duplicate review | Brancusi | 25 | historical target/keeper pairs | Planned |
| D010 | Duplicate review | Brancusi | 20 | historical target/keeper pairs | Planned |
| D011 | Duplicate review | Chelsea Moonwave | 1 | historical target/keeper pairs | Planned |
| D012 | Duplicate review | Chiswick Moon | 4 | historical target/keeper pairs | Planned |
| D013 | Duplicate review | Collection Together | 25 | historical target/keeper pairs | Planned |
| D014 | Duplicate review | Collection Together | 12 | historical target/keeper pairs | Planned |
| D015 | Duplicate review | Coral Spiral | 6 | historical target/keeper pairs | Planned |
| D016 | Duplicate review | Deco Dune Ripple | 25 | historical target/keeper pairs | Planned |
| D017 | Duplicate review | Deco Dune Ripple | 18 | historical target/keeper pairs | Planned |
| D018 | Duplicate review | Deco Palm and Spiral | 25 | historical target/keeper pairs | Planned |
| D019 | Duplicate review | Deco Palm and Spiral | 25 | historical target/keeper pairs | Planned |
| D020 | Duplicate review | Deco Palm and Spiral | 25 | historical target/keeper pairs | Planned |
| D021 | Duplicate review | Deco Palm and Spiral | 25 | historical target/keeper pairs | Planned |
| D022 | Duplicate review | Deco Palm and Spiral | 25 | historical target/keeper pairs | Planned |
| D023 | Duplicate review | Deco Palm and Spiral | 25 | historical target/keeper pairs | Planned |
| D024 | Duplicate review | Deco Palm and Spiral | 25 | historical target/keeper pairs | Planned |
| D025 | Duplicate review | Deco Palm and Spiral | 25 | historical target/keeper pairs | Planned |
| D026 | Duplicate review | Deco Palm and Spiral | 25 | historical target/keeper pairs | Planned |
| D027 | Duplicate review | Deco Palm and Spiral | 25 | historical target/keeper pairs | Planned |
| D028 | Duplicate review | Deco Palm and Spiral | 25 | historical target/keeper pairs | Planned |
| D029 | Duplicate review | Deco Palm and Spiral | 25 | historical target/keeper pairs | Planned |
| D030 | Duplicate review | Deco Palm and Spiral | 25 | historical target/keeper pairs | Planned |
| D031 | Duplicate review | Deco Palm and Spiral | 23 | historical target/keeper pairs | Planned |
| D032 | Duplicate review | Decowaves | 22 | historical target/keeper pairs | Planned |
| D033 | Duplicate review | Dune Ripple | 25 | historical target/keeper pairs | Planned |
| D034 | Duplicate review | Dune Ripple | 3 | historical target/keeper pairs | Planned |
| D035 | Duplicate review | Echo Sound | 23 | historical target/keeper pairs | Planned |
| D036 | Duplicate review | Egyptian Two Palms | 25 | historical target/keeper pairs | Planned |
| D037 | Duplicate review | Egyptian Two Palms | 25 | historical target/keeper pairs | Planned |
| D038 | Duplicate review | Egyptian Two Palms | 25 | historical target/keeper pairs | Planned |
| D039 | Duplicate review | Egyptian Two Palms | 25 | historical target/keeper pairs | Planned |
| D040 | Duplicate review | Egyptian Two Palms | 17 | historical target/keeper pairs | Planned |
| D041 | Duplicate review | Embedded Shells | 1 | historical target/keeper pairs | Planned |
| D042 | Duplicate review | Faceted Mound | 5 | historical target/keeper pairs | Planned |
| D043 | Duplicate review | Fan Folds | 25 | historical target/keeper pairs | Planned |
| D044 | Duplicate review | Fan Folds | 25 | historical target/keeper pairs | Planned |
| D045 | Duplicate review | Fan Folds | 25 | historical target/keeper pairs | Planned |
| D046 | Duplicate review | Fan Folds | 25 | historical target/keeper pairs | Planned |
| D047 | Duplicate review | Fan Folds | 25 | historical target/keeper pairs | Planned |
| D048 | Duplicate review | Fan Folds | 25 | historical target/keeper pairs | Planned |
| D049 | Duplicate review | Fan Folds | 22 | historical target/keeper pairs | Planned |
| D050 | Duplicate review | Fingerprint | 6 | historical target/keeper pairs | Planned |
| D051 | Duplicate review | Fish and Wave | 1 | historical target/keeper pairs | Planned |
| D052 | Duplicate review | Fountain Palm | 8 | historical target/keeper pairs | Planned |
| D053 | Duplicate review | Frozen Fish | 21 | historical target/keeper pairs | Planned |
| D054 | Duplicate review | Gleneagles Vine and Tendril | 3 | historical target/keeper pairs | Planned |
| D055 | Duplicate review | Knightsbridge Fountain | 5 | historical target/keeper pairs | Planned |
| D056 | Duplicate review | Lava Moon | 1 | historical target/keeper pairs | Planned |
| D057 | Duplicate review | Leaf curve | 25 | historical target/keeper pairs | Planned |
| D058 | Duplicate review | Leaf curve | 25 | historical target/keeper pairs | Planned |
| D059 | Duplicate review | Leaf curve | 24 | historical target/keeper pairs | Planned |
| D060 | Duplicate review | Leaf Form | 25 | historical target/keeper pairs | Planned |
| D061 | Duplicate review | Leaf Form | 25 | historical target/keeper pairs | Planned |
| D062 | Duplicate review | Leaf Form | 25 | historical target/keeper pairs | Planned |
| D063 | Duplicate review | Leaf Form | 22 | historical target/keeper pairs | Planned |
| D064 | Duplicate review | Leaf Growth | 25 | historical target/keeper pairs | Planned |
| D065 | Duplicate review | Leaf Growth | 25 | historical target/keeper pairs | Planned |
| D066 | Duplicate review | Leaf Growth | 25 | historical target/keeper pairs | Planned |
| D067 | Duplicate review | Leaf Growth | 12 | historical target/keeper pairs | Planned |
| D068 | Duplicate review | Moon & Shellwave | 25 | historical target/keeper pairs | Planned |
| D069 | Duplicate review | Moon & Shellwave | 15 | historical target/keeper pairs | Planned |
| D070 | Duplicate review | Moon Crater Phase | 25 | historical target/keeper pairs | Planned |
| D071 | Duplicate review | Moon Crater Phase | 23 | historical target/keeper pairs | Planned |
| D072 | Duplicate review | Moon Fishwave | 25 | historical target/keeper pairs | Planned |
| D073 | Duplicate review | Moon Fishwave | 25 | historical target/keeper pairs | Planned |
| D074 | Duplicate review | Moon Fishwave | 13 | historical target/keeper pairs | Planned |
| D075 | Duplicate review | Moon Ring | 2 | historical target/keeper pairs | Planned |
| D076 | Duplicate review | Moon Ripple | 2 | historical target/keeper pairs | Planned |
| D077 | Duplicate review | Mooncrater | 11 | historical target/keeper pairs | Planned |
| D078 | Duplicate review | Moonphases | 25 | historical target/keeper pairs | Planned |
| D079 | Duplicate review | Moonphases | 25 | historical target/keeper pairs | Planned |
| D080 | Duplicate review | Moonphases | 25 | historical target/keeper pairs | Planned |
| D081 | Duplicate review | Moonphases | 9 | historical target/keeper pairs | Planned |
| D082 | Duplicate review | Moonshell Lava | 5 | historical target/keeper pairs | Planned |
| D083 | Duplicate review | Moonshell Lava Corner Curve | 3 | historical target/keeper pairs | Planned |
| D084 | Duplicate review | Moonspirals | 25 | historical target/keeper pairs | Planned |
| D085 | Duplicate review | Moonspirals | 25 | historical target/keeper pairs | Planned |
| D086 | Duplicate review | Moonspirals | 7 | historical target/keeper pairs | Planned |
| D087 | Duplicate review | Moonwater catcher | 25 | historical target/keeper pairs | Planned |
| D088 | Duplicate review | Moonwater catcher | 24 | historical target/keeper pairs | Planned |
| D089 | Duplicate review | Moonwave | 25 | historical target/keeper pairs | Planned |
| D090 | Duplicate review | Moonwave | 25 | historical target/keeper pairs | Planned |
| D091 | Duplicate review | Moonwave | 25 | historical target/keeper pairs | Planned |
| D092 | Duplicate review | Moonwave | 11 | historical target/keeper pairs | Planned |
| D093 | Duplicate review | Panel Curves | 25 | historical target/keeper pairs | Planned |
| D094 | Duplicate review | Panel Curves | 2 | historical target/keeper pairs | Planned |
| D095 | Duplicate review | Raked Spiral | 25 | historical target/keeper pairs | Planned |
| D096 | Duplicate review | Raked Spiral | 6 | historical target/keeper pairs | Planned |
| D097 | Duplicate review | Riyadh Shell Spiral and Wave | 25 | historical target/keeper pairs | Planned |
| D098 | Duplicate review | Rust and Verdigris Panel | 2 | historical target/keeper pairs | Planned |
| D099 | Duplicate review | Seaweed Ripple | 14 | historical target/keeper pairs | Planned |
| D100 | Duplicate review | Shellmoon | 25 | historical target/keeper pairs | Planned |
| D101 | Duplicate review | Shellmoon | 25 | historical target/keeper pairs | Planned |
| D102 | Duplicate review | Shellmoon | 1 | historical target/keeper pairs | Planned |
| D103 | Duplicate review | Soundwave | 1 | historical target/keeper pairs | Planned |
| D104 | Duplicate review | Spiralfish Wave & Tide | 21 | historical target/keeper pairs | Planned |
| D105 | Duplicate review | Spiralmoon | 25 | historical target/keeper pairs | Planned |
| D106 | Duplicate review | Spiralmoon | 15 | historical target/keeper pairs | Planned |
| D107 | Duplicate review | Wall Circle | 3 | historical target/keeper pairs | Planned |
| D108 | Duplicate review | Wall Panel Azure Blue Marble | 1 | historical target/keeper pairs | Planned |
| D109 | Duplicate review | Wave and Moon Shadow | 25 | historical target/keeper pairs | Planned |
| D110 | Duplicate review | Wave and Moon Shadow | 11 | historical target/keeper pairs | Planned |
| B001 | BMP source review | Ammonite | 10 | present baseline-BMP IDs | Capability dependent |
| B002 | BMP source review | Ammonite | 8 | present baseline-BMP IDs | Capability dependent |
| B003 | BMP source review | Barbados Wave | 10 | present baseline-BMP IDs | Capability dependent |
| B004 | BMP source review | Barbados Wave | 1 | present baseline-BMP IDs | Capability dependent |
| B005 | BMP source review | Bone Spiral | 10 | present baseline-BMP IDs | Capability dependent |
| B006 | BMP source review | Bone Spiral | 8 | present baseline-BMP IDs | Capability dependent |
| B007 | BMP source review | Bone Water Spiral | 7 | present baseline-BMP IDs | Capability dependent |
| B008 | BMP source review | Brancusi | 10 | present baseline-BMP IDs | Capability dependent |
| B009 | BMP source review | Brancusi | 10 | present baseline-BMP IDs | Capability dependent |
| B010 | BMP source review | Brancusi | 10 | present baseline-BMP IDs | Capability dependent |
| B011 | BMP source review | Brancusi | 1 | present baseline-BMP IDs | Capability dependent |
| B012 | BMP source review | Brancusi Totem | 2 | present baseline-BMP IDs | Capability dependent |
| B013 | BMP source review | Chelsea Moonwave | 3 | present baseline-BMP IDs | Capability dependent |
| B014 | BMP source review | Chiswick Moon | 3 | present baseline-BMP IDs | Capability dependent |
| B015 | BMP source review | Collection Together | 4 | present baseline-BMP IDs | Capability dependent |
| B016 | BMP source review | Coral Spiral | 3 | present baseline-BMP IDs | Capability dependent |
| B017 | BMP source review | Decowaves | 10 | present baseline-BMP IDs | Capability dependent |
| B018 | BMP source review | Decowaves | 10 | present baseline-BMP IDs | Capability dependent |
| B019 | BMP source review | Decowaves | 10 | present baseline-BMP IDs | Capability dependent |
| B020 | BMP source review | Decowaves | 7 | present baseline-BMP IDs | Capability dependent |
| B021 | BMP source review | Dune Ripple | 10 | present baseline-BMP IDs | Capability dependent |
| B022 | BMP source review | Dune Ripple | 10 | present baseline-BMP IDs | Capability dependent |
| B023 | BMP source review | Dune Ripple | 10 | present baseline-BMP IDs | Capability dependent |
| B024 | BMP source review | Dune Ripple | 6 | present baseline-BMP IDs | Capability dependent |
| B025 | BMP source review | Embedded Shells | 4 | present baseline-BMP IDs | Capability dependent |
| B026 | BMP source review | Fish and Wave | 1 | present baseline-BMP IDs | Capability dependent |
| B027 | BMP source review | Frozen Fish | 10 | present baseline-BMP IDs | Capability dependent |
| B028 | BMP source review | Frozen Fish | 10 | present baseline-BMP IDs | Capability dependent |
| B029 | BMP source review | Frozen Fish | 10 | present baseline-BMP IDs | Capability dependent |
| B030 | BMP source review | Frozen Fish | 6 | present baseline-BMP IDs | Capability dependent |
| B031 | BMP source review | Lava Moon | 3 | present baseline-BMP IDs | Capability dependent |
| B032 | BMP source review | Leaf Form | 10 | present baseline-BMP IDs | Capability dependent |
| B033 | BMP source review | Leaf Form | 10 | present baseline-BMP IDs | Capability dependent |
| B034 | BMP source review | Leaf Form | 9 | present baseline-BMP IDs | Capability dependent |
| B035 | BMP source review | Moon & Shellwave | 10 | present baseline-BMP IDs | Capability dependent |
| B036 | BMP source review | Moon & Shellwave | 10 | present baseline-BMP IDs | Capability dependent |
| B037 | BMP source review | Moon & Shellwave | 10 | present baseline-BMP IDs | Capability dependent |
| B038 | BMP source review | Moon & Shellwave | 10 | present baseline-BMP IDs | Capability dependent |
| B039 | BMP source review | Moon & Shellwave | 10 | present baseline-BMP IDs | Capability dependent |
| B040 | BMP source review | Moon & Shellwave | 10 | present baseline-BMP IDs | Capability dependent |
| B041 | BMP source review | Moon & Shellwave | 3 | present baseline-BMP IDs | Capability dependent |
| B042 | BMP source review | Moon Crater Phase | 10 | present baseline-BMP IDs | Capability dependent |
| B043 | BMP source review | Moon Crater Phase | 4 | present baseline-BMP IDs | Capability dependent |
| B044 | BMP source review | Moon Fishwave | 10 | present baseline-BMP IDs | Capability dependent |
| B045 | BMP source review | Moon Ring | 4 | present baseline-BMP IDs | Capability dependent |
| B046 | BMP source review | Moon Ripple | 2 | present baseline-BMP IDs | Capability dependent |
| B047 | BMP source review | Mooncrater | 4 | present baseline-BMP IDs | Capability dependent |
| B048 | BMP source review | Moonphases | 10 | present baseline-BMP IDs | Capability dependent |
| B049 | BMP source review | Moonphases | 10 | present baseline-BMP IDs | Capability dependent |
| B050 | BMP source review | Moonphases | 10 | present baseline-BMP IDs | Capability dependent |
| B051 | BMP source review | Moonphases | 10 | present baseline-BMP IDs | Capability dependent |
| B052 | BMP source review | Moonphases | 10 | present baseline-BMP IDs | Capability dependent |
| B053 | BMP source review | Moonphases | 10 | present baseline-BMP IDs | Capability dependent |
| B054 | BMP source review | Moonphases | 10 | present baseline-BMP IDs | Capability dependent |
| B055 | BMP source review | Moonphases | 5 | present baseline-BMP IDs | Capability dependent |
| B056 | BMP source review | Moonshell Lava | 4 | present baseline-BMP IDs | Capability dependent |
| B057 | BMP source review | Moonshell Lava Corner Curve | 2 | present baseline-BMP IDs | Capability dependent |
| B058 | BMP source review | Moonspirals | 10 | present baseline-BMP IDs | Capability dependent |
| B059 | BMP source review | Moonspirals | 10 | present baseline-BMP IDs | Capability dependent |
| B060 | BMP source review | Moonspirals | 10 | present baseline-BMP IDs | Capability dependent |
| B061 | BMP source review | Moonspirals | 10 | present baseline-BMP IDs | Capability dependent |
| B062 | BMP source review | Moonspirals | 10 | present baseline-BMP IDs | Capability dependent |
| B063 | BMP source review | Moonspirals | 10 | present baseline-BMP IDs | Capability dependent |
| B064 | BMP source review | Moonspirals | 10 | present baseline-BMP IDs | Capability dependent |
| B065 | BMP source review | Moonspirals | 1 | present baseline-BMP IDs | Capability dependent |
| B066 | BMP source review | Plant Form | 4 | present baseline-BMP IDs | Capability dependent |
| B067 | BMP source review | Raked Spiral | 10 | present baseline-BMP IDs | Capability dependent |
| B068 | BMP source review | Raked Spiral | 10 | present baseline-BMP IDs | Capability dependent |
| B069 | BMP source review | Raked Spiral | 10 | present baseline-BMP IDs | Capability dependent |
| B070 | BMP source review | Raked Spiral | 10 | present baseline-BMP IDs | Capability dependent |
| B071 | BMP source review | Raked Spiral | 4 | present baseline-BMP IDs | Capability dependent |
| B072 | BMP source review | Riyadh Shell Spiral and Wave | 10 | present baseline-BMP IDs | Capability dependent |
| B073 | BMP source review | Riyadh Shell Spiral and Wave | 7 | present baseline-BMP IDs | Capability dependent |
| B074 | BMP source review | Shellmoon | 10 | present baseline-BMP IDs | Capability dependent |
| B075 | BMP source review | Shellmoon | 10 | present baseline-BMP IDs | Capability dependent |
| B076 | BMP source review | Shellmoon | 1 | present baseline-BMP IDs | Capability dependent |
| B077 | BMP source review | Soundwave | 3 | present baseline-BMP IDs | Capability dependent |
| B078 | BMP source review | Spice Texture | 1 | present baseline-BMP IDs | Capability dependent |
| B079 | BMP source review | Spiralfish Wave & Tide | 10 | present baseline-BMP IDs | Capability dependent |
| B080 | BMP source review | Spiralfish Wave & Tide | 7 | present baseline-BMP IDs | Capability dependent |
| B081 | BMP source review | Spiralmoon | 10 | present baseline-BMP IDs | Capability dependent |
| B082 | BMP source review | Spiralmoon | 10 | present baseline-BMP IDs | Capability dependent |
| B083 | BMP source review | Spiralmoon | 10 | present baseline-BMP IDs | Capability dependent |
| B084 | BMP source review | Spiralmoon | 4 | present baseline-BMP IDs | Capability dependent |
| B085 | BMP source review | Wave and Moon Shadow | 6 | present baseline-BMP IDs | Capability dependent |
| I001 | Known identity case | Brancusi/Brancusi Diptych White | 1 | flagged folder case | Capability dependent |
| I002 | Known identity case | Deco Dune Ripple/Deco Dune Ripple Diptych White In Situ | 1 | flagged folder case | Capability dependent |
| I003 | Known identity case | Deco Dune Ripple/Deco Dune Ripple Triptych White In Situ | 1 | flagged folder case | Capability dependent |
| I004 | Known identity case | Decowaves/Frozen Decowaves 1 and Frozen Decowaves 2 Triptych White | 1 | flagged folder case | Capability dependent |
| I005 | Known identity case | Fan Folds/Fold Unfold Diptych on wall | 1 | flagged folder case | Capability dependent |
| I006 | Known identity case | Raked Spiral/Raked Spiral 1 and Raked Spiral 2 and Raked Spiral 3 9x9 White In Situ | 1 | flagged folder case | Capability dependent |
| I007 | Known identity case | Raked Spiral/Raked Spiral 1 and Raked Spiral 2 and Raked Spiral 3 Quartet White In Situ | 1 | flagged folder case | Capability dependent |
| I008 | Known identity case | Wave and Moonshadow/Wave and Moonshadow 1 and Wave and Moonshadow 2 Triptych White | 1 | flagged folder case | Capability dependent |
| I009 | Known identity case | Wave and Moonshadow/Wave and Moonshadow 1 and Wave and Moonshadow 2 Triptych White In Situ | 1 | flagged folder case | Capability dependent |

## Family index

| Family code | Baseline family | Snapshot IDs | Duplicate candidates | BMP-source review IDs | Metadata batches | Duplicate batches | BMP batches |
|---|---|---:|---:|---:|---|---|---|
| FAM01 | Abstract Cave Paintings | 13 | 0 | 0 | M001 | None | None |
| FAM02 | Acanthus | 81 | 0 | 0 | M002 | None | None |
| FAM03 | Ammonite | 256 | 6 | 18 | M003 to M005 | D001 | B001 to B002 |
| FAM04 | Barbados Wave | 34 | 11 | 11 | M006 | D002 | B003 to B004 |
| FAM05 | Bone Spiral | 162 | 22 | 18 | M007 to M008 | D003 | B005 to B006 |
| FAM06 | Bone Water Spiral | 41 | 19 | 7 | M009 | D004 | B007 |
| FAM07 | Brancusi | 392 | 145 | 31 | M010 to M013 | D005 to D010 | B008 to B011 |
| FAM08 | Brancusi Totem | 17 | 0 | 2 | M014 | None | B012 |
| FAM09 | Chelsea Moonwave | 15 | 1 | 3 | M015 | D011 | B013 |
| FAM10 | Chiswick Moon | 21 | 4 | 3 | M016 | D012 | B014 |
| FAM11 | Collection Together | 188 | 37 | 4 | M017 to M018 | D013 to D014 | B015 |
| FAM12 | Concave Moon | 24 | 0 | 0 | M019 | None | None |
| FAM13 | Coral Spiral | 17 | 6 | 3 | M020 | D015 | B016 |
| FAM14 | Cup Ring and Spiral | 30 | 0 | 0 | M021 | None | None |
| FAM15 | Deco Dune Ripple | 225 | 43 | 0 | M022 to M024 | D016 to D017 | None |
| FAM16 | Deco Palm and Spiral | 978 | 348 | 0 | M025 to M034 | D018 to D031 | None |
| FAM17 | Decowaves | 153 | 22 | 37 | M035 to M036 | D032 | B017 to B020 |
| FAM18 | Dune Ripple | 453 | 28 | 36 | M037 to M041 | D033 to D034 | B021 to B024 |
| FAM19 | Echo Sound | 203 | 23 | 0 | M042 to M044 | D035 | None |
| FAM20 | Egyptian Two Palms | 378 | 117 | 0 | M045 to M048 | D036 to D040 | None |
| FAM21 | Embedded Shells | 11 | 1 | 4 | M049 | D041 | B025 |
| FAM22 | Faceted Mound | 13 | 5 | 0 | M050 | D042 | None |
| FAM23 | Fan Folds | 840 | 172 | 0 | M051 to M059 | D043 to D049 | None |
| FAM24 | Fingerprint | 94 | 6 | 0 | M060 | D050 | None |
| FAM25 | Fish and Wave | 6 | 1 | 1 | M061 | D051 | B026 |
| FAM26 | Fountain Palm | 295 | 8 | 0 | M062 to M064 | D052 | None |
| FAM27 | Frozen Fish | 94 | 21 | 36 | M065 | D053 | B027 to B030 |
| FAM28 | Gleneagles Vine and Tendril | 12 | 3 | 0 | M066 | D054 | None |
| FAM29 | Knightsbridge Fountain | 20 | 5 | 0 | M067 | D055 | None |
| FAM30 | Lava Moon | 7 | 1 | 3 | M068 | D056 | B031 |
| FAM31 | Leaf curve | 162 | 74 | 0 | M069 to M070 | D057 to D059 | None |
| FAM32 | Leaf Form | 217 | 97 | 29 | M071 to M073 | D060 to D063 | B032 to B034 |
| FAM33 | Leaf Growth | 203 | 87 | 0 | M074 to M076 | D064 to D067 | None |
| FAM34 | Moon & Shellwave | 180 | 40 | 63 | M077 to M078 | D068 to D069 | B035 to B041 |
| FAM35 | Moon Crater Phase | 195 | 48 | 14 | M079 to M080 | D070 to D071 | B042 to B043 |
| FAM36 | Moon Crater Wide Lip | 9 | 0 | 0 | M081 | None | None |
| FAM37 | Moon Fishwave | 187 | 63 | 10 | M082 to M083 | D072 to D074 | B044 |
| FAM38 | Moon Ring | 8 | 2 | 4 | M084 | D075 | B045 |
| FAM39 | Moon Ripple | 17 | 2 | 2 | M085 | D076 | B046 |
| FAM40 | Mooncrater | 25 | 11 | 4 | M086 | D077 | B047 |
| FAM41 | Moonphases | 350 | 84 | 75 | M087 to M090 | D078 to D081 | B048 to B055 |
| FAM42 | Moonshell Lava | 15 | 5 | 4 | M091 | D082 | B056 |
| FAM43 | Moonshell Lava Corner Curve | 7 | 3 | 2 | M092 | D083 | B057 |
| FAM44 | Moonspirals | 175 | 57 | 71 | M093 to M094 | D084 to D086 | B058 to B065 |
| FAM45 | Moonwater catcher | 106 | 49 | 0 | M095 to M096 | D087 to D088 | None |
| FAM46 | Moonwave | 185 | 86 | 0 | M097 to M098 | D089 to D092 | None |
| FAM47 | Panel Curves | 58 | 27 | 0 | M099 | D093 to D094 | None |
| FAM48 | Plant Form | 7 | 0 | 4 | M100 | None | B066 |
| FAM49 | Raked Spiral | 133 | 31 | 44 | M101 to M102 | D095 to D096 | B067 to B071 |
| FAM50 | Riyadh Shell Spiral and Wave | 64 | 25 | 17 | M103 | D097 | B072 to B073 |
| FAM51 | Rust and Verdigris Panel | 34 | 2 | 0 | M104 | D098 | None |
| FAM52 | Sally With Sculptures | 1 | 0 | 0 | M105 | None | None |
| FAM53 | Seaweed Ripple | 185 | 14 | 0 | M106 to M107 | D099 | None |
| FAM54 | Shellmoon | 120 | 51 | 21 | M108 to M109 | D100 to D102 | B074 to B076 |
| FAM55 | Soundwave | 9 | 1 | 3 | M110 | D103 | B077 |
| FAM56 | Spice Texture | 3 | 0 | 1 | M111 | None | B078 |
| FAM57 | Spiralfish Wave & Tide | 76 | 21 | 17 | M112 | D104 | B079 to B080 |
| FAM58 | Spiralmoon | 108 | 40 | 34 | M113 to M114 | D105 to D106 | B081 to B084 |
| FAM59 | Strata | 20 | 0 | 0 | M115 | None | None |
| FAM60 | Textured panels | 132 | 0 | 0 | M116 to M117 | None | None |
| FAM61 | Videos Of Sculpture Making | 1 | 0 | 0 | M118 | None | None |
| FAM62 | Wall Circle | 172 | 3 | 0 | M119 to M120 | D107 | None |
| FAM63 | Wall Panel Azure Blue Marble | 43 | 1 | 0 | M121 | D108 | None |
| FAM64 | Wave and Moon Shadow | 97 | 36 | 6 | M122 | D109 to D110 | B085 |

## Required batch checkpoint

Save the exact batch ID and input IDs, preflight metadata, approvals, attempted operations, terminal native results, independent postflight reads, keeper/replacement checks, rollback or recovery references, partial/blocked cases and the next batch ID.
Preserve original source fields and append outcomes. Do not rewrite historical approval, status or hash fields to imply fresh approval or fresh content verification.

## Resume instruction

Continue only batch <BATCH_ID> from the Boldstone small-batch plan. Open its exact CSV manifest. Resolve stable IDs to current locations. Perform only the specified workstream and respect its start gates. This plan itself authorizes no mutations. Preserve existing approvals, completed operations, held cases and historical evidence. Save verified outcomes and stop at that batch checkpoint.

## Source files

- Census checkpoint: `Boldstone_Complete_ID_Census_2026-10-14.zip`; SHA-256 `556a95c4f674a04fdc95aba858ccdf09a4d4258c9caba2c5f927a1d2545e1d05`. Presence only for most IDs; not new filename, content or visual verification.
- Earlier folder and held-issue checkpoint: `Boldstone_Cleanup_Retry_2026-10-14.zip`; SHA-256 `a49896d59a52623ca41a8c37deb6d440865783766924283e821f4240c929786b`. Earlier dated observations; nine wording flags are not the total identity queue.
- Completed rename checkpoint: `Boldstone_Approved_Renames_Executed_203_2026-10-14.zip`; SHA-256 `2601956a7627efa58ffc60265ffc9a416b59926ee81703801f97c502d88e04c7`. Do not replay. This batch plan does not change historical approvals or content-verification boundaries.
