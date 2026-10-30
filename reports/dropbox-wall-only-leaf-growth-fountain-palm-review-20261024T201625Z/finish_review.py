import csv
import hashlib
import html
import json
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import quote,unquote,urlsplit,parse_qs

P=Path(__file__).resolve().parent
ROOT=Path('/Users/tprice/Documents/boldstone')
SCOPE='/BOLDSTONE MASTER/Products/01 Wall Sculptures'
FAMILIES=[('Leaf Growth','leaf-growth'),('Fountain Palm','fountain-palm')]
def read(path):return json.loads(Path(path).read_text())
def write(name,data):(P/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def fq(path):return path.split('/',1)[1] if path.startswith('ns:') else path
def home(path):return 'https://www.dropbox.com/home'+quote(path,safe='/')
def image_identity(url):
    u=urlsplit(url)
    assert u.scheme=='https' and u.netloc=='www.dropbox.com'
    if u.path.startswith('/preview/'):
        return unquote(u.path[len('/preview'):])
    assert u.path.startswith('/home/')
    return unquote(u.path[len('/home'):])+'/'+parse_qs(u.query)['preview'][0]

before=read(P/'fresh-complete-native-listings.json');closing=read(P/'fresh-closing-native-listings.json')
for b,a in zip(before['listings'],closing['listings']):
    assert b['name']==a['name'] and not b['result']['has_more'] and not a['result']['has_more']
    assert {r['file_id']:r for r in b['result']['entries']}=={r['file_id']:r for r in a['result']['entries']}
rows=[];byfamily={}
for family,slug in FAMILIES:
    rr=read(P/(slug+'-verified-originals-and-links.json'));byfamily[family]={r['review_index']:r for r in rr};rows+=rr
assert len(rows)==len({r['id'] for r in rows})==316
assert sum(r['size'] for r in rows)==2853284180
nativehash={r['id']:r for r in read(P/'fresh-native-hash-metadata.json')}
for r in rows:
    assert r['content_hash']==r['dropbox_content_hash']==nativehash[r['id']]['content_hash']
    assert Path(r['local_path']).stat().st_size==r['size']==nativehash[r['id']]['size']
    assert r['folder_path'].startswith(SCOPE+'/')
    assert r['folder_url']==home(r['folder_path']) and r['image_url']==home(r['folder_path'])+'?preview='+quote(r['name'],safe='')

protected=read(P/'protected-catalogue-references-before.json')
pointerpath=ROOT/'sculpture-catalogue/current-master.json';pointer=read(pointerpath);regpath=ROOT/'sculpture-catalogue'/pointer['register'];register=read(regpath)
options={o['product_id']:o for o in register['options']};byid={r['id']:r for r in rows}
selected_ids={o[k] for o in protected['options'] for k in ['file_id','context_file_id'] if o.get(k)}
equivalent_url_forms=[]
for o in protected['options']:
    assert options[o['product_id']]==o
    for prefix in ['', 'context_']:
        if not o.get(prefix+'file_id'):continue
        r=byid[o[prefix+'file_id']]
        assert o[prefix+'folder_id']==r['folder_id'] and o[prefix+'folder_url']==r['folder_url']
        assert image_identity(o[prefix+'image_url'])==r['path_display']==image_identity(r['image_url'])
        if o[prefix+'image_url']!=r['image_url']:
            equivalent_url_forms.append({'product_id':o['product_id'],'role':prefix or 'primary','file_id':r['id'],'native_path':r['path_display'],'catalogue_url_preserved':o[prefix+'image_url'],'equivalent_review_url':r['image_url']})
metadata=read(P/'fresh-protected-files-and-family-roots-metadata.json')['metadata'];native_selected={x['file']['id']:x['file'] for x in metadata if x['metadata_type']=='file'}
assert set(native_selected)==selected_ids and len(selected_ids)==8
for fid,m in native_selected.items():
    r=byid[fid];assert m['name']==r['name'] and m['size']==r['size'] and m['path_display']==r['path_display']
write('protected-catalogue-reference-closing-check.json',{'recorded_utc':datetime.now(timezone.utc).isoformat(),'register':str(regpath),'register_sha256':sha(regpath),'all_five_full_option_records_unchanged':True,'eight_distinct_selected_native_file_identity_and_URL_pairs_verified':True,'equivalent_preview_and_home_route_forms':equivalent_url_forms,'canonical_writes_by_this_review':0,'no_photo_or_specification_requests_added':True})

findings=[]
def finding(code,family,indices,observation,next_step,kind='REVIEW_OBSERVATION_NO_MOVE_APPROVAL'):
    rr=[byfamily[family][i] for i in indices]
    findings.append({'id':code,'family':family,'status':kind,'observation':observation,'next_step':next_step,'images':[{**{k:r[k] for k in ['review_index','id','name','folder_id','folder_path','folder_url','image_url','sha256']},'selected_catalogue_photo':r['id'] in selected_ids} for r in rr]})
finding('LEAF-GROWTH-01','Leaf Growth',list(range(66,80))+list(range(81,89)),
    '22 close product/detail photographs are filed in Leaf Growth White In Situ:003–016.jpg,018–020.jpg and021–025.jpeg.',
    'Candidates for the existing Leaf Growth White product folder. An exact move plan and owner decision are still required; no moves are included in this read-only review.')
finding('LEAF-GROWTH-02','Leaf Growth',[64,65,80],
    'Three wider display-board views remain in In Situ:001.jpg,002.jpg and017.jpg. The selected catalogue context001.jpg is one of these.',
    'Retain these wider setting references and their selected context binding.',kind='RETAIN_CURRENT_FILING')
finding('LEAF-GROWTH-03','Leaf Growth',[16,17,18,19,20,60,61,63],
    'Portrait and landscape photographs are kept under the existing Leaf Growth White option. Orientation is not used to infer additional component identities.',
    'Retain existing identity and finish names; no new component number or physical stock count is inferred.',kind='RETAIN_CURRENT_IDENTITY')
finding('FOUNTAIN-PALM-01','Fountain Palm',[70,79],
    'Two close product photographs,002.jpg and079.jpg, are filed in Fountain Palm Egyptian Bronze Verdigris In Situ.',
    'Candidates for the existing Fountain Palm Egyptian Bronze Verdigris product folder. The selected context082.jpg remains unchanged. No move has been proposed for approval or applied here.')
finding('FOUNTAIN-PALM-02','Fountain Palm',list(range(156,162))+list(range(167,181))+[204,205],
    '22 wider brick-wall product-folder views need a filing decision:Egyptian White073–078.jpg,084–097.jpg and121–122.jpg. Intermediate close framings remain unchanged.',
    'Review these exact images for a later In Situ filing plan. An Egyptian White In Situ folder does not currently exist; no new folder has been created.')
finding('FOUNTAIN-PALM-03','Fountain Palm',[91,92],
    'Egyptian White008.jpg and009.jpg show a panel supported above a bucket, with hoses visible. This is setup/testing evidence rather than a clearly finished installation.',
    'Keep both originals in place pending a specific filing decision; do not infer an approved installation or move them outside Wall Sculptures.',kind='UNRESOLVED_CONTEXT_RETAIN_CURRENT_FILING')
finding('FOUNTAIN-PALM-04','Fountain Palm',[211,212],
    'Both joint White photographs show the Egyptian and Mediterranean designs together. The folder already repeats both full component names;002.jpg is the selected shared catalogue context.',
    'Retain the joint folder and selected context; the individual Egyptian and Mediterranean folders remain separate.',kind='RETAIN_EXISTING_ARRANGEMENT_AND_COMPONENTS')
write('review-observations.json',findings)
obs_by_id={}
for f in findings:
    for r in f['images']:obs_by_id.setdefault(r['id'],[]).append(f['id'])
decisions=[{**{k:r[k] for k in ['family','review_index','id','name','folder_id','folder_path','folder_url','image_url']},'reviewed_visually':True,'native_action':'NONE','observation_ids':obs_by_id.get(r['id'],[]),'selected_catalogue_photo':r['id'] in selected_ids,'disposition':'OBSERVATION_RECORDED_NO_MUTATION' if r['id'] in obs_by_id else 'RETAIN_CURRENT_FILING_NO_EXACT_CHANGE_PROPOSED'} for r in rows]
write('all-316-image-folder-links-and-review.json',decisions)
with (P/'all-316-image-folder-links.tsv').open('w',newline='') as f:
    out=csv.DictWriter(f,fieldnames=['family','review_index','id','name','folder_path','folder_url','image_url','disposition'],delimiter='\t',extrasaction='ignore');out.writeheader();out.writerows(decisions)

style='<meta charset="utf-8"><style>body{font:16px system-ui;max-width:1300px;margin:30px auto;padding:0 20px;line-height:1.5}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}article{padding:12px;border:1px solid #ccc}img{width:100%;height:240px;object-fit:contain;background:#eee}a{overflow-wrap:anywhere}</style>'
e=html.escape
parts=[style,'<title>Leaf Growth and Fountain Palm — complete filing review</title><h1>316 originals reviewed; no Dropbox changes</h1><p>Leaf Growth97images and Fountain Palm219images. All original bytes were checked against fresh native content hashes. The findings below are observations for later filing decisions, not approved moves. All selected catalogue photographs and five full option records are unchanged.</p>']
for family,slug in FAMILIES:parts.append('<p><a href="'+slug+'-all-image-folder-links.html">All '+str(len(byfamily[family]))+' '+e(family)+' images and containing folders</a></p>')
for f in findings:
    slug=next(s for family,s in FAMILIES if family==f['family'])
    parts.extend(['<h2>'+e(f['id'])+'</h2><p>'+e(f['observation'])+'</p><p>'+e(f['next_step'])+'</p><div class="grid">'])
    for r in f['images']:parts.append('<article><a href="'+e(r['image_url'])+'"><img loading="lazy" src="thumbnails/'+slug+'/'+str(r['review_index']).zfill(3)+'.jpg"></a><p><a href="'+e(r['image_url'])+'">'+e(r['name'])+'</a><br><a href="'+e(r['folder_url'])+'">Containing folder</a></p>'+('<strong>Selected catalogue reference — unchanged</strong>' if r['selected_catalogue_photo'] else '')+'</article>')
    parts.append('</div>')
(P/'review-findings-and-all-family-links.html').write_text(''.join(parts))

priorpath=ROOT/'reports/dropbox-echo-sound-23-approved-moves-20261024T191800Z/combined-thirty-three-family-current-image-folder-links.json'
old=read(priorpath);merged={r['file_id']:r for r in old};overlap=[]
for r in rows:
    if r['id'] in merged:overlap.append({'file_id':r['id'],'prior_role':merged[r['id']]['role'],'family':r['family']})
    merged[r['id']]={'role':'source','family':r['family'],'file_id':r['id'],**{k:r[k] for k in ['name','size','folder_id','folder_path','folder_url','image_url','sha256','dropbox_content_hash']}}
cumulative=sorted(merged.values(),key=lambda r:(r['family'],r['folder_path'],r['name']))
write('combined-thirty-five-family-current-image-folder-links.json',cumulative)
accounting={'prior_manifest':str(priorpath),'prior_manifest_sha256':sha(priorpath),'new_whole_families':2,'new_originals':316,'prior_overlap':overlap,
    'whole_source_families':len({r['family'] for r in cumulative if r['role']=='source'}),'whole_source_originals':sum(r['role']=='source' for r in cumulative),'comparison_only_originals':sum(r['role']!='source' for r in cumulative),'distinct_original_references':len(cumulative),
    'freshness_note':'Only Leaf Growth and Fountain Palm were freshly inventoried and reviewed here. Earlier family references retain dated captures and approved move overlays; this is not a fresh whole-library inventory.','not_a_unique_design_or_physical_stock_count':True}
assert accounting['whole_source_families']==35 and accounting['whole_source_originals']==1753 and accounting['comparison_only_originals']==8 and len(cumulative)==1761
write('cumulative-link-accounting.json',accounting)
summary={'recorded_utc':datetime.now(timezone.utc).isoformat(),'status':'READ_ONLY_WHOLE_FAMILY_REVIEW_COMPLETE','native_scope':SCOPE,'native_writes':0,'canonical_writes':0,'originals':316,'original_bytes':2853284180,'fresh_http_original_downloads':sum(not r['reused_native_identical_local_bytes'] for r in rows),'actual_existing_originals_rehashed_against_fresh_native_hashes':sum(r['reused_native_identical_local_bytes'] for r in rows),'native_descendant_objects_unchanged':324,'contact_boards_visually_reviewed':16,'full_option_records_unchanged':5,'selected_native_file_identities_verified':8,'native_metadata_objects_verified':10,
    'families':{family:{'files':len(rr),'bytes':sum(r['size'] for r in rr.values()),'folders':len({r['folder_id'] for r in rr.values()})} for family,rr in byfamily.items()},
    'observations_are_not_move_approval':True,'no_new_missing_photo_or_physical_specification_questions':True,'Bone_Spiral_combined_40_and_Chiswick_015_remain_pending_unapplied':True,'Echo_23_native_and_catalogue_complete_not_repeated':True,'cumulative_accounting':accounting}
assert summary['fresh_http_original_downloads']==297 and summary['actual_existing_originals_rehashed_against_fresh_native_hashes']==19
write('validation.json',summary)
excluded={'review-seal.json','coordination-followup.json'}
paths=[x for x in P.rglob('*') if x.is_file() and x.name not in excluded and 'originals' not in x.relative_to(P).parts]
write('review-seal.json',{'recorded_utc':datetime.now(timezone.utc).isoformat(),'status':'SEALED_READ_ONLY_REVIEW','receipt_count':len(paths),'files':[{'path':str(x.relative_to(P)),'size':x.stat().st_size,'sha256':sha(x)} for x in sorted(paths)],'large_originals_bound_by':'leaf-growth-verified-originals-and-links.json and fountain-palm-verified-originals-and-links.json','excluded_mutable_followup':['coordination-followup.json'],'native_writes':0})
print(json.dumps(summary,indent=2));print('REVIEW_SEAL_SHA256',sha(P/'review-seal.json'));print('SEALED_RECEIPTS',len(paths))
