"""Evidence-scoped component register. No writes to Dropbox or source workbooks."""
import hashlib,html,json,re
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path

root=Path(__file__).resolve().parents[1];ev=root/'evidence';base=root.parent/'evidence'
e=json.loads((ev/'evidence_index.json').read_text());source=json.loads((base/'catalogue_source_tables_2026-10-15.json').read_text());old=json.loads((base/'catalogue_model.json').read_text())
comparison=json.loads((base/'platform_comparison_2026-10-16.json').read_text());offers=json.loads((ev/'offer_review_index.json').read_text());assets={a['id']:a for a in e['assets']};groups={int(g['group_ref'][1:]):g for g in e['groups']}
components={};bindings=defaultdict(list);claims=[];issues=[];aliases=[]
def component(key,name,family,gg=(),maker=(),status='Documented or visually distinct design',notes=''):
    components[key]=dict(component_id='BC-'+key,key=key,name=name,family=family,identity_status=status,notes=notes,maker_rows=list(maker),group_refs=[],offer_refs=[],source_codes=[])
    for n in gg:bind(n,key)
    return key
def bind(n,*keys,role=None,note='',qty=None):
    for key in keys:
        assert key in components,key
        bindings[n].append(dict(key=key,role=role,note=note,quantity=(qty or {}).get(key,1)))
def seq(key,names,family,rows,maker=(),status='Documented or visually distinct design',notes=''):
    for i,name in enumerate(names,1):component(key+str(i),name,family,rows[i-1],maker[i-1] if maker else (),status,notes)

component('ICARUS','Icarus / Abstract Cave Paintings 1','Abstract Cave Paintings',[1,2],notes='Source text calls AC730 acrylic-modified gypsum; the prior material-class conflict remains open. Native/public weight is approximately 60 kg, not the older 80 kg note.')
seq('PORTMAN-', ['Portman Agapanthus courtyard panel — left','Portman Agapanthus courtyard panel — right'],'Acanthus',[[3],[3]],status='Bespoke component position; distinct mould identity unconfirmed',notes='Two project panels, not a global Acanthus or Moon alias. Positional labels are local catalogue descriptions.')
component('AC-FULL','Acanthus Full / Acanthus and Moon','Acanthus',range(4,8))
component('AC-FLOWER','Acanthus Flower','Acanthus',[8,9])
component('AC-ONE','Acanthus One Leaf','Acanthus',[10,11])
component('AC-TWO','Acanthus Two Leaves','Acanthus',range(12,19))
seq('AM-', ['Ammonite left panel','Ammonite right panel'],'Ammonite',[[19,20,21,22],[19,20,21,22]],[[93],[93]],notes='Small and Large/Ancient are separate size configurations. Left/right manufacturing codes AMS1/2 and AML1/2.')
seq('BAR-STUDY-', ['Moon-and-wave workshop panel A','Moon-and-wave workshop panel B','Moon-and-wave workshop panel C'],'Barbados Wave',[[23],[23],[23]],status='Bespoke component position; distinct mould identity unconfirmed',notes='Three curved panels visible together. Local A/B/C labels; no authoritative numbered key or scale.')
component('BAR-WAVE','Barbados Wave','Barbados Wave',[24,25])
seq('BONE-', ['Bone Spiral narrow panel (BS1)','Bone Spiral wide panel (BS2)'],'Bone Spiral',[[26,27],[26,27]],[[91],[91]],notes='Unequal panels: 55×30 and 55×55 cm. Never split overall 85 cm width equally.')
component('BONE-WATER','Bonewater / Bone Water Spiral','Bone Water Spiral',[28,29],[110],notes='Native 55×55 size versus 80×60 manufacturing version requires reconciliation.')
component('BR-TOTEM','Brancusi Totem','Brancusi Totem',[30,31])
component('BR-1','Brancusi 1 / Meander Light (MLD1)','Brancusi',[32,33,34,35,36,37,42],[67])
component('BR-2','Brancusi 2 / Meander Dark (MLD2)','Brancusi',[32,33,38,39,40,41,42],[68])
component('CHELSEA','Chelsea Moonwave / Moon Ripple crescent-and-spiral form','Chelsea Moonwave',[43,44,45,233,234],status='Visual design proposal; retail alias unconfirmed',notes='Same visible tall crescent/spiral form across these groups. A formal crosswalk to current Moonwave or Moonspirals is not certified; no specifications transferred from those products.')
component('CHISWICK','Chiswick Moon','Chiswick Moon',[46,47,48,49])
component('CONCAVE','Concave Moon','Concave Moon',[51,52,53,54,55],notes='Possible design-family overlap with MCP4; 25 cm and 50 cm retail sizes must remain distinct.')
component('CORAL','Coral Spiral','Coral Spiral',[56,57])
component('CR-SPIRAL','Cup Ring & Spiral — Spiral (CRS1)','Cup Ring and Spiral',[58,59,60,61,63],[26])
component('CR-RING','Cup Ring & Spiral — Cup Ring (CRS2)','Cup Ring and Spiral',[58,59,60,61,62],[27])
component('DDR-WAVE','Deco Dune Ripple wave (DDR1; DDR3 rotated)','Deco Dune Ripple',[64,65,68,69,70,71],[61,63])
component('DDR-SPIRAL','Deco Dune Ripple spiral (DDR2)','Deco Dune Ripple',[64,65,66,67,70,71],[62])
component('DP-PALM1','Deco Palm 1','Deco Palm and Spiral',[72,73,75,76,78,83])
component('DP-PALM2','Deco Palm 2','Deco Palm and Spiral',[72,74,75,77,78,83])
component('DP-SPIRAL','Deco / Grecian Spiral 1','Deco Palm and Spiral',[76,77,78,79,80,81,82,83])
component('DP-LEAVES','Deco Two Leaves 1','Deco Palm and Spiral',[79,83,84])
component('DECO-1','Coloured Decowaves 1','Decowaves',[85,86,87,88,89],notes='Coloured cast geometry retained separately from the white Frozen Decowaves reference; no automatic mould/chemistry alias.')
component('DECO-2','Coloured Decowaves 2','Decowaves',[85,86,87,90,91],notes='Coloured cast geometry retained separately from the white Frozen Decowaves reference.')
component('FDW-1','Frozen Decowave 1 (FDW1; FDW3 rotated)','Decowaves',[92,93,94,96],[78,80])
component('FDW-2','Frozen Decowave 2 (FDW2)','Decowaves',[92,93,95,96],[79])
component('DR-WAVE1','Dune Ripple Waves — DR1','Dune Ripple',[101,102,113,114,115,116,117,118,119],[54],notes='DR1/DR3 are different moulds. A plain-waves photograph is not enough to allocate every coloured cast to DR1 versus DR3. The Bronze Verdigris group depicts the spiral panel alone, not an extra plain-wave panel.')
component('DR-SPIRAL','Dune Ripple Spiral — DR2','Dune Ripple',[98,99,100,101,102,103,104,105,106,107,108,109,110,111,112,113,114],[55])
component('DR-WAVE3','Dune Ripple Waves — DR3','Dune Ripple',[101,102],[56],notes='Second plain-waves mould documented in the triptych; standalone coloured-member allocation unresolved.')
component('ECHO-1','Echo Sound / Echo Pattern 1 (EP1)','Echo Sound',[120,121,124,125,126,127,128],[31])
component('ECHO-2','Echo Sound / Echo Pattern 2 (EP2)','Echo Sound',[122,123,124,125,126,127,128],[32])
component('EG-1','Egyptian Palm 1','Egyptian Two Palms',[129,130,131,132,137,138,139,140])
component('EG-2','Egyptian Palm 2','Egyptian Two Palms',[133,138,139,140])
component('EG-3','Egyptian Palm 3 / Three Leaves','Egyptian Two Palms',[134])
component('EG-4','Egyptian Palm 4 / Extended','Egyptian Two Palms',[135,136])
bind(137,'DP-LEAVES',note='Smaller right-hand panel; family/mould alias and exact size remain provisional.')
component('EMBED-SHELLS','Embedded Shells','Embedded Shells',[141,142])
component('FACET-MOUND','Faceted Mound','Faceted Mound',[143,144])
seq('FOLD-', ['Fold Unfold 1 / Swan Wing Folds','Fold Unfold 2 / Fan Folds reference','Fold Unfold 3 / Cultivation Folds reference','Fold Unfold 4'],'Fan Folds',[[145,150,151,152,153],[146,150,152,153],[147,150,152,153],[148,150,151,152,153]],notes='Four visually distinct forms. Similar rib patterns and inconsistent historic filenames are not enough to merge components; product references distinguish Fold 2/Fan Folds and Fold 3/Cultivation.')
component('FP-LEFT','Fingerprint concentric rectangular panel — left','Fingerprint',[154,155,156,157,158,160],status='Visual design proposal; production identity unconfirmed',notes='Only matching concentric rectangular frames support this component. Other wavy, oval and altered studies are unresolved media positions, not additional manufactured stock.')
component('FP-RIGHT','Fingerprint concentric rectangular panel — right','Fingerprint',[154,155,156,157,158,160],status='Visual design proposal; production identity unconfirmed',notes='Only matching concentric rectangular frames support this component. Study folder numbers do not certify moulds.')
component('FOUNTAIN-EG','Fountain Palm Egyptian / Deco Fountain','Fountain Palm',[162,163,166])
component('FOUNTAIN-MED','Fountain Palm Mediterranean','Fountain Palm',[164,166])
component('FFS-1','Frozen Fish small left panel (FFS1)','Frozen Fish',[172],[70],notes='Source-key position; full component image assignment remains provisional.')
component('FFS-2','Frozen Fish small solo/centre (FFS2)','Frozen Fish',[167,168,169,170,171,172,173],[73])
component('FFS-3','Frozen Fish small right panel (FFS3)','Frozen Fish',[172,173],[70,71],notes='Source-key position; full component image assignment remains provisional.')
component('FFL-1','Frozen Fish Long (FFL1)','Frozen Fish',[],[73],status='Source-only option; no scaled Dropbox component identified',notes='100×22 cm option is documented; image aspect alone cannot distinguish it reliably from the 70×15 cm version.')
seq('GLEN-', ['Gleneagles Vine and Tendril — top left','Gleneagles Vine and Tendril — top right','Gleneagles Vine and Tendril — bottom left','Gleneagles Vine and Tendril — bottom right'],'Gleneagles Vine and Tendril',[[174,175]]*4,status='Bespoke component position; distinct mould identity unconfirmed',notes='Four installed positions; mould repetition/rotation and individual model names need a maker diagram.')
component('KNIGHT','Knightsbridge Fountain','Knightsbridge Fountain',[176,177])
seq('LAVA-', ['Lava Moon — left panel','Lava Moon — centre panel','Lava Moon — right panel'],'Lava Moon',[[178,179,180]]*3,status='Bespoke component position; distinct mould identity unconfirmed',notes='Three visible joined panels. Outer-panel repetition/rotation not certified.')
component('LEAF-CURVE','Leaf Curve','Leaf Curve',[181,182])
component('LEAF-FORM','Leaf Form (LF1; LF2 opposite orientation)','Leaf Form',[183,185,186,187,188],[36,37])
component('LEAF-GROWTH','Leaf Growth / Magnolia Leaves','Leaf Growth',[190,191,192])
component('MSW-MOON','Moon & Shellwave — Half Moon (MSW1; MSW3 rotated)','Moon & Shellwave',[193,194,195,196,197,198,199,200,201,204],[85,87])
component('MSW-SPIRAL','Moon & Shellwave — Shellwave (MSW2)','Moon & Shellwave',[193,194,195,196,200,201,202,203],[86])
for i,gg,row in [(1,[205,206,207,208,209],41),(2,[205,206,210,211,212,222,223],42),(3,[205,206,213,214,222],43),(4,[205,206,215,216,217,218,219,220,221,223,224],44)]:
    component(f'MCP-{i}',f'Moon Crater Phase {i} (MCP{i})','Moon Crater Phase',gg,[row])
