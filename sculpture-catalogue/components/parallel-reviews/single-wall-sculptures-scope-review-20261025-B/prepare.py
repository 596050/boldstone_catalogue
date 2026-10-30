"""Append one unconfirmed wall-scope source; preserve the sealed 412 rows."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib
W=Path(__file__).resolve().parent
PRIOR=W.with_name('single-wall-sculptures-sheet-20261025-B')
OLD=W.with_name('all-source-workbook-20261025-B')
read=lambda p:json.loads(Path(p).read_text())
write=lambda p,x:Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
d=read(PRIOR/'unified-data.json');old_output=Path(d['output'])
assert sha(old_output)=='da76ca34ffa1f272ef600aff2dd2a1e29f1734fd513b4d95d6b25136ffc5c8c6'
tabs={t['name']:t for t in read(OLD/'workbook-data.json')['tabs']}
sid='6a43e6a4b629f94bfa50bfd2'
si,source=next((i,r) for i,r in enumerate(tabs['Squarespace']['rows']) if r[0]==sid)
matches=[(i,r) for i,r in enumerate(tabs['Squarespace variants']['rows']) if r[1]==sid]
assert len(matches)==1
vi,v=matches[0];vid=v[0];kind='Wall scope review'
status='Wall scope unconfirmed; no catalogue identity/mounting assumed'
raw='SS raw weight / L / W / H: '+' / '.join(str(x) for x in [v[9],v[10],v[11],v[12]])+'; raw units not encoded.'
evidence='Included for wall-scope review because the local export category is /sculpture. No confirmed wall mounting, catalogue identity, Dropbox association or raw-SKU Shopify counterpart. No new sculpture approval.'
record={'key':'SSV:'+vid,'kind':kind,'catalogue_ids':[],'ss_product_ids':[sid],'ss_variant_ids':[vid],'sh_handles':[],'sh_variant_keys':[],'current_file_ids':[],'unassigned_file_ids':[],'folder_ids':[],'supplementary_file_ids':[],'related_catalogue_ids':[],'grouping_basis':evidence}
row=[v[2],kind,status,'Unassigned source',v[4] or 'Default source variant',
 'Source description: 100 cm high. Raw export L / W / H: 8.7 / 8.7 / 19.7; units not encoded. Source size reconciliation remains unresolved.',
 'Raw source weight: '+str(v[9])+'; unit/scope unconfirmed.',
 'Base material not specified in source description; marbled finish is a source claim.',
 'Not stated; wall mounting unconfirmed.',
 'Squarespace source price: '+str(v[5])+'; sale field '+str(v[6])+'; On sale: '+v[7]+'. Currency not encoded.',
 'Historical source stock setting: '+v[8]+'. Current availability and lead time unverified.',
 'Gallery image','','Squarespace','',record['key'],'',sid,vid,v[3],'','','','',0,0,'','',
 'Source gallery image only; not a verified wall-mounted sculpture or exact catalogue option.',raw,evidence,'','Source variant',
 'Wall scope unconfirmed; included for review only. Existing 188 sculpture options and their specifications remain unchanged.']
assert len(row)==len(d['columns'])==34
i=len(d['rows']);assert i==412
d['rows'].append(row);d['records'].append(record)
for j,target,label in [(11,tabs['Squarespace']['links'][str(si)+',18']['target'],'Gallery image'),(13,"#'Squarespace'!A"+str(si+7),'Squarespace'),(32,"#'Squarespace variants'!A"+str(vi+7),'Source variant')]:
 d['links'][str(i)+','+str(j)]={'target':target,'label':label}
d['counts'][kind]=1
d['coverage_counts']['ss_product_ids']+=1;d['coverage_counts']['ss_variant_ids']+=1
d['output']=str(old_output.with_name('Boldstone_Wall_Sculptures_Unified_2026-10-25_v2.xlsx'))
d['formulas']={k:v.replace('420','421') for k,v in d['formulas'].items()};d['expected_formula_values']['D5']=174
write(W/'unified-data.json',d)
scope=read(PRIOR/'scope-membership.json')
for r in scope:
 if r['platform']=='Squarespace' and r['id']==sid:
  assert not r['included'];r['included']=True;r['reason']='Included as an explicit wall-scope review source, not an approved sculpture identity. No wall-mount, Dropbox or retained catalogue association is assumed.'
write(W/'scope-membership.json',scope)
c=read(PRIOR/'coverage.json');c['rows']=413;c['row_types'][kind]=1;c['coverage_counts']=d['coverage_counts'];c['source_only_row_count']=174
c['covered_ids']['ss_product_ids']=sorted(c['covered_ids']['ss_product_ids']+[sid]);c['covered_ids']['ss_variant_ids']=sorted(c['covered_ids']['ss_variant_ids']+[vid])
c['unconfirmed_wall_scope_products']=[sid]
write(W/'coverage.json',c)
im=read(PRIOR/'input-manifest.json')
for x in im['inputs']:assert sha(x['path'])==x['sha256'],x['path']
for p in [old_output,PRIOR/'sealed-handoff.json',PRIOR/'unified-data.json']:
 im['inputs'].append({'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size})
im['captured_utc']=datetime.now(timezone.utc).isoformat();write(W/'input-manifest.json',im)
write(W/'WORK_PLAN.json',{'objective':'Include the sole unconfirmed wall-scope source in the unified review sheet while preserving the prior deliverable and all earlier rows.','steps':[{'step':'Append qualified local source row and freeze previous deliverable','status':'complete'},{'step':'Author, independently verify and visually check revised sheet','status':'in_progress'},{'step':'Seal and deliver revised workbook','status':'pending'}],'canonical_writes':False})
print(json.dumps({'rows':413,'coverage':d['coverage_counts'],'links':len(d['links']),'added_variant':vid,'output':d['output']}))
