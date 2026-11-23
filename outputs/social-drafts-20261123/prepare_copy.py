from pathlib import Path
import json,hashlib
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
rows=json.loads((OUT/'selected-products.json').read_text())
mapping=json.loads((ROOT/'outputs/channel-completion-20261108/master-platform-values.json').read_text())
COPY={
'BSI-DA27DD604F0B':('A fossil spiral, caught in light.','A broad shell spiral sweeps across this tall relief, with rippled ridges that catch the light at different angles. Ammonite Grande I is the left panel of a coordinating pair, and is sold individually.','Tall pale Ammonite Grande I left panel with a large raised half spiral and rippled shell ridges.'),
'BSI-923D5E50A898':('One curve can change a wall.','Brancusi Meander I follows a flowing, wave-shaped recess between two upright edges. Its deep curves create a strong play of light and shadow, giving a compact relief a changing presence through the day.','Brancusi Meander I relief with a deep flowing wave-shaped recess, shown in strong light with pink and blue shadows.'),
'BSI-DDD53E46FB3F':('A palm in a few sweeping lines.','Long curved bands rise from the base of Mediterranean Fountain Palm and fan out across its tall rectangular panel. The simple botanical pattern lets the relief and its shadows do the work.','Tall Mediterranean Fountain Palm relief with curved leaf-like bands fanning upwards from the base.'),
'BSI-6FE9343F889E':('A quiet curve with room to breathe.','Moon and Shell Wave II carries a long crescent across a narrow panel. The broad curve meets a clean straight edge, creating a simple composition that changes as light moves across the surface.','Tall narrow white Moon and Shell Wave II panel with a broad sweeping crescent-shaped relief.'),
'BSI-199FCF3A2B42':('Small details reward a closer look.','Spice Texture I brings scattered fragments, seed-like forms and fine raised marks into a square relief. From a distance they form a textured surface; close up, each small shape catches its own shadow.','Square Spice Texture I relief in a warm pale finish with scattered raised fragments, seed-like shapes and fine textured marks.')}
posts=[]
for r in rows:
 pid=r['catalogue_id'];op,desc,alt=COPY[pid];url=mapping[pid]['pinterest_link'];dims=r['fields']['Dimensions / depth'];title=r['title'];sku=r['sku']
 caption=f'{title}\n\n{op}\n\n{desc}\n\nDimensions: {dims}.\nOne individual sculpture by Boldstone, designed by Sally Price.\n\nView this sculpture: {url}\n\n#Boldstone #SallyPrice #WallSculpture #ReliefSculpture'
 short=f'{title}\n\n{op}\n\n{desc}\n\n{url}'
 assert len(caption)<2200 and len(short)<=500,(title,len(short))
 posts.append({'catalogue_id':pid,'post_key':pid,'title':title,'sku':sku,'price_gbp':r['price_gbp'],'media_path':r['media_path'],'sha256':r['sha256'],'media_sha256':r['sha256'],'media_type':'image/png','alt_text':alt,'website_url':url,'commerce_variant_id':mapping[pid]['pinterest_id'],'captions':{'facebook':caption,'instagram':caption,'threads':short},'status':'PREPARED_NOT_PUBLISHED'})
(OUT/'posts.json').write_text(json.dumps({'batch_id':'component-sculptures-drafts-20261123','publish_authorized':False,'posts':posts},indent=2,ensure_ascii=False)+'\n')
print([(p['title'],len(p['captions']['threads'])) for p in posts])
