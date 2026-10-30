"""Prepare a single complete wall-sculpture view without inferring identities."""
from pathlib import Path
from datetime import datetime,timezone
from collections import defaultdict,Counter
import hashlib,json,sqlite3

W=Path(__file__).resolve().parent;B=W.parents[2]
OLD=W.with_name('all-source-workbook-20261025-B')
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
write=lambda p,v:Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
join=lambda xs:'\n'.join(dict.fromkeys(str(x) for x in xs if x is not None and x!=''))
base=read(OLD/'workbook-data.json');tabs={t['name']:t for t in base['tabs']}
baseline=Path(base['output']);assert sha(baseline)=='9858a137fe23ce721749d659b41ec5e0d881a2a78ff3b99d2348ed4b8090c045'
pointer=read(B/'current-master.json');register_path=B/pointer['register'];reg=read(register_path)
assert sha(register_path)==pointer['register_sha256']=='9b4b15ca857bea027637b3dd1474bfb98c87746bb842b49003b526da6770e748'
G=(B/pointer['current_published_gallery_projection']['path']).parent
db=G/'complete-image-platform-register.sqlite'
with sqlite3.connect('file:'+str(db)+'?mode=ro',uri=True) as c:
 ssrecords=[json.loads(x[0]) for x in c.execute('SELECT record_json FROM local_squarespace_records')]
 shrecords=[json.loads(x[0]) for x in c.execute('SELECT record_json FROM local_shopify_products')]
 galleries=[json.loads(x[0]) for x in c.execute('SELECT record_json FROM source_gallery')]
ss_scope={x['squarespace_native_tuple']['native_product_id'] for x in ssrecords}
sh_scope={x['handle'] for x in shrecords if x['product']['in_preserved_wall_subset']}
assert len(ss_scope)==80 and len(sh_scope)==38
products={r[0]:r for r in tabs['Products']['rows']};pindex={r[0]:i for i,r in enumerate(tabs['Products']['rows'])}
ss={r[0]:r for r in tabs['Squarespace']['rows']};sh={r[0]:r for r in tabs['Shopify']['rows']}
sv={r[0]:r for r in tabs['Squarespace variants']['rows'] if r[1] in ss_scope}
hv={r[0]:r for r in tabs['Shopify variants']['rows'] if r[1] in sh_scope}
assert len(sv)==223 and len(hv)==38
offers={r[3]:r for r in tabs['Reviewed offers']['rows'] if r[3]}
files={r[0]:r for r in tabs['Dropbox files']['rows']}
current={k:v for k,v in files.items() if v[6]=='CURRENT_NATIVE_FILE_AND_ACTUAL_PARENT_VERIFIED'}
unassigned_ids={fid for fid,f in current.items() if f[5]=='No product-option association'}
folders={r[0]:r for r in tabs['Dropbox folders']['rows']}
file_index={r[0]:i for i,r in enumerate(tabs['Dropbox files']['rows'])}
folder_index={r[0]:i for i,r in enumerate(tabs['Dropbox folders']['rows'])}
ss_index={r[0]:i for i,r in enumerate(tabs['Squarespace']['rows'])}
sh_index={r[0]:i for i,r in enumerate(tabs['Shopify']['rows'])}
sv_index={r[0]:i for i,r in enumerate(tabs['Squarespace variants']['rows'])}
hv_index={r[0]:i for i,r in enumerate(tabs['Shopify variants']['rows'])}
by_product=defaultdict(set)
for r in tabs['Image associations']['rows']:by_product[r[1]].add(r[3])
gallery_files=defaultdict(set)
for g in galleries:gallery_files[g['native_product_id']].update(g.get('supported_photo_file_ids',[]))

def link(sheet,i,j):
 l=tabs[sheet]['links'].get(str(i)+','+str(j));return l['target'] if l else ''
def internal(sheet,row):return "#'"+sheet+"'!A"+str(row+7)
def ancestors(ids):
 out=set()
 for fid in ids:
  while fid in folders and fid not in out:
   out.add(fid);fid=folders[fid][3]
 return out
def file_folders(ids):return ancestors(files[fid][12] for fid in ids if files[fid][12] in folders)
def related_family(pids):
 fs=sorted({products[pid][3] for pid in pids if pid in products and products[pid][3]})
 return fs[0] if len(fs)==1 else 'Mixed arrangement' if fs else 'Unassigned source'
def family_folder(family):
 matches=[fid for fid,f in folders.items() if f[1]==family and f[9].count('/')==5]
 if not matches:
  matches=[fid for fid,f in folders.items() if f[1]==family and f[9].rstrip('/').endswith('/01 Wall Sculptures/'+family)]
 return matches[0] if len(matches)==1 else None

