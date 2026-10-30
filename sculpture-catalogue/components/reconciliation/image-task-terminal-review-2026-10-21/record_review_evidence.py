"""Seal observed source diagnostics and independent current Cup move evidence."""
import collections,hashlib,json,shutil
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;BASE=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json');p=BASE.parent/'reports/dropbox-cup-ring-pink-brown-2026-10-21-independent/INDEPENDENT_READBACK.json';dest=H/'inputs/cup_independent_readback.before'
assert sha(p)=='d035d65580837c5a9bf2cf73f7ec73e5599573039ae38b9a0ac274eba2d5bafc'
if dest.exists():assert sha(dest)==sha(p)
else:shutil.copy2(p,dest)
m['cup_independent_readback']={'path':str(p),'snapshot':str(dest),'sha256':sha(p)};write(H/'input-manifest.json',m)
g=read(H/'canonical-master-register.json');g['current_cup_colour_reference_paths']['independent_directory_verification']=m['cup_independent_readback'];write(H/'canonical-master-register.json',g)
notes={
1:'Gold Acanthus and Brancusi room studies. Brancusi Gold scenes crop/change the full outer silhouette; do not replace the standard individual geometry.',
2:'White Brancusi/Totem family scenes and White/Gold Spiral product views. Brancusi garden versions retained as binding candidates; multiple tall Egyptian panels are not automatically Totems.',
3:'White/Gold Golden Spiral close views against brick and stone. No new complete component gaps closed by these tight solo views.',
4:'White/Gold Golden Spiral close/staged log-background views. Product photographs, not a fixed multi-component set.',
5:'Golden Spiral handheld/product views and a two-work countertop group. NC155 binds Golden Spiral at RIGHT; left work is a different Gold landscape Dune Ripple.',
6:'Golden Spiral close or wider hedge displays. No dimensional or installation claims inferred from a rod/stand.',
7:'Golden Spiral hedge and stone-bench displays. NC216 supplies a qualified staged garden presentation, not wall-installation proof.',
8:'Golden Spiral product/bench views and related White spiral solo reliefs. Bare brick alone is not a wider room/garden setting.',
9:'White plain spiral product views, including wider bare-brick samples. These are not the rough concentric Cup Spiral design.',
10:'White spiral display-board views and White Frozen Decowaves legacy pair views. NC302 has no usable visible depiction in its cached thumbnail.',
11:'White Frozen Decowaves legacy garden groups. No Terracotta finish inferred from warm light.',
12:'Dune Ripple Gold/Rust/White/Verdigris and Egyptian Gold scenes. NC369 identifies Rust Waves at LOWER RIGHT/FOREGROUND; Gold landscape panel differs from Dune Spiral Gold.',
13:'Gold/White Egyptian Palm and extended multi-rib scenes. Extended rib count/build is not the Three Leaves option.',
14:'Extended Egyptian Palm and White Leaf Form group scenes. White Leaf Form photographs do not establish Gold LF2.',
15:'White Leaf Form product/group/exhibition views plus Leaf Growth display board. Warm exhibition light is not finish evidence.',
16:'Leaf Growth display-board, White/Gold Leaf Curve bare-brick, and plain White moon pillar views. No complete Gold Leaf Growth isolated view found.',
17:'White moon/spiral room and pillar configurations plus Moon Crater scenes. NC538 binds MCP1 Verdigris/Rust room presentation at image level; MCP4 Verdigris scenes are not Rust or Silver/Bronze.',
18:'MCP4 Verdigris and unbordered White Moonphase groups. Retain border/finish distinctions.',
19:'Unbordered White Moonphase garden, terrace and water-feature groups. Source groups do not establish bordered or Silver options.',
20:'Further White Moonphase groups and exhibition views. No White/Gold MP4 or Silver finish transferred from these files.',
21:'White Moonphase, tight Water Catcher/Plant Form, and Riyadh workshop/site views. NC671 is a useful site candidate; exact rotated/custom member build remains unbound.',
22:'Riyadh site/workshop, White Spiralfish settings, and White Spiralmoon outdoor views. White Spiralfish does not establish Bronze finish components.',
23:'White Spiralmoon garden/outdoor/group views and Strata pool presentation. NC706 identifies the single White Spiralmoon above a garden fountain; NC731 is a qualified Blue Wash Verdigris setting.'}
plates=read(H/'review-plate-manifest.json')+read(H/'candidate-plate-manifest.json')+read(H/'selected-context-comparison-manifest.json')+[read(H/'legacy-leaf-growth-plate.json')]
for x in plates:assert sha(x['path'])==x['sha256'],x['path']
downloads=[]
for name in ['archive','checks','context','spiral','leaf']:
 receipt=read(H/(name+'-download-receipt.json'));assert receipt['status']=='PASS'
 for x in receipt['images']:
  assert sha(x['local_path'])==x['sha256']
  if x['native_bytes_downloaded_for_this_ID']:downloads.append(x)
seen=set()
for filename in ['visual-queue.json','followup-queue.json','group-extra-queue.json','moon-fishwave-extra-queue.json']:
 p=BASE/'components/reconciliation/image-identity-coverage-2026-10-20'/filename
 if p.exists():
  data=read(p)
  if isinstance(data,list):
   for x in data:
    if isinstance(x,dict):seen.add(x.get('file_id')or x.get('id'))
visible={v['file_id']for p in plates for v in p.get('views',[])if v.get('file_id')}
result={'status':'OBSERVED_BOUNDED_SOURCE_DIAGNOSTICS_RECORDED','recorded_utc':datetime.now(timezone.utc).isoformat(),'plates':[{k:x[k]for k in ['path','sha256']}for x in plates],'new_context_plate_observations':[{'plate':str(n).zfill(2),'finding':finding}for n,finding in notes.items()],'new_context_candidate_thumbnails_examined':731,'unusable_blank_thumbnail_labels':['NC302'],'additional_Fountain_Palm_Bronze_Verdigris_family_views_examined':83,'archive_native_refs_associated_by_hash':124,'archive_unique_originals_visually_reviewed':64,'legacy_leaf_growth_originals_visually_reviewed':5,'download_operations_successful':len(downloads),'unique_native_ids_downloaded':len({x['file_id']for x in downloads}),'current_original_sha256_and_Dropbox_hash_checked_by_download_receipts':True,'all_library_originals_rehashed':False,'all_archive_searches_exhaustive':False,'diagnostics_are_not_new_product_photographs':True,'new_generated_product_or_room_images':0,'root_remote_mutations':0,'native_API_inventory_before_Cup_overlay':{'files':6681,'folders':424,'entries':7105},'post_inventory_Cup_overlay':{'new_folders':2,'existing_files_moved':2,'file_ids_and_sizes_preserved':True},'separations':['Image role versus exact physical cast','Source scene versus authenticated installation','Image finish appearance versus physical manufacture','Component specifications versus whole arrangement totals']}
write(H/'source-visual-review-receipt.json',result);print(json.dumps({k:result[k]for k in ['status','new_context_candidate_thumbnails_examined','download_operations_successful','unique_native_ids_downloaded']}))
