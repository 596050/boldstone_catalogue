"""Bind the Step07 file moves by stable ID, preserving all naming uncertainty."""
import copy,hashlib,importlib.util,json,posixpath,re
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urlsplit,unquote,parse_qs
from xml.etree import ElementTree as E
HERE=Path(__file__).resolve().parent;BASE=HERE.parents[2];REPORT=BASE.parent/'reports/dropbox-wall-structure-2026-10-20'
read=lambda p:json.loads(Path(p).read_text());digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
write=lambda p,d:Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
op=REPORT/'step-07-matching-current-overlay.json';sp=REPORT/'step-07-parent-crosswalk-and-match-qualifications.json'
assert digest(op)=='697684bb695cf140b165f202bda42fe55747172a492ab4425945e1305231669c'
assert digest(sp)=='e318e019fc81709ec9a5fb120855f6b6842c994124bfa20740d4ee1d85271325'
d=read(op);side=read(sp);assert all(d['verification'].values())
assert len(d['objects'])==len({x['file_id'] for x in d['objects']})==395
assert len([x for x in d['objects'] if x['object_type']=='file'])==373
for x in d['receipts'].values():assert digest(REPORT/x['path'])==x['sha256']
verification=read(REPORT/d['receipts']['verification']['path'])
assert verification['status']=='PASS_DIRECTORY_AND_VISUAL_GROUP_MATCHING' and all(verification['checks'].values())
byid={x['file_id']:x for x in d['objects']};oldpaths={x['old_display_path'].casefold():x for x in d['objects'] if x.get('old_display_path')}
for i in range(1,12):
    md=read(HERE/'inputs'/f'live-{i}.json');o=byid[md['id']]
    assert md['name']==o['current_name'] and md['path_display'].casefold()==o['current_display_path'].casefold()
    if o['object_type']=='file':assert md['size']==o['size']

def obj(url):
    if not isinstance(url,str) or not url.startswith('https://www.dropbox.com/'):return None
    u=urlsplit(url);path=unquote(u.path)
    for route in ['/home','/preview']:
        if path.startswith(route+'/'):path=path[len(route):];break
    name=parse_qs(u.query).get('preview',[''])[0]
    return oldpaths.get((path+('/'+name if name else '')).casefold())
def current_url(url):
    o=obj(url);return o['current_native_url'] if o else url

assert not (HERE/'input-manifest.json').exists()
ptr=read(BASE/'current-master.json');book=BASE/ptr['workbook'];graph=BASE/ptr['register']
assert digest(book)==ptr['workbook_sha256']=='94dac1373d7c2d6831a49eab3680b07ee630a83ad732140f2ddc9da5e5c5dd91'
assert digest(graph)==ptr['register_sha256']=='7760b44a4d52ff3b78c893d5b86ef174814b48c29f7e41814c8a01a42af5326d'
sources={'master_workbook':book,'master_register':graph,'master_pointer':BASE/'current-master.json','overlay':op,'sidecar':sp,
 'review_progress':BASE/'components/reviews/specification_review_progress.json','component_checkpoint':BASE/'components/checkpoint.json','root_checkpoint':BASE/'checkpoint.json',
 'owner_ledger':BASE/'components/reviews/user_classifications.json','source_model':BASE/'components/evidence/component_register.json'}
sources.update({k:REPORT/v['path'] for k,v in d['receipts'].items()});manifest={}
for key,p in sources.items():
    s=HERE/'inputs'/(key+'.before');s.write_bytes(p.read_bytes());manifest[key]={'path':str(p),'snapshot':str(s),'sha256':digest(p)}
write(HERE/'input-manifest.json',manifest)
g=read(graph);before=copy.deepcopy(g);changes=[]
def setv(node,path,key,value):
    if key in node and node[key]!=value:changes.append({'path':path+[key],'before':node[key],'after':value});node[key]=value
def project(node,path):
    o=byid.get(node.get('file_id')) or obj(node.get('image_url'))
    if o and o['object_type']=='file':
        parent=byid[o['current_parent_id']]
        if node.get('image_url'):setv(node,path,'image_url',o['current_native_url'])
        if node.get('folder_url'):setv(node,path,'folder_url',parent['current_native_url'])
        setv(node,path,'folder_id',o['current_parent_id'])
    else:
        for k in ['image_url','folder_url']:
            if node.get(k):setv(node,path,k,current_url(node[k]))
    ctx=byid.get(node.get('context_file_id')) or obj(node.get('context_image_url'))
    if ctx and ctx['object_type']=='file':
        parent=byid[ctx['current_parent_id']]
        if node.get('context_image_url'):setv(node,path,'context_image_url',ctx['current_native_url'])
        if node.get('context_folder_url'):setv(node,path,'context_folder_url',parent['current_native_url'])
        setv(node,path,'context_folder_id',ctx['current_parent_id'])
for key in ['options','components','aliases','source_review_reconciliation','original_specification_current_references','exceptions']:
    for i,node in enumerate(g[key]):project(node,[key,i])