columns=['Sculpture / source name','Row type','Match status','Family / arrangement','Finish / source variant',
 'Dimensions / depth','Weight','Material / finish','Fixing choices','Price and qualification','Availability / lead time',
 'Image','Dropbox folder','Squarespace record','Shopify record','Row key','Catalogue ID',
 'Squarespace product IDs','Squarespace variant IDs','Squarespace raw SKUs','Shopify handles','Shopify local variant keys','Shopify raw SKUs',
 'Related catalogue IDs','Related current file count','Files without individual association','Dropbox folder IDs','Current Dropbox file IDs',
 'Image / folder qualification','Historical source values and units','Grouping evidence / unresolved issue','Supplementary Dropbox file IDs','Source details','Scope note']
rows=[];records=[];row_links=[]
def add(row,record,links):
 assert len(row)==len(columns),(record['key'],len(row),len(columns),list(enumerate(row)))
 rows.append(row);records.append(record);row_links.append(links)
used_sv=set();used_hv=set()
for pid,p in products.items():
 ssids={p[17]} if p[17] else set();svids={p[18]} if p[18] else set()
 handles={p[19]} if p[19] else set();hvids={k for k,v in hv.items() if v[1] in handles}
 assert svids.issubset(sv) and ssids.issubset(ss_scope) and handles.issubset(sh_scope)
 used_sv.update(svids);used_hv.update(hvids)
 cf=by_product[pid]&current.keys();hist=by_product[pid]-current.keys();fids=file_folders(cf)
 primary=p[25];pri=file_index.get(primary);pi=pindex[pid]
 l={11:link('Products',pi,27),12:link('Products',pi,28),32:internal('Products',pi)}
 if ssids:l[13]=internal('Squarespace',ss_index[next(iter(ssids))])
 if handles:l[14]=internal('Shopify',sh_index[next(iter(handles))])
 prices=[]
 for vid in sorted(svids):
  x=sv[vid];prices.append(f'Squarespace SKU {x[3]}: price {x[5]}; sale field {x[6]}; On sale: {x[7]}; raw units/currency not encoded.')
 for vk in sorted(hvids):
  x=hv[vk];prices.append(f'Shopify SKU {x[3]}: price {x[5]}; compare-at {x[6]}; {x[7]}.')
 record={'key':'CAT:'+pid,'kind':'Individual option','catalogue_ids':[pid],'ss_product_ids':sorted(ssids),'ss_variant_ids':sorted(svids),'sh_handles':sorted(handles),'sh_variant_keys':sorted(hvids),
  'current_file_ids':sorted(cf),'unassigned_file_ids':[],'folder_ids':sorted(fids),'supplementary_file_ids':sorted(hist),
  'grouping_basis':'Existing selected individual plan and retained product-image edges; no new exact identity decision.'}
 row=[p[1],'Individual option',p[2],p[3],p[22],p[6],p[7],p[8],p[9],p[12],p[13],
  'Image' if l[11] else '', 'Folder' if l[12] else '', 'Squarespace' if ssids else '', 'Shopify' if handles else '',record['key'],pid,
  join(sorted(ssids)),join(sorted(svids)),join(sv[x][3] for x in sorted(svids)),join(sorted(handles)),join(sorted(hvids)),join(hv[x][3] for x in sorted(hvids)),
  '',len(cf),0,join(sorted(fids)),join(sorted(cf)),
  'Selected reference role: '+str(p[26] or 'unspecified')+'. Other retained file associations include context and qualified candidates.',join(prices),p[24],join(sorted(hist)),'Working product',p[31]]
 add(row,record,l)

residual_sv={k:v for k,v in sv.items() if k not in used_sv}
residual_hv={k:v for k,v in hv.items() if k not in used_hv}
ss_sku=defaultdict(list);sh_sku=defaultdict(list)
for k,v in sv.items():
 if v[3]:ss_sku[v[3]].append(k)
for k,v in hv.items():
 if v[3]:sh_sku[v[3]].append(k)
