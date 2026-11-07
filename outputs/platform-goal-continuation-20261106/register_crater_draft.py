"""Append the verified created artwork ID without changing any earlier binding."""
import hashlib, importlib.util, json
from pathlib import Path
ROOT=Path('/Users/tprice/Documents/boldstone');OUT=Path(__file__).parent
read=lambda p:json.loads(p.read_text())
intent=read(OUT/'saatchi-crater-iii-create-intent.json')
assert intent['status']=='SAVED_PRIMARY_DRAFT_NATIVE_ID_VERIFIED'
assert intent['sku']=='SQ6211184' and intent['native_artwork_id']=='14396897'
proof=OUT/'evidence/saatchi-14396897-description-initial.txt'
text=proof.read_text()
assert 'saatchiart.com/en-gb/studio/art/14396897/description' in text and intent['title'] in text and 'text DRAFT' in text
assert hashlib.sha256(Path(intent['photo_path']).read_bytes()).hexdigest()==intent['photo_sha256']
registry=ROOT/'outputs/catalogue-marketplace-publication-20261101/saatchi-current/primary-draft-receipts.json'
before=read(registry)
existing=[r for r in before if r['sku']==intent['sku'] or r['artwork_id']==intent['native_artwork_id']]
row=dict(sku=intent['sku'],catalogue_id=intent['catalogue_id'],title=intent['title'],artwork_id=intent['native_artwork_id'],url='https://www.saatchiart.com/en-gb/studio/art/14396897/overview',primary_photo_id='id:cnqzTNngPVsAAAAAAAygfg',primary_sha256=intent['photo_sha256'],primary_original_app_use='In situ',status='DRAFT_PRIMARY_ONLY_NOT_PUBLISHED',saved_utc=intent['saved_utc'],identity_evidence=str(proof.relative_to(ROOT)))
if existing:
 assert len(existing)==1 and existing[0]['sku']==row['sku'] and existing[0]['artwork_id']==row['artwork_id']
 updated=before
else:updated=before+[row]
spec=importlib.util.spec_from_file_location('saatchi',ROOT/'catalogue-review/scripts/prepare_saatchi_catalogue.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
tmp=registry.with_suffix('.pending.json');tmp.write_text(json.dumps(updated,indent=2)+'\n')
bindings=module.native_artwork_bindings(tmp);assert len(bindings)==len(set(bindings.values()))==113
assert updated[:len(before)]==before
tmp.replace(registry)
packets=read(OUT/'context-upload-packets.json')
packet=next(r for r in packets if r['sku']==intent['sku'])
packet.update(native_artwork_id=intent['native_artwork_id'],native_action='COMPLETE_EXISTING_DRAFT_ONLY',publication_status='DRAFT_PRIMARY_UPLOADED_NOT_PUBLISHED')
packet['photo'].update(native_image_upload_test_still_required=False,native_image_format_accepted=True,native_upload_dimensions_verified=[1512,1905])
(OUT/'context-upload-packets.json').write_text(json.dumps(packets,ensure_ascii=False,indent=2)+'\n')
result=dict(status='PASS_APPEND_ONLY_NATIVE_BINDING',existing_rows_preserved=len(before),total_creation_receipts=len(updated),unique_native_bindings=len(bindings),published_before_creation=112,new_drafts=1,native_id='14396897')
(OUT/'crater-native-binding-receipt.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
