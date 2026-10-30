"""Plan owner-equivalence notes without changing retained rows or formulas."""
import importlib.util,json,posixpath
from pathlib import Path
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;B=H.parents[2];OUT=B/'outputs'/H.name;read=lambda p:json.loads(Path(p).read_text())
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
s=importlib.util.spec_from_file_location('n',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(s);s.loader.exec_module(n)
w=n.load(H/'inputs/master_workbook.before');g=read(H/'canonical-master-register.json');proj=read(H/'projection-index.json');OLD=proj['old_output'];changes={};links={}
def value(sn,c,v):
 assert c not in w['formulas'][sn]
 if w['values'][sn].get(c,'')!=v:changes[(sn,c)]={'sheet':sn,'cell':c,'before':w['values'][sn].get(c,''),'value':v}
def protected(sn,c):return sn=='Fingerprint History' or sn=='Source Specifications'and c.rstrip('0123456789')in ['M','N']or sn=='Moonphases and Dune'and c.rstrip('0123456789')=='I'
for sn,z in w['sheets'].items():
 rp=posixpath.join(posixpath.dirname(z['part']),'_rels',posixpath.basename(z['part'])+'.rels');rels={x.get('Id'):x.get('Target')for x in E.fromstring(w['files'][rp])}
 for x in z['root'].findall('.//'+n.q('hyperlink')):
  c=x.get('ref');u='#'+x.get('location')if x.get('location')else rels[x.get('{'+n.R+'}id')];target=u if protected(sn,c)else u.replace(OLD,str(OUT));links[(sn,c)]={'sheet':sn,'cell':c,'label':w['values'][sn].get(c,''),'target':target}
text='188 active options;112 retained component IDs;111 working design groups. Owner confirmed Decowaves1 Verdigris and Frozen Decowaves1 White share a design. Finish options/specifications kept separate; number2 unconfirmed.'
value('Master Catalogue','A3',text);links[('Master Catalogue','A3')]={'sheet':'Master Catalogue','cell':'A3','label':text,'target':str(OUT/'decowaves1-owner-design-equivalence.html')}
value('Master Catalogue','C4','Component ID records')
value('Specifications','A3','Current checklist:188 options and752 physical field groups, including4 water-build comparator-only fields. Accepted estimates/source qualifications retained; no new measured or inspected evidence. Open the evidence checklist for each option.')
value('Components','A3','112 retained component ID records project to111 working design groups after one owner-confirmed equivalence: Decowaves1 Verdigris and Frozen Decowaves1 White. Finish/size/build options remain separate. Physical casts, moulds, stock and whole-library unique total remain unverified.')
note='Owner24 Oct: number1 Verdigris/White are the same design. Both finish options retain their own specs/IDs. Number2 unconfirmed.'
for oid in proj['pair_option_ids']:
 row=next(i for i,o in enumerate(g['options'],10)if o['product_id']==oid)
 for sn,col in [('Master Catalogue','V'),('Photo Coverage','L')]:value(sn,col+str(row),w['values'][sn].get(col+str(row),'')+'\n'+note)
for cid in proj['pair_component_ids']:
 row=next(int(c[1:])for c,v in w['values']['Components'].items()if c.startswith('A')and v==cid)
 value('Components','E'+str(row),'Retained ID in working design group BC-DECO-1. Owner confirmed the number1 Verdigris/White pair; finish options and specifications remain separate. Number2 unconfirmed; no new Terracotta photo approval.')
for key,x in changes.items():
 if key in links:links[key]['label']=x['value']
expected={('Master Catalogue','B4'):188,('Master Catalogue','D4'):112,('Master Catalogue','F4'):188,('Master Catalogue','H4'):187,('Photo Coverage','B4'):177,('Photo Coverage','D4'):166,('Photo Coverage','F4'):117,('Photo Coverage','B5'):11,('Missing Pictures','B4'):23,('Missing Pictures','D4'):1,('Missing Pictures','F4'):70,('Draft Listings','B4'):101,('Draft Listings','D4'):3}
pairrows=[next(i for i,o in enumerate(g['options'],10)if o['product_id']==oid)for oid in proj['pair_option_ids']]
plan={'cell_changes':list(changes.values()),'formula_changes':[{'sheet':sn,'cell':c,'before':w['formulas'][sn][c],'formula':w['formulas'][sn][c],'expected':v}for(sn,c),v in expected.items()],'value_blocks':[{'sheet':x['sheet'],'range':x['cell'],'values':[[x['value']]]}for x in changes.values()],'formula_blocks':[],'hyperlinks':list(links.values()),'row_heights':[{'sheet':'Master Catalogue','row':r,'height':65}for r in pairrows]+[{'sheet':'Photo Coverage','row':53,'height':75}],'table_appends':[],'new_sheets':{},'target_rows':[],'expected_original_sheet_count':28,'expected_formula_count':3407,'summary_expected':[{'sheet':sn,'cell':c,'value':v}for(sn,c),v in expected.items()],'native_link_changes':[],
 'baseline_ranges':[['Components','A3:K3','baseline-component-scope'],['Components','E35:E37','baseline-pair-component-notes'],['Specifications','A2:R5','baseline-physical-checklist-header']],
 'preview_ranges':[['Components','A3:K3','01-current-component-scope'],['Components','E35:E37','02-current-pair-component-notes']],
 'supplemental_preview_ranges':[['Master Catalogue','A2:Y5','03-current-catalogue-header'],['Specifications','A2:R5','05-current-physical-checklist-header']]+[['Photo Coverage','L'+str(r)+':L'+str(r),'04-owner-note-'+str(r)]for r in pairrows]}
write(H/'workbook-edit-plan.json',plan);write(H/'expected-edit.json',{'sheets':{},'hyperlinks':plan['hyperlinks'],'formulas':[]});print(json.dumps({'status':'PLAN_READY','cell_changes':len(changes),'pair_rows':pairrows,'native_image_links_changed':0}))
