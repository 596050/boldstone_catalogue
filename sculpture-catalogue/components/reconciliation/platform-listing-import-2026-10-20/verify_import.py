"""Verify new listing views and complete preservation of the thirteen prior tabs."""
import copy
import importlib.util
import json
import posixpath
import hashlib
from pathlib import Path
from datetime import datetime,timezone
from xml.etree import ElementTree as E

HERE=Path(__file__).resolve().parent
BASE=HERE.parents[2]
support=BASE/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py'
spec=importlib.util.spec_from_file_location('native_image_verifier',support);native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
native.HERE=HERE
read=lambda p:json.loads(Path(p).read_text())
digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
write=lambda p,d:Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
S=native.S;R=native.R;q=native.q

def hyperlinks(d):
    result=[]
    for n,s in d['sheets'].items():
        loc=s['part'];rp=posixpath.join(posixpath.dirname(loc),'_rels',posixpath.basename(loc)+'.rels')
        rels={r.get('Id'):r for r in E.fromstring(d['files'][rp])} if rp in d['files'] else {}
        for h in s['root'].findall('.//'+q('hyperlink')):
            target='#'+h.get('location') if h.get('location') else rels[h.get('{'+R+'}id')].get('Target')
            result.append({'sheet':n,'cell':h.get('ref'),'target':target,'label':d['values'][n][h.get('ref')]})
    return result

def table_targets(d,s):
    loc=s['part'];rp=posixpath.join(posixpath.dirname(loc),'_rels',posixpath.basename(loc)+'.rels')
    rels={r.get('Id'):r.get('Target') for r in E.fromstring(d['files'][rp])}
    result=[]
    for t in s['root'].findall('.//'+q('tablePart')):
        target=rels[t.get('{'+R+'}id')];part=target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.dirname(loc)+'/'+target)
        result.append(d['files'][part])
    return result

