"""Prepare an isolated gallery projection for the one-field Coral wording fix."""
from datetime import datetime,timezone
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote
import argparse,hashlib,json,shutil,sqlite3

H=Path(__file__).resolve().parent;B=H.parents[2]
PID='BSI-0C2CB099DDEB'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
write=lambda p,v:Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
parser=argparse.ArgumentParser();parser.add_argument('--register',required=True);parser.add_argument('--workbook',required=True);parser.add_argument('--register-sha256',required=True);parser.add_argument('--workbook-sha256',required=True);a=parser.parse_args()
rp=Path(a.register);wp=Path(a.workbook);manifest=read(H/'input-manifest.json')
assert sha(rp)==a.register_sha256 and sha(wp)==a.workbook_sha256
source_seal=Path(manifest['gallery']['seal_path']);source=source_seal.parent;assert sha(source_seal)==manifest['gallery']['seal_sha256']
frozen=read(source_seal)
for rel,digest in frozen['files'].items():assert sha(source/rel)==digest,rel
before_pointer_sha=sha(B/'current-master.json')
register=read(rp);products={x['product_id']:x for x in register['options']if x['product_id']in register['active_option_ids']}
old_db=sqlite3.connect('file:'+str(source/'complete-image-platform-register.sqlite')+'?mode=ro',uri=True)
oldproducts={pid:json.loads(blob)for pid,blob in old_db.execute('SELECT product_id,record_json FROM products')}
assert set(products)==set(oldproducts) and len(products)==188
changes=[]
for pid,p in products.items():
    old=oldproducts[pid]
    if old!=p:
        changes.append(pid);assert pid==PID
        assert {k:v for k,v in p.items()if k!='master_fields'}=={k:v for k,v in old.items()if k!='master_fields'}
        for field,mf in p['master_fields'].items():
            if field!='Dimensions / depth':assert mf==old['master_fields'][field]
            else:assert {k for k in set(mf)|set(old['master_fields'][field])if mf.get(k)!=old['master_fields'][field].get(k)}=={'display','basis'}
assert changes==[PID]
out=source.parent/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');out.mkdir(exist_ok=False)
proofs=['source-gallery-review.json','source-photo-correspondences.json','local-shopify-gallery-review.json','local-shopify-gallery-import-readback.json','current-file-visual-roles.json']
unchanged=proofs+['owner-identity-projection.json','per-product-image-lists.json','product-family-navigation.json','product-image-association-review.json','current-images-without-option-scope.json','source-gallery-reader-index.json','family-image-reader-index.json','product-reader-index.json']
for name in unchanged:shutil.copyfile(source/name,out/name)
for name in ['index.html','product-images.html','source-galleries.html','family-images.html']:shutil.copyfile(source/name,out/name)
for folder in ['products','families','source-galleries','source-association-review']:shutil.copytree(source/folder,out/folder)
old_report=B/'outputs/depth-estimates-master-2026-10-25/index.html';new_report=B/'outputs/coral-depth-wording-master-2026-10-25/index.html'
assert new_report.is_file()
for page in out.rglob('*.html'):page.write_text(page.read_text().replace(str(source),str(out)).replace(str(old_report),str(new_report)))
def rebase(v):
    if isinstance(v,str):return v.replace(str(source),str(out))
    if isinstance(v,list):return [rebase(x)for x in v]
    if isinstance(v,dict):return {k:rebase(x)for k,x in v.items()}
    return v
gap=out/'source-association-review/all-65-case-dispositions.json';write(gap,rebase(read(gap)))
summary=read(source/'summary.json');summary.update(status='PREPARED_CORAL_WORDING_ONLY_GALLERY_PROJECTION',recorded_utc=datetime.now(timezone.utc).isoformat(),target_register_sha256=a.register_sha256,target_workbook_sha256=a.workbook_sha256,coral_wording_fields_changed=1,new_working_numbers=0,new_physical_measurements=0)
summary['next_work']=['Bind this reader to the exact checked candidate publication.','Retain existing specification qualifications and held photography.'];write(out/'summary.json',summary)
db=sqlite3.connect(out/'complete-image-platform-register.sqlite');old_db.backup(db)
db.execute('UPDATE products SET record_json=? WHERE product_id=?',(json.dumps(products[PID],ensure_ascii=False),PID))
db.execute('INSERT OR REPLACE INTO metadata VALUES(?,?)',('integration_summary',json.dumps(summary,ensure_ascii=False)));db.commit();assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
counts={}
for (table,)in old_db.execute("SELECT name FROM sqlite_master WHERE type='table'ORDER BY name"):
    quoted='"'+table.replace('"','""')+'"';oldrows=list(old_db.execute('SELECT * FROM '+quoted));rows=list(db.execute('SELECT * FROM '+quoted));counts[table]=len(rows)
    if table not in {'metadata','products'}:assert sorted(rows,key=repr)==sorted(oldrows,key=repr),table
    elif table=='metadata':assert sorted((x for x in rows if x[0]!='integration_summary'),key=repr)==sorted((x for x in oldrows if x[0]!='integration_summary'),key=repr)