component('CRATER-WIDE','Moon Crater Wide Lip / Drip Rust','Moon Crater Wide Lip',[225],status='Visual design proposal; retail alias unconfirmed')
component('MFW-1','Moon Fishwave left panel (MFW1)','Moon Fishwave',[226,228,229],[95])
component('MFW-2','Moon Fishwave right panel (MFW2)','Moon Fishwave',[227,228,229],[95])
component('MOON-RING','Moon Ring','MOON RING',[230])
component('MOON-CRATER','Mooncrater bowl / Moon Crater','Mooncrater',[235,236],notes='Freestanding bowl and water feature images; not automatically a wall product.')
# Manufacturer MP numbers differ from the current Dropbox 1–4 media labels.
component('MP-1','Moonphase plain moon — manufacturing MP1','Moonphases',[244,247,249,250,252,253,254,255,256,257],[9],notes='Dropbox Moonphase 4 includes both directions; source MP1 and MP5 are listed as different moulds, so no unproven merge.')
component('MP-2','Moonphase curl — manufacturing MP2 / Dropbox 1','Moonphases',[237,238,247,248,249,250,251,252,253,254,258],[10])
component('MP-3','Moonphase nested spiral — manufacturing MP3 / Dropbox 2','Moonphases',[239,240,241,247,248,251,252,253,254,255,256,258],[11])
component('MP-4','Moonphase broad spiral — manufacturing MP4 / Dropbox 3','Moonphases',[242,247,251,253,254,257],[12])
component('MP-5','Moonphase opposite plain moon — manufacturing MP5','Moonphases',[243,244,245,247,253,254,255,256,257],[13],notes='Dropbox Moonphase 4 includes both orientations; distinguish MP5 from MP1 using source diagram, not folder number.')
component('LAVA-CORNER','Moonshell Lava Corner Curve','Moonshell Lava Corner Curve',[259])
component('MLAVA-1','Moonshell Lava 1','Moonshell Lava',[260])
component('MLAVA-2','Moonshell Lava 2','Moonshell Lava',[261])
seq('MLAVA-WALL-', ['Moonshell Lava wall pair — left panel','Moonshell Lava wall pair — right panel'],'Moonshell Lava',[[263],[263]],status='Bespoke component position; distinct mould identity unconfirmed',notes='Two-panel portfolio version; exact equivalence to standalone Moonshell Lava 1/2 is not established.')
seq('LUCIANO-', ['Luciano screen panel — left','Luciano screen panel — centre','Luciano screen panel — right'],'Moonshell Lava',[[262]]*3,status='Bespoke component position; distinct mould identity unconfirmed',notes='Documented three-panel screen 215×180 cm overall; local positional labels. Only details exist in this image group.')
component('MS-1','Moonspiral 1 (MS1)','Moonspirals',[264,265,269,270,271],[106])
component('MS-2','Moonspiral 2 (MS2)','Moonspirals',[266,267,269,271,272],[107])
component('MS-3','Moonspiral 3 (MS3)','Moonspirals',[268,270,271,272],[108])
component('MOON-WATER','Moon Water Catcher (MWC1)','Moonwater catcher',[273,274],[103])
component('MOONWAVE','Moonwave','Moonwave',[275,276])
component('PANEL-CURVES','Panel Curves fan-and-arc','Panel Curves',[277,278],status='Visual design proposal; retail alias unconfirmed',notes='Beige workshop form may be master/mould; multicolour patina is not solid gold or a documented material recipe.')
component('PLANT','Plant Form','Plant Form',[279,280])
component('RW-SPIRAL1','Raked Water RW4 / Dropbox Raked Spiral 1','Raked Spiral',[281,285,286,287,288,289,290],[22])
component('RW-WAVE','Raked Water RW1 (RW3 rotated) / Dropbox Raked Spiral 2','Raked Spiral',[282,285,286,287,288,289,290],[19,21])
component('RW-SPIRAL3','Raked Water RW2 / Dropbox Raked Spiral 3','Raked Spiral',[283,284,287,288,289,290],[20])
# The Cambridge nine-panel commission also reuses existing designs from other families.
bind(289,'CR-RING','CR-SPIRAL','ECHO-1','ECHO-2',note='Source-assisted layout; exact rotations provisional. Cup Ring repeats.')
seq('RIYADH-', ['Riyadh wave panel 1','Riyadh spiral panel 2','Riyadh plain moon panel 3'],'Riyadh Shell Spiral and Wave',[[291],[292,293],[294]],status='Visual design proposal; retail alias unconfirmed')
component('RUST-PANEL','Rust and Verdigris flat panel','Rust and Verdigris Panel',[295,296])
component('SEAWEED-ROUGH','Seaweed Ripple Rough / Fossil Sand Ripple','Seaweed Ripple',[299,302])
component('SEAWEED-SMOOTH','Seaweed Ripple Smooth / Smooth Sand Ripple','Seaweed Ripple',[300,301,302])
component('SHELL-B1','Battersea Shellmoon 1 (BSM1)','Shellmoon',[303,304,305],[112])
component('SHELL-B2','Battersea Shellmoon 2','Shellmoon',[306])
component('SHELL-I','Islington / Dropbox Battersea Shellmoon 3 (ISM1)','Shellmoon',[307,308,309],[114],notes='The manufacturing drawing identifies this horizontal form as Islington; do not reuse the vertical Battersea label for specifications.')
component('SPICE','Spice Texture','Spice Texture',[311,312])
component('SF-1','Spiralfish Wave & Tide left panel (SF1)','Spiralfish Wave & Tide',[313,314,315,316,319],[89])
component('SF-2','Spiralfish Wave & Tide right panel (WT2)','Spiralfish Wave & Tide',[313,317,318,319],[89])
component('SM-SPIRAL','Spiralmoon (SM1)','Spiralmoon',[320,322,323,324],[46])
component('SM-QUARTER','Quarter Moon (QM1; QM2 rotated)','Spiralmoon',[321,323,324],[49])
component('STRATA','Strata (ST1)','Strata',[325,326,327,328],[116])
component('TEXTURE-WIDE','Textured panel — blue/brown/rust','Textured panels',[329],status='Visual design proposal; retail alias unconfirmed')
component('TEXTURE-TALL','Textured panel — rust/blue patina','Textured panels',[330],status='Visual design proposal; retail alias unconfirmed')
component('WALL-CIRCLE','Wall Circle — pattern / lighting catalogue','Wall Circle',range(331,344),status='Concept/media and offered options; physical variants unverified',notes='One sale design family with 144 native option rows. Generated texture sheets, discs and reflections are not additional manufactured sculptures.')
component('AZURE','Azure blue-and-white marbled wall panel','Wall Panel Azure Blue Marble',[344,345])
component('WBMS-WAVE','Wave Between Moonshadow — Wave (WBMS2)','Wave and Moonshadow',[346,347,349,350],[101])
component('WBMS-MOON','Wave Between Moonshadow — Moonshadow (WBMS1; WBMS3 rotated)','Wave and Moonshadow',[346,348,349,350],[97])
component('MIX-SPIRALS','Stacked spiral strip in mixed workshop views','Collection Together',[50],status='Visual design proposal; retail alias unconfirmed',notes='Tall narrow strip with repeated spirals visible in mixed workshop photographs. Independent mould count and sale identity unresolved.')

