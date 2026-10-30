"""Project the verified Azure folder renames into current native references.

The workbook was authored with artifact-tool. Its established native-hyperlink
fallback is reused for this path-only edit; no cells or calculation parts change.
"""
import copy
import hashlib
import json
import sys
import zipfile
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import quote,unquote,urlsplit,urlunsplit,parse_qs
from xml.etree import ElementTree as E
from xml.sax.saxutils import escape

HERE=Path(__file__).resolve().parent
BASE=HERE.parents[2]
REPORT=BASE.parent/'reports/dropbox-wall-structure-2026-10-20'
OVERLAY=REPORT/'step-06-azure-renames-current-overlay.json'
OVERLAY_SHA='be42403ac250cbbd5e7f447b5cb646a01bc8400387e9593724b5f5d0ffc799b3'
CONTROLS=['components/reviews/specification_review_progress.json','components/checkpoint.json','checkpoint.json','current-master.json']
read=lambda p:json.loads(Path(p).read_text())
digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.now(timezone.utc).isoformat()
relative=lambda p:str(Path(p).relative_to(BASE))
def write(p,d):
    p=Path(p);t=p.with_name(p.name+'.azure-tmp');t.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');t.replace(p)

def verified_overlay():
    assert digest(OVERLAY)==OVERLAY_SHA
    d=read(OVERLAY);assert d['status']=='PASS_CURRENT_PATH_OVERLAY'
    assert len(d['objects'])==len({x['file_id'] for x in d['objects']})==40
    assert Counter(x['object_type'] for x in d['objects'])=={'file':37,'folder':3}
    assert all(d['verification'].values())
    assert all(x['old_name']==x['current_name'] for x in d['objects'] if x['object_type']=='file')
    assert all(x['path_changed'] for x in d['objects'])
    for r in d['receipts'].values():assert digest(REPORT/r['path'])==r['sha256']
    assert read(REPORT/d['receipts']['verification']['path'])['status']=='PASS'
    objects={x['file_id']:x for x in d['objects']}
    for i,fid in enumerate(['id:cnqzTNngPVsAAAAAAAyfXA','id:cnqzTNngPVsAAAAAAAyenw','id:cnqzTNngPVsAAAAAAA5RBQ','id:cnqzTNngPVsAAAAAAAyfXg','id:cnqzTNngPVsAAAAAAAyfgw'],1):
        s=read(HERE/'inputs'/f'live-metadata-{i}.json')['structuredContent'];o=s[s['metadata_type']];x=objects[fid]
        assert o['id']==fid and o['name']==x['current_name'] and o['path_display']==x['current_display_path']
        if x['object_type']=='file':assert o['size']==x['size']
    return d

def transform(url,d):
    if not isinstance(url,str) or not url.startswith('https://www.dropbox.com/'):return url
    parts=urlsplit(url);route=next((r for r in ['/home','/preview'] if parts.path.startswith(r+'/')),None)
    if not route:return url
    path=unquote(parts.path[len(route):]);name=parse_qs(parts.query).get('preview',[''])[0]
    for m in d['prefix_maps']:
        prefix=m['old_prefix']
        if path==prefix or path.startswith(prefix+'/'):
            old_object_path=path+('/'+name if route=='/home' and name else '')
            obj=next((x for x in d['objects'] if x['old_display_path']==old_object_path),None)
            assert obj is not None,'Current hyperlink has no stable-ID overlay object: '+old_object_path
            newpath=m['current_prefix']+path[len(prefix):]
            new_object_path=newpath+('/'+name if route=='/home' and name else '')
            assert obj['current_display_path']==new_object_path
            return urlunsplit((parts.scheme,parts.netloc,route+quote(newpath,safe='/'),parts.query,parts.fragment))
    return url

