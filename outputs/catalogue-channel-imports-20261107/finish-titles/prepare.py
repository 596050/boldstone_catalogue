import csv,hashlib,json,re,shutil,sys
from pathlib import Path
ROOT=Path('/Users/tprice/Documents/boldstone');OUT=Path(__file__).parent;PARENT=OUT.parent
sys.path[:0]=[str(ROOT/'catalogue-review'),str(ROOT/'catalogue-review/scripts')]
from channel_content import finish_retail_name
from import_saatchi_snapshot import Xlsx
read=lambda n:json.loads((PARENT/n).read_text())
write=lambda n,v:(OUT/n).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
pointer=json.loads((ROOT/'sculpture-catalogue/current-master.json').read_text());source=pointer['current_app_review_workbook']
assert source['sha256']==hashlib.sha256(Path(source['path']).read_bytes()).hexdigest()
shutil.copyfile(source['path'],OUT/'previous-catalogue.xlsx');write('source-pointer-before.json',pointer);write('previous-dropbox-metadata.json',source['dropbox'])
for name in ['app-specifications.json','google-sheet-destinations.json']:shutil.copyfile(PARENT/name,OUT/name)
book=Xlsx(OUT/'previous-catalogue.xlsx');app=read('app-specifications.json');products={p['id']:p for p in app['products']}
patches=[];changed=[]
for row in range(8,189):
    pid=book.value('Wall Sculptures','AA'+str(row));before=book.value('Wall Sculptures','XV'+str(row));title=finish_retail_name(products[pid])
    if title!=before:
        patches.append(dict(sheet='Wall Sculptures',cell='XV'+str(row),before=before,value=title))
        changed.append(dict(catalogue_id=pid,row=row,before=before,title=title))
matches=read('google-source-reconciliation.json')['wall_sculpture_matches_detail'];id_to_pid={r['google_offer_id']:r['catalogue_id'] for r in matches}
records=read('pinterest-feed-records.json');headers=read('pinterest-template-schema.json')['fields']
for r in records:r['title']=finish_retail_name(products[id_to_pid[r['id']]])
with (OUT/'pinterest_wall_sculptures.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=headers);w.writeheader();w.writerows(records)
write('pinterest-feed-records.json',records)
write('google-native-title-differences.json',[dict(catalogue_id=r['catalogue_id'],native_google_title=r['google_title'],catalogue_title=finish_retail_name(products[r['catalogue_id']])) for r in matches if r['google_title']!=finish_retail_name(products[r['catalogue_id']])])
write('native-title-pastes.json',dict(master_range='XV8:XV188',master_tsv='\n'.join(finish_retail_name(products[book.value('Wall Sculptures','AA'+str(row))]) for row in range(8,189)),
    public_range='B2:B177',public_tsv='\n'.join(r['title'] for r in records)))
write('plan.json',dict(scope='Keep decorative surface effects explicit in prepared Pinterest titles using the current catalogue. Native Google titles remain as observed. Other descriptions, IDs, prices, imagery and channel statuses unchanged.',
    patches=patches,previews=[dict(name='pinterest-titles',range='XU7:XW10')],row_heights=[],faire_products_verified=176,new_instagram_publications=0,
    new_native_publications_recorded=0,new_native_drafts_recorded=0,public_feed_rows=records,pinterest_feed_fields=headers))
print(json.dumps(dict(pinterest_master_titles_changed=len(patches),publication_titles_changed=len(json.loads((OUT/'google-native-title-differences.json').read_text())),core_records=181,publication_records=176)))
