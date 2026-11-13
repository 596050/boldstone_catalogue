"""Plan only the Catawiki fields affected by the current instruction."""
from pathlib import Path
from datetime import datetime, timezone
import json, re, hashlib, sys
ROOT=Path('/Users/tprice/Documents/boldstone');OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'catalogue-review/scripts'))
from import_saatchi_snapshot import Xlsx,column,column_index
x=Xlsx(OUT/'previous-catalogue.xlsx');sheet='Wall Sculptures'
headers={x.value(sheet,a):column(column_index(a)) for a in x.cells[sheet] if re.fullmatch(r'[A-Z]+7',a)}
data=json.loads((OUT/'readiness.json').read_text());patches=[]
now=datetime.now(timezone.utc)
serial=(now-datetime(1899,12,30,tzinfo=timezone.utc)).total_seconds()/86400
def put(name,row,value):
    assert name.startswith('catawiki_')
    a=headers[name]+str(row);before=x.value(sheet,a)
    if before!=value:patches.append({'sheet':sheet,'cell':a,'field':name,'before':before,'value':value,'formula':x.formula(sheet,a)})
for p in data['products']:
    r=p['catalogue_row']
    put('catawiki_price_basis',r,'Catalogue GBP retail + GBP100, converted to whole EUR at the recorded reference FX. Keep these proposed prices; no additional EUR200 asking floor is applied. Owner accepts the eight modelled net-proceeds shortfalls. Shipping separate; an estimate is not a guaranteed auction sale price.')
    put('catawiki_value_review',r,'Seller proposal meets the EUR150 numeric threshold in the current Direct from the Artist guidance. This does not prove market value, artistic selection or expert acceptance. No additional common minimum value is a preparation hold.')
    if p['reserve_price_eur_proposed'] is None:
        put('catawiki_reserve_price_eur',r,'')
        review='No reserve: explicitly owner-authorised for the original 97 below-EUR200 targets. The estimate does not prevent a lower winning bid. Do not apply an additional EUR200 floor.'
    else:
        put('catawiki_reserve_price_eur',r,p['reserve_price_eur_proposed'])
        review='Seller-proposed reserve EUR'+format(p['reserve_price_eur_proposed'],'.0f')+' below proposed estimate; expert approval required. This catalogue entry is not native acceptance or a live reserve. No 90-percent after-auction concession authorised.'
    put('catawiki_reserve_review',r,review)
    put('catawiki_photo_review',r,'Catawiki current art guidance asks for high-resolution photographs without a published numeric pixel minimum. A 2000px long edge is a working recommendation, not an acceptance threshold. Native editor previously requested five suitable photos. Confirm original photos of the actual sale cast; accurately labelled AI/reference setting images can supplement, not replace, originals. See the per-product readiness report for all selected links and the 52 candidate-count shortfalls.')
    put('catawiki_object_details_review',r,'New casts confirmed by owner; catalogue examples may vary from the actual cast. Signature and actual-cast production era await the pending one-time owner confirmation. Unsigned means physically not signed; general contemporary-art rules require supporting attribution evidence for unsigned works. Leave unknown exact years blank and do not copy Saatchi-only edition/year estimates.')
    dims=' × '.join(format(p[k],'g') for k in ['packed_length_cm_estimate','packed_width_cm_estimate','packed_height_cm_estimate'])
    put('catawiki_shipping_review',r,'Planned quote group '+p['shipping_profile']+'; estimated packed '+dims+' cm / '+format(p['packed_weight_kg_estimate'],'g')+' kg, not measured carrier-accepted packing. PACK & SEND specialist RFQ covers 176 separate potential shipments across six profiles, with 15 freight/crate assessments; prices and gypsum breakage cover awaited. Moviiu displayed EUR736 incl tax for an 8kg Acanthus Bath-London example including its packaging/insurance option; disproportionate to the EUR208 product proposal, not adopted. Collection from Court Essington, Midford, Bath BA2 7BX plus shipping intended. No approved destination tariff; blank rates are not free shipping. Quote evidence: outputs/catawiki-20261111/readiness-and-quotes-20261111/.')
    put('catawiki_exclusivity_status',r,'Planned cast label '+p['planned_cast_label']+'. Not an actual stock hold: identify and label the physical cast, photograph that cast and remove it from available cross-channel stock before an auction. No auction is live and no other platform inventory change is asserted. Separate genuinely available casts can support other listings.')
    put('catawiki_prepared_utc',r,serial)
assert len(patches)==len({p['cell'] for p in patches}) and all(len(str(p['value']))<32767 for p in patches)
plan={'created_utc':now.isoformat(),'source_sha256':hashlib.sha256((OUT/'previous-catalogue.xlsx').read_bytes()).hexdigest(),
      'scope':'Catawiki-only readiness: retain GBP100 uplift, remove the superseded additional-EUR200-floor clarification hold, retain 97 no-reserve permissions, prepare 79 expert-review reserve proposals, document all176 photo checks and six shipping quote groups. Unknown signature/era/year remain blank. Planned cast labels are not asserted stock holds. Core catalogue prices and all other channels preserved; no public Catawiki submissions.',
      'counts':data['counts'],'patches':patches,
      'previews':[{'name':'reserve-policy','range':headers['catawiki_reserve_price_eur']+'7:'+headers['catawiki_value_review']+'10'}]}
(OUT/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'patches':len(patches),'counts':plan['counts']}))