rotation_rows=[('RW-WAVE','RW3','RW1','90 degrees anticlockwise',15),('LEAF-FORM','LF2','LF1','opposite orientation',34),('DDR-WAVE','DDR3','DDR1','180 degrees',58),('FDW-1','FDW3','FDW1','180 degrees',75),('MSW-MOON','MSW3','MSW1','180 degrees',83),('WBMS-MOON','WBMS3','WBMS1','180 degrees',97),('SM-QUARTER','QM2','QM1','180 degrees',49)]
for key,alias,canonical,rotation,row in rotation_rows:aliases.append(dict(component_id='BC-'+key,alias=alias,canonical=canonical,relationship='Same mould; orientation option',rotation=rotation,source=f'manufacture-stevensons:row{row}'))
aliases.extend([dict(component_id='BC-MP-2',alias='Dropbox Moonphase 1',canonical='MP2',relationship='Numbering crosswalk from labelled image',rotation='',source='manufacture-stevensons:row10'),dict(component_id='BC-MP-3',alias='Dropbox Moonphase 2',canonical='MP3',relationship='Numbering crosswalk from labelled image',rotation='',source='manufacture-stevensons:row11'),dict(component_id='BC-MP-4',alias='Dropbox Moonphase 3',canonical='MP4',relationship='Numbering crosswalk from labelled image',rotation='',source='manufacture-stevensons:row12')])

def plain(s):return ' '.join(html.unescape(re.sub('<[^>]+>',' ',s or '')).split())
def finish(g):
    s=g['name'].lower()
    ordered=[('white and gold','White and gold'),('gold leaf','Gold leaf'),('marbled green and white','Marbled green and white'),('pale blue and white','Pale blue and white'),('white and black','White and black'),('marbled black and white','Marbled black and white'),('blue splashes','Blue splashes'),('blue wash verdigris','Blue wash verdigris'),('copper and partial verdigris','Copper and partial verdigris'),('bronze verdigris','Bronze verdigris'),('verdigris rust','Verdigris/rust'),('verdigris and rust','Verdigris and rust'),('multicolour patina','Multicolour patina'),('sandstone','Sandstone appearance'),('silver leaf','Silver appearance'),('silver','Silver appearance'),('pewter','Pewter appearance'),('terracotta','Terracotta effect'),('paver brown','Brown paver'),('verdigris','Verdigris'),('copper','Copper effect'),('gold','Gold appearance'),('rust','Rust effect'),('beige','Beige'),('white','White')]
    return next((v for k,v in ordered if k in s),'Unspecified / mixed appearance')
excluded={10:'Mixed workshop / detail',50:'Mixed collection',72:'Mixed collection',82:'Concept / scene study',97:'Empty folder',140:'Concept / scene study',149:'Making process',153:'Concept / scene study',158:'Unresolved design studies',159:'Empty folder',161:'Unallocated cropped detail',165:'Making process',170:'Cropped detail',184:'Empty folder',189:'Making process',200:'Concept / scene study',231:'Unallocated cropped detail',232:'Unallocated cropped detail',246:'Reverse / fixing detail',247:'Mixed component stock',262:'Project details only',277:'Master / cast role unresolved',289:'Mixed-family arrangement',297:'Portrait / workshop',298:'Making process',310:'Unallocated cropped detail',331:'Concept / pattern study',332:'Generated texture study',333:'Generated texture study',334:'Generated texture study',335:'Generated texture study',336:'Generated texture study',340:'AI scene rendition',342:'AI scene rendition',343:'Concept / pattern study'}
for n in [187,188,204]:excluded[n]='Arrangement image'
for n in [13,15,191,314,317]:excluded[n]='Cropped detail'
excluded[98]='Arrangement image'
for n,g in groups.items():
    g['review_basis']='Representative images viewed in this review; '+('earlier complete group review retained' if g['earlier_full_group_review'] else 'not a fresh file-by-file classification')
    g['finish_appearance']=finish(g)
    role=excluded.get(n)
    if not role:
        s=g['name'].lower(); role='Context image' if ('in situ'in s or 'garden views'in s or 'room views'in s or 'scene views'in s) else ('Arrangement image' if len(bindings[n])>1 else 'Single component image')
    if not g['files']:role='Empty folder'
    g['role']=role;g['component_ids']=list(dict.fromkeys('BC-'+b['key'] for b in bindings[n]));g['assignment_status']='Visual/source-assisted group association' if bindings[n] else 'No individual component allocated'
    # Context can also be an arrangement: the media roles are not mutually exclusive.
    # These additional groups have clear environmental scenes in the reviewed representatives.
    g['has_context']=role in ['Context image','Concept / scene study','AI scene rendition'] or n in [3,71,179,183,197,206,289,306,322,330]
    g['has_arrangement']=role in ['Arrangement image','Mixed-family arrangement'] or (g['has_context'] and len(g['component_ids'])>1) or n in [3,7,31,55,187,188,204,324]
    if n==3:g['finish_appearance']='Bronze effect (project source)'
    if n in [23,174,178,179,180,262,263]:g['assignment_status']='Proposed project component positions; maker key pending'
    if n in [154,155,156,158,160]:g['assignment_status']='Partial only; variable fingerprint geometries require file-level allocation'
    if n in [50,72,297]:g['assignment_status']='Partial mixed inventory; all background objects not individually allocated'
    for b in bindings[n]:
        c=components[b['key']]
        if g['group_ref'] not in c['group_refs']:c['group_refs'].append(g['group_ref'])

# Offer bill of materials: quantity is a source sale unit, not a count of unique moulds.
offer_def={
1:['WALL-CIRCLE'],2:['DR-SPIRAL'],3:['CONCAVE'],4:['DR-WAVE1'],5:['MCP-3'],6:['MCP-4'],7:['MCP-1'],8:['MCP-2'],9:['DR-SPIRAL'],10:['MP-2','MP-3','MP-4'],11:['CONCAVE'],12:['SEAWEED-SMOOTH'],13:['DDR-SPIRAL','DDR-WAVE'],14:['FOUNTAIN-EG'],15:['CONCAVE'],16:['MOONWAVE'],17:['RW-WAVE','RW-SPIRAL3','RW-WAVE','RW-SPIRAL1'],18:['AM-1','AM-2'],19:['ECHO-1','ECHO-2'],20:['DP-LEAVES','DP-SPIRAL'],21:['MSW-MOON','MSW-MOON'],22:['FOLD-2'],23:['FOLD-3'],24:['FDW-1','FDW-2'],25:['FDW-1','FDW-2','FDW-1'],26:['SEAWEED-ROUGH'],27:['DP-SPIRAL','DP-PALM1','DP-PALM2'],28:['LEAF-FORM','LEAF-FORM'],29:['BR-1','BR-2'],30:['MP-1','MP-2','MP-3','MP-4','MP-5'],31:['MP-2','MP-3','MP-4'],32:['MSW-MOON','MSW-SPIRAL','MSW-MOON'],33:['MSW-MOON','MSW-SPIRAL'],34:['BONE-1','BONE-2'],35:['SF-1','SF-2'],36:['SM-SPIRAL'],37:['LEAF-GROWTH'],38:['DR-WAVE1'],39:['DR-SPIRAL'],40:['MS-2'],41:['EG-1','EG-2'],42:['EG-1'],43:['MFW-1','MFW-2'],44:['WBMS-MOON','WBMS-WAVE','WBMS-MOON'],45:['FOLD-1'],46:['DP-SPIRAL'],47:['DP-SPIRAL'],48:['AM-1','AM-2'],49:['FFS-2'],50:['DECO-1'],51:['DR-WAVE1'],52:['DR-SPIRAL'],53:['DP-PALM2'],54:['DP-PALM1'],55:['DP-PALM1','DP-PALM2','DP-SPIRAL'],56:['DP-SPIRAL','DP-PALM1'],57:['ECHO-1','ECHO-2'],58:['LEAF-FORM'],59:['MOON-WATER'],60:['DECO-1','DECO-2'],61:['ICARUS'],62:['STRATA'],63:['FFS-2'],64:['CONCAVE'],65:['MP-2'],66:['RUST-PANEL'],67:['DR-WAVE1'],68:['DR-SPIRAL'],69:['AC-TWO'],70:['MP-5'],71:['AC-FULL'],72:['ECHO-1','ECHO-2'],73:['AZURE'],74:['MP-3'],75:['MP-4'],76:['AC-FULL'],77:['AC-FLOWER'],78:['BAR-WAVE'],79:['BONE-WATER'],80:['BR-TOTEM']}
offer_cautions={6:'Proposed MCP4 geometry; exact exported file/specimen not yet certified.',7:'Proposed MCP1 geometry; exact exported file/specimen not yet certified.',10:'Gallery contains three phases but text says each. Sale quantity unresolved; BOM is a gallery proposal, not a certified three-part sale.',11:'25 cm concave/spherical member; exact specimen unresolved. Do not transfer 50 cm offer.',15:'Identity conflict: the title says Concave Moon, but the primary image matches Moon Water Catcher in Dropbox. Intended Concave Moon BOM remains provisional; do not transfer these offer dimensions/weight to that photographed Water Catcher.',20:'Primary photo shows Two Leaves plus Spiral; it does not show two Palm panels. BOM follows the photograph.',32:'Triptych follows title, first two images and maker key; a four-panel alternative is also in the gallery.',38:'Plain-waves photo matches the group; exact DR1 versus DR3 mould allocation remains provisional.',40:'Hero matches Moonspiral 2; mixed two-panel gallery views are alternative works, not the sale unit.',47:'Same spiral geometry as Deco Spiral. Native 45×40 size must not be replaced with Golden Spiral 30×30.',49:'Terracotta single geometry supported; shared reverse image with Frozen Deco is not identity proof.',57:'Pair shown, while text/SKU lacks a clear pair sale quantity; confirm sale unit.',58:'Single-item offer even though gallery includes a pair. 40×20 text differs from square 35×35 template.',60:'Coloured Decowaves pair, not automatically the white Frozen Decowaves mould/finish version.',70:'Silver plain-moon image; manufacturing MP1/MP5 orientation identity remains a source crosswalk question.',72:'Pair description, with only one principal component shown in selected front images. Whole weight is not component weight.',73:'One panel sold; the paired room scene includes a different panel. Second panel remains an unallocated background work.',79:'Native 55×55 versus 80×60 maker version; do not certify absolute size from the photograph.'}
historical_by_sku={r['SKU']:r for r in source['Historical Products']}
match_by_pid={r['sq_id']:r for r in comparison['matches']}
native_by_pid={r['Product ID [Non Editable]']:r for r in source['SS Wall Products']}
platform=[];bom=[]
accepted={}
for r in json.loads((base/'image_review_curated_review.json').read_text()):
    if (r.get('source') or {}).get('id') in assets:accepted[r['pid']]=dict(file_id=r['source']['id'],state=r['state'],basis=r.get('notes',''))
