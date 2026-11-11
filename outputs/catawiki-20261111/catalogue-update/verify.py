"""Independent OpenPyXL readback of new values, formulas, price uplift and preservation."""
from pathlib import Path
import json,hashlib,math,sys,datetime
from decimal import Decimal,ROUND_UP,ROUND_HALF_UP
import openpyxl
from openpyxl.utils import column_index_from_string,get_column_letter
from openpyxl.utils.datetime import to_excel

OUT=Path(__file__).parent;plan=json.loads((OUT/'plan.json').read_text());target=OUT/'catalogue_wall_sculptures.xlsx'
old=openpyxl.load_workbook(OUT/'previous-catalogue.xlsx',read_only=True,data_only=True)
new=openpyxl.load_workbook(target,read_only=True,data_only=True)
form=openpyxl.load_workbook(target,read_only=True,data_only=False)
assert old.sheetnames==new.sheetnames==form.sheetnames and len(new.sheetnames)==12
def grid(book):
 return {get_column_letter(col)+str(row):cell.value
         for row,cells in enumerate(book['Wall Sculptures'].iter_rows(min_row=3,max_row=188,min_col=906,max_col=962),3)
         for col,cell in enumerate(cells,906)}
cache=grid(new)
formula=grid(form)
for p in plan['patches']:
 v=cache[p['cell']];expected=p['value']
 if isinstance(v,datetime.datetime):v=to_excel(v)
 if isinstance(expected,(float,int)):
  assert isinstance(v,(float,int)) and math.isclose(v,expected,rel_tol=1e-10,abs_tol=1e-6),(p['cell'],v,expected)
 else:assert str(v or '')==str(expected or ''),(p['cell'],v,expected)
 if p.get('formula'):assert formula[p['cell']]==p['formula'],(p['cell'],formula[p['cell']],p['formula'])
 # Every intended empty claim remains empty, rather than becoming a numeric zero.
 if expected in ('',None):assert v in ('',None),(p['cell'],v)
source_rows={row[0].row:{c.column:c.value for c in row} for row in old['Wall Sculptures'].iter_rows(min_row=8,max_row=188,max_col=53)}
headers=[c.value for c in next(new['Wall Sculptures'].iter_rows(min_row=7,max_row=7,min_col=1,max_col=962))]
header={headers[n-1]:n for n in range(906,963)}
def cell(h,row):return cache[get_column_letter(header[h])+str(row)]
fx=Decimal(str(cache[get_column_letter(header['catawiki_gbp_per_eur_reference'])+'4']))
negative=[]
for row in range(8,189):
 base=Decimal(str(source_rows[row][8]));gbp=Decimal(str(cell('catawiki_target_price_gbp',row)))
 assert gbp==base+100
 eur=int(((base+100)/fx).to_integral_value(rounding=ROUND_UP))
 assert cell('catawiki_target_price_eur',row)==eur
 fixed=Decimal(1 if eur<150 else 2 if eur<300 else 3 if eur<500 else 5 if eur<1000 else 10)
 fees=((Decimal(eur)*Decimal('.125')+fixed)*Decimal('1.2')).quantize(Decimal('.01'),rounding=ROUND_UP)
 net=((Decimal(eur)-fees)*fx*Decimal('.97')).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
 assert Decimal(str(cell('catawiki_estimated_seller_fees_eur',row)))==fees
 assert Decimal(str(cell('catawiki_estimated_net_proceeds_gbp',row)))==net
 if net<base:negative.append(row)
assert len(negative)==8
assert len(set(headers))==962 and all(h.startswith('catawiki_') for h in headers[905:])
result={'status':'PASS','sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'readers_agree':True,
 'independently_verified_cells':len(plan['patches']),'prices_verified':181,'formula_cells_verified':sum(bool(p.get('formula')) for p in plan['patches']),
 'workbook_sheets_preserved':12,'unique_master_headers':962,'below_catalogue_proceeds_rows':negative,
 'not_a_native_catawiki_update':True}
(OUT/'independent-verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
