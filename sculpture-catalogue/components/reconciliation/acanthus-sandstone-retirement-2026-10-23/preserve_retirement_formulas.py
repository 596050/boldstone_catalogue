"""Retirement labels must be calculated where the existing cells are formulas."""
import importlib.util,json,shutil
from pathlib import Path
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text())
s=importlib.util.spec_from_file_location('v',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');v=importlib.util.module_from_spec(s);s.loader.exec_module(v);b=v.load(H/'inputs/master_workbook.before');p=read(H/'workbook-edit-plan.json');forms={(x['sheet'],x['cell']):x for x in p['formula_changes']};keep=[];converted=[]
for x in p['cell_changes']:
 sn,c=x['sheet'],x['cell'];old=b['formulas'][sn].get(c)
 if old is None:keep.append(x);continue
 expected=x['value']
 if sn=='Components':expected=2;formula='=COUNTIFS(\'Master Catalogue\'!$D$10:$D$197,A'+c[1:]+',\'Master Catalogue\'!$L$10:$L$197,"<>Retired")'
 elif sn=='Selling Details'and c in ['C16','D16']:formula=old
 else:
  condition='L16="Retired"'if sn=='Master Catalogue'else'\'Master Catalogue\'!L16="Retired"';label=json.dumps(expected,ensure_ascii=False);formula='=IF('+condition+','+label+','+old[1:]+')'
 forms[(sn,c)]={'sheet':sn,'cell':c,'before':old,'formula':formula,'expected':expected};converted.append([sn,c])
for c in ['E16','F16','G16','H16']:forms[('Master Catalogue',c)]={'sheet':'Master Catalogue','cell':c,'before':b['formulas']['Master Catalogue'][c],'formula':b['formulas']['Master Catalogue'][c],'expected':''}
p['cell_changes']=keep;p['value_blocks']=[{'sheet':x['sheet'],'range':x['cell'],'values':[[x['value']]]}for x in keep];p['formula_changes']=list(forms.values());p['summary_expected']=[{'sheet':x['sheet'],'cell':x['cell'],'value':x['expected']}for x in forms.values()]
(H/'workbook-edit-plan.json').write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n')
archive=H/'iteration1';archive.mkdir(exist_ok=False)
for name in ['master-workbook.pending','native-attachment.json','saved-file-verification.json','native-binding-verification.json','artifact-authoring-receipt.json','preview-manifest.json','formula-error-scan.ndjson']:
 if(H/name).exists():shutil.move(H/name,archive/name)
print(json.dumps({'preserved_formula_cells':converted,'expected_total_formulas':p['expected_formula_count']}))
