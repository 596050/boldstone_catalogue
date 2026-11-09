import json
from pathlib import Path
OUT=Path(__file__).parent
products=json.loads((OUT/'social-five-products.json').read_text())
copy={
'BSI-489226D6FF87':('A narrow wall can hold a strong sculptural rhythm.','Brancusi Totem Relief brings a long, rippling line to the wall. The white surface lets the raised contours and their shadows do the work, changing quietly as the light moves.','A tall narrow white wall relief with a rippling vertical profile and deep shadows, photographed on a white wall.'),
'BSI-3625008B0B78':('Small discoveries from the shoreline, gathered into one relief.','Embedded Seashells sets shell spirals into a textured white panel. It brings the detail of beachcombing to a garden wall, courtyard or a quiet corner indoors.','A narrow textured white wall panel with raised spiral shell motifs arranged down its length.'),
'BSI-987E02C8748D':('A landscape of folds, made visible by the light.','Cultivation Folds Relief combines broad, sweeping curves with a closely spaced fan of ridges. The meeting of the two gives the panel its shifting pattern of light and shadow.','A white rectangular wall relief with closely spaced curved ridges on the left and broad flowing folds on the right.'),
'BSI-96174B219ECA':('The sweep of a wing, held in a sculpted surface.','Folded Swan Wing opens into two fans of curved ridges. Crisp edges and soft shadows give this white relief movement, even on a still wall.','A white rectangular wall relief with two fans of curved ridges opening around a diagonal central fold.'),
'BSI-1A7497B69626':('A spiral that gives the eye somewhere to wander.','Lunar Spiral I traces a curling form across a textured white panel. Its sweeping outer curve and recessed spiral suggest an orbit or a tide, with the relief changing as light crosses it.','A textured white rectangular wall relief with a curling central spiral and a broad sweeping curve around it.')}
companions={
'BSI-987E02C8748D':'Part of the coordinating folds group with Folded Fan, Fold and Unfold IV and Folded Swan Wing. Each sculpture is sold separately.',
'BSI-96174B219ECA':'Part of the coordinating folds group with Cultivation Folds Relief, Folded Fan and Fold and Unfold IV. Each sculpture is sold separately.',
'BSI-1A7497B69626':'Lunar Spiral I can be arranged with Lunar Spiral II and III. Each sculpture is sold separately.'}
for p in products:
    opening,design,alt=copy[p['catalogue_id']]
    common=p['title']+'\n\n'+opening+'\n\n'+design+'\n\n'+p['dimensions']+'. Made from a gypsum-based material. Suitable for outdoor use and indoor display.'
    if p['catalogue_id'] in companions:common+='\n\n'+companions[p['catalogue_id']]
    common+='\n\nAll designs can be customised, and completely new commissions can be developed with designer Sally Price.'
    p['alt_text']=alt
    p['captions']={
        'instagram':common+'\n\nTap the product tag to view the sculpture and purchase on the website. Browse the collection through the link in our bio.\n\n#Boldstone #SallyPrice #WallSculpture #ReliefSculpture #GardenArt #SculptureForInteriors',
        'facebook':common+'\n\nView this sculpture and order: '+p['tracked_urls']['facebook'],
        'linkedin':common+'\n\nFor homes, gardens and design projects. View the individual sculpture: '+p['tracked_urls']['linkedin']+'\n\n#WallSculpture #SallyPrice #Boldstone #InteriorDesign #LandscapeDesign'}
    assert len(p['captions']['instagram'])<2200
(OUT/'social-five-products.json').write_text(json.dumps(products,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'products':5,'prepared_posts':15,'published':0}))
