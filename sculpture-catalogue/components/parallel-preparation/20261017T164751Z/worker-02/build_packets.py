"""Build advisory worker-02 packets from immutable source snapshots and viewed images."""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import hashlib, json
ROOT=Path(__file__).resolve().parent
A=json.load(open(ROOT/'assignment.json'))
SOURCES=Path('/Users/tprice/Library/Application Support/BoldstoneImageConsistency/product-evidence-resolution-20261016T201618Z')
PRICE=Path('/Users/tprice/Documents/boldstone/sculpture-catalogue/components/evidence/price-source-review-2026-10-17')
ASSETS={r['id']:r for r in A['assets']}
GROUPS={r['group_ref']:r for r in A['groups']}
OFFERS={r['offer_ref']:r for r in A['platform_records']}
MAKER={r['row']:r for r in json.load(open(SOURCES/'Manufacturing_Sheet_Extract.json'))}
TRADE=json.load(open(PRICE/'trade_price_rows.json'))
REFS=json.load(open(SOURCES/'Manufacturing_Labelled_References.json'))
CLAIMS={c['component_id']:[r for r in A['claims'] if r['component_id']==c['component_id']] for c in A['components']}

# Indexes are fixed local snapshots. All selected images were actually viewed in the saved contact sheets.
def fid(gr, idx=0):return GROUPS[gr]['selected'][idx]
PRIMARY={
 'BC-FFS-2':fid('G169'), 'BC-FFS-3':None,
 'BC-KNIGHT':None,
 'BC-LEAF-CURVE':fid('G181'), 'BC-LEAF-FORM':fid('G185'), 'BC-LEAF-GROWTH':fid('G190'),
 'BC-MSW-MOON':fid('G198'), 'BC-MSW-SPIRAL':fid('G202',1),
 'BC-MCP-1':fid('G209',1),'BC-MCP-2':fid('G212',1),'BC-MCP-3':fid('G214',1),'BC-MCP-4':fid('G219'),
 'BC-CRATER-WIDE':fid('G225'), 'BC-MFW-1':fid('G226'),'BC-MFW-2':fid('G227'),
 'BC-MOON-RING':fid('G230'),'BC-MOON-CRATER':'id:cnqzTNngPVsAAAAAAAuV1w',
 'BC-MP-1':'id:cnqzTNngPVsAAAAAAAylaA','BC-MP-2':fid('G237'),'BC-MP-3':fid('G239'),'BC-MP-4':fid('G242'),
 'BC-MP-5':'id:cnqzTNngPVsAAAAAAAylaQ',
 'BC-LAVA-CORNER':fid('G259',1),'BC-MLAVA-1':fid('G260'),'BC-MLAVA-2':fid('G261')}
for c in A['components']:PRIMARY.setdefault(c['component_id'],None)

# Explicit visual observations of the viewed representative assets. Missing keys mean association only.
CROPS={fid(g) for g in ['G170','G176','G191','G209','G212','G214','G218']}
CROPS.add(fid('G172'))
VISUAL={
 'BC-FFS-2':'Complete tall, narrow white panel; repeated tapered fish-like ribs; all outer edges visible. Matches the FFS2 solo maker reference.',
 'BC-FFS-3':'The complete G172 triptych reference shows the right panel, but no isolated complete FFS3 front is established. Use third position only; do not crop the set into a new source asset.',
 'BC-KNIGHT':'The sole solo-folder image is a tight spiral/outlet detail. G177 process/installation images show a square, thick, ground-set fountain block with a spiral upper surface; this is not established as a wall-hanging panel.',
 'BC-LEAF-CURVE':'Complete approximately square panel on a brick wall, with two sweeping leaf/eye-like arcs and mottled pale/gold-looking surface. Scale and leaf chemistry are unproved.',
 'BC-LEAF-FORM':'Complete square white leaf relief. Maker row34 explicitly states one mould used in opposite directions as LF1/LF2; the paired positions are not two proved distinct moulds.',
 'BC-LEAF-GROWTH':'Complete tall white botanical panel with branching curved leaves; the bottom and top edges are visible. Gold-looking examples are close detail views, not a complete gold-variant front.',
 'BC-MSW-MOON':'Complete narrow white Half Moon panel. Maker row83 explicitly states MSW1 is turned upside down to form MSW3; preserve the hanging orientation and fixing position.',
 'BC-MSW-SPIRAL':'Complete narrow white Shellwave panel, front view with nested flowing arcs and spiral. Source MSW2 is distinct from the Half Moon mould.',
 'BC-MCP-1':'Complete square white crater-phase front selected instead of the first white crop; source MCP1 comparison remains a proposed source crosswalk.',
 'BC-MCP-2':'Complete square white panel with raised circular central form and surrounding ring. The blue-splash and verdigris images are separate finish examples.',
 'BC-MCP-3':'Complete square white panel with raised central sphere/circle and broad ring, compared to labelled MCP3; preserve its difference from MCP2.',
 'BC-MCP-4':'Complete white square concave crater/bowl relief. Silver and verdigris examples remain separate surface variants, with no shared formulation implied.',
 'BC-CRATER-WIDE':'Complete rust-looking square bowl relief with a rough, broad lip. A formal Moon Crater Phase alias is not established.',
 'BC-MFW-1':'Complete white left panel, broad upper arc and multiple fish/rays; source pair row95 names MFW1 on the left.',
 'BC-MFW-2':'Complete white right panel, broad upper arc, fish/rays and lower spiral; source pair row95 names MFW2 on the right.',
 'BC-MOON-RING':'Complete approximately square crescent/ring relief fixed to a timber background. Do not merge with the similarly named Moon Crater Phase or Moonphase moulds.',
 'BC-MOON-CRATER':'Complete freestanding square basin seen obliquely, with a deep circular hollow. Water in a photograph does not establish a tested waterproof specification or wall fixing.',
 'BC-MP-1':'Complete single plain-moon panel selected from mixed G244. Arc orientation was compared with labelled manufacturing MP1 and the five-member source row3; folder number 4 alone is insufficient.',
 'BC-MP-2':'Complete white curl panel; manufacturing MP2 corresponds to Dropbox Moonphase 1. Bordered versions are separate outer treatments.',
 'BC-MP-3':'Complete white nested-spiral panel; manufacturing MP3 corresponds to Dropbox Moonphase 2. Bordered and gold-looking surface versions need separate dimensions/material records.',
 'BC-MP-4':'Complete broad-spiral white panel; manufacturing MP4 corresponds to Dropbox Moonphase 3.',
 'BC-MP-5':'Complete single opposite plain-moon panel selected from G244 after source-diagram comparison. Manufacturing MP1 and MP5 are explicitly different moulds in row3; do not merge merely because rotation can look similar.',
 'BC-LAVA-CORNER':'Complete pale square corner-curve panel selected instead of the more distant timber-wall view. Coarse upper texture and smoother lower relief are visible.',
 'BC-MLAVA-1':'Complete pale approximately square spiral panel, coarse crescent texture on the upper/outer arc, smoother inner curl.',
 'BC-MLAVA-2':'Complete pale panel with left spiral/crescent, coarse upper-left texture and broad smooth sweeping arc; distinct visible form from standalone member1.'}