for r in json.loads((base/'established_image_decisions.json').read_text()):
    if r.get('asset_id') in assets:accepted[r['pid']]=dict(file_id=r['asset_id'],state=r['basis'],basis=r.get('detail',''))
retrieval=json.loads((ev/'image_retrieval_candidates.json').read_text()) if (ev/'image_retrieval_candidates.json').exists() else []
retrieval={r['pid']:r for r in retrieval}
for n,o in enumerate(offers,1):
    raw=native_by_pid[o['pid']];hist=historical_by_sku.get(o['sku'],{});match=match_by_pid.get(o['pid'],{});keys=offer_def[n];caution=offer_cautions.get(n,'')
    visual=accepted.get(o['pid'],{});r=retrieval.get(o['pid'],{});candidate=r.get('candidates',[{}])[0]
    # Explicitly reviewed primary pairings. Low feature distance alone is never identity authority.
    reviewed_primary={12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,46,47,48}
    if n in reviewed_primary and candidate.get('asset_id'):
        visual=dict(file_id=candidate['asset_id'],state='Visually confirmed primary design / arrangement',basis='Native primary and candidate image pairs visually reviewed; size, mass and cast chemistry remain source claims. Pixel/byte equality not asserted.')
        if n==15:visual['state']='Photograph confirmed; named product identity conflicts'
    if n==45:
        visual=dict(file_id=groups[145]['selected'][0],state='Design confirmed against source reference; exact hero file not located',basis='S-turn Swan Wing relief matches Fold Unfold 1. The retrieval rankings for similar fan ribs were rejected as identity proof.')
    native_parts=int(hist.get('Parts') or 1)
    unit='Sale component' if len(keys)==1 else 'Sale arrangement components'
    if n in [10,57]:unit='Gallery proposal; sale quantity unresolved'
    po=dict(offer_ref=o['ref'],platform='Squarespace'+(' + Shopify' if match else ' only'),sq_id=o['pid'],sh_handle=match.get('sh_handle',''),sku=o['sku'],title=o['title'],source_url=o['url'],source_row=raw['_row'],page_status=o['page_status'],page_sha256=o.get('page_sha256',''),native_parts=native_parts,proposed_bom_pieces=len(keys),sale_unit_state=unit,source_each_cm=hist.get('Each component (cm)',''),source_overall_cm=hist.get('Overall (cm)',''),source_set_weight_kg=hist.get('Export weight (kg)',''),native_price=raw.get('Price',''),native_currency='Unencoded in original export',native_description=plain(raw.get('Description','')),raw_weight=raw.get('Weight',''),raw_length=raw.get('Length',''),raw_width=raw.get('Width',''),raw_height=raw.get('Height',''),raw_units='Native Squarespace dimensions/weight do not encode units',visible=raw.get('Visible',''),stock=raw.get('Stock',''),match_status='Unique shared SKU confirmed' if match else 'Squarespace only; no confirmed Shopify counterpart',image_file_id=visual.get('file_id',''),image_state=visual.get('state','Design/arrangement comparison; exact source file unresolved'),cautions=caution)
    if po['image_file_id']:
        a=assets[po['image_file_id']];po.update(image_folder_id=a['folder_id'],image_path=a['path'])
    else:po.update(image_folder_id='',image_path='')
    public_product=next((v for v in o.get('structured',[]) if v.get('@type')=='Product'),{})
    public_offer=public_product.get('offers',{})
    if isinstance(public_offer,list):public_offer=public_offer[0] if public_offer else {}
    po.update(public_price=public_offer.get('price',''),public_low_price=public_offer.get('lowPrice',''),public_high_price=public_offer.get('highPrice',''),public_currency=public_offer.get('priceCurrency',''),public_sku=public_offer.get('sku',''),public_availability=public_offer.get('availability',''),public_sku_comparison='Same SKU' if public_offer.get('sku')==o['sku'] else ('Different SKU; current page/version needs review' if public_offer.get('sku') else 'SKU not exposed in public structured offer'))
    platform.append(po)
    for pos,key in enumerate(keys,1):
        c=components[key];c['offer_refs'].append(o['ref']);gg=[groups[int(x[1:])] for x in c['group_refs']];fileids=list(dict.fromkeys(fid for g in gg for fid in g['selected']))
        bom.append(dict(bom_id=o['ref']+f'-P{pos:02d}',offer_ref=o['ref'],component_id=c['component_id'],component_name=c['name'],position=pos,quantity=1,sku=o['sku'],sq_id=o['pid'],sh_handle=match.get('sh_handle',''),scope=unit,orientation='Source diagram position; rotated duplicates retained as positions',component_dimensions_source_cm=hist.get('Each component (cm)','') if n!=34 else ('55 × 30 × 7' if pos==1 else '55 × 55 × 7'),dimensions_state='Native each-component claim; depth not physically measured' if hist else 'See component/source claims; not an allocation of whole dimensions',set_overall_cm=hist.get('Overall (cm)',''),set_weight_kg=hist.get('Export weight (kg)',''),set_price=raw.get('Price',''),component_weight='Not divided from set weight',component_price=raw.get('Price','') if len(keys)==1 else 'No standalone price established by this set',folder_ids='\n'.join(g['id'] for g in gg),example_file_ids='\n'.join(fileids[:10]),mapping_state=po['image_state'],cautions=caution))
# Blank-SKU Shopify draft is linked only to its photographed white arrangement.
draft=comparison['shopify_only'][0]
platform.append(dict(offer_ref='SH-DRAFT',platform='Shopify only',sq_id='',sh_handle=draft['handle'],sku=draft['sku'],title=draft['title'],source_url=draft['raw'].get('Image Src',''),source_row=draft['source_row'],page_status='Historical export; live state not inspected',native_parts='',proposed_bom_pieces=3,sale_unit_state='Photographed triptych; blank description/SKU',source_each_cm='',source_overall_cm='',source_set_weight_kg=draft['raw'].get('Variant Grams',''),native_price=draft['raw'].get('Variant Price',''),native_description='',raw_units='Zero/unfilled draft weight and price are not a physical specification',match_status='Unmatched blank SKU; not either coloured Squarespace single',image_file_id=accepted.get('SH:frozen-fish',{}).get('file_id',''),image_state='Previously confirmed white triptych image',cautions='No current stock or live state inferred.'))
draft_fid=platform[-1]['image_file_id'] or groups[172]['selected'][0]
platform[-1].update(image_file_id=draft_fid,image_folder_id=assets[draft_fid]['folder_id'],image_path=assets[draft_fid]['path'])
for pos,key in enumerate(['FFS-1','FFS-2','FFS-3'],1):
    c=components[key];c['offer_refs'].append('SH-DRAFT');g=groups[172]
    bom.append(dict(bom_id=f'SH-DRAFT-P{pos}',offer_ref='SH-DRAFT',component_id=c['component_id'],component_name=c['name'],position=pos,quantity=1,sku='',sq_id='',sh_handle=draft['handle'],scope='Historical draft pictured components; sale specifications incomplete',folder_ids=g['id'],example_file_ids='\n'.join(g['selected']),component_weight='Unknown',component_price='Unknown',mapping_state='Photograph / maker-key proposal; cast-specific size not measured',cautions='Do not merge with coloured singles through a blank SKU.'))

