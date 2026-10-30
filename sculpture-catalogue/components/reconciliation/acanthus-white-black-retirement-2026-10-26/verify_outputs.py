"""Independent saved-reader/export checks before publishing the current pointer."""
from pathlib import Path
from html.parser import HTMLParser
from collections import Counter
import csv,hashlib,json
H=Path(__file__).resolve().parent
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
manifest=read(H/'output-manifest.json');out=Path(manifest['output_directory'])
g=read(H/'canonical-master-register.json');old=read(H/'inputs/register.json');ids=g['active_option_ids'];byid={o['product_id']:o for o in g['options']}
native=read(H/'current-native-overlay.json');current=native['current_objects']
OID='BSI-B0D0CCA7E318';checks=0
def check(value,message):
    global checks
    checks+=1
    assert value,message
def rows(name):
    with (out/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
check(sha(H/'canonical-master-register.json')=='1774c391792a5ccb7c65c4d4c6ba48b32f5956278de02e5ca5354b9e7c611c58','Frozen app-ready source')
for path,digest in manifest['outputs'].items():check(sha(path)==digest,'Output bytes '+path)
check(len(ids)==187 and len(g['options'])==189 and len(g['retired_option_ids'])==2,'Lifecycle counts')
for o in old['options']:
    if o['product_id']!=OID:check(o==byid[o['product_id']],'Other option unchanged '+o['product_id'])
for key in ['master_fields','specifications','source_product_sha256','file_id','folder_id']:
    check(byid[OID][key]==next(o for o in old['options'] if o['product_id']==OID)[key],'Retired history '+key)
check(g['original_review_specification_assertions']==old['original_review_specification_assertions'],'Original assertions')
options=rows('Current_Individual_Options_187.csv')
check([r['option_id'] for r in options]==ids,'Exact active option CSV order')
for r in options:
    o=byid[r['option_id']]
    for k,v in o['master_fields'].items():
        check(r[k]==v['display'] and r[k+' evidence state']==v['state'],'Exact field '+r['option_id']+' '+k)
    fid=r['reference_file_id'];folder=r['reference_folder_id']
    check(r['image_url']==current.get(fid,{}).get('image_url',''),'Current source-image URL '+fid)
    check(r['folder_url']==current.get(folder,{}).get('folder_url',''),'Current actual-folder URL '+folder)
fields=rows('Specification_Verification_Checklist_1122_Fields.csv')
check(len(fields)==1122 and set(r['option_id'] for r in fields)==set(ids),'Field population')
check(Counter(r['option_id'] for r in fields)==dict.fromkeys(ids,6),'Six fields each')
for r in fields:
    v=byid[r['option_id']]['master_fields'][r['field']]
    check(r['working_display']==v['display'] and r['evidence_state']==v['state'] and r['basis']==v['basis'],'Checklist exact evidence')
photo=rows('Photo_Coverage_187.csv');check([r['option_id'] for r in photo]==ids,'Photo population')
for r in photo:
    o=byid[r['option_id']]
    for role in ['individual','in_situ','series']:check(r[role]==o['photo_coverage'][role],'Retained photo role '+role)
check(sum(r['in_situ_owner_hold']=='True' for r in photo)==22,'Owner holds preserved')
treatments=rows('Active_Listing_Treatments_187.csv');check({r['product_id'] for r in treatments}==set(ids),'Listing treatment population')
payload=(out/'Active_Listing_Treatments_187.csv').read_text()
for text in [OID,'BOLD-B0D0CCA7E318','boldstone-acanthus-two-leaves-white-and-black-a7e318']:check(text not in payload,'Retired proposed identifier removed')
physical=rows('Physical_Verification_Input_187_Options.csv');check({r['option_id'] for r in physical}==set(ids),'Physical input population')
pointer=read(H/'inputs/pointer.json');base=H.parents[2]
with (base/pointer['current_specification_verification']['actual_physical_measurement_input']).open(encoding='utf-8-sig',newline='') as f:
    previous={r['option_id']:r for r in csv.DictReader(f)}
for r in physical:
    before=previous[r['option_id']]
    for k,v in r.items():
        if k not in {'individual_image','containing_folder','file_id','folder_id'}:check(v==before[k],'No changed physical input '+r['option_id']+' '+k)
class Articles(HTMLParser):
    def __init__(self):super().__init__();self.ids=[];self.links=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='article':self.ids.append(a.get('id'))
        if tag=='a':self.links.append(a.get('href'))
for name in ['all-options.html','specifications-to-verify.html','photograph-checklist.html','listing-treatments.html']:
    parser=Articles();text=(out/name).read_text();parser.feed(text)
    check(parser.ids==ids,'HTML active identities/order '+name)
    check(OID not in text,'Retired option not active HTML '+name)
    check(all(link for link in parser.links),'No empty links '+name)
check(all(r['target'] not in current for r in read(H/'native-readback.json')['rows']),'Retired native IDs absent')
report={'status':'PASS_CURRENT187_SAVED_OUTPUTS','checks':checks,'active_options':187,'retained_options':189,'retired_options':2,
    'specification_field_rows':1122,'other_option_objects_exactly_unchanged':188,'original_assertions_preserved':1668,
    'native_snapshot':manifest['summary']['native_snapshot'],'in_situ_owner_holds_preserved':22,
    'no_new_physical_verification':True,'native_platform_or_review_writes':0,'output_manifest_sha256':sha(H/'output-manifest.json'),
    'workbook_verification_sha256':sha(H/'saved-workbook-verification.json'),'terminal_script_sha256':sha(H/'walkthrough.py')}
(H/'saved-output-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