def prepare():
    d=verified_overlay();assert not (HERE/'input-manifest.json').exists()
    ptr=read(BASE/'current-master.json');book=BASE/ptr['workbook'];graph=BASE/ptr['register']
    assert digest(book)==ptr['workbook_sha256']=='5c3cc206164ef91e40fdd07c3318393212a4eaad5a7236f47b5d365963a6239e'
    assert digest(graph)==ptr['register_sha256']=='91d28036a57cd18c7a210f96160992d7c6334837b11a1d89113e900dd5bd03ae'
    sources={'workbook':book,'register':graph,'overlay':OVERLAY,'owner_ledger':BASE/'components/reviews/user_classifications.json','source_model':BASE/'components/evidence/component_register.json'}
    sources.update({r:REPORT/x['path'] for r,x in d['receipts'].items()})
    sources.update({r:BASE/r for r in CONTROLS})
    manifest={}
    for i,(key,source) in enumerate(sources.items()):
        snap=HERE/'inputs'/f'{i:02d}-{source.name}.before';snap.write_bytes(source.read_bytes());manifest[key]={'source':str(source),'snapshot':str(snap),'sha256':digest(source)}
    write(HERE/'input-manifest.json',manifest)
    g=read(graph);updated=copy.deepcopy(g);changes=[]
    def project(node,path):
        for key in ['image_url','folder_url','context_image_url','context_folder_url']:
            if key not in node:continue
            after=transform(node[key],d)
            if after!=node[key]:changes.append({'path':path+[key],'before':node[key],'after':after});node[key]=after
    # Only current-reference projections change. Accepted fields, historical raw
    # URLs and sealed media/listing evidence remain exactly as originally recorded.
    for key in ['options','components','aliases','source_review_reconciliation','original_specification_current_references','exceptions']:
        for i,node in enumerate(updated[key]):project(node,[key,i])
    for key in ['source_sets','source_offer_edges']:
        for i,node in enumerate(updated[key]):project(node.get('current_primary_reference',{}),[key,i,'current_primary_reference'])
    for i,node in enumerate(updated['arrangement_context_references']):
        project(node,['arrangement_context_references',i])
        for j,im in enumerate(node.get('images',[])):project(im,['arrangement_context_references',i,'images',j])
    restored=copy.deepcopy(updated)
    for c in changes:
        node=restored
        for k in c['path'][:-1]:node=node[k]
        node[c['path'][-1]]=c['before']
    assert restored==g and changes
    azure=next(o for o in updated['options'] if o['product_id']=='BSI-3C849B547D50')
    assert azure['name']=='Azure — Blue and White Marbled Panel'
    assert azure['file_id']=='id:cnqzTNngPVsAAAAAAAyfXg' and azure['folder_id']=='id:cnqzTNngPVsAAAAAAAyenw'
    scope={'status':'APPLIED_VERIFIED_CURRENT_PATHS','recorded_utc':now(),'source_overlay':str(OVERLAY),'source_overlay_sha256':OVERLAY_SHA,
      'summary':d['summary'],'prefix_maps':d['prefix_maps'],'current_reference_changes':changes,'catalogue_identity_guard':d['catalogue_identity_guard'],
      'prior_register':ptr['register'],'prior_register_sha256':ptr['register_sha256'],'remote_writes_by_master_refresh':0,
      'fresh_readback':'Three folder IDs and the current primary/context file IDs independently read back; all five paths and both file sizes match the sealed overlay.',
      'file_content_hash_or_http_access_audit':False}
    updated['latest_azure_current_paths']=scope
    write(HERE/'canonical-master-register.json',updated)
    write(HERE/'refresh-plan.json',{'status':'PREPARED','workbook':ptr['workbook'],'old_workbook_sha256':ptr['workbook_sha256'],'graph_url_changes':changes,
       'all_non_url_graph_fields_preserved':True,'all_sealed_listing_and_image_evidence_preserved':True,'scope':scope})
    print(json.dumps({'status':'PREPARED','graph_url_changes':len(changes),'azure_name':azure['name']}))

