#!/usr/bin/env python3
"""Independent saved-file and source-scope checks for all current options."""
import csv
import hashlib
import json
import re
import zipfile
from xml.etree import ElementTree as ET
from collections import Counter
from pathlib import Path

ROOT = Path('/Users/tprice/Documents/boldstone')
WORK = Path(__file__).resolve().parent
OUT = ROOT/'sculpture-catalogue/outputs/01a13fe6-495b-7253-b923-31823b4cbca8/matched-listing-2026-10-25'
GALLERY = ROOT/'sculpture-catalogue/components/parallel-reviews/all-record-image-matching-20261024-B/published-projections/20261025T014714043538Z'

def read(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rows(p):
    with Path(p).open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))
def plain(s): return re.sub(r'\s+',' ',str(s).replace('**','')).strip()

def main():
    checks=[]
    def check(ok, label):
        checks.append({'check':label,'pass':bool(ok)})
        if not ok: raise AssertionError(label)
    manifest=read(WORK/'input-manifest.json')
    for r in manifest['inputs']: check(sha(r['path'])==r['sha256'],'Source unchanged: '+r['path'])
    baseline=read(manifest['inputs'][0]['path'])
    active=set(baseline['active_option_ids'])
    originals={o['product_id']:o for o in baseline['options'] if o['product_id'] in active}
    candidates={o['product_id']:o for o in read(WORK/'prepared-working-options.json')['options']}
    treatment=read(WORK/'listing-treatment-register.json')
    treatments={o['product_id']:o for o in treatment['options']}
    crosswalk=read(manifest['inputs'][1]['path'])
    ss={s['offer_ref']:s for s in crosswalk['squarespace_source_records']}
    saved=rows(OUT/'Boldstone_All_188_Products_2026-10-25.csv')
    byid={x['catalogue_option_id']:x for x in saved}
    change_packet=read(WORK/'specification-completion-packet.json')
    changes={(c['product_id'],c['field']):c for c in change_packet['changes']}
    check(set(originals)==set(candidates)==set(treatments)==set(byid)==active,'Exact coverage of all188 active options')
    check(len(saved)==188 and len(changes)==30,'188 unique CSV rows and30 scoped field changes')
    field_columns={'Dimensions / depth':'dimensions_and_depth','Weight':'weight','Material / finish':'material_and_finish','Fixing':'fixing_detail','Individual price':'price_display','Availability':'availability_detail'}
    for pid, before in originals.items():
        after=candidates[pid]
        row=byid[pid]
        check({k:v for k,v in before.items() if k!='master_fields'}=={k:v for k,v in after.items() if k!='master_fields'},pid+' non-specification fields unchanged')
        check(row['product_name']==before['name'],pid+' current name preserved')
        for field,col in field_columns.items():
            expected=changes[(pid,field)]['after'] if (pid,field) in changes else before['master_fields'][field]
            check(after['master_fields'][field]==expected,pid+' exact field object: '+field)
            check(row[col]==plain(expected['display']),pid+' CSV field readback: '+field)
            check(treatments[pid]['accepted_working_fields'][field]==expected,pid+' matching-plan field readback: '+field)
        check(float(row['individual_price_gbp'])==before['selling_details']['estimated_price'],pid+' retained numeric individual price')
        check(float(row['lead_time_min_weeks'])==before['selling_details']['lead_time_min_weeks'],pid+' retained minimum lead time')
        check(float(row['lead_time_max_weeks'])==before['selling_details']['lead_time_max_weeks'],pid+' retained maximum lead time')
        image=before.get('owner_confirmed_design_reference') if before['photo_coverage']['individual']=='Shared design reference' else before
        for col,key in [('image_url','image_url'),('folder_url','folder_url'),('image_file_id','file_id'),('folder_id','folder_id')]:
            check(row[col]==image[key],pid+' reference '+col)
        check(bool(row['image_url']) and bool(row['folder_url']),pid+' has review image and folder links')
        check(Path(row['all_images_review']).is_file(),pid+' complete image reader exists')
        if before['photo_coverage']['in_situ']!='Available':
            check(not row['installation_image_url'],pid+' unavailable/deferred context not promoted as current')
        t=treatments[pid]
        check(t['native_execution_allowed'] is False,pid+' no native execution')
        if t['selected_squarespace_variant_id']:
            if t['listing_treatment']=='REUSE_RECORDED_PATTERN_VARIANT_WORKING_MAPPING':
                old=next(v for v in baseline['wall_circle_native_options'] if v['variant_id']==t['selected_squarespace_variant_id'])
                check(old['sku']==t['selected_existing_source_sku'],pid+' exact saved pattern SKU')
                check(old['attributes']['Diameter Size']=='50cm/19.7in' and old['attributes']['Lighting']=='RGB Color Light',pid+' exact saved pattern configuration')
            else:
                ref=t['selected_source_offer_refs'][0]
                record=ss[ref]
                for dest,source in [('selected_squarespace_product_id','native_product_id'),('selected_squarespace_variant_id','native_variant_id'),('selected_existing_source_sku','sku_raw')]:
                    check(t[dest]==record['squarespace_native_tuple'][source],pid+' saved native identity '+dest)
                check(record['retained_source_offer']['sale_unit_state']=='Sale component',pid+' selected source is an individual sale unit')
                if t['selected_local_shopify_handle']:
                    check(t['selected_local_shopify_handle']==record['shopify_local_product']['handle'],pid+' local Shopify handle')
                    check(record['shopify_local_variant']['sku_raw'].strip()==t['selected_existing_source_sku'].strip(),pid+' local Shopify SKU equality')
        check(t['shopify_numeric_product_id'] is None and t['shopify_numeric_variant_id'] is None,pid+' no invented Shopify numeric IDs')
    for c in changes.values():
        check(c['before']==originals[c['product_id']]['master_fields'][c['field']],c['product_id']+' exact before object')
        check(c['after']['physical_verification']==0,c['product_id']+' proposal not a physical verification')
        check(c['after']['completion_proposal']['owner_confirmed_specific_value'] is False,c['product_id']+' no invented individual approval')
    check(Counter(c['field'] for c in changes.values())=={'Material / finish':27,'Dimensions / depth':3},'Exact27/3 change population')
    for pid,depth in [('BSI-65A93033A200',6),('BSI-4515726BBC18',6),('BSI-3C849B547D50',3)]:
        check(candidates[pid]['master_fields']['Dimensions / depth']['completion_proposal']['depth_cm']==depth,pid+' depth retained')
    special=treatments['BSI-04D6E8690F30']
    check(not special['selected_squarespace_product_id'] and not special['proposed_listing_sku'],'FFL1 retained without new duplicate SKU')
    check(not treatments['BSI-EBD43DF0704F']['selected_squarespace_variant_id'],'MCP1 candidate not promoted to selected variant')
    for key in ['selected_squarespace_variant_id','proposed_listing_sku']:
        vals=[t[key] for t in treatments.values() if t[key]]
        check(len(vals)==len(set(vals)),'No collision in '+key)
    check(treatment['summary']['historical_65_dispositions']==dict(Counter(t['listing_treatment'] for t in treatments.values() if t['historical_queue'].startswith('65_'))),'All65 dispositions reconcile')
    check(sum(t['historical_queue'].startswith('123_') for t in treatments.values())==123,'All123 associated options covered')
    audit=read(WORK/'all-source-association-audit.json')['entries']
    check(Counter((a['product_id'],a['offer_ref']) for a in audit)==Counter((e['product_id'],e['offer_ref']) for e in baseline['current_listing_match_evidence']['edges']),'All262 prior matching edges retained')
    media=rows(OUT/'Product_Image_Assignments_188.csv')
    check(len(media)==188 and {m['catalogue_option_id'] for m in media}==active,'All188 primary/shared references exported')
    all_media=rows(OUT/'All_Product_Image_Associations_10847.csv')
    source_images=read(GALLERY/'per-product-image-lists.json')
    actual={(x['catalogue_option_id'],x['file_id']):x for x in all_media}
    expected={(pid,x['file_id']):x for pid,ls in source_images.items() for x in ls}
    check(len(actual)==len(expected)==10847,'All10847 qualified image associations preserved once')
    for key,x in expected.items():
        y=actual[key]
        check(all(y[k]==('' if x[k] is None else x[k]) for k in ['image_url','folder_url','native_status','visual_role']),'Image association readback '+str(key))
        check(y['association_statuses']=='; '.join(x['association_statuses']),'Image association qualification '+str(key))
    # Artifact Tool import readback, comparing every exported data cell. Native
    # hyperlinks are independently checked in the saved relationship parts below.
    wb=read(WORK/'saved-workbook-readback.json')
    expected_wb=read(WORK/'workbook-expected.json')
    for sheet,exp in expected_wb.items():
        got=wb[sheet]
        check(got['values'][6]==exp['headers'],sheet+' saved headers')
        for i,row in enumerate(exp['rows']):
            for j,value in enumerate(row):
                label=exp['linkColumns'].get(str(j))
                if label and value:
                    check(got['values'][i+7][j]==label,f'{sheet} saved link label {i+8}/{j+1}')
                else:
                    actual_value=got['values'][i+7][j]
                    check(actual_value==value or (actual_value is None and value==''),f'{sheet} saved cell {i+8}/{j+1}')
    check(wb['Products']['values'][3][2]==188,'Saved formula active-option count188')
    check(wb['Products']['values'][3][5]==27,'Saved formula material proposal count27')
    check(wb['Products']['values'][3][8]==3,'Saved formula face-size estimate count3')
    text=(OUT/'index.html').read_text()
    check(len(re.findall(r'<article id="BSI-',text))==188,'All188 HTML product cards')
    for p in ['Boldstone_Matched_Product_List_2026-10-25.xlsx','Boldstone_All_188_Products_2026-10-25.csv','Product_Image_Assignments_188.csv','All_Product_Image_Associations_10847.csv','Specification_Changes_30.csv','Listing_Treatments_188.csv']:
        check((OUT/p).is_file() and (OUT/p).stat().st_size>0,'Download exists '+p)
    xlsx=OUT/'Boldstone_Matched_Product_List_2026-10-25.xlsx'
    with zipfile.ZipFile(xlsx) as z:
        check(z.testzip() is None,'Saved XLSX container readable')
        check(len([n for n in z.namelist() if re.fullmatch(r'xl/worksheets/sheet\d+\.xml',n)])==4,'Four saved worksheets')
        check(len([n for n in z.namelist() if re.fullmatch(r'xl/tables/table\d+\.xml',n)])==4,'Four saved filter tables')
        S='http://schemas.openxmlformats.org/spreadsheetml/2006/main';R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
        for n,(name,exp) in enumerate(expected_wb.items(),1):
            sheetxml=ET.fromstring(z.read(f'xl/worksheets/sheet{n}.xml'))
            rels={r.get('Id'):r for r in ET.fromstring(z.read(f'xl/worksheets/_rels/sheet{n}.xml.rels'))}
            links={h.get('ref'):h for h in sheetxml.findall('{'+S+'}hyperlinks/{'+S+'}hyperlink')}
            for i,row in enumerate(exp['rows'],8):
                for j,label in exp['linkColumns'].items():
                    if not row[int(j)]:continue
                    address=chr(65+int(j))+str(i)
                    h=links[address];rel=rels[h.get('{'+R+'}id')]
                    check(rel.get('Target')==row[int(j)] and rel.get('TargetMode')=='External' and h.get('display')==label,f'{name} native hyperlink {address}')
    sealed=read(WORK/'sealed-specification-packet.json')
    check(sha(sealed['path'])==sealed['sha256'],'Frozen specification packet unchanged')
    result={'status':'PASS_ALL_OPTION_AND_SAVED_OUTPUT_CHECKS','checks_passed':len(checks),'failures':0,'active_options':188,'source_matching_edges':262,'image_associations':10847,'changed_specification_fields':30,'unchanged_active_specification_fields':1098,'unchanged_retained_specification_fields':1104,'native_writes':0,'validation_scope':'Saved local files, source identity/scope, proposal qualification, no duplicate selected native IDs/SKUs, images and workbook readback. Not physical or live platform certification.'}
    (WORK/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__': main()
