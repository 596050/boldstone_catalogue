import collections, csv, datetime, hashlib, json, pathlib, re
from html.parser import HTMLParser
from urllib.parse import unquote

HERE = pathlib.Path(__file__).resolve().parent
CAT = HERE.parents[2]
JOB = CAT / "components/reconciliation/master-only-source-correction-2026-10-23"
OUT = CAT / "outputs/master-only-source-correction-2026-10-23"
def load(path): return json.loads(path.read_text())
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def check(condition, message):
    if not condition: raise AssertionError(message)
pattern = re.compile(r"BOLDSTONE[_ ]BACKUP", re.I)
def backup_hits(value, path="", historical=False):
    if isinstance(value, dict):
        for key, item in value.items():
            old = historical or key.startswith("historical_") or key.startswith("candidate_review_before_owner_")
            yield from backup_hits(item, path + "." + key, old)
    elif isinstance(value, list):
        for i, item in enumerate(value):
            yield from backup_hits(item, path + "[" + str(i) + "]", historical)
    elif isinstance(value, str) and pattern.search(unquote(value)):
        yield {"path": path, "historical": historical}
class Links(HTMLParser):
    def __init__(self): super().__init__(); self.links=[]
    def handle_starttag(self, tag, attrs):
        for key,value in attrs:
            if key in ("href","src") and value: self.links.append(value)

register_path = JOB / "canonical-master-register.json"
register = load(register_path)
before = load(JOB / "inputs/register.before")
current = {x["product_id"]:x for x in register["options"]}
prior = {x["product_id"]:x for x in before["options"]}
affected = {"BSI-C41824131174","BSI-3635E3DC3434"}
check(set(current)==set(prior) and len(current)==188,"Product identities changed")
check(len(register["components"])==112,"Component count")
check(register["components"]==before["components"],"Component definitions changed")
unchanged = []
business_fields = ["name","retained_names","canonical_key","canonical_design_id","canonical_component_id",
    "option_family_id","family","sale_unit","specifications","master_fields","selling_details",
    "current_commercial_policy","offered_fixing_choices","six_working_fields_recorded",
    "physical_specifications_verified","platform_publication_performed","confirmed_arrangement_ids"]
for key, item in current.items():
    if key not in affected: check(item==prior[key],"Unexpected option change: "+key); unchanged.append(key)
    for field in business_fields:
        check(item.get(field)==prior[key].get(field),"Business detail changed: "+key+"."+field)
sandstone=current["BSI-C41824131174"]
pewter=current["BSI-3635E3DC3434"]
check(not sandstone["image_url"] and sandstone["file_id"]=="Unbound","Sandstone still has unsupported primary")
check(sandstone["photo_coverage"]["individual"]=="No verified image","Sandstone photo state")
check(pewter["photo_coverage"]["individual"]=="Available","Pewter primary lost")
check(all(current[k]["photo_coverage"]["series"]=="No verified image" for k in affected),"Series not reopened")
counts={role:dict(collections.Counter(o["photo_coverage"][role] for o in current.values()))
        for role in ["individual","in_situ","series"]}
check(counts["individual"]=={"Available":177,"No verified image":1,"Unbound identity":1,"Group only":9},"Individual totals")
check(counts["in_situ"]=={"Available":135,"No verified image":53},"In situ totals")
check(counts["series"]=={"Optional / no fixed set":54,"Available":116,"No verified image":18},"Series totals")
source_scans=[]
for name in ["canonical-master-register.json","current-assets.json","current-native-reference-map.json",
             "guided-owner-review-state.json","image-coverage-current.json","photo-review-queue.json"]:
    path=JOB/name
    hits=list(backup_hits(load(path)))
    active=[x for x in hits if not x["historical"]]
    check(not active,"Active backup reference: "+name+" "+str(active[:2]))
    source_scans.append({"file":str(path),"sha256":sha(path),"active_backup_references":0,
                         "historical_audit_mentions":len(hits)})