maker_rows={r['row']:r['values'] for r in e['manufacturing_rows']}
def addclaim(key,field,value,scope,status,source_ref,unit='As stated'):
    if value not in ['',None]:claims.append(dict(claim_id='CE-'+hashlib.sha256(f'{key}|{field}|{value}|{scope}|{source_ref}'.encode()).hexdigest()[:12].upper(),component_id='BC-'+key,field=field,value=str(value).strip(),unit=unit,scope=scope,status=status,source_ref=source_ref))
for key,c in components.items():
    for row in c['maker_rows']:
        v=maker_rows[row];code=v.get('Product Code A','').strip();c['source_codes'].append(code)
        for field,nativefield in [('Manufacturing mould / repetition','SIZE A                        \nMould Description'),('Manufacturing component dimensions / side depth','SIZE A                          \nCast Description'),('Manufacturing description','Description of whole piece in Standard Size A '),('Conditional component weight','Approximate Weight of each piece in Standard Size A '),('Fixings instruction','Instructions on number of fixings and sizes of fixings')]:
            if key!='FFL-1':addclaim(key,field,v.get(nativefield,''),'Historical standard white-marble Jesmonite AC730 template; not every photographed finish','MAKER SOURCE; approximate calculated weight',f'manufacture-stevensons:Sheet1!row{row}/{nativefield}')
        if key in ['AM-1','AM-2','FFL-1']:
            c['source_codes'].append(v.get('Product Code B','').strip())
            for field,nativefield in [('Large-size dimensions','SIZE B                  \nCast Description larger size'),('Large-size weight','Approximate Weight of each piece in Standard Size B ')]:addclaim(key,field,v.get(nativefield,''),'Historical large-size AC730 option only','MAKER SOURCE; approximate calculated weight',f'manufacture-stevensons:Sheet1!row{row}/{nativefield}')
    c['source_codes']=list(dict.fromkeys(v for v in c['source_codes'] if v))
offer_keys_by_component=defaultdict(set)
for b in bom:
    p=next(p for p in platform if p['offer_ref']==b['offer_ref']);
    if p['sq_id']:offer_keys_by_component[b['component_id']].add('SQ:'+p['sq_id'])
    if p.get('sh_handle'):offer_keys_by_component[b['component_id']].add('SH:'+p['sh_handle'])
for key,c in components.items():
    for f in old['facts']:
        if f['offer_key'] in offer_keys_by_component[c['component_id']]:addclaim(key,f['field'],f['value'],f['scope']+'; copied as offer evidence, not automatically component-specific',f['status'],f['locator'],f['unit'])
    for p in platform:
        if p['offer_ref'] not in c['offer_refs'] or p['offer_ref']=='SH-DRAFT':continue
        if p.get('public_currency'):
            value=f'{p["public_currency"]} {p["public_price"]}' if p.get('public_price')!='' else f'{p["public_currency"]} {p.get("public_low_price","")}–{p.get("public_high_price","")} range'
            addclaim(key,'Current public offer price',value,'Entire source offer / sale unit; do not divide a set price to create component prices','PUBLIC STRUCTURED OFFER SOURCE',p['source_url']+' / JSON-LD Product.offers',p['public_currency'])
        # Preserve any current public specification lines, including additions missing from the export.
        textpath=ev/'public-pages'/(p['sq_id']+'.txt')
        if textpath.exists():
            lines=list(dict.fromkeys(l for l in textpath.read_text().splitlines() if re.search(r'\b(cm|mm|kg|Jesmonite|gypsum|plaster|keyhole|cleat|pallet|production time)\b',l,re.I)))
            for n,line in enumerate(lines,1):addclaim(key,'Current public specification text',line,'Current public offer; component applicability follows BOM and sale-scope cautions','PUBLIC PAGE SOURCE CLAIM',p['source_url']+f' / extracted specification line {n}')

# Concise component-level dimensional register, keeping conflicting versions visible.
dimensions={
'ICARUS':'200 × 100 × 5 cm panel; 186 × 86 × 6.5 cm framework', 'AC-FULL':'50 × 30 × 6 cm native; brochure versions differ','AC-FLOWER':'30 × 30 × 6 cm','AC-TWO':'30 × 30 × 6 cm bronze native; other finishes unmeasured','AM-1':'Small native 52 × 25 × 5 cm; maker 52 × 26 cm; brochure 50 × 25 cm. Large 120 × 60 × 6 cm','AM-2':'Small native 52 × 25 × 5 cm; maker 52 × 26 cm; brochure 50 × 25 cm. Large 120 × 60 × 6 cm','BAR-WAVE':'100 × 100 × 8 cm','BONE-1':'55 × 30 cm from maker; native set depth 7 cm','BONE-2':'55 × 55 cm from maker; native set depth 7 cm','BONE-WATER':'Native 55 × 55; maker 80 × 60 cm — size/version conflict','BR-TOTEM':'Description 100 × 22 × 8 cm; conflicting raw dimensions retained','BR-1':'50 × 25 × 8 cm native; historic side 5–7 cm','BR-2':'50 × 25 × 8 cm native; historic side 5–7 cm','CONCAVE':'50 × 50 × 6 cm white native; 25 × 25 × 6 cm coloured native','DDR-WAVE':'100 × 22 × 6 cm native; maker side 5–7 cm','DDR-SPIRAL':'100 × 22 × 6 cm native; maker side 5–7 cm','DECO-1':'90 × 15 × 9 cm terracotta; coloured pair 90 × 15 × 8 cm each','DECO-2':'Coloured pair 90 × 15 × 8 cm each','FDW-1':'90 × 15 × 8 cm native; maker side 5–7 cm','FDW-2':'90 × 15 × 8 cm native; maker side 5–7 cm','DR-WAVE1':'35 × 20 × 6 cm historic; coloured native 35 × 21 × 6 cm','DR-WAVE3':'35 × 20 cm maker; side 5–7 cm','DR-SPIRAL':'35 × 20 × 5 cm historical gold; coloured native 35 × 21 × 6 cm','ECHO-1':'30 × 30 × 6 cm white pair; coloured native depth 7 cm','ECHO-2':'30 × 30 × 6 cm white pair; coloured native depth 7 cm','EG-1':'50 × 30 × 7 cm native; other versions unmeasured','EG-2':'50 × 30 × 7 cm native','FOLD-1':'70 × 50 × 6 cm native','FOLD-2':'70 × 50 × 6 cm native; primary-image conflict','FOLD-3':'70 × 50 × 6 cm native','FOUNTAIN-EG':'100 × 50 × 6 cm native','FFS-1':'70 × 15 cm maker; side 5–7 cm','FFS-2':'70 × 15 × 7 cm coloured native; maker side 5–7 cm','FFS-3':'70 × 15 cm maker; side 5–7 cm','FFL-1':'100 × 22 cm maker; side 5–7 cm','LEAF-FORM':'35 × 35 × 6 cm pair; single description 40 × 20 cm — conflict','LEAF-GROWTH':'100 × 30 × 6 cm native','MSW-MOON':'100 × 22 × 6 cm native; maker side 5–7 cm','MSW-SPIRAL':'100 × 22 × 6 cm native; maker side 5–7 cm','MFW-1':'55 × 42 × 7 cm native; maker side 5–7 cm','MFW-2':'55 × 42 × 7 cm native; maker side 5–7 cm','MS-1':'70 × 50 cm maker; side 5–7 cm','MS-2':'70 × 50 × 7 cm native; maker side 5–7 cm','MS-3':'70 × 50 cm maker; side 5–7 cm','MOON-WATER':'Native 50 cm diameter × 8 cm versus rectangular photo; maker 51 × 48 cm; retail 50.5 × 47.5 cm','MOONWAVE':'74 × 35 × 9 cm native','SEAWEED-ROUGH':'50 × 100 × 6 cm native','SEAWEED-SMOOTH':'50 × 100 × 6 cm native','SHELL-B1':'70 × 50 cm maker; side 5–7 cm','SHELL-I':'50 × 70 cm maker; side 5–7 cm','SF-1':'55 × 55 × 7 cm native; maker side 5–7 cm','SF-2':'55 × 55 × 7 cm native; maker side 5–7 cm','SM-SPIRAL':'55 × 55 × 7 cm native; maker side 5–8 cm','SM-QUARTER':'55 × 55 cm maker; side 5–8 cm','STRATA':'30 × 30 × 6 cm coloured native','WBMS-WAVE':'40 × 40 × 6 cm native; maker side 5–7 cm','WBMS-MOON':'40 × 40 × 6 cm native; maker side 5–7 cm'}
for i in range(1,6):dimensions[f'MP-{i}']='30 × 30 cm maker; side 5–7 cm; native plaster versions 6 cm deep'
for i in range(1,5):dimensions[f'MCP-{i}']='25 × 25 cm maker; side 4–6 cm; native versions require dimension reconciliation'
for k in ['DP-PALM1','DP-PALM2','DP-SPIRAL','DP-LEAVES']:dimensions[k]='30 × 30 cm and 45 × 40 cm retail versions; exact size of each image/cast unverified'
dimensions['FOLD-2']='70 × 50 × 6 cm native'
dimensions['BONE-WATER']='Native 55 × 55 × 7 cm; maker 80 × 60 cm — size/version conflict'
for k in ['DP-PALM1','DP-PALM2','DP-SPIRAL']:dimensions[k]='30 × 30 cm, 45 × 40 cm and 40 × 45 × 6 cm source versions; image/cast size unmeasured'
weights={'ICARUS':'Approximately 60 kg native/current page','AC-FULL':'Approx. 8 kg native per panel','AC-FLOWER':'Approx. 4 kg native','BAR-WAVE':'Approx. 83 kg native/current page','BONE-1':'Brochure 8.5 kg; maker 10–12 kg calculated each (conflict)','BONE-2':'Brochure 15 kg; maker 10–12 kg calculated each (conflict)','DECO-1':'Approx. 6 kg terracotta native; 14 kg coloured pair is not a per-panel weight','STRATA':'4 kg coloured native'}
for key,c in components.items():
    c['dimensions_available']=dimensions.get(key,'No component dimensions established')
    single_weights=[p['source_set_weight_kg']+' kg native single-item export claim' for p in platform if p['offer_ref'] in c['offer_refs'] and p.get('proposed_bom_pieces')==1 and p.get('source_set_weight_kg')]
    weight_field='Approximate Weight of each piece in Standard Size B ' if key=='FFL-1' else 'Approximate Weight of each piece in Standard Size A '
    maker_weights=[str(maker_rows[row].get(weight_field,'')).strip()+' (calculated AC730 template)' for row in c['maker_rows'] if maker_rows[row].get(weight_field)]
    c['weight_available']=weights.get(key,'; '.join(dict.fromkeys(single_weights+maker_weights)) or 'No individual weight established')
    c['weight_status']='Approximate/source values; cast-specific weighing not verified'
    c['fixing_available']='; '.join(dict.fromkeys(maker_rows[row].get('Instructions on number of fixings and sizes of fixings','').strip() for row in c['maker_rows'] if maker_rows[row].get('Instructions on number of fixings and sizes of fixings'))) or 'See linked native/source claims; no complete component fixing record'
    native_material=list(dict.fromkeys(f['value'] for f in old['facts'] if f['offer_key'] in offer_keys_by_component[c['component_id']] and 'Material' in f['field']))
    c['material_available']=('; '.join(native_material)[:1800]+'; offer/finish scope only') if native_material else ('Historical white standard: Jesmonite AC730; photographed coloured variants require their own linked material claim' if c['maker_rows'] else 'No object-specific substrate claim identified; visible finish is not a material certificate')
    c['standalone_offer_refs']=[p['offer_ref'] for p in platform if p['offer_ref'] in c['offer_refs'] and p.get('proposed_bom_pieces')==1]
    c['current_individual_prices']='; '.join(p['offer_ref']+': '+p.get('public_currency','')+' '+str(p.get('public_price','')) for p in platform if p['offer_ref'] in c['standalone_offer_refs'] and p.get('public_currency') and p.get('public_price')!='')
    c['listing_action']='Review existing individual offer and resolve specifications' if c['standalone_offer_refs'] else 'Prepare individual component listing / variant; price and sale status required'
    if c['identity_status'].startswith(('Bespoke','Visual')):c['listing_action']='Confirm component identity / production status, then prepare individual listing'
    if c['identity_status'].startswith(('Concept','Source-only')):c['listing_action']='Confirm actual production / intended range before creating buyable variants'
    c['physical_specs_verified']=False