for n,pos in enumerate(['top left','top right','bottom left','bottom right'],1):
 VISUAL[f'BC-GLEN-{n}']=f'Four-panel square composition in G174; target is {pos} position. Fruit/leaf motifs and curved circular arcs are visible. Position does not prove a unique mould; no isolated front for this position was recovered.'
for n,pos in enumerate(['left','centre','right'],1):
 VISUAL[f'BC-LAVA-{n}']=f'Three joined tall panels form one large spiral/rounded relief. Target is the {pos} panel position in G178/G180. All three are context/series evidence; no standalone mould identity is established.'
for n,pos in enumerate(['left','right'],1):
 VISUAL[f'BC-MLAVA-WALL-{n}']=f'The {pos} position in a pale two-panel outdoor brick-wall composition. It resembles the standalone Moonshell Lava family, but exact member/mould equivalence is not established by these photos.'

# Numeric values below are intentionally proposals, not measurements. Broad ranges are owner discussion prompts.
GUESSES={
 'BC-LEAF-CURVE':('about 35 × 35 × 5–7 cm (working envelope; 30–40 cm square plausible)','about 5–8 kg if made as a 35 cm square AC730-like cast','white stone-effect composite with gold-looking leaf accents; AC730 and genuine metal leaf are hypotheses','single inset stainless keyhole, following 35 cm square template; rear position must be checked','GBP 300–450 for one accented panel (working retail proposal)'),
 'BC-CRATER-WIDE':('about 25 × 25 × 4–7 cm, by analogy with the smaller crater family; could be another size','about 2–5 kg only if the proposed small composite version is right','cast composite with rust/iron-effect surface; binder and actual metal content open','single inset stainless keyhole as a small-panel proposal','GBP 250–350 for the shown rust-effect individual (working retail proposal)'),
 'BC-MOON-RING':('about 30 × 30 × 5–7 cm; 25–40 cm square remains plausible','about 3–6 kg for a small cast-composite version','white stone-effect composite; AC730 is a candidate, not an identified substrate','single inset stainless keyhole as a small-panel proposal','GBP 200–300 for one white panel (working retail proposal)'),
 'BC-MOON-CRATER':('about 45–60 cm square × 10–18 cm overall height/depth (low-confidence basin envelope)','about 10–20 kg only for a hollow/lightweight cast-composite basin; solid construction could differ greatly','white/light stone-effect cementitious or Jesmonite composite; exact binder and water-contact system open','freestanding basin on a designed level support; wall keyhole is not proposed','GBP 450–750 for the basin only (working quotation range; pump/plumbing/site work excluded)'),
 'BC-LAVA-CORNER':('about 50 × 50 × 5–8 cm (working envelope; compare 40–55 cm square reliefs)','about 8–15 kg if a lightweight composite panel at the proposed envelope','pale stone-effect cast composite with coarse aggregate texture; binder open','two rear stainless fixings as a larger-panel hypothesis; source drawing needed','GBP 400–600 for one textured panel (working retail proposal)'),
 'BC-MLAVA-1':('about 55 × 55 × 5–8 cm (working envelope; not a measurement)','about 8–16 kg if a lightweight composite at the proposed envelope','pale stone-effect cast composite with coarse aggregate texture; binder open','two rear stainless fixings as a larger-panel hypothesis; source drawing needed','GBP 450–650 for one textured panel (working retail proposal)'),
 'BC-MLAVA-2':('about 55 × 55 × 5–8 cm (working envelope; not a measurement)','about 8–16 kg if a lightweight composite at the proposed envelope','pale stone-effect cast composite with coarse aggregate texture; binder open','two rear stainless fixings as a larger-panel hypothesis; source drawing needed','GBP 450–650 for one textured panel (working retail proposal)')}
