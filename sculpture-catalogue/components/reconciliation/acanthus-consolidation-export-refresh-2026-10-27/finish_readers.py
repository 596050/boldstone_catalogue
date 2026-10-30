"""Expose current aliases, specifications, approved extra pictures and counts."""
from common import *
from html import escape
import csv

titles=read(H/'white-title-audit-input.json')
for p in (H/'gallery-projection').glob('*.html'):
    text=p.read_text()
    for r in titles['corrected']:
        original=next(o for o in read(manifest['sources']['register']['snapshot'])['options'] if o['product_id']==r['id'])
        text=text.replace('<h2>'+escape(original['name'])+'</h2>','<h2>'+escape(r['name'])+'</h2>')
    if p.name=='product-images.html':
        keeper=options['BSI-93ADE7C4103D'];extra=[]
        for fid,label in [('id:cnqzTNngPVsAAAAAAAyj8Q','Additional reviewed listing and advertising photograph'),('id:cnqzTNngPVsAAAAAAAyluQ','Additional qualified group context')]:
            f=files[fid];extra.append('<a href="'+escape(f['image_url'],quote=True)+'">'+escape(label)+'</a> · <a href="'+escape(f['folder_url'],quote=True)+'">Actual containing folder</a>')
        heading='<article id="BSI-93ADE7C4103D"><h2>'+escape(keeper['name'])+'</h2>'
        text=text.replace(heading,heading+'<p>'+(' · '.join(extra))+'</p><p class="small">Original Primary and board-display context retained. The transferred group view remains qualified by its identified position, scene origin and scale.</p>')
    p.write_text(text)
seal=read(H/'gallery-projection/sealed-handoff.json');seal['files']={p.name:sha(p) for p in (H/'gallery-projection').glob('*.html')};write(H/'gallery-projection/sealed-handoff.json',seal)
gallery=read(H/'gallery-preparation.json');gallery.update(database_sha256=seal['database_sha256'],seal_sha256=sha(H/'gallery-projection/sealed-handoff.json'));write(H/'gallery-preparation.json',gallery)
report=read(H/'register-preparation.json');report['register_sha256']=sha(H/'canonical-master-register.json');write(H/'register-preparation.json',report)
rows=[]
for o in g['options']:
    if o['product_id'] not in active:continue
    row={'product_id':o['product_id'],'name':o['name'],'family':o['family'],'component_id':o.get('canonical_component_id') or '', 'retained_names':' | '.join(o.get('retained_names',[]))}
    row.update({k:v.get('display','') for k,v in o['master_fields'].items()})
    row.update(primary_image=o.get('image_url',''),containing_folder=o.get('folder_url',''),file_id=o.get('file_id') or '',folder_id=o.get('folder_id') or '')
    rows.append(row)
p=OUT/'Current_Individual_Options_186.csv'
with p.open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
count={'active_individual_options':186,'retained_records':189,'retired_records':3,'retired_option_ids':g['retired_option_ids'],'identified_active_component_ids':len({o['canonical_component_id'] for o in g['options'] if o['product_id'] in active and o.get('canonical_component_id')}),'retained_component_identity_rows':len(g['components']),'six_working_field_groups':1116,'original_specification_assertions_retained':1668,'current_primary_references':report['current_primary_references'],'current_context_references':report['current_context_references'],'current_series_references':report['current_series_references'],'open_primary_selections':1,'open_series_replacements':6,'owner_held_context_cases':27,'owner_held_series_cases':1,'snapshot_files':len(files),'scope':'Individual component/finish/size catalogue options. Sets, aliases, source photographs and unlimited custom requests do not add to this count. Physical mould count and physical stock are unverified.','physical_stock':None,'physical_mould_count':None}
write(OUT/'current-count-summary.json',count)
paths=read(H/'current-reader-paths.json');paths.update(current_option_list=str(p.relative_to(BASE)),count_summary=str((OUT/'current-count-summary.json').relative_to(BASE)));write(H/'current-reader-paths.json',paths)
print('Current186 option list, count definitions and approved additional image links prepared')
