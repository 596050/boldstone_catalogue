"""Plan current qualified draft copy and the scoped owner group-reference decision."""
import importlib.util,json,posixpath
from pathlib import Path
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;B=H.parents[2];OUT=B/'outputs'/H.name;read=lambda p:json.loads(Path(p).read_text())
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
s=importlib.util.spec_from_file_location('native',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(s);s.loader.exec_module(n)
w=n.load(H/'inputs/master_workbook.before');g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');proj=read(H/'projection-index.json');OLD=proj['old_output'];changes={};links={};heights=[]
def value(sn,c,v):
 assert c not in w['formulas'][sn]
 if w['values'][sn].get(c,'')!=v:changes[(sn,c)]={'sheet':sn,'cell':c,'before':w['values'][sn].get(c,''),'value':v}
for sn,z in w['sheets'].items():
 rp=posixpath.join(posixpath.dirname(z['part']),'_rels',posixpath.basename(z['part'])+'.rels');rels={x.get('Id'):x.get('Target')for x in E.fromstring(w['files'][rp])}
 for x in z['root'].findall('.//'+n.q('hyperlink')):
  c=x.get('ref');u='#'+x.get('location')if x.get('location')else rels[x.get('{'+n.R+'}id')];links[(sn,c)]={'sheet':sn,'cell':c,'label':w['values'][sn].get(c,''),'target':u.replace(OLD,str(OUT))}
copies=read(H/'current-copy-projections.json');copymap={x['option_id']:x for x in copies};copycells=[]
for c,oid in w['values']['Listing Corrections'].items():
 if c.startswith('B')and oid in copymap:
  rr=c[1:];field=w['values']['Listing Corrections']['D'+rr];text=copymap[oid]['copy_values'][field];value('Listing Corrections','E'+rr,text);value('Listing Corrections','F'+rr,text);value('Listing Corrections','G'+rr,copymap[oid]['current_working_fields'][field]['state']);copycells.append({'option_id':oid,'field':field,'cell':'F'+rr})
assert len(copycells)==24
draftrows=[]
for oid in proj['draft_option_ids']:
 row=next(c[1:]for c,v in w['values']['Draft Listings'].items()if c.startswith('A')and v==oid);old=w['values']['Draft Listings']['N'+row];needle='Numeric selling price, stock and lead time unconfirmed';assert needle in old
 text=old.replace(needle,'Working estimated price and made-to-order1–2week policy recorded. Current native quote and physical stock remain unverified.');value('Draft Listings','N'+row,text);draftrows.append({'option_id':oid,'row':int(row)})
oid='BSI-C3AA3700F7DA';row=next(i for i,o in enumerate(g['options'],10)if o['product_id']==oid);c=next(c for c in a['coverage']if c['option_id']==oid);ar=next(i for i,t in enumerate(a['missing_pictures'],10)if t['option_id']==oid and t['role']=='Individual');t=a['missing_pictures'][ar-10];note=g['options'][row-10]['owner_accepted_listing_references']['basis'];caption=read(H/'imported-owner-image-acceptance.json')['approved_caption']
value('Master Catalogue','V'+str(row),note+'\n'+caption+'\nEarlier source notes: '+w['values']['Master Catalogue']['V'+str(row)])
value('Photo Coverage','L'+str(row),note+'\n'+caption+'\nEarlier role notes: '+w['values']['Photo Coverage']['L'+str(row)]);value('Photo Coverage','U'+str(row),c['owner_review'])
for col,k in [('F','action'),('L','qualification'),('M','owner_response'),('N','status')]:value('Missing Pictures',col+str(ar),t[k])
for sn,r in [('Master Catalogue',row),('Photo Coverage',row),('Missing Pictures',ar)]:heights.append({'sheet':sn,'row':r,'height':240})
headers={
 'Master Catalogue':'188 active options;189 retained records;112 working component identities. One owner-qualified whole-group listing reference accepted for Moon and Shellwave2 White Water Feature. Group only remains the technical photo type. Local draft fields/copy refreshed from existing qualified values.',
 'Photo Coverage':'177 complete individual photographs;10 owner-accepted qualified group/combined listing references.11 technical individual gaps remain, with no separate capture requests. Frozen Fish legacy identity remains deferred. All22 missing context and one missing Series request stay held.',
 'Missing Pictures':'24 diagnostic requirements retained:22 owner-held context,one owner-held Series and one deferred Frozen Fish identity. No active photograph prompts. MSW2 whole group accepted as a qualified one-panel listing reference; no standalone photograph newly verified.',
 'Draft Listings':'101 current individual option drafts and three custom-pattern draft scopes. All101 individual drafts now embed six qualified working fields in the canonical register. Six Fingerprint scaffolds retain their IDs and activation/media conditions. Drafts remain local and uncreated.',
 'Listing Corrections':'Four local copy drafts use the current six working field descriptions, including estimate labels and owner-instructed made-to-order1–2weeks. Native IDs, SKUs and historical request drafts remain unchanged. No platform execution.'}
for sn,text in headers.items():value(sn,'A3',text);links[(sn,'A3')]={'sheet':sn,'cell':'A3','label':text,'target':str(OUT/('current-draft-projections.html'if sn in ['Draft Listings','Listing Corrections']else'water-group-listing-reference.html'))}
for k,x in changes.items():
 if k in links:links[k]['label']=x['value']
expected={('Master Catalogue','B4'):188,('Master Catalogue','F4'):188,('Master Catalogue','H4'):187,('Photo Coverage','B4'):177,('Photo Coverage','D4'):166,('Photo Coverage','F4'):117,('Photo Coverage','B5'):11,('Missing Pictures','B4'):23,('Missing Pictures','D4'):1,('Missing Pictures','F4'):70}
firstcopy=copycells[0]['cell'][1:];firstdraft=draftrows[0]['row']
plan={'cell_changes':list(changes.values()),'formula_changes':[{'sheet':sn,'cell':c,'before':w['formulas'][sn][c],'formula':w['formulas'][sn][c],'expected':v}for(sn,c),v in expected.items()],'value_blocks':[{'sheet':x['sheet'],'range':x['cell'],'values':[[x['value']]]}for x in changes.values()],'formula_blocks':[],'hyperlinks':list(links.values()),'row_heights':heights,'table_appends':[],'new_sheets':{},'target_rows':[],'expected_original_sheet_count':28,'expected_formula_count':3407,'summary_expected':[{'sheet':sn,'cell':c,'value':v}for(sn,c),v in expected.items()],'copy_cells':copycells,'draft_rows':draftrows,'owner_option_row':row,'owner_action_row':ar,
 'baseline_ranges':[['Listing Corrections','D'+firstcopy+':F'+str(int(firstcopy)+2),'baseline-current-copy'],['Photo Coverage','L'+str(row)+':L'+str(row),'baseline-water-source-scope']],
 'preview_ranges':[['Listing Corrections','D'+firstcopy+':F'+str(int(firstcopy)+2),'01-current-copy-specifications'],['Listing Corrections','D'+str(int(firstcopy)+4)+':F'+str(int(firstcopy)+5),'02-current-copy-price-availability'],['Draft Listings','N'+str(firstdraft)+':N'+str(firstdraft),'03-fingerprint-current-conditions'],['Photo Coverage','L'+str(row)+':L'+str(row),'04-water-qualified-group-reference'],['Missing Pictures','L'+str(ar)+':N'+str(ar),'05-resolved-capture-by-owner-reference']],
 'supplemental_preview_ranges':[['Missing Pictures','A2:F5','06-current-diagnostic-counts']]}
write(H/'workbook-edit-plan.json',plan);write(H/'expected-edit.json',{'sheets':{},'hyperlinks':plan['hyperlinks'],'formulas':[]});print(json.dumps({'status':'PLAN_READY','cell_changes':len(changes),'copy_field_cells':24,'fingerprint_condition_rows':6,'group_only_type_unchanged':True}))