for n in range(1,5):GUESSES[f'BC-GLEN-{n}']=('nominal 40 × 40 × 5–7 cm for this position; a 35–45 cm square panel is a low-confidence size analogy','about 6–10 kg per panel only if the proposed 40 cm composite version is right','pale/white cast stone-effect composite; AC730 is a working candidate only','one or two concealed stainless fixings per panel; exact count/spacing must come from a rear drawing','GBP 300–500 per position as a reproduction budget idea; original commission price is unknown')
for n in range(1,4):GUESSES[f'BC-LAVA-{n}']=('nominal envelope about 100 × 25 × 5–8 cm per tall panel; absolute scale uncalibrated and outer curved edge varies','about 8–14 kg per panel if a lightweight composite at the proposed envelope','cast stone-effect composite, pale/sandstone-looking variants; binder and pigment open','two concealed rear stainless fixings per tall panel as a working design idea','GBP 400–700 per panel as a bespoke reproduction budget idea; no sourced individual sale price')
for n in range(1,3):GUESSES[f'BC-MLAVA-WALL-{n}']=('about 50–60 cm square × 5–8 cm per position, by family analogy only','about 8–16 kg per position if the proposed lightweight-composite size is right','pale cast stone-effect textured composite; do not apply Luciano fibrous-cement specification','two concealed rear stainless fixings per panel as a working idea','GBP 450–650 per panel as an enquiry budget; no standalone offer confirmed')
GUESSES['BC-KNIGHT']=('No defensible numeric specification from the solo crop; project/process context suggests a thick, square freestanding fountain block. Obtain the project drawing.','No useful numeric mass guess: hollow/solid construction and block depth are unknown. Obtain a separate weight.','white/light cementitious or Jesmonite-type composite is a hypothesis; waterproofing and internal construction open','freestanding fountain block with project-specific support and plumbing; no wall-hanging fixing proposed','quotation-only; a provisional GBP 600–1,200 relief/block budget could start discussion, excluding reservoir, pump, plumbing and installation')

NAMES={
 'BC-LEAF-FORM':'Leaf Form — square standard (LF1/LF2 orientations)',
 'BC-MSW-MOON':'Half Moon — Moon & Shellwave (MSW1; MSW3 rotated)',
 'BC-MOON-CRATER':'Mooncrater basin — freestanding water-feature form',
 'BC-KNIGHT':'Knightsbridge spiral fountain block — project version'}

# Other composition rows provide the authoritative reuse context omitted from single-position row excerpts.
EXTRA_ROWS={'BC-LEAF-FORM':[34], 'BC-MSW-MOON':[82,83], 'BC-MSW-SPIRAL':[82,83]}
for n in range(1,6):EXTRA_ROWS[f'BC-MP-{n}']=[3]

RETAIL_NEW={
 'Frozen Fish':{'price':262.50,'weight':'6 kg each','page':2,'size':'70 × 15 cm'},
 'Leaf Form':{'price':306.25,'weight':'7 kg each','page':1,'size':'35 × 35 cm'},
 'Leaf Growth':{'price':750.00,'weight':'12 kg each','page':2,'size':'100 × 30 cm'},
 'Moon & Shellwave':{'price':550.00,'weight':'10 kg each','page':2,'size':'100 × 22 cm'},
 'Moon Crater Phase':{'price':156.25,'weight':'5 kg each','page':1,'size':'25 × 25 cm'},
 'Moonphases':{'price':225.00,'weight':'6.5 kg each','page':1,'size':'30 × 30 cm'}}
TRADE_SECTIONS={'Frozen Fish':'Frozen Fish Series','Leaf Form':'Deco Leaf Form','Leaf Growth':'Leaf Growth Series','Moon & Shellwave':'Moon & Shellwave Series','Moon Crater Phase':'Moon Crater Phases Series','Moonphases':'Moonphases Series','Moon Fishwave':'Moon Fishwave'}

def relevant_trade(c):
 rows=[r for r in TRADE if r['section']==TRADE_SECTIONS.get(c['family'],'')]
 if c['component_id']=='BC-FFS-2': members=['2']
 elif c['component_id']=='BC-FFS-3':members=['3']
 elif c['component_id']=='BC-MSW-MOON':members=['1','3']
 elif c['component_id']=='BC-MSW-SPIRAL':members=['2']
 elif c['component_id'].startswith(('BC-MCP-','BC-MP-')):members=[c['component_id'].split('-')[-1]]
 elif c['component_id']=='BC-LEAF-FORM':members=['1','2']
 else:members=['']
 return [r for r in rows if r['scope']=='whole arrangement' or r['member_label'] in members]

def t_ref(r):return f"{r['source_id']}:p{r['page']}:table{r['table']}:row{r['table_row']}"
def unique(x):return list(dict.fromkeys(x))

def classify_claim(r):
 f=r['field'].lower()
 if any(w in f for w in ['material','finish','suitability']):return 'material_finish'
 if 'weight' in f or 'grams' in f:return 'weight'
 if any(w in f for w in ['fixing','mounting']):return 'fixing'
 if any(w in f for w in ['dimensions','length','width','height','component (cm)','overall (cm)']):return 'dimensions'
 if any(w in f for w in ['price','sale']):return 'individual_price'
 if any(w in f for w in ['stock','inventory','published','status','visible']):return 'availability'
 return None

def source_claim(r):
 return {'claim_id':r.get('claim_id'),'field':r['field'],'value':r['value'],'unit':r.get('unit'),'scope':r.get('scope'),'source_ref':r['source_ref'],'source_status':r.get('status'),'observation_basis':'Immutable catalogue source snapshot copied 2026-10-17; underlying document/public-page date is retained in source_ref/status. Not live reverified by worker02.'}

def spec(display,proposal,state,refs,limits=None,claims=None):
 return {'display':display,'proposal':proposal,'evidence_state':state,'basis_refs':unique(refs),'requires_owner_check':True,'limits':limits or ['Proposal for owner discussion, not a physical measurement or approved catalogue fact.'],'sourced_claims':claims or []}