for key in ['source_sets','source_offer_edges']:
    for i,node in enumerate(g[key]):project(node.get('current_primary_reference',{}),[key,i,'current_primary_reference'])
for i,node in enumerate(g['arrangement_context_references']):
    project(node,['arrangement_context_references',i])
    for j,im in enumerate(node.get('images',[])):project(im,['arrangement_context_references',i,'images',j])
scope={'status':'VERIFIED_CURRENT_PATHS_AND_PARENT_BINDINGS; INDIVIDUAL_FP_NUMBERING_PENDING','recorded_utc':datetime.now(timezone.utc).isoformat(),
 'overlay':str(op),'overlay_sha256':digest(op),'sidecar':str(sp),'sidecar_sha256':digest(sp),'summary':d['summary'],
 'file_classification_count':373,'numbered_component_crosswalk':d['numbered_component_crosswalk'],'numbering_status':side['numbering_status'],
 'visual_match_qualifications':side['visual_match_qualifications'],'graph_changes':changes,
 'guard':'Current references follow stable file IDs and current parent IDs. No individual Fingerprint1/2 assignment, new isolated-photo coverage, physical size/cast equivalence, catalogue identity, specification or platform match is inferred from folder placement.'}
g['latest_four_family_matching']=scope
restored=copy.deepcopy(g);restored.pop('latest_four_family_matching')
for c in changes:
    n=restored
    for k in c['path'][:-1]:n=n[k]
    n[c['path'][-1]]=c['before']
assert restored==before
write(HERE/'canonical-master-register.json',g)

# Read old native links without authoring any spreadsheet cells.
helper=BASE/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py'
s=importlib.util.spec_from_file_location('native_reader',helper);n=importlib.util.module_from_spec(s);s.loader.exec_module(n);old=n.load(book)
links=[]
for name,sheet in old['sheets'].items():
    loc=sheet['part'];rp=posixpath.join(posixpath.dirname(loc),'_rels',posixpath.basename(loc)+'.rels');rels={r.get('Id'):r for r in E.fromstring(old['files'][rp])}
    for h in sheet['root'].findall('.//'+n.q('hyperlink')):
        url='#'+h.get('location') if h.get('location') else rels[h.get('{'+n.R+'}id')].get('Target')
        links.append({'sheet':name,'cell':h.get('ref'),'target':url,'label':old['values'][name][h.get('ref')]})
lookup={(x['sheet'],x['cell']):x for x in links};updates={};target_changes=[]
pairs={'Master Catalogue':[('N','O','R'),('T','U',None)],'Specifications':[('J','K','M')],'Components':[('F','G','I')],
 'Sets and Context':[('I','J','L')],'Aliases':[('F','G','I')],'References and Gaps':[('F','G',None)],'Platform Sources':[('U','V','X')],
 'Source Mapping':[('H','I',None)],'Source Specifications':[('H','I',None)],
 'Photo Coverage':[('D','E','N'),('G','H','P'),('J','K','R')],'Missing Pictures':[('G','H','J')],
 'Identity Review':[('G','H','J'),('L','M','P')],'Listing Reconciliation':[('M','N','P')],
 'Listing Offer Links':[('R','S','U')],'Listing Issues':[('J','K','M')]}
original_targets={(x['sheet'],x['cell']):x['target'] for x in links}
for x in links:x['target']=current_url(x['target'])
for x in links:
    col,row=re.fullmatch(r'([A-Z]+)(\d+)',x['cell']).groups()
    if int(row)<10:continue
    o=obj(original_targets[(x['sheet'],x['cell'])])
    if not o or o['object_type']!='file':continue
    for image,folder,idcol in pairs.get(x['sheet'],[]):
        if col!=image:continue
        parent=byid[o['current_parent_id']];key=(x['sheet'],folder+row)
        if key in lookup:lookup[key]['target']=parent['current_native_url']
        if idcol:
            cell=idcol+row;value=old['values'][x['sheet']].get(cell,'')
            if value!=o['current_parent_id']:updates[(x['sheet'],cell)]={'sheet':x['sheet'],'cell':cell,'before':value,'value':o['current_parent_id'],'file_id':o['file_id'],'old_parent_id':o['old_parent_id'],'current_parent_id':o['current_parent_id']}
for x in links:
    oldtarget=original_targets[(x['sheet'],x['cell'])]
    if x['target']!=oldtarget:target_changes.append({**x,'before':oldtarget})
write(HERE/'workbook-edit-plan.json',{'cell_changes':list(updates.values()),'hyperlinks':links,'target_changes':target_changes,'graph_changes':changes,'scope':scope,
 'original_sheet_count':16,'no_name_specification_count_or_coverage_changes':True})
print(json.dumps({'status':'PREPARED','graph_reference_changes':len(changes),'native_link_updates':len(target_changes),'current_parent_ID_cells':len(updates),'numeric_names_changed':0}))
