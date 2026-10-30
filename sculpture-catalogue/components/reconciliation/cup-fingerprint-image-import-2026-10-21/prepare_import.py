"""Prepare a bounded image/identity addendum against the current master."""
import collections, copy, csv, hashlib, importlib.util, json, math, posixpath, re, shutil
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import unquote, urlparse, parse_qs
from xml.etree import ElementTree as E

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]
ROOT = BASE.parent
read = lambda p: json.loads(Path(p).read_text())
digest = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
now = lambda: datetime.now(timezone.utc).isoformat()
def write(p, d):
    Path(p).write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
spec = importlib.util.spec_from_file_location('native_support', BASE/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py')
v = importlib.util.module_from_spec(spec); spec.loader.exec_module(v)
ptr = read(BASE/'current-master.json')
sources = {
 'master_workbook': BASE/ptr['workbook'], 'master_register': BASE/ptr['register'],
 'master_pointer': BASE/'current-master.json',
 'review_progress': BASE/'components/reviews/specification_review_progress.json',
 'component_checkpoint': BASE/'components/checkpoint.json', 'root_checkpoint': BASE/'checkpoint.json',
 'owner_ledger': BASE/'components/reviews/user_classifications.json',
 'source_model': BASE/'components/evidence/component_register.json',
 'prior_audit': BASE/ptr['latest_image_coverage_audit']['audit'],
 'cup_seal': BASE/'components/reconciliation/image-identity-resolution-2026-10-21-b/SEAL.json',
 'cup_addendum': BASE/'components/reconciliation/image-identity-resolution-2026-10-21-b/IMAGE_IDENTIFICATION_ADDENDUM.json',
 'fingerprint_addendum': ROOT/'reports/dropbox-fingerprint-numbering-2026-10-21/numbering-source-addendum.json',
 'fingerprint_bindings': ROOT/'reports/dropbox-fingerprint-numbering-2026-10-21/source-native-bindings.json',
 'fingerprint_downloads': ROOT/'reports/dropbox-fingerprint-numbering-2026-10-21/source-download-receipt.json',
 'component_organisation_audit': ROOT/'reports/dropbox-component-organisation-2026-10-21/component-organisation-audit.json',
 'native_metadata': HERE/'fresh-native-metadata.json'
}
assert digest(sources['master_workbook']) == ptr['workbook_sha256']
assert digest(sources['master_register']) == ptr['register_sha256']
assert digest(sources['cup_seal']) == 'd3114c3ddd14f959ec8f8b222bab2e6f748e843de4a6b695912b2dc2d0e41ec4'
assert digest(sources['cup_addendum']) == '97bccf540c85092b5e5032eb4b8bc83149c61d83b1dd9b17e5de2ca6d01041cf'
assert digest(sources['fingerprint_addendum']) == 'e835bab9b4d9ea63b64661191a21f56898bcd195667876eb68b3a15e9c13d927'
assert digest(sources['fingerprint_bindings']) == '51eb75e3da3dfc5b383b2f36add2997c334d4913f23c89e7cd0d90a328d879c3'
assert digest(sources['component_organisation_audit']) == '90672baf977bd77801fb264b676b8c80f2153f3ecafe7e2f2d7c6aca733c369e'
for x in read(sources['cup_seal'])['files']:
    assert digest(x['path']) == x['sha256'] and Path(x['path']).stat().st_size == x['bytes']
def dbhash(p):
    acc = hashlib.sha256()
    with Path(p).open('rb') as f:
        while chunk := f.read(4*1024*1024): acc.update(hashlib.sha256(chunk).digest())
    return acc.hexdigest()
for x in read(sources['fingerprint_downloads'])['sources']:
    assert digest(x['local_path']) == x['sha256'] and dbhash(x['local_path']) == x['content_hash']
manifest = {}
for key, p in sources.items():
    dest = HERE/'inputs'/f'{key}.before'
    if dest.exists():
        assert digest(dest)==digest(p),f'Prepared input drift: {p}'
    else:
        shutil.copy2(p, dest)
    manifest[key] = {'path': str(p), 'snapshot': str(dest), 'sha256': digest(p)}
write(HERE/'input-manifest.json', manifest)
g = read(sources['master_register']); oldg = copy.deepcopy(g)
audit = read(sources['prior_audit']); oldaudit = copy.deepcopy(audit)
add = read(sources['cup_addendum']); cup = add['cup_ring']; image = cup['historical_complete_image']
assert digest(image['local_path']) == image['sha256'] and dbhash(image['local_path']) == image['content_hash']
fp = read(sources['fingerprint_addendum']); bindings = read(sources['fingerprint_bindings'])
live = {x['id']: x for x in read(sources['native_metadata'])}
assert live[image['id']]['path_display'] == image['path_display'] and live[image['id']]['size'] == image['size']
assert live[image['folder_id']]['path_display'] == image['folder_path']
for x in bindings['sources']:
    z = live[x['file_id']]
    assert (z['path_display'], z['size'], z['rev']) == (x['path'], x['size'], x['rev'])
assert live[bindings['parent']['file_id']]['path_display'] == bindings['parent']['path']
b = v.load(sources['master_workbook'])
def links_from(book):
    result = {}
    for sn, info in book['sheets'].items():
        loc = info['part']; rp = posixpath.join(posixpath.dirname(loc), '_rels', posixpath.basename(loc)+'.rels')
        rs = {x.get('Id'): x for x in E.fromstring(book['files'][rp])} if rp in book['files'] else {}
        for h in info['root'].findall('.//'+v.q('hyperlink')):
            target = '#'+h.get('location') if h.get('location') else rs[h.get('{'+v.R+'}id')].get('Target')
            result[(sn, h.get('ref'))] = {'sheet': sn, 'cell': h.get('ref'), 'label': book['values'][sn].get(h.get('ref'), ''), 'target': target}
    return result
links = links_from(b)
changes = {}
def setcell(sn, cell, value):
    old = b['values'][sn].get(cell, '')
    if old != value: changes[(sn,cell)] = {'sheet':sn, 'cell':cell, 'before':old, 'value':value}
def setlink(sn, cell, target, label=None):
    prior = links.get((sn,cell))
    label = label or (prior['label'] if prior else 'Source reference')
    links[(sn,cell)] = {'sheet':sn, 'cell':cell, 'target':target, 'label':label}
    setcell(sn,cell,label)
def row_for(sn, col, value):
    out=[i for i in range(10,1500) if b['values'][sn].get(col+str(i)) == value]
    assert len(out)==1,(sn,value,out)
    return out[0]
pid = cup['product_id']; o = next(x for x in g['options'] if x['product_id']==pid)
prior_ref = {k:o.get(k) for k in ['file_id','folder_id','image_url','folder_url','image_role','current_link_basis']}
ref = {'file_id':image['id'],'folder_id':image['folder_id'],'name':image['name'], 'path':image['path'],
       'image_url':image['image_url'],'folder_url':image['folder_url'],'review_label':'HISTORICAL_EDITED_ISOLATED_453PX'}
qualifier = 'Historical edited website image, 453 × 453 pixels: complete isolated White Ring design reference. Current cast, exact size and current finish batch unverified; archive filename does not renumber CRS2.'
readiness = 'Six working specifications recorded. A complete isolated historical edited image is now linked (453 × 453 pixels); high-resolution/current-cast photography remains desirable. Cast measurements, hardware/load, stock and lead time remain unverified.'
for k in ['file_id','folder_id','image_url','folder_url']: o[k]=ref[k]
o.update(image_role='Complete isolated historical edited catalogue image', current_link_basis='Native archive ID/path rechecked 21 October; downloaded bytes/hash and complete geometry reviewed', readiness_note=readiness)
o['photo_coverage']['individual']='Available'
o['current_image_resolution']={'status':'HISTORICAL_COMPLETE_ISOLATED_REFERENCE_FOUND','reference':ref,'qualification':qualifier,'prior_primary':prior_ref,
 'paired_reference_retained_as_series':cup['current_paired_reference'],'source_addendum':str(sources['cup_addendum']),'source_sha256':manifest['cup_addendum']['sha256']}
o['remaining_evidence_gaps'][0]='High-resolution/current-cast Ring photograph if required; historical complete isolated catalogue reference is now available'
component = next(x for x in g['components'] if x['component_id']=='BC-CR-RING')
for k in ['file_id','folder_id','image_url','folder_url']: component[k]=ref[k]
component['current_image_resolution']=copy.deepcopy(o['current_image_resolution'])
cr=row_for('Components','A','BC-CR-RING')
setlink('Components','F'+str(cr),ref['image_url'],'Historical isolated image')
setlink('Components','G'+str(cr),ref['folder_url'])
setcell('Components','H'+str(cr),ref['file_id']);setcell('Components','I'+str(cr),ref['folder_id'])
main=row_for('Master Catalogue','A',pid)
setlink('Master Catalogue',f'N{main}',ref['image_url'],'Historical isolated image')
setlink('Master Catalogue',f'O{main}',ref['folder_url'])
for c,k in [('Q','file_id'),('R','folder_id')]:setcell('Master Catalogue',c+str(main),ref[k])
setcell('Master Catalogue','V'+str(main),readiness)
for i in range(10,1114):
    if b['values']['Specifications'].get('A'+str(i)) == pid:
        setlink('Specifications','J'+str(i),ref['image_url'],'Historical isolated image');setlink('Specifications','K'+str(i),ref['folder_url'])
        setcell('Specifications','L'+str(i),ref['file_id']);setcell('Specifications','M'+str(i),ref['folder_id'])
pc=row_for('Photo Coverage','A',pid)
setcell('Photo Coverage','C'+str(pc),'Available')
for c,k in [('D','image_url'),('E','folder_url')]:setlink('Photo Coverage',c+str(pc),ref[k])
for c,k in [('M','file_id'),('N','folder_id')]:setcell('Photo Coverage',c+str(pc),ref[k])
setcell('Photo Coverage','L'+str(pc),'No exact wider room/garden view verified.\nWhite pair retained as series context; no pair dimensions/price assigned to the component.\n'+qualifier)
setcell('Photo Coverage','S'+str(pc),'All current Cup Ring family files and historical website archive sources reviewed; processed coloured references are not assigned as physical finish options.')
setcell('Photo Coverage','T'+str(pc),'Historical Photoshop website export; present cast and capture provenance unverified')
mr=next(i for i in range(10,221) if b['values']['Missing Pictures'].get('B'+str(i))==pid and b['values']['Missing Pictures'].get('D'+str(i))=='Individual')
setcell('Missing Pictures','F'+str(mr),'Resolved: complete isolated White Ring catalogue image found in the historical website source archive. High-resolution/current-cast photography remains desirable.')
for c,k in [('G','image_url'),('H','folder_url')]:setlink('Missing Pictures',c+str(mr),ref[k])
for c,k in [('I','file_id'),('J','folder_id')]:setcell('Missing Pictures',c+str(mr),ref[k])
setcell('Missing Pictures','K'+str(mr),'21 October archive image addendum; previous Group only action retained as dated history')
setcell('Missing Pictures','L'+str(mr),qualifier);setcell('Missing Pictures','N'+str(mr),'Resolved')
ir=row_for('Identity Review','A','ID-CUP-RING')
setcell('Identity Review','E'+str(ir),'Identity retained; historical isolated image found')
setcell('Identity Review','F'+str(ir),qualifier+' New ChatGPT-labelled coloured references have unverified edit/generation provenance and physical finish.')
for c,k in [('G','image_url'),('H','folder_url')]:setlink('Identity Review',c+str(ir),ref[k])
for c,k in [('I','file_id'),('J','folder_id')]:setcell('Identity Review',c+str(ir),ref[k])
pair=cup['current_paired_reference']
for c,k in [('L','image_url'),('M','folder_url')]:setlink('Identity Review',c+str(ir),pair[k])
for c,k in [('N','file_id'),('P','folder_id')]:setcell('Identity Review',c+str(ir),pair[k])
ffl=row_for('Identity Review','A','ID-FROZEN-FISH-LONG')
setcell('Identity Review','F'+str(ffl),'Exact 100 × 22 cm photograph remains unbound. Maker sources reuse one picture for 70 × 15 and 100 × 22 cm; the July email explicitly supports the 70 × 15 cm terracotta panel. Identify a file showing a measured 100 × 22 cm cast. Proportions and fin count do not establish the actual size or geometry parent.')
for sn,cols in [('Draft Listings',('I','J','K','L')),('Listing Resolution',('R','S','T','U'))]:
    i=row_for(sn,'A',pid);a,c,e,f=cols
    setlink(sn,a+str(i),ref['image_url']);setlink(sn,c+str(i),ref['folder_url'])
    setcell(sn,e+str(i),ref['file_id']);setcell(sn,f+str(i),ref['folder_id'])
    if sn=='Draft Listings':
        setcell(sn,'N'+str(i),'No individual native record supported in the checked public/export scope. Current image supersession: historical complete isolated edited reference available, 453 × 453 pixels; present cast/finish unverified.')
        setcell(sn,'P'+str(i),qualifier+' Earlier Group only limitation is retained in the sealed source packet as dated history.')
# Source compositions are a separate additive layer, never member renumbering.
source_note='Source composition 2 contains both accepted Left and Right components. Numbers 1/2 label whole pattern-inspiration compositions; individual member numbers and physical mould codes are not established.'
source1_note='Norwich PDF page 1 labels this whole rough/offset paired composition 1. The number does not identify either member, confirm unique moulds or establish a physical cast.'
source_pdf=bindings['sources'][0];source_folder=bindings['parent']
for comp in g['components']:
    if comp['component_id'] in ['BC-FP-LEFT','BC-FP-RIGHT']:
        comp['source_composition_attribution']={'source_composition_number':'2','number_scope':'Whole proposed composition','individual_member_number':None,'native_source':source_pdf,'note':source_note}
        i=row_for('Components','A',comp['component_id'])
        setcell('Components','E'+str(i),b['values']['Components']['E'+str(i)]+'\n'+source_note)
for opt in g['options']:
    if opt['canonical_component_id'] in ['BC-FP-LEFT','BC-FP-RIGHT']:
        opt['source_composition_attribution']={'source_composition_number':'2','individual_member_number':None,'native_source':source_pdf,'note':source_note}
        i=row_for('Master Catalogue','A',opt['product_id']);prior=b['values']['Master Catalogue'].get('V'+str(i),'')
        setcell('Master Catalogue','V'+str(i),(prior+'\n' if prior else '')+source_note+' Source PDF is linked in Identity Review, rough-concentric rows.')
for i in [60,61]:
    assert b['values']['Identity Review'].get('I'+str(i))=='id:cnqzTNngPVsAAAAAAAyhPw'
    setcell('Identity Review','F'+str(i),b['values']['Identity Review']['F'+str(i)]+'\n'+source1_note+' '+source_note)
    setlink('Identity Review','L'+str(i),source_pdf['current_native_url'],'Source PDF, page 1')
    setlink('Identity Review','M'+str(i),source_folder['native_url'],'Source folder')
    setcell('Identity Review','N'+str(i),source_pdf['file_id']);setcell('Identity Review','P'+str(i),source_folder['file_id'])
    setcell('Identity Review','K'+str(i),'BC-FP-LEFT; BC-FP-RIGHT — both source composition 2; no individual 1/2 assignment')
sr=row_for('Sets and Context','K','id:cnqzTNngPVsAAAAAAAyhPw')
setcell('Sets and Context','G'+str(sr),b['values']['Sets and Context']['G'+str(sr)]+'\n'+source1_note)
wc=0
for opt in g['options']:
    resolution=opt.get('current_listing_resolution',{});t=resolution.get('conditional_native_tuple')
    if not t:continue
    i=row_for('Identity Review','K',opt['product_id']);wc+=1
    setcell('Identity Review','E'+str(i),'Conditional pattern; working native tuple located')
    setcell('Identity Review','F'+str(i),f"Visual candidate: {t['pattern_short_name']}. Conditional working lookup: {t['diameter_option']}, {t['lighting_option']}, SKU {t['sku']}. Confirm the exact pattern relationship before assigning this native variant. Photograph does not certify physical diameter, lighting hardware or all specifications.")
assert wc==4
setcell('Photo Coverage','A3','21 October update: all 184 options assessed; 158 have complete individual references, including the historical edited Cup Ring image. Individual, in situ and series coverage remain separately qualified.')
setcell('Missing Pictures','A3','Current picture work: 119 find/capture actions, 38 existing-image checks and 53 optional series references. The resolved Cup Ring action remains in this table as dated history. Each action has an image and containing folder.')
setcell('Identity Review','A3','Current review: Cup Ring historical isolated image found; four Wall Circle native tuples conditional on visual pattern identity; Fingerprint source numbers apply to whole compositions. Group positions remain candidates until component identity is supported.')
setcell('Identity Review','C4','Conditional Wall Circle lookups')
formula_changes=[{'sheet':'Identity Review','cell':'D4','before':b['formulas']['Identity Review']['D4'],'formula':'=COUNTIF(E10:E108,"Conditional pattern; working native tuple located")','expected':4}]
row_heights={}
for (sn,cell),change in changes.items():
    if cell=='A3' or not isinstance(change['value'],str):continue
    letters=re.match('[A-Z]+',cell)[0];idx=0
    for c in letters:idx=idx*26+ord(c)-64
    rn=int(cell[len(letters):]);root=b['sheets'][sn]['root'];width=13
    for c in root.findall('.//'+v.q('col')):
        if int(c.get('min'))<=idx<=int(c.get('max')):width=float(c.get('width',13));break
    lines=sum(max(1,math.ceil(len(s)/max(8,width*.90)))for s in change['value'].split('\n'))
    required=lines*13+12
    oldrow=next(x for x in root.find(v.q('sheetData'))if x.get('r')==str(rn))
    original=float(oldrow.get('ht',15))
    if required>original:
        assert required<=409,(sn,cell,required)
        key=(sn,rn);row_heights[key]=max(row_heights.get(key,original),required)
plan={'cell_changes':list(changes.values()),'formula_changes':formula_changes,'hyperlinks':list(links.values()),'native_link_additions':4,
      'row_heights':[{'sheet':sn,'row':rn,'height':height}for(sn,rn),height in row_heights.items()],
      'preview_ranges':[
       ['Photo Coverage','A2:L5','01-current-coverage-summary'],['Photo Coverage','A37:F39','02-cup-isolated-coverage'],
       ['Photo Coverage','L38:T38','03-cup-qualifications'],['Missing Pictures','B10:F12','04-missing-actions'],
       ['Missing Pictures','I11:N11','05-resolved-cup-action'],['Identity Review','B11:F11','06-cup-identity'],
       ['Identity Review','B60:F61','07-fingerprint-source-scope'],['Identity Review','L60:P61','08-fingerprint-source-links'],
       ['Identity Review','B12:F18','09-wall-circle-conditions'],['Master Catalogue',f'N{main}:R{main}','10-cup-primary'],
       ['Specifications','J178:M179','11-specification-example'],['Draft Listings','I22:Q22','12-current-draft-media']
       ,['Components','E27:I27','13-current-component-media']
       ,['Identity Review','A2:F5','14-current-identity-summary']
      ]}
write(HERE/'workbook-edit-plan.json',plan)
# Rebase the current coverage/action projection from saved native cells/links.
# The immutable 20 October audit is left untouched.
for sn,cells in b['values'].items():
    for (n,c),change in changes.items():
        if n==sn:cells[c]=change['value']
def current_ref(sn,row,ic,fc,fidc,folderidc,prior):
    fid=b['values'][sn].get(fidc+str(row),'')
    if not fid:return None
    old=copy.deepcopy(prior or {});iu=links[(sn,ic+str(row))]['target'];fu=links[(sn,fc+str(row))]['target']
    name=parse_qs(urlparse(iu).query).get('preview',[Path(unquote(urlparse(iu).path)).name])[0]
    folder_path=unquote(urlparse(fu).path.removeprefix('/home').removeprefix('/preview'))
    old.update(file_id=fid,folder_id=b['values'][sn].get(folderidc+str(row),''),image_url=iu,folder_url=fu,name=name,path='ns:202238505/'+folder_path+'/'+name)
    return old
for row in audit['coverage']:
    i=row_for('Photo Coverage','A',row['option_id'])
    for role,sc,ic,fc,idc,dc in [('individual','C','D','E','M','N'),('in_situ','F','G','H','O','P'),('series','I','J','K','Q','R')]:
        row[role]['status']=b['values']['Photo Coverage'].get(sc+str(i),'')
        row[role]['reference']=current_ref('Photo Coverage',i,ic,fc,idc,dc,row[role].get('reference'))
    if row['option_id']==pid:
        row['individual'].update(reference=ref,exact_option=True,qualification=qualifier,physical_cast_or_size_certified=False)
        row['notes']=[qualifier];row['scope']=b['values']['Photo Coverage']['S'+str(i)]
        row['scene_origin']=b['values']['Photo Coverage']['T'+str(i)]
for x in audit['missing_pictures']:
    i=next(i for i in range(10,221)if b['values']['Missing Pictures'].get('B'+str(i))==x['option_id'] and b['values']['Missing Pictures'].get('D'+str(i))==x['role'])
    x['reference']=current_ref('Missing Pictures',i,'G','H','I','J',x.get('reference'))
    for key,c in [('action','F'),('scope','K'),('qualification','L'),('owner_response','M'),('status','N')]:x[key]=b['values']['Missing Pictures'].get(c+str(i),'')
for x in audit['identity_review']:
    i=row_for('Identity Review','A',x.get('review_id',x.get('case_id',x.get('id')))) if any(k in x for k in ['review_id','case_id','id']) else None
    if i is None:raise AssertionError(list(x))
    x['reference']=current_ref('Identity Review',i,'G','H','I','J',x.get('reference'))
    x['comparison']=current_ref('Identity Review',i,'L','M','N','P',x.get('comparison'))
    for key,c in [('state','E'),('check','F')]:x[key]=b['values']['Identity Review'].get(c+str(i),'')
active=[x for x in audit['missing_pictures']if x['status']!='Resolved']
audit['recorded_utc']=now();audit['status']='CURRENT_BOUNDED_COVERAGE_WITH_ARCHIVE_IMAGE_AND_SOURCE_COMPOSITION_ADDENDUM'
audit['counts']['individual_statuses']=dict(collections.Counter(x['individual']['status']for x in audit['coverage']))
audit['counts']['actions_by_role']=dict(collections.Counter(x['role']for x in active))
audit['counts']['actions_by_type']=dict(collections.Counter(x['action_type']for x in active))
audit['counts'].update(resolved_action_rows=1,active_action_rows=len(active),historical_action_rows_retained=211,conditional_wall_circle_working_tuples=4,physical_casts_certified=0)
group_reviews=[x for x in audit['identity_review']if not x['case_id'].startswith('ID-')]
unresolved_positions=[x for x in group_reviews if x['state']in ['Candidate position; identity unverified','Component identification needed']]
assert len(group_reviews)==90 and len(unresolved_positions)==83
audit['counts'].update(group_and_collection_review_positions=90,group_and_collection_positions_identity_unresolved=83,group_positions_linked_to_existing_components=7)
audit['source_addenda']={'cup':manifest['cup_addendum'],'fingerprint':manifest['fingerprint_addendum'],'fingerprint_native_bindings':manifest['fingerprint_bindings']}
audit['historical_audit']={'path':str(sources['prior_audit']),'sha256':manifest['prior_audit']['sha256'],'prior_counts':oldaudit['counts']}
assert audit['counts']['individual_statuses']=={'Available':158,'Detail only':5,'Group only':20,'Unbound size':1}
assert audit['counts']['actions_by_type']=={'Find / capture':119,'Verify existing image':38,'Optional image':53}
assert len([x for x in active if x['role']=='Individual'])==26
write(HERE/'image-coverage-current.json',audit)
def csv_write(name,items):
    with (HERE/name).open('w',newline='',encoding='utf-8-sig')as f:
        w=csv.DictWriter(f,fieldnames=['priority','option_id','name','role','action_type','status','action','image_url','folder_url','file_id','folder_id','scope','qualification']);w.writeheader()
        for x in items:
            r={k:x.get(k,'')for k in ['priority','option_id','name','role','action_type','status','action','scope','qualification']};r.update({k:x['reference'][k]for k in ['image_url','folder_url','file_id','folder_id']});w.writerow(r)
csv_write('Missing_Pictures_Required_2026-10-21.csv',[x for x in active if x['status']!='Optional'])
csv_write('Missing_Individual_Images_2026-10-21.csv',[x for x in active if x['role']=='Individual'])
csv_write('Optional_Series_Images_2026-10-21.csv',[x for x in active if x['status']=='Optional'])
g['historical_image_coverage_audits']=[copy.deepcopy(g['latest_image_coverage_audit'])]
g['latest_image_coverage_audit']={**g['latest_image_coverage_audit'],'status':audit['status'],'recorded_utc':now(),
 'audit':str((HERE/'image-coverage-current.json').relative_to(BASE)),'audit_sha256':digest(HERE/'image-coverage-current.json'),'counts':audit['counts'],
 'source_scope':'184 options assessed; dated bounded audit with current stable-ID reference projections, complete historical isolated Cup Ring image, Fingerprint composition-source qualification and four conditional Wall Circle native lookups. No exact physical stock/cast or current hardware claims.',
 'prior_audit_preserved':audit['historical_audit']}
g['fingerprint_source_compositions']={'source':manifest['fingerprint_addendum'],'native_bindings':bindings,'findings':fp['findings'],'component_crosswalk':fp['component_crosswalk'],
 'scope_guard':fp['source_heading_guard'],'superseded_question':bindings['superseded_owner_question'],'individual_names_or_member_numbers_changed':False}
g['latest_image_identity_resolution']={'status':'CURRENT_IMAGE_AND_SOURCE_SCOPE_ADDENDUM_IMPORTED','recorded_utc':now(),'cup_source':manifest['cup_addendum'],
 'cup_primary':ref,'cup_qualification':qualifier,'processed_reference_provenance':cup['new_png_reference_provenance'],
 'frozen_fish_long':add['frozen_fish_long'],'fingerprint_source':manifest['fingerprint_addendum'],
 'conditional_wall_circle_options':4,'accepted_specification_changes':0,'identity_count_changes':0,'platform_or_dropbox_writes':0}
g['component_organisation_policy']={'policy':'Known individual components have separate component and purchasable option records. Group photographs remain arrangement references. Unidentified positions remain review candidates until evidence supports individual identities.',
 'source':manifest['component_organisation_audit'],'individual_component_names_or_numbers_inferred':False,
 'current_options':184,'identified_catalogue_components':111,'group_and_collection_review_positions':90,'unresolved_position_reviews_not_added_as_identities':83,
 'position_reviews_linked_to_existing_components':7,'position_rows_are_not_unique_design_counts':True,'Dropbox_organisation_owner':'01a159af-d182-7393-9201-a2ac7ccba14a','root_remote_writes':0}
write(HERE/'canonical-master-register.json',g)
assert g['summary']==oldg['summary']
assert g['original_review_specification_assertions']==oldg['original_review_specification_assertions']
assert all(x['name']==y['name'] and x['product_id']==y['product_id'] and x['master_fields']==y['master_fields'] and x['specifications']==y['specifications'] for x,y in zip(g['options'],oldg['options']))
for key in ['current_listing_resolution','current_listing_resolution_details','listing_resolution_source_edges','listing_resolution_native_action_drafts','latest_listing_resolution','current_listing_source_links','current_listing_match_evidence','current_listing_issues']:
    assert g[key]==oldg[key], key
write(HERE/'preparation-verification.json',{'status':'PASS','cell_changes':len(changes),'hyperlinks':len(links),'individual_available':158,'individual_gaps':26,
 'required_actions':157,'find_capture_actions':119,'verify_existing_actions':38,'optional_actions':53,'historical_actions_retained':211,
 'names_specifications_or_count_changes':0,'listing_resolution_preserved':True,'new_native_or_dropbox_writes':0})
print(json.dumps(read(HERE/'preparation-verification.json')))
