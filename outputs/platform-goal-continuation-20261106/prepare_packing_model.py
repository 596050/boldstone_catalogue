"""Prepare editable Saatchi-only crate allowances and affected price formulas."""
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP
from pathlib import Path
import hashlib, json, re, sys, urllib.request

ROOT=Path('/Users/tprice/Documents/boldstone'); BASE=Path(__file__).parent; OUT=BASE/'packing'
OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT/'catalogue-review/scripts'))
from import_saatchi_snapshot import Xlsx, column, column_index

read=lambda p:json.loads(p.read_text())
save=lambda n,d:(OUT/n).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
D=lambda n:Decimal(str(n)); ceil=lambda n:int(D(n).to_integral_value(rounding=ROUND_CEILING));floor=lambda n:int(D(n).to_integral_value(rounding=ROUND_FLOOR))
money=lambda n:float(D(n).quantize(D('.01'),rounding=ROUND_HALF_UP)); round0=lambda n:int(D(n).to_integral_value(rounding=ROUND_HALF_UP))
pointer=read(ROOT/'sculpture-catalogue/current-master.json'); source=pointer['current_app_review_workbook']
body=Path(source['path']).read_bytes(); assert hashlib.sha256(body).hexdigest()==source['sha256']
assert not (OUT/'dropbox-receipt.json').exists(),'Reconcile any previous publication first'
if (OUT/'previous-catalogue.xlsx').exists():assert (OUT/'previous-catalogue.xlsx').read_bytes()==body
else:(OUT/'previous-catalogue.xlsx').write_bytes(body)
save('source-pointer-before.json',pointer);save('previous-dropbox-metadata.json',source['dropbox'])
with urllib.request.urlopen('http://127.0.0.1:8767/api/specifications',timeout=120) as response:app=json.load(response)
save('app-specifications.json',app)
x=Xlsx(OUT/'previous-catalogue.xlsx'); M='Wall Sculptures'; C='Channel Details'
headers={x.value(M,a):re.sub(r'\d','',a) for a in x.cells[M] if re.fullmatch('[A-Z]+7',a)}
first=max(map(column_index,headers.values()))+1
added=['saatchi_packaging_allowance_gbp','saatchi_packed_width_cm_target','saatchi_packed_height_cm_target','saatchi_packed_depth_cm_target','saatchi_artwork_upper_weight_kg','saatchi_packing_target_status']
assert not set(added)&set(headers)
headers.update({h:column(first+i) for i,h in enumerate(added)})
channel_rows={x.value(C,'A'+str(r)):r for r in range(5,186)}
controls=[
 ('buffer_cm','Crate protection per side (cm)',8),
 ('ply_cm','Plywood thickness (cm)',1.2),
 ('ply_gbp','Plywood sheet price (GBP)',29),
 ('ply_m2','Plywood sheet area (m²)',2.9768),
 ('ply_kg','Plywood sheet weight (kg)',22.505),
 ('foam_gbp','Liner sheet price (GBP)',19),
 ('foam_m2','Liner sheet area (m²)',2.88),
 ('foam_kg','Liner sheet weight (kg)',1.872),
 ('reinforcement','Plywood reinforcement allowance',.20),
 ('waste','Material cutting waste',.25),
 ('misc_kg','Wrap, screws and tape (kg)',.5),
 ('consumables_gbp','Wrap, screws and tape (GBP)',5),
 ('procurement_gbp','Material delivery allowance (GBP)',5),
 ('contingency','Packing contingency',.20),
 ('rounding_gbp','Packing budget round-up (GBP)',5),
]
control_cells={key:'$'+column(16+i)+'$3' for i,(key,_,_) in enumerate(controls)}
settings={key:D(value) for key,_,value in controls}
build_keys=['catalogue_id','sku','title','artwork_width_cm','artwork_height_cm','artwork_depth_cm','artwork_weight_kg','packed_width_cm','packed_height_cm','packed_depth_cm','crate_face_area_m2','reinforced_plywood_area_m2','plywood_weight_kg','liner_weight_kg','packed_weight_kg','plywood_cost_gbp','liner_cost_gbp','consumables_gbp','procurement_gbp','subtotal_gbp','packing_allowance_gbp','packing_status']
build_cols={key:column(16+i) for i,key in enumerate(build_keys)}
changes={}
def put(sheet,address,value,formula=None):
    before=x.value(sheet,address); old_formula=x.formula(sheet,address)
    if before==value and old_formula==(formula[1:] if formula else None):return
    changes[sheet,address]=dict(sheet=sheet,cell=address,before=before,before_formula=old_formula,value=value,formula=formula)