# Conditional historic individual price references: already priced by the maker per piece,
# not a division of arrangement prices and not a current selling-price recommendation.
retail_groups=[(['MCP-1','MCP-2','MCP-3','MCP-4'],'25×25',4,130.84),(['MP-1','MP-2','MP-3','MP-4','MP-5','RW-WAVE','RW-SPIRAL1','RW-SPIRAL3','CR-RING','CR-SPIRAL','ECHO-1','ECHO-2','STRATA'],'30×30',5.5,182.05),(['LEAF-FORM'],'35×35',6,241.54),(['DP-PALM1','DP-PALM2','DP-SPIRAL'],'45×40',8,345.28),(['SM-SPIRAL','SM-QUARTER'],'55×55',12,562.36),(['DR-WAVE1','DR-WAVE3','DR-SPIRAL'],'35×20',4.5,146.09),(['BR-1','BR-2'],'50×25',6,248.50),(['MOON-WATER'],'50.5×47.5',10,451.82),(['FFS-1','FFS-2','FFS-3'],'70×15',6.5,220.99),(['MS-1','MS-2','MS-3','SHELL-B1','SHELL-I'],'70×50 (orientation varies)',12,646.71),(['FDW-1','FDW-2'],'90×15',8,281.97),(['MSW-MOON','MSW-SPIRAL','FFL-1','DDR-WAVE','DDR-SPIRAL'],'100×22',10,432.41),(['LEAF-GROWTH'],'100×30',12,569.49)]
for keys,size,kg,gbp in retail_groups:
    for key in keys:
        addclaim(key,'Historic per-piece retail reference',f'Size {size} cm; estimated {kg} kg each; GBP {gbp:.2f} per piece','2025 white marble stone made-to-order standard; extra finishes, water features, delivery and packaging quoted separately','DATED MAKER PRICE / ESTIMATE; NOT CURRENT PRICE','retail-2025:table '+size,'cm; kg; GBP')
        components[key]['historic_individual_price']=f'GBP {gbp:.2f} each (2025 white standard, {size} cm; not current/other finishes)'

# Explicit per-component inference. Never claim that images determine mass or chemistry.
inferences=[]
def infer(key,field,proposal,basis,confidence,needed):inferences.append(dict(component_id='BC-'+key,component_name=components[key]['name'],field=field,proposal=proposal,basis=basis,confidence=confidence,status='PROPOSED / NOT A MEASUREMENT',needed=needed,folder_ids='\n'.join(groups[int(g[1:])]['id'] for g in components[key]['group_refs']),example_file_ids='\n'.join(fid for g in components[key]['group_refs'] for fid in groups[int(g[1:])]['selected'])[:2500]))
visual_forms={'AC-ONE':'Square panel with three broad concentric leaf/arc bands; approximately 1:1 face aspect','CHELSEA':'Tall rectangular panel with a separate upper crescent and lower shell spiral; roughly 2:1 height-to-width in the full views','CHISWICK':'Approximately square face with a deep spiral and swept crescent; the water-feature and wall versions need separate plumbing/build specifications','CORAL':'Approximately square relief with coarse, branching spiral ridges; surface appearance does not establish substrate','EG-3':'Portrait panel with three broad palm-frond arcs; not enough calibration to inherit another Palm size','EG-4':'Extended narrow palm relief; visibly taller in proportion than the standard Egyptian pair','EMBED-SHELLS':'Tall narrow strip with embedded shell forms; visible shells do not determine the backing material','FACET-MOUND':'Portrait rectangular panel with two smooth faceted/curved bulges; gold appearance is not a leaf-content test','FOUNTAIN-MED':'Portrait rectangular palm/fountain relief; similar proportions to the Egyptian companion, different rib geometry','KNIGHT':'Approximately square fountain relief with a central spiral/water outlet; hose, reservoir and pump are outside the image specification','LEAF-CURVE':'Approximately square panel with intersecting broad leaf curves; white/gold mottling appears on the face','CRATER-WIDE':'Approximately square bowl relief with a broad rough rim and rust appearance; cannot deduce mass or a formal MCP alias','MOON-RING':'Approximately square shallow crescent/ring relief; distinct visible form, no absolute scale','MOON-CRATER':'Square plan with a deep circular basin; outdoor/water imagery does not establish waterproofing or load details','LAVA-CORNER':'Square corner-curve textured relief; some large upper texture detail is cropped','MLAVA-1':'Approximately square coarse spiral panel','MLAVA-2':'Approximately square/rectangular relief with a spiral and broad smooth moon arcs; local member numbering only','PANEL-CURVES':'Square fan-and-arc relief, with beige process views and multicolour patina; process colour is not an offered finish','PLANT':'Approximately square panel with raised seed/leaf forms crossing the face','RUST-PANEL':'Flat approximately square panel with rust and turquoise surface areas; there is no visible relief design to allocate a mould by','SHELL-B2':'Portrait rectangular shell/crescent relief with a water outlet; its spiral differs from the BSM1 reference','SPICE':'Approximately square textured relief with scattered seed/stick-like inclusions','TEXTURE-WIDE':'Broad rectangular textured panel; blue/brown/rust coating views and close surface crops','TEXTURE-TALL':'Tall rectangular panel with dark vertical streaks and blue patina','AZURE':'Very tall narrow rectangular marbled panel; the second wavy panel in a paired scene is a separate unresolved subject','MIX-SPIRALS':'Tall strip with a stack of repeated spirals visible in mixed workshop photographs; repeated spirals are surface elements, not separately buyable pieces'}
for key,form in visual_forms.items():infer(key,'Visible component form / proportion',form,'Reviewed full-view or source-linked component images; apparent proportions are not a calibrated measurement','Moderate for visible form; no absolute scale inferred','Confirm a maker drawing or ruler-calibrated photograph for dimensions and production identity')
for key in ['BONE-1','BONE-2']:
    infer(key,'Panel width / split',('30 cm' if key.endswith('1') else '55 cm'),'Labelled maker row91 plus visible unequal seam; 30+55=85 cm native overall width','High for the standard design; current specimen unmeasured','Confirm current cast dimensions and depth; weigh separately')