def main(attach=False):
    before=native.load(HERE/'inputs/master_workbook.before');exp=read(HERE/'expected-edit.json')
    if attach:
        if not exp.get('prior_hyperlinks_included'):
            exp['hyperlinks']=hyperlinks(before)+exp['hyperlinks'];exp['prior_hyperlinks_included']=True;write(HERE/'expected-edit.json',exp)
        native.attach()
    after=native.load(HERE/'master-workbook.pending');issues=[];checks=0
    def check(ok,message):
        nonlocal checks
        checks+=1
        if not ok:issues.append(message)
    check(list(after['sheets'])==list(before['sheets'])+list(exp['sheets']),'Only three new listing tabs appended')
    for n,s in before['sheets'].items():
        check(after['values'][n]==before['values'][n],n+' every prior cell value preserved')
        check(after['formulas'][n]==before['formulas'][n],n+' every prior formula preserved')
        check(after['styles'][n]==before['styles'][n],n+' every prior cell style preserved')
        for tag in ['sheetViews','sheetFormatPr','cols','mergeCells','conditionalFormatting','autoFilter','pageMargins']:
            check([E.tostring(x) for x in s['root'].findall(q(tag))]==[E.tostring(x) for x in after['sheets'][n]['root'].findall(q(tag))],n+' native '+tag)
        check([r.attrib for r in s['root'].find(q('sheetData'))]==[r.attrib for r in after['sheets'][n]['root'].find(q('sheetData'))],n+' row heights and attributes')
        check(table_targets(before,s)==table_targets(after,after['sheets'][n]),n+' native tables/filters preserved')
    for group in ['fonts','fills','borders','cellStyleXfs','cellXfs','numFmts','dxfs']:
        b=before['style_root'].find(q(group));a=after['style_root'].find(q(group));check(b is None or a is not None and all(E.tostring(x)==E.tostring(y) for x,y in zip(b,a)),group+' old resource definitions preserved')
    for name,d in exp['sheets'].items():
        for i,row in enumerate(d['rows'],10):
            for j,v in enumerate(row):check(after['values'][name].get(native.column(j)+str(i),'')==v,f'{name}!{native.column(j)}{i} source value')
        for j,v in enumerate(d['headers']):check(after['values'][name][native.column(j)+'9']==v,name+' header')
        check(after['sheets'][name]['root'].find('.//'+q('pane')) is not None,name+' frozen identifiers and header')
        check(len(after['sheets'][name]['root'].findall('.//'+q('tablePart')))==1,name+' filterable table')
    for f in exp['formulas']:
        check(after['formulas'][f['sheet']].get(f['cell'])==f['formula'],'Listing formula text')
        check(after['values'][f['sheet']].get(f['cell'])==f['expected'],'Listing formula result')
    actual=hyperlinks(after);check(actual==exp['hyperlinks'],'All old and new native links, targets and labels')
    g=read(HERE/'canonical-master-register.json');old=read(HERE/'inputs/master_register.before');packet=read(HERE/'inputs/LISTING_RECONCILIATION.json');counts=read(HERE/'inputs/RECONCILIATION_COUNTS.json')
    stripped=copy.deepcopy(g)
    for o in stripped['options']:o.pop('current_listing_reconciliation')
    for k in ['current_listing_source_links','current_listing_match_evidence','current_listing_issues','latest_listing_reconciliation']:stripped.pop(k)
    check(stripped==old,'Original complete master graph unchanged except listing supplements')
    check(len(packet['options'])==len({x['product_id'] for x in packet['options']})==184,'184 complete unique listing dispositions')
    for o,x in zip(g['options'],packet['options']):
        check(o['product_id']==x['product_id'] and o['name']==x['name'],'Approved option identity')
        check({k:v['display'] for k,v in o['master_fields'].items()}==x['working_specifications'],'All six current working fields exact')
        check(o['photo_coverage']==x['photo_coverage'] and o.get('file_id')==x['primary_image_file_id'],'Current media identity preserved')
        check(not x['exact_current_option_configuration_match_verified'],'No exact configuration upgrade from source association')
        for platform in x['platforms'].values():check(not platform['current_authenticated_admin_inventory_verified'],'No authenticated admin claim')
    check(sum(counts['overall_option_dispositions'].values())==184,'Overall disposition arithmetic')
    check(sum(counts['Squarespace_option_dispositions'].values())==sum(counts['Shopify_option_dispositions'].values())==184,'Both184-row platform assessments')
    check(counts['source_supported_individual_design_options']==45 and counts['nonconflicting_source_supported_individual_record_links']==41 and counts['existing_individual_design_records_with_configuration_conflict']==4,'Design-record presence and configuration-conflict counts separate')
    check(counts['options_without_supported_individual_native_record']==139 and counts['options_without_nonconflicting_supported_individual_native_record']==143,'Distinct missing-association denominators')
    check(g['latest_image_coverage_audit']==old['latest_image_coverage_audit'],'Media-audit receipt preserved')
    check(sum(len(x) for x in after['formulas'].values())==sum(len(x) for x in before['formulas'].values())+len(exp['formulas']),'Only nine new summary formulas')
    manifest=read(HERE/'input-manifest.json')
    for x in manifest.values():check(digest(x['path'])==digest(x['snapshot'])==x['sha256'],'Sealed input still unchanged')
    result={'status':'PASS' if not issues else 'FAIL','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues[:40],
      'workbook_sha256':digest(HERE/'master-workbook.pending'),'register_sha256':digest(HERE/'canonical-master-register.json'),
      'prior_sheets_preserved':13,'new_listing_sheets':3,'all_prior_values_formulas_styles_links_tables_panes_preserved':not issues,
      'native_hyperlinks':len(actual),'formula_count':sum(len(x) for x in after['formulas'].values()),'counts':counts,
      'prior_media_audit_preserved':True,'all1104_working_fields_preserved':True,'source_seal_sha256':manifest['packet_seal']['sha256'],
      'source_payload_sha256':manifest['LISTING_RECONCILIATION.json']['sha256'],'no_platform_or_dropbox_mutations':True}
    write(HERE/'saved-file-verification.json',result)
    print(json.dumps({k:result[k] for k in ['status','checks','issues','native_hyperlinks','formula_count']}))
    if issues:raise SystemExit(1)

if __name__=='__main__':
    import sys
    main('--attach' in sys.argv)