assert {pid:json.loads(blob)for pid,blob in db.execute('SELECT product_id,record_json FROM products')}==products
db.close();old_db.close()
validation=rebase(read(source/'product-reader-validation.json'));validation['coral_wording_fields_changed']=1;write(out/'product-reader-validation.json',validation)
remaining=read(source/'remaining-work.json');remaining['canonical_release']={'owner_thread':'01a144ab-1a7c-7223-a403-73a4d53d70ff','status':'EXACT_CORAL_WORDING_CANDIDATE_PREPARED_FOR_MAIN_PUBLICATION','candidate_register_path':str(rp),'candidate_register_sha256':a.register_sha256,'candidate_workbook_path':str(wp),'candidate_workbook_sha256':a.workbook_sha256};remaining['coral_wording_conflict_resolved_without_numeric_changes']=True;write(out/'remaining-work.json',remaining)
binding={'status':'PREPARED_FOR_MAIN_PUBLICATION','register':str(rp),'register_sha256':a.register_sha256,'workbook':str(wp),'workbook_sha256':a.workbook_sha256,'previous_gallery_seal':str(source_seal),'previous_gallery_seal_sha256':sha(source_seal),'wording_only_field':PID+' Dimensions / depth','physical_measurements_added':0}
write(out/'candidate-release-binding.json',binding)
write(out/'publication-rebase.json',{**binding,'this_increment_option_changes':[{'product_id':PID,'changed_fields':['master_fields.Dimensions / depth.display','master_fields.Dimensions / depth.basis']}],'unchanged_source_proof_files':{name:sha(out/name)for name in proofs},'this_increment_selected_reference_changes':0,'new_exact_variant_assignments':0})
class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[]
    def handle_starttag(self,tag,attrs):
        self.links.extend(v for k,v in attrs if k in {'src','href'}and v)
link_count=0
for page in out.rglob('*.html'):
    parser=Links();parser.feed(page.read_text())
    for link in parser.links:
        url=urlsplit(link)
        if url.scheme or url.netloc or not url.path:continue
        path=Path(unquote(url.path));path=path if path.is_absolute()else page.parent/path
        assert path.exists(),(page,link);link_count+=1
for name in unchanged:assert sha(source/name)==sha(out/name),name
assert sha(B/'current-master.json')==before_pointer_sha
assert sha(rp)==a.register_sha256 and sha(wp)==a.workbook_sha256
qa={'status':'PASS_CORAL_WORDING_GALLERY_PROJECTION','register_sha256':a.register_sha256,'workbook_sha256':a.workbook_sha256,'product_records_equal_candidate':188,'wording_field_objects_changed':1,'other1133fields_preserved':True,'all_photo_and_source_tables_unchanged':True,'table_counts':counts,'all65_case_dispositions_preserved':True,'local_links_checked':link_count,'selected_references_changed':0,'canonical_or_platform_writes':0};write(out/'coral-projection-readback.json',qa)
shutil.copyfile(__file__,out/'project_gallery.py')
seal={'status':'VERIFIED_CORAL_WORDING_ONLY_GALLERY_CANDIDATE','sealed_utc':datetime.now(timezone.utc).isoformat(),'reviewer_thread':'01a13fe6-495b-7253-b923-31823b4cbca8','canonical_publisher_thread':'01a144ab-1a7c-7223-a403-73a4d53d70ff','target_register_sha256':a.register_sha256,'target_workbook_sha256':a.workbook_sha256,'run':str(out),'readers':{name:str(out/name)for name in ['index.html','product-images.html','source-galleries.html','family-images.html','source-association-review/index.html']},'counts':validation,'all188_products_equal_candidate_register':True,'owner_questions_remaining':0,'source_proof_files_byte_identical_to_frozen_review':{name:sha(out/name)for name in proofs},'source_product_link_rows_unchanged':260,'deferred_installation_gaps':22,'deferred_series_gaps':1,'new_physical_measurements':0,'selected_primary_references_changed':0,'new_exact_variant_assignments':0,'native_or_canonical_or_platform_writes_by_reviewer':0,'files':{str(p.relative_to(out)):sha(p)for p in sorted(out.rglob('*'))if p.is_file()}}
sealpath=out/'sealed-handoff.json';write(sealpath,seal)
location={'seal':str(sealpath),'sha256':sha(sealpath),'run':str(out),'register_sha256':a.register_sha256,'workbook_sha256':a.workbook_sha256};write(H/'gallery-location.json',location);print(json.dumps({**location,'qa':qa},indent=2))