def image_record(file_id,reason,complete=None):
 a=ASSETS[file_id];g=next(g for g in A['groups'] if g['id']==a['folder_id'])
 return {'file_id':file_id,'folder_id':a['folder_id'],'preview_path':a['thumb'],'shows_complete_single_component':bool(complete if complete is not None else g['role']=='Single component image' and file_id not in CROPS),'selection_reason':reason,'group_ref':g['group_ref'],'group_name':g['name'],'source_role':g['role'],'image_observation':'Locally cached thumbnail visually inspected, with group/source comparisons; no live Dropbox read.','scene_provenance':'Library/source association only; no new installation/client authentication.','content_hash_snapshot':a.get('content_hash')}

ENTRIES=[]
for c in A['components']:
 cid=c['component_id'];cl=CLAIMS[cid];groups=[GROUPS[x] for x in c['group_refs']];file=PRIMARY[cid]
 frefs=[f"component_register:{cid}"]
 rows=unique(c.get('maker_rows',[])+EXTRA_ROWS.get(cid,[]))
 mrefs=[f'manufacture-stevensons:Sheet1!row{n}' for n in rows]
 reviewrefs=[f'group:{g["group_ref"]}' for g in groups]
 dims=c['dimensions_available'];weight=c['weight_available'];material=c['material_available'];fixing=c['fixing_available']
 fieldclaims={k:[source_claim(r) for r in cl if classify_claim(r)==k] for k in ['dimensions','weight','material_finish','fixing','individual_price','availability']}
 refs={k:[r['source_ref'] for r in cl if classify_claim(r)==k] for k in fieldclaims}
 dt=[r for r in relevant_trade(c) if r['scope']=='individual piece']
 at=[r for r in relevant_trade(c) if r['scope']=='whole arrangement']
 nr=RETAIL_NEW.get(c['family'])
 pricefacts=[]
 if c.get('current_individual_prices'):pricefacts.append('Cached public/native individual offers: '+c['current_individual_prices']+' (dated catalogue source, not live rechecked)')
 if c.get('historic_individual_price'):pricefacts.append('Prior dated estimate: '+c['historic_individual_price'])
 if dt:
  dvals=unique([f"GBP {r['prices']['GBP']:.2f}; estimated {r['estimated_weight_kg_cell']}" for r in dt])
  pricefacts.append('Supplied printed 2025 trade draft, per-piece row(s): '+' / '.join(dvals))
  refs['individual_price'] += [t_ref(r) for r in dt]
  refs['weight'] += [t_ref(r) for r in dt]
  refs['dimensions'] += [t_ref(r) for r in dt]
 if nr:
  ref=f"draft-retail-2025-named:p{nr['page']}:table-size-{nr['size']}"
  pricefacts.append(f"Supplied named Retail draft: GBP {nr['price']:.2f} per standard white piece; {nr['weight']} estimated (2025 in filename, no printed year on table)")
  for k in ['dimensions','weight','individual_price']:refs[k].append(ref)
  refs['availability'].append('draft-retail-2025-named:p3:conditions')
  weight += f"; named Retail draft {nr['weight']}; dated variants, not measured"
 if dt:weight+='; printed 2025 trade '+ '/'.join(unique(r['estimated_weight_kg_cell'] for r in dt))+' estimated each'
 price_display='; '.join(pricefacts) if pricefacts else 'No sourced current individual selling price.'
 conflicts=[];missing=[];handoff=[]
 # Default proposals retain the most useful measured-size template without turning it into a measurement.
 if c.get('maker_rows'):
  dimprop='Use the maker per-component size/depth as the provisional standard-white template; confirm actual cast/finish and measure depth before publication.'
  wprop='Use the maker calculated each-piece range only as a historical AC730 planning estimate; keep the dated draft estimates alongside it and weigh the actual cast.'
  matprop='Historical white-standard hypothesis: Jesmonite AC730 with white marble stone finish. Link any gypsum/plaster, coloured, metal-effect or bordered version separately.'
  fixprop='Carry forward the historical maker fixing instruction for the standard orientation, then confirm the actual rear hardware and its position.'
 else:
  dimprop='Obtain the component drawing or measure the actual object.';wprop='Weigh the individual object; no set total has been divided.'
  matprop='White stone-effect cast composite is a working material description; exact substrate requires the production card.';fixprop='Obtain a rear photograph or fixing drawing for this individual object.'
 if cid=='BC-LEAF-GROWTH':
  dimprop='Use 100 × 30 × 6 cm as the provisional native single-item size, subject to cast confirmation.'
  wprop='Use 12–18 kg only as a working discrepancy range: draft estimate 12 kg versus native single-item claim 18 kg; weigh the cast.'
  matprop='Working binder hypothesis: AC730-like stone composite with white marble stone finish; binder itself is not established by the offer text.'
  fixprop='Working hypothesis: two concealed stainless rear fixings for a tall 100 × 30 cm panel; actual hardware/spacing unrecorded.'
 if cid in GUESSES:
  gg=GUESSES[cid];dimprop='WORKING GUESS: '+gg[0];wprop='WORKING GUESS: '+gg[1];matprop='WORKING GUESS: '+gg[2];fixprop='WORKING GUESS: '+gg[3]
  priceprop='WORKING GUESS: '+gg[4]+'. Confirm manufacturing availability and present pricing with the owner.'
  missing.extend(['Component dimensions/depth not sourced','Individual measured mass','Object-specific substrate/coating record','Individual rear/fixing record','Present price and sale policy'])
 else:
  if c.get('current_individual_prices'):
   priceprop='Retain the separate cached offer/finish prices for review; owner chooses the current price for the exact version. Do not replace a listed offer with a historical trade/retail estimate.'
  elif nr:priceprop=f"WORKING PRICE PROPOSAL: GBP {nr['price']:.2f} per standard white component, using the supplied named Retail draft as the discussion starting point; this is not a confirmed current selling price."
  elif cid.startswith('BC-MFW-'):
   priceprop='WORKING PRICE PROPOSAL: GBP 450–600 per white panel. No sourced standalone price; pair prices are comparison context, not source values for this panel.'
  else:priceprop='Price by owner quotation; no sourced standalone value.'
 # Scope of availability is never a stock verification.
 one_offers=[OFFERS[o] for o in c.get('standalone_offer_refs',[]) if o in OFFERS]
 offer_states=[f"{o['offer_ref']}: cached public {o.get('public_availability','unrecorded')}, export stock {o.get('stock','unrecorded')}" for o in one_offers]
 avdisplay=('; '.join(offer_states)+'. ' if offer_states else 'No standalone stock/availability record. ')
 if nr or dt:avdisplay+='Dated price-list conditions describe standard white work as made to order; present production capacity not checked.'
 else:avdisplay+='Historical image/commission presence is not present stock.'
 avprop='WORKING POLICY PROPOSAL: made to order / enquiry before purchase; actual mould condition, lead time and stock require owner confirmation.'
 if cid in GUESSES or 'Bespoke' in c['identity_status']:avprop='WORKING POLICY PROPOSAL: enquiry-only / bespoke reproduction subject to maker confirmation; no stock quantity or orderable status proposed.'
 if cid=='BC-MOON-CRATER':avprop='WORKING POLICY PROPOSAL: enquiry-only basin/water-feature commission; confirm product category, manufacture and water-contact system before offering.'
 # Dated references make disagreements reviewable instead of silently replacing numbers.
 if nr:
  conflicts.append('Prior retail-2025 estimate and supplied named Retail draft have different per-piece price/weight versions; both retained. Trade is a separate tier, not a current retail contradiction.')
 if c.get('maker_rows'):
  conflicts.append('Maker mass is an approximate AC730 calculation; dated draft weights and native exports can describe other formulations/versions. No physical weighing was verified.')
 if one_offers:
  conflicts.append('Cached InStock/Unlimited or quantity-one fields describe platform configuration, not physical stock or current manufacture.')
 if cid=='BC-FFS-2':
  conflicts += ['Terracotta O049 GBP44.44 and verdigris O063 GBP180 are distinct cached finish offers; do not merge prices or infer identical formulation.', 'O049 shared/reused reverse image is not proof of the exact photographed specimen; O063 raw zero weight is unfilled data, not zero physical mass.']
  handoff += ['Review white standard against FFS2 first, then handle terracotta and verdigris as separate material/price variants. Do not apply small 70×15 specifications to Frozen Fish Long 100×22.']
 if cid=='BC-FFS-3':
  conflicts += ['Maker row71 product code reads FFS32 but its written mould order is FFS2 then FFS3; use the labelled diagram, not code digit order alone.', 'SH-DRAFT is a photographed white triptych with blank SKU/description and zero/unfilled price/weight, not an approved sale listing.']
  missing += ['Isolated complete FFS3 front and exact individual image assignment']
  handoff += ['Use complete triptych G172 second selected image for right-position discussion only; do not let the crop selected first in that group stand in for the full component.']
 if cid.startswith('BC-GLEN-'):
  conflicts += ['Four catalogue records are installed positions; mould repetition/rotation is unconfirmed.', 'The library Gleneagles family label does not authenticate the scene location. The separately captioned Gleneagles restaurant source in case5 concerns other mixed works and is not silently applied to this Vine/Tendril set.']
  missing += ['Maker four-position/mould diagram','Isolated complete front for this position','Direct project/source caption for the selected scene']
 if cid.startswith('BC-LAVA-') and cid!='BC-LAVA-CORNER':
  conflicts += ['Left/centre/right are visible joined-panel positions, not certified distinct moulds. Sandstone-looking and white surfaces do not identify the binder or actual stone.', 'Absolute component size and mass cannot be allocated from the complete three-panel photograph.']
  missing += ['Panel seam/mould diagram and original commission dimensions','Isolated complete front for this panel']
 if cid=='BC-KNIGHT':
  conflicts += ['Solo-folder representative is a close crop; the complete project views depict a ground-set fountain block, not a ready-to-hang wall sculpture.', 'Named Knightsbridge project text establishes a courtyard water-feature/wall-sculpture commission, but supplies no object-specific material, numeric dimension, mass or fixing record.']
  missing += ['Isolated product view of the complete fountain block','Project drawing, internal construction, water system and present product category']
  frefs+=['knightsbridge-project:p1']
 if cid=='BC-LEAF-FORM':
  conflicts += ['35×35 cm square maker/pair source versus O058 40×20 cm single-offer text/SKU; image correspondence alone does not choose the correct size.', 'Maker row34 explicitly says one mould in opposite directions A/B; LF1/LF2 single rows are position records, not proof of separate moulds.']
  missing += ['Correct the 40×20 versus 35×35 version/offer association','Orientation-specific fixing/back photograph']
  handoff += ['Keep one working design with opposite orientations unless owner evidence requires another version; do not create an extra mould solely from LF2 numbering.']
 if cid=='BC-LEAF-GROWTH':
  conflicts += ['Native single-item claim 18 kg differs from both dated draft estimates 12 kg; preserve rather than averaging.', 'White marble stone finish is source wording; it does not by itself establish the binder.']
  missing += ['Exact binder for the white/gold variants','Complete gold-variant front if that finish is to be offered','Actual rear fixing record']
 if cid=='BC-MSW-MOON':
  conflicts += ['Maker row83 explicitly states MSW1 upside down forms MSW3. Keep the two arrangement positions/orientations without counting another physical mould.', 'O021/O032/O033 are pair/triptych arrangement prices and weights, not standalone Half Moon values.']
  handoff += ['Use the source MSW1/MSW3 orientation convention; rear fixing position must follow the approved hanging orientation. Black/white scene-study variants do not certify an additional manufactured substrate or stock.']
 if cid=='BC-MSW-SPIRAL':conflicts+=['O032/O033 prices/weights belong to whole arrangements; no standalone price or mass is derived by division.']
 if cid.startswith('BC-MCP-'):
  conflicts += ['Native Squarespace numeric dimensions/weights lack encoded units; do not silently read 9.8 as centimetres or 8.8 as kilograms.', 'White standard 25×25 cm and 4–6 cm side depth cannot be generalized to an unmeasured coloured edition or a room mock-up scale.']
  if cid in ['BC-MCP-1','BC-MCP-4']:missing += ['Exact exported specimen/file link for '+('O007' if cid.endswith('1') else 'O006')+'; design-level mapping remains provisional']
  if cid=='BC-MCP-2':conflicts+=['O008 title says Blue, but confirmed linked image is in the verdigris/rust group; reconcile gallery/title/finish before applying offer details to a cast.']
 if cid=='BC-CRATER-WIDE':missing+=['Formal product alias and relationship to MCP moulds']
 if cid.startswith('BC-MFW-'):
  # The supplied table explicitly labels estimates each part; no price is allocated.
  weight+='; printed trade2025 Moon Fishwave table: estimated 12 kg each part; named Retail draft shared Bone Spiral/Moon Fishwave row: 12–15 kg each part (version scope to confirm)'
  refs['weight']+=['draft-trade-2025:p13:table1:row10','draft-retail-2025-named:p3:Moon Fishwave row']
  price_display+=' Context only: cached O043 GBP800 per pair; supplied trade draft GBP584 per pair; named Retail draft GBP1168.75 per pair. No source individual price.'
  refs['individual_price']+=['draft-trade-2025:p13:table1:row10','draft-retail-2025-named:p3:Moon Fishwave row']
  conflicts+=['Maker 8–10 kg each, trade estimated 12 kg each part, named Retail draft shared row 12–15 kg each part, and native 30 kg set claim are distinct unweighed version claims; do not divide the set total.', 'Pair overall width 84 cm in native catalogue versus 85 cm in printed drafts may reflect wall gap/rounding; the stated each-panel width remains 42 cm.', 'GBP800, GBP584 and GBP1168.75 are whole-pair prices. The working per-panel price is a proposal, not a source split.']
  missing+=['Current standalone price/variant and cast-specific mass','Exact fixing size/spacing for the two-fixing maker instruction']
 if cid.startswith('BC-MP-'):
  conflicts += ['Manufacturing MP numbers differ from Dropbox folder numbers; preserve the labelled source crosswalk.', 'Standard maker white AC730 specification, dated draft estimates and plaster-offer descriptions are formulation/version claims; identical-looking fronts do not establish identical chemistry.']
  if cid in ['BC-MP-2','BC-MP-3','BC-MP-4']:
   conflicts += ['O010 says each but gallery contains three phases; sale quantity is unresolved. Its GBP150 is not silently assigned to all three panels.']
  if cid in ['BC-MP-1','BC-MP-5']:
   conflicts += ['Maker row3 expressly lists five different moulds including MP1 and MP5; G244 contains both plain-moon directions. Folder title Moonphase4 cannot merge them.']
  if cid in ['BC-MP-2','BC-MP-3']:missing+=['Outer dimensions/depth, mass and substrate of the bordered version; do not inherit unbordered values']
  if cid=='BC-MP-5':
   conflicts += ['O070 silver offer says about8 kg and30×30×7 cm; that claim is separate from3–5 kg white AC730 template and dated5.5/6.5 kg draft estimates.', 'O070 exact image link is confirmed, but MP1/MP5 orientation identity of the silver specimen remains a source-crosswalk question.']
   missing += ['Maker confirmation of O070 silver plain-moon orientation/mould']
 if cid.startswith('BC-MLAVA-WALL-'):
  conflicts += ['Two wall positions are not yet proved identical to standalone Moonshell Lava1/2; visual resemblance is a candidate only.', 'Luciano is a separate three-part commission; its fibrous-cement material and2.15×1.80 m overall size are not applied here.']
  frefs+=['portfolio-interior-exterior:p1','archive:case51','prior-visual:case51']
  missing+=['Individual mould/source crosswalk and complete isolated front','Product/production record for this two-panel version','Named project locator if required; Brentford filename alone does not authenticate it']
 if cid in ['BC-MLAVA-1','BC-MLAVA-2','BC-LAVA-CORNER']:conflicts+=['Do not apply the separately documented Luciano fibrous-cement commission material or overall dimensions to this standalone version.']
 if cid=='BC-MOON-CRATER':missing+=['Confirm freestanding basin rather than wall-product category','Material, drainage/water-contact treatment, support and current supply scope']
 # Six specifications, with source facts and proposals visibly separate.
 sd=spec(dims,dimprop,'DATED_SOURCE_WITH_VERSION_CHECK' if c.get('maker_rows') or cid=='BC-LEAF-GROWTH' else 'MISSING_SOURCE_WORKING_GUESS',refs['dimensions']+mrefs+reviewrefs,
  ['No absolute scale measured from photographs. No whole-set envelope allocated to this component.','Size/finish versions and any border need separate confirmation.'],fieldclaims['dimensions'])
 sw=spec(weight,wprop,'APPROXIMATE_OR_CONFLICTING_SOURCE' if c.get('maker_rows') or cid=='BC-LEAF-GROWTH' else 'MISSING_SOURCE_CONDITIONAL_GUESS',refs['weight']+mrefs+reviewrefs,
  ['No actual cast weighed. Conditional guesses depend on proposed size and substrate.','Not a shipping weight, load rating, or equal allocation of a set mass.'],fieldclaims['weight'])
 sm=spec(material,matprop,'HISTORICAL_STANDARD_OR_OFFER_SCOPE_ONLY' if c.get('maker_rows') or cid=='BC-LEAF-GROWTH' else 'VISIBLE_APPEARANCE_WITH_BINDER_GUESS',refs['material_finish']+mrefs+reviewrefs,
  ['Colour does not establish chemistry, genuine metal leaf, solid copper, substrate or weather resistance.','White historical AC730 claims are not propagated to plaster/gypsum or bespoke versions.'],fieldclaims['material_finish'])
 sf=spec(fixing,fixprop,'HISTORICAL_INSTRUCTION_REAR_UNVERIFIED' if c.get('maker_rows') else 'MISSING_SOURCE_WORKING_DESIGN_IDEA',refs['fixing']+mrefs,
  ['No rear-hardware inspection, anchor specification, wall suitability or tested load rating.','Fixing proposals are discussion prompts; count, material, position and orientation need the actual rear drawing.'],fieldclaims['fixing'])
 sp=spec(price_display,priceprop,'DATED_OFFERS_AND_DRAFTS_NOT_APPROVED_CURRENT_PRICE' if pricefacts else 'NO_SOURCE_INDIVIDUAL_PRICE_WORKING_QUOTATION',refs['individual_price']+['draft-trade-2025:p14:conditions','draft-retail-2025-named:p3:conditions'],
  ['Dated trade and retail variants do not supersede a current owner price.','White-standard drafts exclude extra finish/water-feature/shipping scope; any standalone split or new price is an estimate.'],fieldclaims['individual_price'])
 sa=spec(avdisplay,avprop,'PLATFORM_CONFIGURATION_OR_HISTORICAL_POLICY_NOT_STOCK',refs['availability']+['draft-retail-2025-named:p3:conditions'],
  ['No physical stock, current mould condition, lead time or production capability checked.','No live account or public page read by this worker.'],fieldclaims['availability'])
 if file:
  primary=image_record(file,VISUAL[cid],True)
  primary['identity_scope']='Working visual/source association for owner review; no user classification or approval recorded.'
 else:
  primary={'file_id':None,'folder_id':None,'preview_path':None,'shows_complete_single_component':False,'selection_reason':VISUAL[cid]+' No isolated complete single-component product example selected; use the following series/context records for discussion only.'}
 alternatives=[];contexts=[];series=[]
 for g in groups:
  if not g.get('selected'):continue
  fi=g['selected'][0]
  if fi==file:continue
  role=g['role']
  r=image_record(fi,'Viewed representative from '+g['group_ref']+'; '+('detail/context only; not a complete individual front' if fi in CROPS else 'group role retained without certification of stock or specimen identity'))
  if role in ['Context image','Concept / scene study']:
   r['shows_complete_single_component']=False
   if role=='Concept / scene study':r['scene_provenance']='Concept/scene study; not proof of an installed or manufactured product.'
   contexts.append(r)
  elif role in ['Arrangement image','Mixed component stock']:
   r['shows_complete_single_component']=False;series.append(r)
  else:alternatives.append(r)
 # Prefer complete second FFS triptych when the first selected representative was only detail.
 if cid=='BC-FFS-3':
  fi=fid('G172',1)
  series.insert(0,image_record(fi,'Complete three-piece source-linked composition; FFS3 is the right-hand position, not a standalone product image.',False))
 if cid=='BC-KNIGHT':
  fi='id:cnqzTNngPVsAAAAAAAud8w'
  contexts.insert(0,image_record(fi,'Complete fountain block in process context; shows ground-set thick square block and spiral outlet, not an isolated retail front.',False))
 if cid=='BC-MOON-CRATER':alternatives=[r for r in alternatives if r['file_id']!=fid('G235')]+[image_record(fid('G235'),'Basin/rim close view; outer footprint cropped; detail only.',False)]
 if not file:missing.append('No isolated complete single-component product example selected')
 if c.get('missing_specification_fields'):missing.append(c['missing_specification_fields'])
 missing+=['Owner confirmation of the exact version and proposed specifications','Fresh stable-ID metadata/link check by central coordinator before use','Actual cast measurement/weight and present stock/lead time remain unverified']
 mapped=[]
 for oref in c.get('offer_refs',[]):
  if oref not in OFFERS:continue
  o=OFFERS[oref];bm=[b for b in A['bom'] if b['component_id']==cid and b['offer_ref']==oref]
  mapped.append({'offer_ref':oref,'platform':o.get('platform'),'native_title':o.get('title'),'sq_id':o.get('sq_id'),'shopify_handle':o.get('sh_handle'),'sku':o.get('sku'),'source_url':o.get('source_url'),'mapping_state':o.get('image_state'),'match_status':o.get('match_status'),'sale_unit_state':o.get('sale_unit_state'),'native_parts':o.get('native_parts'),'source_each_cm':o.get('source_each_cm'),'source_overall_cm':o.get('source_overall_cm'),'source_set_weight_kg':o.get('source_set_weight_kg'),'price_scope':'individual cached offer' if oref in c.get('standalone_offer_refs',[]) else o.get('sale_unit_state'),'cached_public_price':o.get('public_price'),'cached_currency':o.get('public_currency'),'cached_availability':o.get('public_availability'),'image_file_id':o.get('image_file_id'),'cautions':o.get('cautions'),'bom_source_rows':bm,'limits':'Immutable cached mapping. No live platform verification, new SKU match or publication performed.'})
 idsources=[r for r in cl if r['field'] in ['Manufacturing mould / repetition','Composition']]
 identity={'status':c['identity_status'],'notes':VISUAL[cid],'source_component_name':c['name'],'source_notes':c.get('notes',''),'maker_rows':rows,'source_codes':c.get('source_codes',[]),'source_refs':unique(frefs+mrefs+reviewrefs+[r['source_ref'] for r in idsources]),'maker_composition_context':[MAKER[n] for n in EXTRA_ROWS.get(cid,[])],'source_claims':[source_claim(r) for r in idsources],'limits':'Working advisory association; design, finish, size, cast, component position and sale unit are distinct. No accepted identity decision or user approval written.'}
 ready=bool(file)
 handoff+=['All six specifications require owner review. Working guesses are deliberately separate from source claims.','Interactive session01a144ab-1a7c-7223-a403-73a4d53d70ff owns all approvals, checkpoints and shared catalogue/register/workbook writes.','No automatic import, publication, Dropbox mutation or source-file change is authorized by this packet.']
 ENTRIES.append({'component_id':cid,'proposed_name':NAMES.get(cid,c['name']),'family':c['family'],'identity_evidence':identity,'source_refs':identity['source_refs'],'primary_example':primary,'alternate_examples':alternatives,'context_images':contexts,'series_images':series,'specifications':{'dimensions':sd,'weight':sw,'material_finish':sm,'fixing':sf,'individual_price':sp,'availability':sa},'dated_additional_price_sources':{'individual_trade_rows':dt,'arrangement_trade_rows_context_only':at,'named_retail_draft_per_piece':nr,'source_limits':'2025 printed trade and filename-dated retail draft are separate versions/tiers. These are source values, not new approved current prices.'},'source_conflicts':unique(conflicts),'missing_evidence':unique(missing),'platform_mapping':{'existing_records':mapped,'new_match_claimed':False,'requires_central_current_read':True,'limits':'Confirmed source-image links are preserved only at their stated scope; collection, finish and current offer identity are not inferred from names.'},'review_ready':ready,'review_ready_scope':'Ready for owner specification discussion with a complete single-object example; not ready to publish.' if ready else 'Research packet complete, but identity/category/image boundary needs owner discussion before an individual product review.','handoff_notes':handoff})