paired_h=set();source_pair_count=0
for vid,v in residual_sv.items():
 sid=v[1];source=ss[sid];o=offers[sid]
 hkeys=[]
 if v[3] and len(ss_sku[v[3]])==len(sh_sku[v[3]])==1:
  candidate=sh_sku[v[3]][0]
  if candidate in residual_hv:hkeys=[candidate];paired_h.add(candidate);source_pair_count+=1
 handles={hv[k][1] for k in hkeys}
 related=set(source[8].split('\n'))-{''};family=related_family(related)
 ff=family_folder(family);cf=gallery_files[sid]&current.keys();hist=gallery_files[sid]-current.keys();fids=file_folders(cf)
 if ff:fids.update(ancestors([ff]))
 if sid=='68dc0a35a7ac865209b39248':kind='Other website variant';status='Unmatched exact catalogue option'
 elif o[6]=='Sale component':kind='Unmatched website source';status='Related source; exact option unresolved'
 else:kind='Set / arrangement source';status='Related arrangement; individual assignment separate'
 native=['Source each: '+str(o[12])+' cm' if o[12] else '', 'Source overall: '+str(o[13])+' cm' if o[13] else '']
 if not any(native):native=['Raw export L / W / H: '+' / '.join('(blank)' if x is None else str(x) for x in [v[10],v[11],v[12]])+'; units not encoded.']
 price='Squarespace source price: '+str(v[5])+'; sale field '+str(v[6])+'; On sale: '+str(v[7])+'. Currency not encoded.'
 if o[6]!='Sale component':price+=' Source sale quantity: '+str(o[7])+'; '+str(o[6])+'. Not a per-panel allocation.'
 shvals=[]
 for hk in hkeys:
  x=hv[hk];shvals.append('Shopify SKU '+str(x[3])+': price '+str(x[5])+'; compare-at '+str(x[6])+'; '+str(x[7])+'.')
 rawunits='SS raw weight / L / W / H: '+' / '.join('(blank)' if x is None else str(x) for x in [v[9],v[10],v[11],v[12]])+'; raw units not encoded.\n'+join(shvals)
 evidence=('Squarespace and Shopify source rows grouped by identical, unique, non-empty raw SKU '+v[3]+'. ' if hkeys else 'Squarespace source row retained separately. ')
 evidence+='This source grouping does not establish exact cast, finish, size or individual sale quantity. '+str(o[21] or '')
 l={11:link('Squarespace',ss_index[sid],18),12:link('Dropbox folders',folder_index[ff],8) if ff else '',13:internal('Squarespace',ss_index[sid]),32:internal('Squarespace variants',sv_index[vid])}
 if handles:l[14]=internal('Shopify',sh_index[next(iter(handles))])
 key='SSV:'+vid;record={'key':key,'kind':kind,'catalogue_ids':[],'ss_product_ids':[sid],'ss_variant_ids':[vid],'sh_handles':sorted(handles),'sh_variant_keys':hkeys,
  'current_file_ids':sorted(cf),'unassigned_file_ids':sorted(cf&unassigned_ids),'folder_ids':sorted(fids),'supplementary_file_ids':sorted(hist),'related_catalogue_ids':sorted(related),'grouping_basis':evidence}
 row=[v[2],kind,status,family,v[4] or 'Default source variant',join(native),
  'Source set weight: '+str(o[14])+' kg' if o[14] else 'Raw source weight: '+str(v[9])+'; unit/scope unconfirmed.',
  'See source description; no individual material inferred.','Source hardware / load not independently confirmed.',price,
  'Historical source stock setting: '+str(v[8])+'. Current availability and lead time unverified.',
  'Gallery image' if l[11] else '','Family folder' if l[12] else '','Squarespace','Shopify' if handles else '',key,'',sid,vid,v[3],join(sorted(handles)),join(hkeys),join(hv[k][3] for k in hkeys),join(sorted(related)),
  len(cf),len(cf&unassigned_ids),join(sorted(fids)),join(sorted(cf)),
  'Image is a product-gallery reference; this export does not bind it to this exact variant. Folder, where supplied, is the related family.',rawunits,evidence,join(sorted(hist)),'Source variant',
  'Retained source record; not an additional approved individual sculpture or newly verified specification.']
 add(row,record,l)