def target(header,row,value,formula=None):put(M,headers[header]+str(row),value,formula)
def mr(header,row):return headers[header]+str(row)
for h in added:put(M,headers[h]+'7',h)
put(C,'P1','Saatchi packing estimates (GBP)')
for i,(key,label,value) in enumerate(controls):
    col=column(16+i);assert x.value(C,col+'2') is None and x.value(C,col+'3') is None
    put(C,col+'2',label);put(C,col+'3',value)
for key,col in build_cols.items():put(C,col+'4','saatchi_'+key)
source_rows=[
 ('P188','Plywood source','Q188','https://www.wickes.co.uk/Non-Structural-Hardwood-Plywood-Sheet---12-x-1220-x-2440mm/p/110116'),
 ('P189','Liner source','Q189','https://www.wickes.co.uk/Jabfloor-70-Polystyrene-Insulation-Board---2400-x-1200-x-50mm/p/287738'),
 ('P190','Packing policy','Q190','https://support.saatchiart.com/hc/en-us/articles/14709932602139-Packaging-Your-Artwork'),
 ('P191','Artist packing cost','Q191','https://support.saatchiart.com/hc/en-us/articles/14707798367259-Cost-of-Shipping'),
 ('P192','Rates checked','Q192','6 November 2026. Plywood GBP29; liner GBP19. Both exclude supplier delivery. Supplier product weights and sheet dimensions are the mass/area sources.'),
 ('P193','Planning assumptions','Q193','8 cm protection each side, 20% plywood reinforcement, 25% cutting waste, GBP5 consumables, GBP5 material delivery, 20% contingency, budgets rounded up to GBP5. These are editable estimates, not measured packing or supplier quotes. Packing labour remains zero.'),
 ('P194','Before collection','Q194','Use a crate meeting Saatchi guidelines. Weigh and measure the completed crate and provide its photographs before collection. Carrier shipping remains a separate collector-paid charge.'),
]
for a,av,b,bv in source_rows:put(C,a,av);put(C,b,bv)
fx=D(x.value(M,'BB4')); commission=D(x.value(M,'BM4')); discount=D(x.value(M,'BN4'))
records=[]
for row in range(8,189):
    pid=x.value(M,'AA'+str(row)); cr=channel_rows[pid]; sku=x.value(M,'AQ'+str(row))
    dims=[x.value(M,headers['saatchi_'+axis+'_cm']+str(row)) for axis in ['width','height','depth']]
    weight_text=str(x.value(M,'E'+str(row))); assert 'kg' in weight_text.lower()
    nums=re.findall(r'\d+(?:\.\d+)?',weight_text);assert nums
    upper=max(map(D,nums));assert upper>0
    valid=all(isinstance(v,(float,int)) and v>0 for v in dims)
    z={key:build_cols[key]+str(cr) for key in build_keys}
    vals={'catalogue_id':pid,'sku':sku,'title':x.value(M,'AV'+str(row)),'artwork_weight_kg':float(upper)}; forms={}
    for axis,dim in zip(['width','height','depth'],dims):
        ref="'Wall Sculptures'!$"+headers['saatchi_'+axis+'_cm']+'$'+str(row)
        vals['artwork_'+axis+'_cm']=dim if valid or isinstance(dim,(int,float)) else 'n.a.'
        forms['artwork_'+axis+'_cm']=f'=IF(AND(ISNUMBER({ref}),{ref}>0),{ref},"n.a.")'
        key='packed_'+axis+'_cm'; input_ref=z['artwork_'+axis+'_cm']
        vals[key]=ceil(D(dim)+2*settings['buffer_cm']+2*settings['ply_cm']) if isinstance(dim,(int,float)) and dim>0 else 'n.a.'
        forms[key]=f'=IF(ISNUMBER({input_ref}),ROUNDUP({input_ref}+2*{control_cells["buffer_cm"]}+2*{control_cells["ply_cm"]},0),"n.a.")'
    forms.update({
        'crate_face_area_m2':f'=IF(COUNT({z["packed_width_cm"]}:{z["packed_depth_cm"]})=3,2*({z["packed_width_cm"]}*{z["packed_height_cm"]}+{z["packed_width_cm"]}*{z["packed_depth_cm"]}+{z["packed_height_cm"]}*{z["packed_depth_cm"]})/10000,"n.a.")',
        'reinforced_plywood_area_m2':f'=IF(ISNUMBER({z["crate_face_area_m2"]}),{z["crate_face_area_m2"]}*(1+{control_cells["reinforcement"]}),"n.a.")',
        'plywood_weight_kg':f'=IF(ISNUMBER({z["reinforced_plywood_area_m2"]}),{z["reinforced_plywood_area_m2"]}*{control_cells["ply_kg"]}/{control_cells["ply_m2"]},"n.a.")',
        'liner_weight_kg':f'=IF(ISNUMBER({z["crate_face_area_m2"]}),{z["crate_face_area_m2"]}*{control_cells["foam_kg"]}/{control_cells["foam_m2"]},"n.a.")',
        'packed_weight_kg':f'=IF(AND(ISNUMBER({z["artwork_weight_kg"]}),{z["artwork_weight_kg"]}>0,COUNT({z["plywood_weight_kg"]}:{z["liner_weight_kg"]})=2),ROUNDUP(SUM({z["artwork_weight_kg"]},{z["plywood_weight_kg"]},{z["liner_weight_kg"]},{control_cells["misc_kg"]}),0),"n.a.")',
        'plywood_cost_gbp':f'=IF(ISNUMBER({z["reinforced_plywood_area_m2"]}),{z["reinforced_plywood_area_m2"]}*{control_cells["ply_gbp"]}/{control_cells["ply_m2"]}*(1+{control_cells["waste"]}),"n.a.")',
        'liner_cost_gbp':f'=IF(ISNUMBER({z["crate_face_area_m2"]}),{z["crate_face_area_m2"]}*{control_cells["foam_gbp"]}/{control_cells["foam_m2"]}*(1+{control_cells["waste"]}),"n.a.")',
        'consumables_gbp':'='+control_cells['consumables_gbp'],
        'procurement_gbp':'='+control_cells['procurement_gbp'],
        'subtotal_gbp':f'=IF(COUNT({z["plywood_cost_gbp"]}:{z["procurement_gbp"]})=4,SUM({z["plywood_cost_gbp"]}:{z["procurement_gbp"]}),"n.a.")',
        'packing_allowance_gbp':f'=IF(ISNUMBER({z["subtotal_gbp"]}),ROUNDUP({z["subtotal_gbp"]}*(1+{control_cells["contingency"]})/{control_cells["rounding_gbp"]},0)*{control_cells["rounding_gbp"]},"n.a.")',
        'packing_status':f'=IF(ISNUMBER({z["packing_allowance_gbp"]}),"Planning estimate; measure and weigh the completed crate before collection","Missing artwork dimensions; packing estimate unavailable")',
    })
    vals.update(consumables_gbp=float(settings['consumables_gbp']),procurement_gbp=float(settings['procurement_gbp']))
    if valid:
        w,h,d=(D(vals['packed_'+axis+'_cm']) for axis in ['width','height','depth'])
        area=2*(w*h+w*d+h*d)/10000;wood_area=area*(1+settings['reinforcement'])
        woodkg=wood_area*settings['ply_kg']/settings['ply_m2'];foamkg=area*settings['foam_kg']/settings['foam_m2']
        woodcost=wood_area*settings['ply_gbp']/settings['ply_m2']*(1+settings['waste']);foamcost=area*settings['foam_gbp']/settings['foam_m2']*(1+settings['waste'])
        subtotal=woodcost+foamcost+settings['consumables_gbp']+settings['procurement_gbp']
        packing=ceil(subtotal*(1+settings['contingency'])/settings['rounding_gbp'])*int(settings['rounding_gbp'])
        vals.update(crate_face_area_m2=float(area),reinforced_plywood_area_m2=float(wood_area),plywood_weight_kg=float(woodkg),liner_weight_kg=float(foamkg),packed_weight_kg=ceil(upper+woodkg+foamkg+settings['misc_kg']),plywood_cost_gbp=float(woodcost),liner_cost_gbp=float(foamcost),subtotal_gbp=float(subtotal),packing_allowance_gbp=packing,packing_status='Planning estimate; measure and weigh the completed crate before collection')
        retail=D(x.value(M,'H'+str(row))); manuf=D(x.value(M,'AM'+str(row))); labour=D(x.value(M,'AL'+str(row)))
        net=ceil((retail+packing)*fx);minimum=ceil(D(net)/(1-commission));asking=ceil(D(minimum)/(1-discount));sale=round0(D(asking)*(1-discount));proceeds=floor(D(sale)*(1-commission));net_gbp=money(D(proceeds)/fx);profit=money(D(net_gbp)-manuf-labour-packing)
        assert D(profit)+D('.005')>=retail-manuf-labour,(pid,profit,retail-manuf-labour)
        price_values=dict(net_target_usd=net,minimum_sale_price_usd=minimum,asking_price_usd=asking,discounted_sale_usd=sale,proceeds_after_discount_usd=proceeds,net_after_discount_gbp=net_gbp,profit_after_discount_gbp=profit)
    else:
        for key in ['crate_face_area_m2','reinforced_plywood_area_m2','plywood_weight_kg','liner_weight_kg','packed_weight_kg','plywood_cost_gbp','liner_cost_gbp','subtotal_gbp','packing_allowance_gbp']:vals[key]='n.a.'
        vals['packing_status']='Missing artwork dimensions; packing estimate unavailable'
        price_values={key:'n.a.' for key in ['net_target_usd','minimum_sale_price_usd','asking_price_usd','discounted_sale_usd','proceeds_after_discount_usd','net_after_discount_gbp','profit_after_discount_gbp']}
    for key in build_keys:put(C,z[key],vals[key],forms.get(key))
    def build_lookup(key):
        col=build_cols[key]
        return "INDEX('Channel Details'!$"+col+"$5:$"+col+"$185,MATCH(AA"+str(row)+",'Channel Details'!$P$5:$P$185,0))"
    for header,key in [('saatchi_packaging_allowance_gbp','packing_allowance_gbp'),('saatchi_packed_width_cm_target','packed_width_cm'),('saatchi_packed_height_cm_target','packed_height_cm'),('saatchi_packed_depth_cm_target','packed_depth_cm'),('saatchi_artwork_upper_weight_kg','artwork_weight_kg'),('saatchi_packing_target_status','packing_status')]:target(header,row,vals[key],'='+build_lookup(key))
    allowance=mr('saatchi_packaging_allowance_gbp',row)
    netref=mr('saatchi_net_target_usd',row);minref=mr('saatchi_minimum_sale_price_usd',row);askref=mr('saatchi_asking_price_usd',row);discref=mr('saatchi_discounted_sale_usd',row);procref=mr('saatchi_proceeds_after_discount_usd',row);gbpref=mr('saatchi_net_after_discount_gbp',row);com=mr('saatchi_commission_rate',row);disc=mr('saatchi_discount_allowance',row)
    price_forms={
        'net_target_usd':f'=IF(ISNUMBER({allowance}),ROUNDUP((H{row}+{allowance})*$BB$4,0),"n.a.")',
        'minimum_sale_price_usd':f'=IF(ISNUMBER({netref}),ROUNDUP({netref}/(1-{com}),0),"n.a.")',
        'asking_price_usd':f'=IF(ISNUMBER({minref}),ROUNDUP({minref}/(1-{disc}),0),"n.a.")',
        'discounted_sale_usd':f'=IF(ISNUMBER({askref}),ROUND({askref}*(1-{disc}),0),"n.a.")',
        'proceeds_after_discount_usd':f'=IF(ISNUMBER({discref}),ROUNDDOWN({discref}*(1-{com}),0),"n.a.")',
        'net_after_discount_gbp':f'=IF(ISNUMBER({procref}),ROUND({procref}/$BB$4,2),"n.a.")',
        'profit_after_discount_gbp':f'=IF(ISNUMBER({gbpref}),ROUND({gbpref}-AM{row}-AL{row}-{allowance},2),"n.a.")',
    }
    for key,value in price_values.items():target('saatchi_'+key,row,value,price_forms[key])
    target('saatchi_packed_kg_estimate',row,vals['packed_weight_kg'],'='+build_lookup('packed_weight_kg'))
    packed_text=' × '.join(str(vals['packed_'+axis+'_cm']) for axis in ['width','height','depth'])+' cm' if valid else 'n.a.'
    aw,ah,ad=(mr('saatchi_packed_'+axis+'_cm_target',row) for axis in ['width','height','depth'])
    target('saatchi_packed_cm_estimate',row,packed_text,f'=IF(ISNUMBER({aw}),{aw}&" × "&{ah}&" × "&{ad}&" cm","n.a.")')
    target('saatchi_packing_basis',row,'Saatchi crate planning estimate from artwork dimensions and upper recorded kg; separate plywood, lining, wrap, screws, procurement and contingency allowances. Editable Channel Details P3:AD3. Not measured packing. Weigh/measure/photo before collection. Packing labour is zero.')
    target('saatchi_price_basis',row,'Saatchi artwork price recovers core catalogue retail plus the separate packing allowance after the existing 40% commission and 20% discount assumptions. FX remains the editable catalogue reference. Collector carrier shipping/tax remain separate. Core retail and manufacturing costs unchanged.')
    target('saatchi_update_state',row,'Packing-inclusive Saatchi targets prepared; reconcile and update the existing native artwork ID. Native prices and publication fields remain dated observations until verified.')
    records.append(dict(catalogue_id=pid,sku=sku,row=row,channel_row=cr,title=x.value(M,'AV'+str(row)),status='PLANNING_ESTIMATE' if valid else 'HELD_MISSING_DIMENSIONS',upper_artwork_kg=float(upper),packed_cm=[vals['packed_'+axis+'_cm'] for axis in ['width','height','depth']],packed_kg=vals['packed_weight_kg'],packing_allowance_gbp=vals['packing_allowance_gbp'],asking_usd=price_values['asking_price_usd'],profit_after_discount_gbp=price_values['profit_after_discount_gbp']))
assert len(records)==181 and sum(r['status']=='PLANNING_ESTIMATE' for r in records)==180
plan=dict(scope='Add an editable Saatchi-only packing model and include its allowance in protected artwork price targets. Preserve core app retail, manufacturing costs, zero labour, all other platforms and native observation fields. 180 estimates; one held missing dimensions. Native changes are not implied by workbook targets.',patches=list(changes.values()),headers=headers,added_headers=added,first_added_column=first,last_column=first+len(added)-1,controls=controls,control_cells=control_cells,build_columns=build_cols,records=records,component_records=181,valid_packing_estimates=180,held_missing_dimensions=1,created_utc=datetime.now(timezone.utc).isoformat(),source_sha256=source['sha256'])
save('plan.json',plan);save('packing-estimates.json',records)
print(json.dumps(dict(patches=len(changes),estimates=180,held=1,crater=next(r for r in records if r['sku']=='SQ6211184'))))
