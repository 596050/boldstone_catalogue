"""Bind curated retail names and two existing in-situ candidates to stable IDs."""
from pathlib import Path
import csv, hashlib, html, json

OUT = Path(__file__).resolve().parent
raw = (OUT / 'catalogue-snapshot.json').read_bytes()
snapshot = json.loads(raw)
assert snapshot['event_cutoff'] == 14327
names = '''Icarus I - Abstract Cave Relief
Acanthus Moon - Gold Leaf Finish
Acanthus Bloom - White
Acanthus Moon - White
Acanthus Frond (Left) - Pewter
Acanthus Frond (Left) - White
Acanthus Twin Leaves - Bronze
Acanthus Twin Leaves - Pale Blue and White
Acanthus Twin Leaves - Pewter
Acanthus Twin Leaves - White
Ammonite Grande I (Left) - White
Ammonite Grande II (Right) - White
Ammonite Petite I (Left) - White
Ammonite Petite II (Right) - White
Barbados Wave Relief
Bone Spiral I (Narrow) - White
Bone Spiral II (Wide) - White
Bone Water Spiral Relief - White
Brancusi Meander I - Gold Leaf Finish
Brancusi Meander I - White
Brancusi Meander II - Gold Leaf Finish
Brancusi Meander II - White
Brancusi Totem Relief - White
Chelsea Moonwave Relief
Chiswick Moon Relief
Chiswick Moon Fountain
Coral Spiral Relief - White
Ancient Cup Ring - White
Cup Ring and Spiral Paver I - Brown
Cup Ring and Spiral Paver II - Brown
Ancient Spiral - White
Deco Dune Spiral - White
Deco Dune Spiral - Verdigris
Deco Dune Wave - Verdigris
Deco Dune Wave - White
Deco Golden Spiral - White and Gold
Deco Palm I - White
Deco Palm II - White
Deco Timeless Spiral - White
Deco Wave I - Terracotta
Deco Wave I - Verdigris
Deco Wave II - Terracotta
Deco Wave II - Verdigris
Frozen Deco Wave I - White
Frozen Deco Wave II - White
Dune Ripple I - Blue Verdigris and Bronze
Dune Ripple I - Rust
Dune Ripple I - Verdigris
Dune Ripple I - Verdigris and Rust
Dune Ripple I - White
Dune Ripple II - Bronze and Verdigris
Dune Ripple II - Copper
Dune Ripple II - Copper with Verdigris Accents
Dune Ripple II - Gold
Dune Ripple II - Rust
Dune Ripple II - Verdigris and Copper
Dune Ripple II - White
Echo Rhythm I - Verdigris
Echo Rhythm I - White
Echo Rhythm II - Verdigris
Echo Rhythm II - White
Egyptian Palm IV (Extended) - White
Egyptian Palm I - Gold Leaf Finish
Egyptian Palm I - Black and White Marble Effect
Egyptian Palm I - Pewter
Egyptian Palm I - White
Egyptian Palm III (Three Leaves) - White
Egyptian Palm II - White
Embedded Seashells - White
Golden Facets - Gold Leaf Finish
Cultivation Folds Relief - White
Folded Fan - White
Fold and Unfold IV - White
Folded Swan Wing - White
Fingerprint Rings I - Cream
Fingerprint Rings I - White
Fingerprint Rings II - Cream
Fingerprint Rings II - White
Fingerprint Rings III - Cream
Fingerprint Rings III - White
Egyptian Fountain Palm - Bronze and Verdigris
Egyptian Fountain Palm - White
Mediterranean Fountain Palm - White
Frozen Fish Relief - Terracotta
Frozen Fish Relief - Verdigris
Frozen Fish Relief - White
Gleneagles Vine I - White
Gleneagles Vine II - White
Gleneagles Vine III - White
Gleneagles Vine IV - White
Knightsbridge Fountain Relief - White
Lava Moon I - White
Lava Moon II - White
Lava Moon III - White
Curving Leaf - White and Gold Leaf Finish
Leaf Silhouette - White
Leaf Silhouette II - Gold
Magnolia Growth - White
Magnolia Growth - White and Gold Leaf Finish
Moon and Shell Wave I - White
Moon and Shell Wave I Fountain - White
Moon and Shell Wave II - Black and White
Moon and Shell Wave II - White
Moon and Shell Wave II Fountain - White
Crater Moon I - Verdigris and Rust
Crater Moon I - White
Crater Moon II - Blue Splash
Crater Moon II - Verdigris and Rust
Crater Moon II - White
Crater Moon III - Verdigris and Rust
Crater Moon III - White
Crater Moon IV - Silver and Bronze
Crater Moon IV - Verdigris
Crater Moon IV - Verdigris and Rust
Crater Moon IV - White
Wide-Lip Crater Moon - Rust Drip
Moon Fish Wave I - White
Moon Fish Wave II - White
Lunar Ring - White
Crater Moon Basin - White
Lunar Phase IV - Silver
Lunar Phase IV - White
Lunar Phase IV - White and Gold
Lunar Phase I - White
Lunar Phase I (Bordered) - White
Lunar Phase III - White
Lunar Phase II - White
Lunar Phase II - White and Gold
Lunar Phase II (Bordered) - White
Lava Moonshell I - White
Lava Moonshell II - White
Lava Moonshell Corner Curve - White
Lunar Spiral I - White
Lunar Spiral III - White
Lunar Spiral II - White
Lunar Water Catcher - White
Lunar Wave - White
Sculpted Curves - Beige
Sculpted Curves - Textured Gold Leaf Finish
Botanical Form - White
Raked Spiral I - Beige
Raked Spiral I - White
Raked Spiral II - Beige
Raked Spiral II - White
Raked Spiral III - Beige
Raked Spiral III - White
Riyadh Dune Ripple - White
Riyadh Moon - White
Riyadh Shellmoon Relief
Patina Panel - Rust and Verdigris
Fossil Sand Ripple Relief - White
Smooth Sand Ripple Relief - White
Battersea Shellmoon I - White
Battersea Shellmoon I Fountain - White
Battersea Shellmoon II Fountain - White
Islington Shellmoon Relief - White
Islington Shellmoon Fountain - White
Soundwave Rhythm - White
Spice Texture I - White
Spice Texture II - White
Spiralfish Wave and Tide I - Bronze
Spiralfish Wave and Tide I - White
Spiralfish Wave and Tide II - Bronze
Spiralfish Wave and Tide II - White
Quarter Moon Relief - White
Spiral Moon Relief - White
Strata Relief - Blue Wash Verdigris
Strata Relief - Verdigris
Strata Relief - White
Textured Earth - Blue, Brown and Rust
Textured Earth - Rust and Blue Patina
Marbled Circle - Azure Blue and White
World Colours Circle - Brass
Marbled Circle - Green and White
Marbled Circle - Pale Blue
Marbled Circle - Terracotta
Marbled Circle - Turquoise
Marbled Circle - Yellow and Grey
Azure Marble-Effect Relief - Blue and White
Wave and Moonshadow I - White
Wave and Moonshadow II - White'''.splitlines()
assert len(names) == len(snapshot['products']) == 181
assert len(set(names)) == len(names)
assert all('—' not in n and len(n) < 100 for n in names)
products = []
for p, retail_name in zip(snapshot['products'], names):
    rows = [r for r in snapshot['images'] if r['product_id'] == p['id'] and r['scope'] == 'Associated'
            and r['image']['source'] == 'Dropbox' and 'in_situ' in r['image']['effective_types']
            and not r['image']['excluded'] and not r['image']['withheld_reasons']]
    # Respect saved order, then prefer a clear image already reviewed for public use.
    rows.sort(key=lambda r: (not bool(set(r['choice'].get('uses', [])) & {'listing', 'advertising'}),
                             r['choice'].get('order', 0), r['image']['name'], r['image']['id']))
    selected, hashes = [], set()
    for r in rows:
        im = r['image']; digest = im['original'].get('dropbox_content_hash')
        if not digest or digest in hashes: continue
        hashes.add(digest)
        selected.append({'image_id': im['id'], 'name': im['name'], 'url': im['url'],
            'folder_url': im['folder_url'], 'content_hash': digest, 'bytes': im['original']['bytes'],
            'types': im['effective_types'], 'existing_uses': r['choice'].get('uses', []),
            'alt': f'{retail_name}, shown in situ', 'status': 'candidate_pending_visual_and_native_check'})
        if len(selected) == 2: break
    products.append({'catalogue_id': p['id'], 'catalogue_name': p['name'], 'retail_name': retail_name,
        'family': p['family'], 'listing_decision': p['listing_decision'], 'app_url': p['app_url'],
        'folder_url': p['folder_url'], 'in_situ_available': len(rows), 'in_situ': selected})
payload = {'source_snapshot_sha256': hashlib.sha256(raw).hexdigest(), 'event_cutoff': snapshot['event_cutoff'],
    'naming_policy': 'Separate retail titles. Original names, identities, finish variants, SKUs, URLs and prices retained.',
    'image_policy': 'Two distinct associated, non-excluded, unrestricted Dropbox in-situ images per listing. Type and purpose tags remain unchanged.',
    'products': products}
(OUT / 'retail-plan.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2))
with (OUT / 'retail-names.csv').open('w', newline='') as stream:
    fields = ['catalogue_id', 'catalogue_name', 'retail_name', 'family', 'listing_decision', 'app_url', 'folder_url', 'in_situ_available']
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore'); writer.writeheader(); writer.writerows(products)
print(json.dumps({'names': len(products), 'included': sum(p['listing_decision']=='include' for p in products),
    'below_two_in_situ': [{k:p[k] for k in ('catalogue_id','catalogue_name','listing_decision','in_situ_available')} for p in products if len(p['in_situ'])<2]}, indent=2))
