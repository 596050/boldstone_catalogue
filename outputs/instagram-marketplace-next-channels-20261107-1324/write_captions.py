"""Prepare five new, source-bound Instagram captions and accessible image text."""
import json
import hashlib
import re
import sys
from pathlib import Path

OUT = Path(__file__).parent
ROOT = OUT.parent.parent
sys.path.insert(0,str(ROOT/'catalogue-review/scripts'))
from import_saatchi_snapshot import Xlsx
pointer = json.loads((OUT/'source-workbook-pointer.json').read_text())
assert hashlib.sha256(Path(pointer['path']).read_bytes()).hexdigest() == pointer['sha256']
book = Xlsx(Path(pointer['path']))
headers = {book.value('Wall Sculptures',a):re.sub(r'\d','',a) for a in book.cells['Wall Sculptures'] if re.fullmatch('[A-Z]+7',a)}
rows = {book.value('Wall Sculptures','AA'+str(r)):r for r in range(8,189)}
publication = json.loads((ROOT/'outputs/catalogue-marketplace-publication-20261101/current-prepared-catalogue.json').read_text())
scope = {r['sku'] for r in publication['records']}
copy = {
 'BSI-2CA935C1A57A': (
  'A little courtyard sunshine for the wall.\n\nAcanthus Moon - Gold Finish brings sweeping leaf-like curves and a broad crescent into a warm, sculptural relief. The raised lines catch the light while quiet recesses give the composition its depth.\n\nHandmade from a gypsum-based material with an applied imitation gold leaf finish, suitable for indoor or outdoor display. The surface-effect pattern will vary and differ from the photographs. One sculpture is supplied.\n\nAll designs can be customised, and completely new commissions can be created with designer Sally Price. Tap the product tag for dimensions, more photographs and current pricing.\n\n#BoldstoneSculpture #WallSculpture #GoldFinish #BotanicalArt #CourtyardDesign',
  'Gold-finished rectangular Acanthus Moon wall relief with a broad crescent and sweeping raised leaf-like curves against a pale wall.'),
 'BSI-0D80125C0E35': (
  'A shoal held in a moment of stillness.\n\nFrozen Fish Relief - Verdigris Finish repeats small raised fish-like forms along a tall, narrow panel. Sea-green colour and rougher surface details give this simple rhythm a weathered, coastal character.\n\nHandmade from a gypsum-based material with an applied decorative verdigris finish. Its surface-effect pattern will vary and differ from the photographs. Suitable for indoor or outdoor display; one sculpture is supplied.\n\nAll designs can be customised, and completely new commissions can be created with designer Sally Price. Tap the product tag to explore the full details.\n\n#BoldstoneSculpture #CoastalArt #VerdigrisFinish #WallRelief #GardenArt',
  'Tall narrow sea-green Frozen Fish wall relief with a repeated vertical sequence of small raised fish-like shapes, mounted on a pale wall.'),
 'BSI-BF85B0E4D43E': (
  'What might an echo look like?\n\nEcho Rhythm I - White follows a sequence of sweeping ridges around a small circular centre. The grainy surface and deep channels let light turn a repeated pattern into a changing composition.\n\nDisplay it alone or with Echo Rhythm II as a coordinating pair. Each sculpture is sold separately. Handmade from a gypsum-based material, suitable for indoor or outdoor display.\n\nAll designs can be customised, and completely new commissions can be created with designer Sally Price. Tap the product tag for dimensions, more photographs and current pricing.\n\n#BoldstoneSculpture #TexturedWallArt #SculpturalDesign #WhiteInteriors #GardenSculpture',
  'White square Echo Rhythm I wall panel with rough-textured curved ridges sweeping around a small circular centre near the right edge.'),
 'BSI-1E0C826D896E': (
  'Follow the water inward.\n\nBone Water Spiral Relief - White turns a broad curling form into a fluid, organic relief. The pale surface lets each raised edge and hollow gather its own changing light, recalling the movement of water and the quiet structure of a shell.\n\nHandmade from a gypsum-based material, suitable for indoor or outdoor display. One sculpture is supplied. Place it where the light changes through the day to enjoy the shifting shadows.\n\nAll designs can be customised, and completely new commissions can be created with designer Sally Price. Tap the product tag for dimensions, more photographs and current pricing.\n\n#BoldstoneSculpture #SpiralArt #WallRelief #OrganicDesign #IndoorOutdoorLiving',
  'White Bone Water Spiral wall relief with a broad curling raised form and deep curved hollows, shown against a pale wall.'),
 'BSI-923D5E50A898': (
  'A line that refuses to stand still.\n\nBrancusi Meander I - White balances long, flowing curves with a clean rectangular outline. Side light traces the raised edges and turns each recess into a quiet ribbon of shadow. Shown under coloured light; the offered finish is White.\n\nDisplay it alone or with Brancusi Meander II. Each sculpture is sold separately. Handmade from a gypsum-based material, suitable for indoor or outdoor display.\n\nAll designs can be customised, and completely new commissions can be created with designer Sally Price. Tap the product tag to explore this design.\n\n#BoldstoneSculpture #WallRelief #AbstractSculpture #SculpturalInteriors #LightAndShadow',
  'White Brancusi Meander I rectangular relief with long raised flowing curves, photographed under pink and blue-toned side lighting.')
}
records = json.loads((OUT/'instagram-five-posts.json').read_text())
assert len(records) == len(copy) == 5
for record in records:
    row = rows[record['catalogue_id']]
    record['sku'] = book.value('Wall Sculptures','AQ'+str(row))
    assert record['sku'] in scope
    assert not book.value('Wall Sculptures',headers['instagram_post_url']+str(row))
    record['source_workbook_sha256'] = pointer['sha256']
    record['caption'],record['alt_text'] = copy[record['catalogue_id']]
    record['source_revision'] = json.loads((OUT/'app-specifications.json').read_text())['revision']
    assert len(record['caption']) < 2200 and record['caption'].count('#') == 5
    assert record['width']/record['height'] >= .8
    assert record['width']/record['height'] <= 1.91
(OUT/'instagram-five-posts.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
print(json.dumps([dict(title=r['title'],sku=r['sku'],caption_characters=len(r['caption'])) for r in records],indent=2))