def stage():
    d=verified_overlay();manifest=read(HERE/'input-manifest.json')
    for x in manifest.values():assert digest(x['source'])==digest(x['snapshot'])==x['sha256']
    src=Path(manifest['workbook']['snapshot']);dest=HERE/'master-workbook.pending';assert not dest.exists()
    changed=[];parts=[];external=0
    with zipfile.ZipFile(src) as before,zipfile.ZipFile(dest,'w') as out:
        for info in before.infolist():
            raw=before.read(info.filename);new=raw
            if info.filename.endswith('.rels'):
                root=E.fromstring(raw);replacements={}
                for r in root:
                    if r.get('Type','').endswith('/hyperlink'):
                        external+=1;url=r.get('Target','');after=transform(url,d)
                        if after!=url:replacements[url]=after;changed.append({'part':info.filename,'relationship_id':r.get('Id'),'before':url,'after':after})
                for url,after in replacements.items():
                    attr=lambda u:('Target="'+escape(u,{'"':'&quot;'})+'"').encode()
                    assert attr(url) in new;new=new.replace(attr(url),attr(after))
            if new!=raw:parts.append(info.filename)
            out.writestr(info,new)
    assert changed
    with zipfile.ZipFile(src) as b,zipfile.ZipFile(dest) as a:
        assert b.namelist()==a.namelist()
        for name in b.namelist():
            old,new=b.read(name),a.read(name)
            if name not in parts:assert old==new,'Unrelated workbook part changed: '+name
            else:
                r1,r2=E.fromstring(old),E.fromstring(new);assert len(r1)==len(r2)
                for x,y in zip(r1,r2):
                    expected=dict(x.attrib)
                    if expected.get('Type','').endswith('/hyperlink'):expected['Target']=transform(expected['Target'],d)
                    assert expected==y.attrib and x.tag==y.tag
        assert a.testzip() is None
        for name in a.namelist():
            if name.endswith('.rels'):
                for r in E.fromstring(a.read(name)):
                    if r.get('Type','').endswith('/hyperlink'):assert transform(r.get('Target',''),d)==r.get('Target','')
    g=read(HERE/'canonical-master-register.json');old=read(manifest['register']['snapshot']);plan=read(HERE/'refresh-plan.json')
    restored=copy.deepcopy(g);restored.pop('latest_azure_current_paths')
    for c in plan['graph_url_changes']:
        node=restored
        for k in c['path'][:-1]:node=node[k]
        node[c['path'][-1]]=c['before']
    assert restored==old
    for key in ['summary','original_review_specification_assertions','current_listing_source_links','current_listing_match_evidence','current_listing_issues','latest_listing_reconciliation','latest_image_coverage_audit']:
        assert g[key]==old[key]
    assert all(a['master_fields']==b['master_fields'] and (a['product_id'],a['name'])==(b['product_id'],b['name']) for a,b in zip(g['options'],old['options']))
    prior=read(BASE/'current-master.json');previous=BASE/prior['latest_listing_reconciliation']['verification']
    assert read(previous)['status']=='PASS'
    result={'status':'PASS','recorded_utc':now(),'workbook_sha256':digest(dest),'register_sha256':digest(HERE/'canonical-master-register.json'),
       'old_workbook_sha256':manifest['workbook']['sha256'],'old_register_sha256':manifest['register']['sha256'],
       'source_overlay_sha256':OVERLAY_SHA,'changed_native_link_destinations':len(changed),'changed_archive_parts':parts,'changes':changed,
       'external_native_hyperlink_relationships':external,'native_hyperlinks':read(previous)['native_hyperlinks'],'formula_count':read(previous)['formula_count'],
       'all_cell_formula_cache_style_table_pane_calc_and_other_parts_byte_identical':True,'all_non_url_graph_fields_preserved':True,
       'all184_options_and1104_current_fields_and_listing_media_audits_preserved':True,'no_old_azure_prefix_in_current_native_links':True,
       'previous_workbook_verification':str(previous),'previous_workbook_verification_sha256':digest(previous),
       'visual_and_calculation_verification':'Prior verified views and formula results reused. Every worksheet,cell,style,formula,cache and calculation part is byte-identical; only native hyperlink destinations changed.',
       'current_azure_metadata_readbacks':5,'remote_writes':0,'file_hash_or_http_access_audit':False}
    write(HERE/'saved-file-verification.json',result)
    print(json.dumps({'status':'PASS','native_destinations_updated':len(changed),'changed_relationship_parts':len(parts),'all_worksheet_parts_byte_identical':True,'workbook_sha256':result['workbook_sha256']}))