for hk,h in residual_hv.items():
 if hk in paired_h:continue
 handle=h[1];source=sh[handle];related=set(source[7].split('\n'))-{''};family=related_family(related);ff=family_folder(family);fids=ancestors([ff]) if ff else set()
 key='SHV:'+hk;kind='Unmatched Shopify source'
 l={11:link('Shopify',sh_index[handle],17),12:link('Dropbox folders',folder_index[ff],8) if ff else '',14:internal('Shopify',sh_index[handle]),32:internal('Shopify variants',hv_index[hk])}
 evidence='No unique raw-SKU counterpart among the retained wall Squarespace variants. Existing family relationships remain qualified.'
 record={'key':key,'kind':kind,'catalogue_ids':[],'ss_product_ids':[],'ss_variant_ids':[],'sh_handles':[handle],'sh_variant_keys':[hk],'current_file_ids':[],'unassigned_file_ids':[],'folder_ids':sorted(fids),'supplementary_file_ids':[],'related_catalogue_ids':sorted(related),'grouping_basis':evidence}
 row=[h[2],kind,'Unmatched exact catalogue option',family,h[4] or 'Default source variant',
  'Not established for an individual component.','Source grams: '+str(h[8])+'; '+str(h[10]),'Not established for an individual component.','Not established for this source option.',
  'Shopify source price: '+str(h[5])+'; compare-at '+str(h[6])+'; '+str(h[7])+'.',
  'Historical source status: '+str(h[21])+'. Current stock and lead time unverified.','Gallery image' if l[11] else '','Family folder' if l[12] else '','','Shopify',key,'','','','',handle,hk,h[3],join(sorted(related)),0,0,join(sorted(fids)),'',
  'Product-gallery reference; no explicit variant-image assignment.',str(h[10]),evidence,'','Source variant','Retained historical source; no new individual identity or specification inferred.']
 add(row,record,l)

unassigned={fid:f for fid,f in current.items() if f[5]=='No product-option association'}
groups=defaultdict(list)
for fid,f in unassigned.items():groups[f[12]].append(fid)
for fid,ids in sorted(groups.items(),key=lambda x:folders[x[0]][1]):
 f=folders[fid];ids=sorted(ids);roles=Counter(current[x][4] for x in ids)
 ambiguous=bool(roles.get('individual') or roles.get('uncertain'))
 kind='Unassigned photograph group' if ambiguous else 'Context photograph group'
 preferred=sorted(ids,key=lambda x:(current[x][4] not in ['individual','uncertain'],current[x][1]))[0]
 key='DBF:'+fid;fids=ancestors([fid]);evidence='Grouped only by the current native parent folder ID. '+', '.join(str(v)+' '+k for k,v in sorted(roles.items()))+'. No new component or finish identity inferred.'
 record={'key':key,'kind':kind,'catalogue_ids':[],'ss_product_ids':[],'ss_variant_ids':[],'sh_handles':[],'sh_variant_keys':[],'current_file_ids':ids,'unassigned_file_ids':ids,'folder_ids':sorted(fids),'supplementary_file_ids':[],'grouping_basis':evidence}
 row=[f[1],kind,'Unmatched image identity' if ambiguous else 'Context only; no individual assignment',f[2],
  'Folder label only; finish not newly verified.','Not assigned to an individual sculpture.','','','','','',
  'Folder photo','Folder','','',key,'','','','','','','','',len(ids),len(ids),join(sorted(fids)),join(ids),
  'Representative folder image only. Existing photography deferrals remain unchanged.','',evidence,'','Folder inventory',
  'A photograph group is not an additional sculpture count. All '+str(len(ids))+' files remain represented.']
 l={11:link('Dropbox files',file_index[preferred],13),12:link('Dropbox folders',folder_index[fid],8),32:internal('Dropbox folders',folder_index[fid])}
 add(row,record,l)

covered_folders=set().union(*(set(r['folder_ids']) for r in records))
for fid in sorted(folders.keys()-covered_folders):
 f=folders[fid];key='EMPTY:'+fid;kind='Folder only';fids=ancestors([fid])
 record={'key':key,'kind':kind,'catalogue_ids':[],'ss_product_ids':[],'ss_variant_ids':[],'sh_handles':[],'sh_variant_keys':[],'current_file_ids':[],'unassigned_file_ids':[],'folder_ids':sorted(fids),'supplementary_file_ids':[],'grouping_basis':'Current native folder retained; no current descendant file is indexed.'}
 row=[f[1],kind,'No current photographs in saved inventory',f[2],'','','','','','','','','Folder','','',key,'','','','','','','','',0,0,join(sorted(fids)),'','','',record['grouping_basis'],'','Folder inventory','Folder is not evidence of an extra manufactured sculpture.']
 add(row,record,{12:link('Dropbox folders',folder_index[fid],8),32:internal('Dropbox folders',folder_index[fid])})