notes=[
 'Worker02 preparation only;34 assigned entries. Writes confined to worker-02. Concave Moon, Wall Circle and all shared approvals/checkpoints/registers/workbooks excluded.',
 'No Dropbox API/tools, live reads, remote mutations, platform writes or contacts used. Parent reports74 fake adapter tests passed before its central live read; this worker makes no separate live-sandbox claim.',
 'Viewed six group contact sheets(87 representatives), four extra sheets(62 selected/source candidates), and two targeted context/detail sheets(25 assets). Sheets are local deterministic review composites, not generated product images.',
 'Visually checked supplied trade page images1,2,4,6,9,10,11,13,14 and all3 pages of named Retail draft. Source pricing/weight variants remain separate. No individual source price or weight derived by dividing a set total.',
 'Leaf Form mould reuse is explicit in manufacturer row34; MSW1/MSW3 reuse is explicit in row83. Single-position numbering is not mould count. MP1/MP5 remain separate under row3 five-different-mould record.',
 'review_ready refers only to suitability for the owner discussion and a complete single-object front; it never means complete measured specifications, sale authorization or publication readiness.',
 'All numeric guesses are broad owner-discussion hypotheses based on stated analogies; no physical measurement, material test, stock check, fixing inspection or load rating is claimed.',
 'Private cached thumbnails are referenced locally; no private image uploaded or generatively altered.']