html_pages=[]
csv_files=[]
for path in sorted(OUT.iterdir()):
    if path.suffix not in [".html",".csv"]: continue
    body=path.read_text()
    check(not pattern.search(unquote(body)),"Backup reference remains in report: "+path.name)
    if path.suffix==".html":
        parser=Links();parser.feed(body)
        outside=[]
        for url in parser.links:
            decoded=unquote(url)
            if re.match(r"https://www.dropbox.com/(?:home|preview)/",decoded):
                if not re.match(r"https://www.dropbox.com/(?:home|preview)/BOLDSTONE MASTER(?:/|$|\\?)",decoded):
                    outside.append(url)
        check(not outside,"Dropbox browse reference outside Master: "+path.name)
        html_pages.append({"file":str(path),"sha256":sha(path),"links":len(parser.links),"backup_references":0})
    else:
        with path.open(encoding="utf-8-sig",newline="") as handle: rows=list(csv.DictReader(handle))
        csv_files.append({"file":str(path),"sha256":sha(path),"rows":len(rows)})
def csv_rows(name):
    with (OUT/name).open(encoding="utf-8-sig",newline="") as handle:return list(csv.DictReader(handle))
expected={"Missing_Individual_Images.csv":2,"Missing_In_Situ_Images.csv":53,"Missing_Series_Images.csv":18,
          "Missing_Pictures_Required.csv":73,"Resolved_Image_Associations.csv":81,
          "Existing_Images_to_Check.csv":1}
for name, count in expected.items():check(len(csv_rows(name))==count,"CSV count: "+name)
series_rows=csv_rows("Missing_Series_Images.csv")
check(affected <= {x["option_id"] for x in series_rows},"Affected series missing from queue")
individual=csv_rows("Missing_Individual_Images.csv")
check({x["option_id"] for x in individual}=={"BSI-C41824131174","BSI-04D6E8690F30"},"Individual queue identities")
required=csv_rows("Missing_Pictures_Required.csv")
check(dict(collections.Counter(x["action_type"] for x in required))=={"Find / capture":72,"Verify existing image":1},"Required action categories")
check(len({(x["option_id"],x["role"]) for x in required})==73,"Duplicate required actions")
check(any(x["option_id"]=="BSI-04D6E8690F30" and "deferred" in x["action"].lower() for x in individual),"Frozen Fish deferral")
wall=load(CAT/"components/parallel-reviews/wall-circle-in-situ-review-2026-10-23/review-state.json")
check(wall["status"]=="DEFERRED_BY_OWNER" and not any(x["owner_approved"] for x in wall["cases"]),"Wall Circle deferral changed")
pointer=load(CAT/"current-master.json")
published=(CAT/pointer["register"]).resolve()==register_path.resolve()
if published:
    check(pointer["register_sha256"]==sha(register_path),"Published register hash")
    workbook=CAT/pointer["workbook"]
    check(pointer["workbook_sha256"]==sha(workbook),"Published workbook hash")
    for key,num in [("individual_gaps",2),("in_situ_gaps",53),("series_gaps",18),("required_actions",73)]:
        check(pointer["current_missing_picture_lists"][key]==num,"Published pointer count: "+key)
    check(not list(backup_hits(pointer.get("next_catalogue_actions",[]))),"Old active backup question in pointer")
receipt={
 "status":"PASS_PUBLISHED_DATA_AND_REPORTS" if published else "PASS_PREPARED_DATA_AND_REPORTS",
 "recorded_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
 "register":str(register_path),"register_sha256":sha(register_path),"published_pointer_matches":published,
 "options":188,"component_identities":112,"unaffected_options_unchanged":len(unchanged),
 "all_188_names_specifications_commercial_values_preserved":True,"photo_status_counts":counts,
 "individual_actions":2,"separate_individual_photo_required":1,"deferred_legacy_identity_actions":1,
 "in_situ_gaps":53,"series_gaps":18,"required_picture_actions":73,"resolved_picture_actions":81,
 "source_scans":source_scans,"html_pages_checked":html_pages,"csv_files_checked":csv_files,
 "active_backup_links":0,"historical_audit_not_reused_as_current_evidence":True,
 "wall_circle_reviews_remain_deferred":True,
 "canonical_writes":False,"dropbox_writes":False,"workbook_export_performed":False
}
path=HERE/("published-data-readback.json" if published else "prepared-data-readback.json")
path.write_text(json.dumps(receipt,indent=2)+"\n")
print(json.dumps({k:v for k,v in receipt.items() if k not in ["source_scans","html_pages_checked","csv_files_checked","photo_status_counts"]}))