for key in components:
    c=components[key]
    if key=='WALL-CIRCLE':
        infer(key,'Production identity','One configurable circle family; generated patterns and scene discs do not establish manufactured stock','Image content, explicit generated series and native 144 option rows','High for catalogue structure; physical options unverified','Production specification and real product photographs for each intended option');continue
    if key=='FFL-1':continue
    if key not in dimensions:
        shape='Single relief panel / component position; absolute size, depth and weight cannot be recovered from these unscaled views'
        if key.startswith('LUCIANO-'):shape='If three equal-width vertical panels span the documented 215×180 cm screen, each would be about 215×60 cm; this is conditional and gaps/unequal panels may change it'
        elif key in ['FOLD-4']:shape='Proposed 70×50 cm companion size, with 6 cm depth only as an analogy; use 18 kg only as a whole-panel reference from the related Fold listings, not a predicted weight'
        elif key=='AC-ONE':shape='Proposed 30×30 cm companion square; related Acanthus single and brochure support a size candidate. Depth and mass remain unknown'
        elif key in ['EG-3','EG-4']:shape='Family geometry suggests a palm panel; 50×30 cm is a reference for the standard Egyptian pair, not a measured size for this different/extended form'
        elif key=='FOUNTAIN-MED':shape='Proposed 100×50 cm companion size from the Egyptian Fountain reference; photographs show another relief, so dimensions and mass need confirmation'
        elif key=='SHELL-B2':shape='Proposed 70×50 cm companion scale from Battersea/Islington standards; relief/centre differs and current size is unverified'
        elif key in ['MIX-SPIRALS','KNIGHT']:shape='Tall/multi-spiral or fountain relief identifiable visually; scale, internal build and water-feature plumbing cannot be established from the image'
        infer(key,'Visual form / size hypothesis',shape,'Reviewed contact sheet, stable image references and related component/source specifications','Low for numeric analogies; moderate for visible form / count','Maker drawing or ruler-calibrated front/side image, material card, separate weighing, fixing and price')
    if c['maker_rows'] and not c['standalone_offer_refs']:
        infer(key,'Historical side depth / approximate weight',f'Use the linked maker side-depth range and calculated each-piece weight only as a historical white AC730 template: {c["weight_available"]}','Labelled manufacturing row(s) '+','.join(map(str,c['maker_rows']))+'; not set-weight division','Medium for a proposed template; low for any different photographed finish','Confirm substrate and current version, measure depth and weigh the actual component')
    infer(key,'Material, mass, fixing capacity and individual price','Do not infer chemistry, real mass, load rating or standalone price from photographs. Preserve explicit source claims and leave unsupported fields open.','Images provide form, visible count, apparent finish and orientation; they do not provide density, construction, load tests or pricing policy.','Not inferable reliably from current image evidence','Production card, scale measurement, fixing drawing/load specification and individual sale price')

# Photo audit is per component + depicted finish, so a white scene cannot fill a bronze photo gap.
configs=[]
for key,c in components.items():
    gg=[groups[int(x[1:])] for x in c['group_refs'] if groups[int(x[1:])]['files']]
    byfinish=defaultdict(list)
    for g in gg:byfinish[g['finish_appearance']].append(g)
    if not gg:byfinish['White standard option (source only)']=[]
    for f,rows in byfinish.items():
        roles={g['role'] for g in rows}
        solo=[g for g in rows if g['role']=='Single component image']
        context=[g for g in rows if g['has_context']]
        series=[g for g in rows if g['has_arrangement']]
        # These groups contain variable arrangements. Existence is a candidate, not a per-file blanket classification.
        if key.startswith('FP-'):photo_state='Partial: only matched concentric rectangular frames; other geometries unallocated'
        else:photo_state='Group-level presence from representative / prior reviewed imagery; no per-file totals implied'
        eligible_series=any(len(bindings[int(g[1:])])>1 or groups[int(g[1:])]['has_arrangement'] for g in c['group_refs'])
        cfgid='CFG-'+hashlib.sha256((c['component_id']+'|'+f).encode()).hexdigest()[:10].upper()
        config=dict(configuration_id=cfgid,component_id=c['component_id'],component_name=c['name'],family=c['family'],finish_appearance=f,size_options=c['dimensions_available'],individual_front='Identified' if solo else 'Not identified in this review',in_situ='Context image identified' if context else 'No context image identified',series='Arrangement image identified' if series else ('No arrangement image identified' if eligible_series else 'Optional: no fixed multi-part series established'),solo_folder_ids='\n'.join(g['id'] for g in solo),context_folder_ids='\n'.join(g['id'] for g in context),series_folder_ids='\n'.join(g['id'] for g in series),all_folder_ids='\n'.join(g['id'] for g in rows),example_file_ids='\n'.join(dict.fromkeys(fid for g in rows for fid in g['selected'])),photo_scope=photo_state,scene_provenance='Known AI / study scenes present' if any(g['role'] in ['Concept / scene study','AI scene rendition'] for g in context) else ('Project evidence available for some files; see source decisions' if any(g['source_decision'].get('scene_origin',{}).get('evidence_level')=='PROJECT_RECORD_MATCH' for g in context) else 'Client installation provenance not certified'),missing_specs='Current measured weight; cast-specific material; exact fixing/load record; care/packaging; '+('individual selling price; ' if not c['standalone_offer_refs'] else '')+('component dimensions/depth; ' if key not in dimensions else 'reconcile size/version/depth claims; '),readiness='Needs source confirmation before complete individual listing',image_finish_status='Visible appearance / media grouping; chemical finish and actual manufacture not proved by colour')
        configs.append(config)

# Retain unresolved cropped and changing-study imagery explicitly instead of manufacturing phantom models.
unresolved=[]
for n in [10,23,50,72,149,154,155,156,158,160,161,165,184,189,200,231,232,246,247,262,263,277,289,297,298,310,331,332,333,334,335,336,340,342,343]:
    g=groups[n]
    if not g['files']:continue
    unresolved.append(dict(group_ref=g['group_ref'],family=g['family'],group_name=g['name'],folder_id=g['id'],files=g['files'],state=g['assignment_status'],role=g['role'],finding=g['earlier_observations'] or 'Representative review: cropped / mixed / process or unresolved component evidence. Do not count this folder as an extra sculpture.',source_finding=g['source_decision'].get('component_numbers',{}).get('finding',''),next_action='Obtain a maker-approved component key, original uncropped views or production status; deduplicate designs before adding sale records.',example_file_ids='\n'.join(g['selected'])))
g=groups[345]
unresolved.append(dict(group_ref=g['group_ref'],family=g['family'],group_name=g['name'],folder_id=g['id'],files=g['files'],state='One mapped Azure panel plus a different panel in the paired room scene',role='Unallocated background component',finding='The second white/blue wavy panel in the two-panel lifestyle scene is not the single Azure specimen pictured beside it. No standalone product identity, actual stock or specifications are certified for that second panel.',source_finding='Squarespace offer O073 sells one Azure panel; a scene quantity does not define its sale unit.',next_action='Confirm whether the second panel is an actual intended product or a scene-study variant; supply a front view and component key.',example_file_ids='\n'.join(g['selected'])))

