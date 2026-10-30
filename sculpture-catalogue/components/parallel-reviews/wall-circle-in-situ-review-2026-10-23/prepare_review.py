import datetime, hashlib, html, json, pathlib
from urllib.parse import quote

JOB = pathlib.Path(__file__).resolve().parent
CATALOGUE = JOB.parents[2]
pointer = json.loads((CATALOGUE / "current-master.json").read_text())
register_path = CATALOGUE / pointer["register"]
register_bytes = register_path.read_bytes()
assert hashlib.sha256(register_bytes).hexdigest() == pointer["register_sha256"]
options = {x["product_id"]: x for x in json.loads(register_bytes)["options"]}
sources = json.loads((JOB / "current-source-metadata.json").read_text())
by_id = {x["id"]: x for x in sources["entries"]}
metadata = {x["file"]["id"]: x["file"] for x in sources["metadata"]}
verification = json.loads((JOB / "source-verification.json").read_text())
by_receipt = {x["file_id"]: x for x in verification["selected_sources_current_content_verified"]}
selection = [
 ("BSI-22DA74B2107E", "id:cnqzTNngPVsAAAAAAAr1JQ", "Complete blue and white circle with a warm halo against a textured wall; no wider room visible.", "Close-wall display and lighting reference"),
 ("BSI-C87B4CF945C7", "id:cnqzTNngPVsAAAAAAAs86g", "Complete green and white circle with a warm halo against a textured wall; no wider room visible.", "Close-wall display and lighting reference"),
 ("BSI-1B20DCA291BB", "id:cnqzTNngPVsAAAAAAAr1KQ", "Complete multicoloured circle against a plain glossy surface. No wider setting or backlighting is shown; mounting is not established by this view.", "Individual appearance reference; installation coverage unresolved"),
 ("BSI-67B24409A253", "id:cnqzTNngPVsAAAAAAAs86Q", "Complete turquoise circle with a warm halo against a textured wall; no wider room visible.", "Close-wall display and lighting reference"),
 ("BSI-65520F070145", "id:cnqzTNngPVsAAAAAAAr1IQ", "Complete yellow and grey circle with a warm halo against a textured wall; no wider room visible.", "Close-wall display and lighting reference")
]
cases = []
for i, (pid, file_id, finding, proposal) in enumerate(selection, 1):
    option = options[pid]
    source = by_id[file_id]
    path = source["path_display"]
    parent = path.rsplit("/", 1)[0]
    image_url = "https://www.dropbox.com/preview" + quote(path, safe="/")
    folder_url = "https://www.dropbox.com/home" + quote(parent, safe="/")
    row = {
        "sequence": i, "product_id": pid, "name": option["name"],
        "status": "DEFERRED_BY_OWNER",
        "review_finding": finding, "proposed_role": proposal,
        "wider_room_image_found": False, "owner_approved": False,
        "source_reference": {**source, "rev": metadata[file_id]["rev"],
                             "image_url": image_url, "folder_url": folder_url,
                             "local_image": by_receipt[file_id]["local_file"],
                             "sha256": by_receipt[file_id]["sha256"]},
        "primary_reference": {k:option.get(k) for k in ["file_id","image_url","folder_url"]},
        "current_master_photo_coverage": option["photo_coverage"],
        "source_provenance": "Not independently established; image review does not establish a photographed physical installation.",
        "coverage_change_applied": False
    }
    cases.append(row)