counts={'assigned':len(A['component_ids']),'entries':len(ENTRIES),'primary_complete_single_component':sum(e['primary_example']['shows_complete_single_component'] for e in ENTRIES),'without_isolated_primary':sum(not e['primary_example']['shows_complete_single_component'] for e in ENTRIES),'review_ready_for_owner_discussion':sum(e['review_ready'] for e in ENTRIES),'needs_identity_or_image_boundary_first':sum(not e['review_ready'] for e in ENTRIES),'all_six_specifications':sum(set(e['specifications'])=={'dimensions','weight','material_finish','fixing','individual_price','availability'} for e in ENTRIES),'every_field_requires_owner_check':all(s['requires_owner_check'] for e in ENTRIES for s in e['specifications'].values()),'working_guess_fields':sum('WORKING' in s['proposal'] for e in ENTRIES for s in e['specifications'].values()),'live_dropbox_reads':0,'remote_mutations':0,'user_approvals_written':0,'shared_files_written':0}
result={'schema':'boldstone.parallel-preparation.worker-packets.v1','worker_number':2,'prepared_utc':datetime.now(timezone.utc).isoformat(),'source_assignment_sha256':hashlib.sha256((ROOT/'assignment.json').read_bytes()).hexdigest(),'entries':ENTRIES,'counts':counts,'validation_notes':notes,'memory_procedure_refs':['MEMORY.md:22-29'],'source_paths':{'assignment':str(ROOT/'assignment.json'),'component_snapshot':A['source_snapshot'],'manufacturing_sheet':str(SOURCES/'Manufacturing_Sheet_Extract.json'),'manufacturing_labelled_refs':str(SOURCES/'Manufacturing_Labelled_References.json'),'additional_price_intake':str(PRICE/'price_source_intake.json'),'trade_price_rows':str(PRICE/'trade_price_rows.json'),'retail_draft_pdf':'/Users/tprice/Documents/boldstone/price list draft documents/Retail PRICE List 2025.docx.pdf','trade_draft_pdf':'/Users/tprice/Documents/boldstone/price list draft documents/SCULPTURE TRADE PRICE List 2025.docx (1).pdf'}}
(ROOT/'packets.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(counts,indent=2))