# File-specific mixed-scene associations. Parent-folder membership alone never assigns
# every file to every component in a mixed group.
mixed_map={1:['MSW-SPIRAL','DDR-WAVE','DDR-SPIRAL'],3:['FDW-1','FDW-2','FFS-2','SM-SPIRAL','MIX-SPIRALS'],5:['BONE-1','BONE-2','FDW-1','FDW-2','FFS-2','SM-SPIRAL'],9:['SM-SPIRAL','MS-2'],18:['MSW-SPIRAL','FFS-2'],35:['FFS-2','MS-2','MSW-SPIRAL','SM-SPIRAL'],64:['EG-1','DP-LEAVES'],65:['EG-1','DP-LEAVES','DP-SPIRAL'],68:['AC-FULL','EG-1','EG-2'],74:['EG-1','DP-SPIRAL'],99:['EG-1','DP-SPIRAL'],103:['EG-1','DP-SPIRAL','MP-1'],120:['DR-SPIRAL','DP-SPIRAL'],123:['DP-SPIRAL','FFS-2'],127:['SF-1','SF-2','MSW-MOON','MSW-SPIRAL'],130:['WBMS-WAVE','WBMS-MOON','MS-1','MS-2'],133:['MOONWAVE'],138:['EG-1','DP-LEAVES','DP-SPIRAL'],141:['DP-LEAVES','DP-PALM1','DP-PALM2','DP-SPIRAL'],143:['FFS-2','MS-2','SM-SPIRAL'],151:['DR-WAVE1'],152:['RUST-PANEL','STRATA']}
mixed_bindings=[]
for a in e['assets']:
    if a['folder_id']!=groups[50]['id']:continue
    serial=int(re.search(r'__(\d+)\.',a['name']).group(1))
    for key in mixed_map.get(serial,[]):mixed_bindings.append(dict(component_id='BC-'+key,file_id=a['id'],folder_id=a['folder_id'],file_path=a['path'],scope='Visible design in this mixed photograph; size/finish/specimen not certified',basis='Full mixed contact sheet visually reviewed'))

# File-level observed scene counts in variable Fingerprint imagery, with stable per-position work items.
positions=[]
for a in e['assets']:
    gn=next((n for n,g in groups.items() if g['id']==a['folder_id']),None)
    if gn not in [156,158,160]:continue
    serial=int(re.search(r'__(\d+)\.',a['name']).group(1))
    count=2
    if gn==156 and serial==2:count=0 # Irregular segmentation: a maker key is needed to decide separate buyable components.
    if gn==158 and serial in [7,8,9]:count=1
    if gn==158 and serial==26:count=4
    if gn==160 and serial in [4,5]:count=4
    if gn==160 and serial==6:count=3
    for pos in (range(1,count+1) if count else [0]):positions.append(dict(position_id='POS-'+a['id'][3:]+f'-{pos}',group_ref=groups[gn]['group_ref'],folder_id=a['folder_id'],file_id=a['id'],file_path=a['path'],position=pos or 'Segmentation unresolved',depicted_count=count or 'Unknown; segmented study',identity='Unresolved fingerprint media position; may repeat another design',physical_count='Not certified; excluded from distinct component count',needed='Geometry deduplication and maker approval; generated/edited study status needs confirmation'))

# Project-specific assertions remain whole-work claims.
for key in ['LUCIANO-1','LUCIANO-2','LUCIANO-3']:
    addclaim(key,'Whole screen size / material','215 × 180 cm overall; 3-part wall sculpture screen; fibrous cement and silver sand surface texture; January 2006','Whole Luciano Chelsea commission; not an individual panel measurement','MAKER PROJECT SOURCE','luciano-garden:p1')
for key in ['PORTMAN-1','PORTMAN-2']:addclaim(key,'Project finish','Bronze effect in exact Portman project photographs; portfolio also lists copper, silver pewter and white marble for the project range','This courtyard pair; not proof of each finish in each panel','MAKER PROJECT / ARCHIVE MATCH','portman-project:p1; archive:case1')
for key in ['AM-1','AM-2','MSW-MOON','MSW-SPIRAL','WBMS-WAVE','WBMS-MOON','MS-1','MS-2']:
    value='Large Ammonite 120×120 cm overall, not each panel' if key.startswith('AM-') else ('Shellwave between Moons: three panels each 100×22 cm' if key.startswith('MSW-') else ('Wave and Moonshadow: three pieces each 40×40 cm' if key.startswith('WBMS-') else 'Two Moonspirals each 70×50 cm'))
    addclaim(key,'Royal Yacht commission dimensions',value,'Named hotel commission; whole/set figures retain their original scope','MAKER PROJECT SOURCE','royal-yacht:p1')
for key in ['MP-1','MP-2','MP-3','MP-4','MP-5','AM-1','AM-2','BONE-1','BONE-2','DDR-WAVE','DDR-SPIRAL','DR-WAVE1','DR-WAVE3','DR-SPIRAL']:
    if key.startswith('MP-'):value='Each Moonphase 30×30 cm, 5.5 kg';page='Moonphase'
    elif key.startswith('AM-'):value='Each small Ammonite part 50×25 cm, 5.5 kg';page='Ammonite'
    elif key.startswith('BONE-'):value='Narrow panel 55×30 cm, 8.5 kg' if key=='BONE-1' else 'Wide panel 55×55 cm, 15 kg';page='Bone Spiral'
    else:value='Long panel 100×22 cm, 10 kg each' if key.startswith('DDR-') else 'Small panel 35×20 cm, 4.5 kg each';page='Deco Dune'
    addclaim(key,'Additional brochure dimension/version evidence',value,'Brochure source version; not a replacement for conflicting native or manufacturing values','DATED BROCHURE SOURCE; SCOPE / VERSION VARIES','brochure-upper:'+page+' page')

for c in components.values():
    c['offer_refs']=list(dict.fromkeys(c['offer_refs']));c['configuration_count']=sum(x['component_id']==c['component_id'] for x in configs)
    missing=[]
    if c['dimensions_available'].startswith('No '):missing.append('Component dimensions and depth')
    elif any(w in c['dimensions_available'] for w in ['conflict','versus','version','differs','unverified','unmeasured','require']):missing.append('Resolve size/version/depth applicability')
    if c['weight_available'].startswith('No '):missing.append('Individual weight')
    elif 'calculated'in c['weight_available'] or 'conflict'in c['weight_available']:missing.append('Confirm current cast weight / material against historic estimate')
    if c['material_available'].startswith(('No ','Historical')):missing.append('Object/finish-specific material')
    if c['fixing_available'].startswith('See '):missing.append('Component fixing detail')
    if not c['standalone_offer_refs']:missing.append('Current individual price and sale/availability decision')
    missing.append('Cast/finish applicability and specification conflicts require final maker review')
    c['missing_specification_fields']='; '.join(missing)
    c['folder_ids']='\n'.join(groups[int(g[1:])]['id'] for g in c['group_refs']);c['example_file_ids']='\n'.join(dict.fromkeys(fid for gr in c['group_refs'] for fid in groups[int(gr[1:])]['selected']))

work_components=[c for c in components.values() if not c['identity_status'].startswith(('Source-only','Concept'))]
counts=dict(families=63,groups=350,files=6656,platform_pairs=37,squarespace_only=43,shopify_only=1,components_in_working_register=len(work_components),standard_design_records=sum(c['identity_status']=='Documented or visually distinct design' for c in work_components),visual_identity_proposals=sum(c['identity_status'].startswith('Visual') for c in work_components),bespoke_position_records=sum(c['identity_status'].startswith('Bespoke') for c in work_components),source_only_options=sum(c['identity_status'].startswith('Source-only') for c in components.values()),concept_families=sum(c['identity_status'].startswith('Concept') for c in components.values()),component_finish_groups=len(configs),components_without_individual_offer=sum(not c['standalone_offer_refs'] for c in work_components),components_with_an_individual_offer=sum(bool(c['standalone_offer_refs']) for c in work_components),component_finish_groups_without_context=sum(x['in_situ']=='No context image identified' for x in configs if x['component_id']!='BC-WALL-CIRCLE' and x['component_id']!='BC-FFL-1'),component_finish_groups_without_series=sum(x['series']=='No arrangement image identified' for x in configs if x['component_id']!='BC-WALL-CIRCLE' and x['component_id']!='BC-FFL-1'),fully_physically_verified=0,public_pages_read=sum(o['page_status']=='READ' for o in offers),public_pages_unavailable=sum(o['page_status']!='READ' for o in offers),unresolved_media_position_records=len(positions),unresolved_group_work_items=len(unresolved),specification_claims=len(claims),inference_records=len(inferences))
model=dict(created_utc=datetime.now(timezone.utc).isoformat(),scope=e['inventory_finished_utc'],source_sha256=hashlib.sha256(Path('/Users/tprice/Documents/boldstone/Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx').read_bytes()).hexdigest(),counts=counts,components=list(components.values()),configurations=configs,platform_records=platform,bom=bom,groups=list(groups.values()),assets=e['assets'],claims=claims,inferences=inferences,aliases=aliases,unresolved=unresolved,unresolved_positions=positions,mixed_bindings=mixed_bindings,document_sources=e['document_sources'],historical=comparison['historical'],limitations=['Working catalogue records are not a count of physical inventory or certified distinct moulds. Bespoke positional records and visual proposals may repeat other designs.','All 350 groups had representative visual review; 74 groups additionally have retained earlier complete reviews. All 6656 asset IDs are indexed, not all freshly classified at component level.','One row per depicted finish group is not an independent SKU/stock item. Multiple sizes, native variants, rotations and repeated casts remain separate relationships.','Source-only FFL1 and Wall Circle concept options are outside the working sculpture count. Unresolved Fingerprint/cropped/mixed background media remain a visible queue; no final complete physical count is claimed.','Weight, chemistry, engineering capacity, exact depth, individual price and stock cannot be established from unscaled images. Proposed values must be approved/measured before publication.'])
from apply_catalogue_updates import apply_updates
model=apply_updates(model,root)
(ev/'component_register.json').write_text(json.dumps(model,ensure_ascii=False));print(json.dumps(model['counts'],indent=2))