priority={'Individual option':0,'Set / arrangement source':1,'Unmatched website source':2,'Other website variant':3,'Unmatched Shopify source':4,'Unassigned photograph group':5,'Context photograph group':6,'Folder only':7}
order=sorted(range(len(rows)),key=lambda i:(str(rows[i][3] or '').casefold(),priority[rows[i][1]],rows[i][0].casefold(),rows[i][4].casefold(),rows[i][15]))
rows=[rows[i] for i in order];records=[records[i] for i in order];row_links=[row_links[i] for i in order]
links={str(i)+','+str(j):{'target':u,'label':rows[i][j]} for i,ls in enumerate(row_links) for j,u in ls.items() if u}
coverage={k:sorted(set().union(*(set(r[k]) for r in records))) for k in ['catalogue_ids','ss_product_ids','ss_variant_ids','sh_handles','sh_variant_keys','current_file_ids','unassigned_file_ids','folder_ids','supplementary_file_ids']}
expected={'catalogue_ids':set(products),'ss_product_ids':ss_scope,'ss_variant_ids':set(sv),'sh_handles':sh_scope,'sh_variant_keys':set(hv),'current_file_ids':set(current),'unassigned_file_ids':set(unassigned),'folder_ids':set(folders)}
for key,ids in expected.items():assert set(coverage[key])==ids,(key,len(coverage[key]),len(ids))
assert len(rows)==412 and len({r[15] for r in rows})==412
assert max(len(str(x or '')) for r in rows for x in r)<=32767
counts=dict(Counter(r[1] for r in rows))
assert counts['Individual option']==188 and source_pair_count==23 and len(unassigned)==625 and len(groups)==49

scope=[]
for sid,r in ss.items():
 included=sid in ss_scope
 reason='Member of the retained 80-product wall-sculpture review with stable native product ID.' if included else 'Outside the retained wall-sculpture review; export category '+repr(r[14])+'. Kept on Squarespace and raw source tabs.'
 if not included and '/sculpture' in r[14]:
  reason={'6aa01ade4b08934e6b0d3db1':'Source describes a tabletop catch-all bowl; no wall-sculpture association established.',
   '6a425bf2870e0e6bc1e1a24e':'Source describes a decorative stool/stand; no wall-sculpture association established.',
   '6a43e6a4b629f94bfa50bfd2':'Decorative balloon source has no established wall-mount or retained Wall Sculptures association; wall scope unconfirmed, not discarded.'}[sid]
 scope.append({'platform':'Squarespace','id':sid,'title':r[1],'included':included,'source_category':r[14],'reason':reason})
for handle,r in sh.items():scope.append({'platform':'Shopify','id':handle,'title':r[1],'included':handle in sh_scope,'source_type':r[11],'reason':'Included by the preserved wall-sculpture subset flag.' if handle in sh_scope else 'Outside the preserved wall-sculpture subset; retained on Shopify and raw source tabs.'})
write(W/'scope-membership.json',scope)
write(W/'coverage.json',{'status':'PASS_ALL_SCOPED_RECORD_IDS_REPRESENTED','rows':len(rows),'row_types':counts,'coverage_counts':{k:len(v) for k,v in coverage.items()},'covered_ids':coverage,'residual_raw_SKU_groups':source_pair_count,'source_only_row_count':173,'unassigned_photograph_groups':49,'unassigned_individual_views':sum(r[4]=='individual' for r in unassigned.values()),'photo_group_count_is_not_sculpture_count':True,'new_identity_approvals':0})
out=baseline.with_name('Boldstone_Wall_Sculptures_Unified_2026-10-25.xlsx')
payload={'baseline':str(baseline),'output':str(out),'sheet':'Wall Sculptures','header_row':8,'first_data_row':9,'columns':columns,'rows':rows,'records':records,'links':links,'counts':counts,'coverage_counts':{k:len(v) for k,v in coverage.items()},
 'formulas':{'B5':f'=COUNTIF(B9:B{len(rows)+8},"Individual option")','D5':f'=COUNTA(P9:P{len(rows)+8})-B5-F5-H5','F5':f'=COUNTIF(B9:B{len(rows)+8},"Unassigned photograph group")+COUNTIF(B9:B{len(rows)+8},"Context photograph group")','H5':f'=COUNTIF(B9:B{len(rows)+8},"Folder only")'},
 'expected_formula_values':{'B5':188,'D5':173,'F5':49,'H5':2}}
write(W/'unified-data.json',payload)
inputs=[baseline,OLD/'workbook-data.json',OLD/'sealed-handoff.json',OLD/'validation.json',B/'current-master.json',register_path,db]
write(W/'input-manifest.json',{'captured_utc':datetime.now(timezone.utc).isoformat(),'inputs':[{'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size} for p in inputs]})
plan=read(W/'WORK_PLAN.json');plan['steps'][0]['status']='complete';plan['steps'][1]['status']='complete';plan['steps'][2]['status']='in_progress';write(W/'WORK_PLAN.json',plan)
print(json.dumps({'status':'PREPARED','rows':len(rows),'row_types':counts,'coverage':{k:len(v) for k,v in coverage.items()},'links':len(links),'max_cell_text':max(len(str(x or '')) for r in rows for x in r)},indent=2))
