import json,sys
from pathlib import Path
ROOT=Path('/Users/tprice/Documents/boldstone'); OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'catalogue-review/scripts'))
from import_saatchi_snapshot import Xlsx
pointer=json.loads((ROOT/'sculpture-catalogue/current-master.json').read_text())['current_app_review_workbook']
x=Xlsx(pointer['path']);rows={x.value('Wall Sculptures','AA'+str(n)):n for n in range(8,189)}
copy={
'BSI-0C2CB099DDEB':(
    'A small spiral with a rugged shoreline character.\n\nCoral Spiral Relief - White follows a curling ridge across a richly textured square panel. The raised lines catch the light while rougher recesses suggest coral, rock and the marks left by the sea. A pale wall keeps the focus on those small changes of depth.\n\nHandmade from a gypsum-based material, suitable for indoor or outdoor display. One sculpture is supplied. All designs can be customised, and completely new commissions can be created with designer Sally Price.\n\nTap the product tag for dimensions, more photographs and current pricing.\n\n#BoldstoneSculpture #WallSculpture #CoastalInteriors #TexturedArt #GardenArt',
    'Square white Coral Spiral wall relief with a curling raised spiral and rough, coral-like texture against a pale wall.'),
'BSI-48D13D8D7E67':(
    'A vine, a curve and a little garden light.\n\nGleneagles Vine III - White brings a cluster of rounded grapes, a delicate leaf and a sweeping curved form into one quiet composition. Its simple pale surface lets the raised details cast their own changing shadows.\n\nDisplay it alone or with the other Gleneagles Vine panels for a coordinating arrangement. Each sculpture is sold separately. Handmade from a gypsum-based material, suitable for indoor or outdoor display.\n\nAll designs can be customised, and completely new commissions can be created with designer Sally Price. Tap the product tag to explore this design.\n\n#BoldstoneSculpture #BotanicalArt #WallRelief #SculpturalInteriors #GardenDesign',
    'White square Gleneagles Vine III wall panel with a raised bunch of grapes, a small leaf and a broad curved form.'),
'BSI-21E7F11ACAAA':(
    'Where a shell meets an imagined lunar landscape.\n\nLava Moonshell II - White balances a broad, smooth crescent with a rough, crater-like inner curve. The contrast in texture gives the pale relief depth, from a clean sweep of light to small pockets of shadow.\n\nIt can stand alone or join the other Lava Moonshell designs in a coordinating display. Each panel is sold separately. Handmade from a gypsum-based material, suitable for indoor or outdoor display.\n\nAll designs can be customised, and completely new commissions can be created with designer Sally Price. Tap the product tag for the full details.\n\n#BoldstoneSculpture #LunarInspired #WallSculpture #NaturalForms #IndoorOutdoorLiving',
    'Square white Lava Moonshell II relief with a smooth sweeping crescent beside a rough, textured inner curve.'),
'BSI-FE973AD4748E':(
    'The calm of a raked garden, carried onto a wall.\n\nRaked Spiral I - White lets broad ridges unfurl from a small spiral into flowing waves. Its grainy surface softens the pattern, giving light a different path across every curve. A quiet piece with plenty to discover up close.\n\nDisplay it on its own or alongside the other Raked Spiral panels. Each sculpture is sold separately. Handmade from a gypsum-based material, suitable for indoor or outdoor display.\n\nAll designs can be customised, and completely new commissions can be created with designer Sally Price. Tap the product tag to see dimensions and more photographs.\n\n#BoldstoneSculpture #SpiralArt #TexturedWallArt #GardenInspiration #SculpturalDesign',
    'White square Raked Spiral I wall relief with grainy, flowing ridges expanding outward from a small central curl.'),
'BSI-DF3FF43C94C9':(
    'A tide-mark rhythm that stays with the wall.\n\nFossil Sand Ripple Relief - White traces long, undulating channels across a rectangular panel. Fine texture and narrow ridges recall ripples in sand, with each line becoming clearer as the light moves across it.\n\nIt can be displayed alone or with coordinating Seaweed Ripple designs. Each sculpture is sold separately. Handmade from a gypsum-based material, suitable for indoor or outdoor display.\n\nAll designs can be customised, and completely new commissions can be created with designer Sally Price. Tap the product tag for photographs, dimensions and current pricing.\n\n#BoldstoneSculpture #CoastalArt #WallRelief #TexturedInteriors #GardenSculpture',
    'White horizontal Fossil Sand Ripple relief with long, flowing ridges and textured channels, mounted against a pale wall.')}
records=json.loads((OUT/'instagram-five-posts.json').read_text())
for r in records:
    r['sku']=x.value('Wall Sculptures','AQ'+str(rows[r['catalogue_id']]))
    r['caption'],r['alt_text']=copy[r['catalogue_id']]
    assert r['sku'] and len(r['caption'])<2200 and r['caption'].count('#')==5
    r['source_revision']=json.loads((OUT/'app-specifications.json').read_text())['revision']
(OUT/'instagram-five-posts.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
print([(r['title'],r['sku'],len(r['caption'])) for r in records])