def publish():
    manifest=read(HERE/'input-manifest.json');check=read(HERE/'saved-file-verification.json');assert check['status']=='PASS'
    for x in manifest.values():assert digest(x['source'])==x['sha256']
    pending=HERE/'master-workbook.pending';assert digest(pending)==check['workbook_sha256']
    assert digest(HERE/'canonical-master-register.json')==check['register_sha256']
    ptr=copy.deepcopy(read(BASE/'current-master.json'));g=read(HERE/'canonical-master-register.json')
    ptr.update(recorded_utc=now(),workbook_sha256=check['workbook_sha256'],register=relative(HERE/'canonical-master-register.json'),register_sha256=check['register_sha256'],publication_receipt=relative(HERE/'publication-receipt.json'))
    ptr['current_path_scope']+='; three approved Azure folder renames retaining Wall Panel'
    ptr['latest_path_refresh']={'scope':'Azure family and two child-folder native reference URLs','source_overlay_sha256':OVERLAY_SHA,
      'native_link_destinations_updated':check['changed_native_link_destinations'],'verification':relative(HERE/'saved-file-verification.json'),
      'verification_sha256':digest(HERE/'saved-file-verification.json'),'all_cells_formulas_and_visuals_unchanged':True,'remote_writes':0}
    updates={}
    for f in CONTROLS[:-1]:
        d=read(BASE/f);d['current_master_catalogue']=copy.deepcopy(ptr);d['current_master_workbook']=ptr['workbook'];d['current_master_register']=ptr['register'];d['updated_utc']=now();d['latest_azure_current_paths']=copy.deepcopy(ptr['latest_path_refresh'])
        if f=='components/checkpoint.json':d['current_master_validation']={'path':relative(HERE/'saved-file-verification.json'),'sha256':digest(HERE/'saved-file-verification.json')}
        updates[f]=d
    write(HERE/'export-receipt.json',{'status':'PASS','recorded_utc':now(),'workbook':ptr['workbook'],'workbook_sha256':ptr['workbook_sha256'],'register':ptr['register'],'register_sha256':ptr['register_sha256'],
      'native_link_destinations_updated':check['changed_native_link_destinations'],'verification':relative(HERE/'saved-file-verification.json'),'cell_and_calculation_parts_byte_identical':True})
    target=BASE/ptr['workbook'];pending.replace(target)
    for f,d in updates.items():write(BASE/f,d)
    write(BASE/'current-master.json',ptr)
    assert digest(target)==ptr['workbook_sha256'] and read(BASE/'current-master.json')==ptr
    for f in updates:assert read(BASE/f)['current_master_catalogue']==ptr
    for key in ['owner_ledger','source_model','register','overlay']:
        assert digest(manifest[key]['source'])==manifest[key]['sha256']
    result={'status':'PASS_PUBLISHED_AND_READ_BACK','recorded_utc':now(),'workbook':str(target),'workbook_sha256':digest(target),
      'register':str(HERE/'canonical-master-register.json'),'register_sha256':ptr['register_sha256'],'verification':relative(HERE/'saved-file-verification.json'),
      'source_overlay_sha256':OVERLAY_SHA,'native_link_destinations_updated':check['changed_native_link_destinations'],
      'all184_options_1104fields_media_and_listing_evidence_preserved':True,'prior_register_and_workbook_snapshot_preserved':True,
      'current_master_pointer_sha256':digest(BASE/'current-master.json'),'controls_sha256':{f:digest(BASE/f) for f in updates},'remote_writes':0}
    write(HERE/'publication-receipt.json',result)
    write(HERE/'completion.json',{'status':'COMPLETE_AZURE_CURRENT_REFERENCE_REFRESH','recorded_utc':now(),'publication_receipt':relative(HERE/'publication-receipt.json'),
       'azure_catalogue_name':'Azure — Blue and White Marbled Panel','new_family_folder':'Wall Panel Azure','catalogue_name_or_specification_changes':0,
       'native_link_destinations_updated':check['changed_native_link_destinations'],'workbook_sha256':ptr['workbook_sha256'],'register_sha256':ptr['register_sha256']})
    print(json.dumps({k:result[k] for k in ['status','native_link_destinations_updated','workbook_sha256','register_sha256']}))

if __name__=='__main__':{'prepare':prepare,'stage':stage,'publish':publish}[sys.argv[1]]()