state = {
    "recorded_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "owner_thread": "01a13fe6-495b-7253-b923-31823b4cbca8",
    "master_thread": "01a144ab-1a7c-7223-a403-73a4d53d70ff",
    "source_master": str(register_path), "source_master_sha256": pointer["register_sha256"],
    "scope": "Five Wall Circle finishes with no verified wider installation setting",
    "scan": {"current_files":167,"current_folders":14,"pattern_swatch_files":138,"scene_study_files":10,
             "all_nine_existing_contact_sheets_visually_reviewed":True,
             "all_contact_sheet_file_ids_and_sizes_match_current_listing":True,
             "seven_selected_originals_match_current_dropbox_content_hash":True},
    "findings": [
        "Existing wider scene studies show Pale Blue and Terracotta, which already have context coverage.",
        "The other five options have no wider exact-finish room scene identified in this family folder.",
        "Blue/White, Green/White, Turquoise and Yellow/Grey each have a full-circle close-wall lighting image.",
        "Mixed Colour has a full-circle plain-background image; installation and mounting are not established.",
        "Generated Series 001-005 contain rectangular pattern swatches, not room installations."
    ],
    "pending_question": {
        "product_id": cases[0]["product_id"],
        "question": "Use this complete, backlit circle as a close-wall installation reference, labelled no wider room view?",
        "status": "WITHDRAWN_DEFERRED_BY_OWNER",
        "options": ["Use image as close-wall reference", "Wait for a wider room image"]
    },
    "acanthus": {
        "product_id": "BSI-C41824131174", "status": "PREVIOUS_QUESTION_SUPERSEDED_MASTER_ONLY",
        "question_owner": "01a144ab-1a7c-7223-a403-73a4d53d70ff",
        "current_action": "Main session is correcting the review to use BOLDSTONE MASTER sources only.",
        "new_owner_decision_received": False
    },
    "cases": cases,
    "shared_catalogue_writes": False,
    "dropbox_writes": False
}
state_path = JOB / "review-state.json"
assert not state_path.exists(), "Do not overwrite decisions; update the review state explicitly."
state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")
e = html.escape
cards = []
for c in cases:
    s = c["source_reference"]
    image_src = "originals/" + quote(s["name"])
    cards.append(f"""<article id="case-{c['sequence']}">
<h2>{c['sequence']} of 5 · {e(c['name'])}</h2>
<p class="state">{e(c['status'].replace('_',' ').title())}</p>
<a href="{e(s['image_url'])}"><img src="{e(image_src)}" alt="{e(c['name'])} — unaltered source image"></a>
<p><a href="{e(s['image_url'])}">Dropbox image</a> · <a href="{e(s['folder_url'])}">Containing folder</a></p>
<p>{e(c['review_finding'])}</p>
<dl><dt>Proposed use</dt><dd>{e(c['proposed_role'])}</dd>
<dt>Wider room view</dt><dd>Still missing for this finish</dd>
<dt>Decision</dt><dd>No new approval recorded</dd></dl></article>""")
page = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Wall Circle — five installation reference reviews</title>
<style>body{font:17px/1.5 system-ui;margin:0 auto;max-width:1000px;padding:28px;background:#f5f3ee;color:#192625}a{color:#165b62}h1{font-size:30px}h2{font-size:23px}article{background:white;border:1px solid #d8dfd9;border-radius:12px;padding:24px;margin:32px 0}img{max-width:100%;max-height:620px;display:block;margin:auto;object-fit:contain}.state{font-size:14px;color:#626d64}dt{font-weight:650}dd{margin:0 0 14px}aside{padding:18px;background:#e6ece8;border-radius:9px}</style>
<h1>Wall Circle — installation reference review</h1>
<p>These five reviews are deferred at the owner’s request. No new image choice has been approved. Four have a complete circle against a textured wall with backlighting. Mixed Colour has a plain-background image. No wider room scene for these exact finishes was identified in the current Wall Circle folders.</p>
<p>Existing room scenes show Pale Blue and Terracotta. They remain linked to those finishes.</p>
<aside>Acanthus One Leaf Left — Sandstone remains with the main session. Its earlier image-choice question has been withdrawn while the review is corrected to use BOLDSTONE MASTER sources only.</aside>
""" + "".join(cards) + """<p>Review imagery is shown without cropping or colour changes. Source images alone do not establish a physical installation. No new decisions or catalogue coverage changes are recorded on this page.</p></html>"""
(JOB / "review.html").write_text(page)
assert all(pathlib.Path(c["source_reference"]["local_image"]).exists() for c in cases)
print(json.dumps({"status":"PASS","case_count":len(cases),"pending_case":cases[0]["name"],
                  "review":str(JOB/"review.html"),"shared_writes":False}))

