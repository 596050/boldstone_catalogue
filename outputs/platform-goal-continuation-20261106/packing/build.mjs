import fs from 'node:fs/promises';
import path from 'node:path';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';

const out=path.dirname(new URL(import.meta.url).pathname);
const plan=JSON.parse(await fs.readFile(out+'/plan.json','utf8'));
const mode=process.argv[2],final=mode==='--final';
const book=await SpreadsheetFile.importXlsx(await FileBlob.load(out+(final?'/catalogue_wall_sculptures.xlsx':'/previous-catalogue.xlsx')));
const master=book.worksheets.getItem('Wall Sculptures'),channel=book.worksheets.getItem('Channel Details');
const priceRange=plan.headers.saatchi_net_target_usd+'7:'+plan.headers.saatchi_profit_after_discount_gbp+'8';
async function render(sheetName,range,name){const blob=await book.render({sheetName,range,scale:1,format:'png'});await fs.writeFile(out+'/'+name+'.png',new Uint8Array(await blob.arrayBuffer()));}
if(mode==='--before'){
 await render('Channel Details','A1:G6','before-channel-layout');
 await render('Wall Sculptures',priceRange,'before-prices');
 console.log(JSON.stringify({status:'BEFORE_RENDERED'}));
}else{
 const close=(actual,expected)=>typeof expected==='number'?typeof actual==='number'&&Math.abs(actual-expected)<1e-6:actual===expected;
 const verify=()=>{for(const p of plan.patches){const actual=book.worksheets.getItem(p.sheet).getRange(p.cell).values[0][0];if(!close(actual,p.value))throw Error(JSON.stringify({cell:p.sheet+'!'+p.cell,actual,expected:p.value}));}};
 if(!final){
  master.getRangeByIndexes(6,plan.first_added_column-1,182,plan.added_headers.length).format={font:{name:'Calibri',size:11},wrapText:true,verticalAlignment:'top',columnWidth:32};
  master.getRangeByIndexes(6,plan.first_added_column-1,1,plan.added_headers.length).format={fill:'#263F35',font:{name:'Calibri',size:11,bold:true,color:'#FFFFFF'}};
  channel.getRange('P1:AK194').format={font:{name:'Calibri',size:11},columnWidth:28,verticalAlignment:'top',wrapText:true};
  channel.getRange('P1').format={font:{name:'Calibri',size:14,bold:true,color:'#253D32'},wrapText:false};
  channel.getRange('P2:AD2').format={fill:'#263F35',font:{name:'Calibri',size:11,bold:true,color:'#FFFFFF'},wrapText:true};
  channel.getRange('P3:AD3').format={fill:'#FFF3CF',font:{name:'Calibri',size:11,color:'#1563AD'},numberFormat:'0.0000'};
  channel.getRange('P4:AK4').format={fill:'#263F35',font:{name:'Calibri',size:11,bold:true,color:'#FFFFFF'},wrapText:true};
  channel.getRange('P5:R185').format.numberFormat='@';
  channel.getRange('S5:AI185').format.numberFormat='0.000';
  channel.getRange('AI5:AJ185').format.numberFormat='"£"#,##0.00';
  channel.getRange('AK5:AK185').format.numberFormat='@';
  channel.getRange('Q188:Q194').format={wrapText:false,font:{name:'Calibri',size:11,color:'#526056'}};
  for(const [key] of plan.controls)if(['reinforcement','waste','contingency'].includes(key))channel.getRange(plan.control_cells[key].replaceAll('$','')).format.numberFormat='0%';
  for(const p of plan.patches){const cell=book.worksheets.getItem(p.sheet).getRange(p.cell);if(p.formula){cell.formulas=[[p.formula]];}else{cell.values=[[p.value]];}}
  for(const key of ['artwork_width_cm','artwork_height_cm','artwork_depth_cm'])channel.getRange(plan.build_columns[key]+'5:'+plan.build_columns[key]+'185').format.font.color='#217A43';
  channel.getRange(plan.build_columns.artwork_weight_kg+'5:'+plan.build_columns.artwork_weight_kg+'185').format.font.color='#1563AD';
  for(const key of ['packed_width_cm','packed_height_cm','packed_depth_cm','packed_weight_kg'])channel.getRange(plan.build_columns[key]+'5:'+plan.build_columns[key]+'185').format.numberFormat='0';
  for(const key of ['plywood_cost_gbp','liner_cost_gbp','consumables_gbp','procurement_gbp','subtotal_gbp','packing_allowance_gbp'])channel.getRange(plan.build_columns[key]+'5:'+plan.build_columns[key]+'185').format.numberFormat='"£"#,##0.00';
  for(const key of ['saatchi_packaging_allowance_gbp','saatchi_artwork_upper_weight_kg'])master.getRange(plan.headers[key]+'8:'+plan.headers[key]+'188').format.numberFormat=key.endsWith('gbp')?'"£"#,##0.00':'0.00';
  for(const axis of ['width','height','depth'])master.getRange(plan.headers['saatchi_packed_'+axis+'_cm_target']+'8:'+plan.headers['saatchi_packed_'+axis+'_cm_target']+'188').format.numberFormat='0';
  await book.recalculate();verify();
  const first=plan.records.find(r=>r.sku==='SQ6211184'),row=first.row;
  const savedControls=Object.fromEntries(plan.controls.map(([key,,value])=>[key,value]));
  const control=key=>channel.getRange(plan.control_cells[key].replaceAll('$',''));
  const read=key=>master.getRange(plan.headers[key]+row).values[0][0];
  const cases=[];
  const ceil=x=>Math.ceil(x-1e-9),round0=x=>Math.floor(x+0.5),floor=x=>Math.floor(x+1e-9);
  const retail=master.getRange('H'+row).values[0][0],fx=master.getRange('BB4').values[0][0],com=master.getRange('BM4').values[0][0],disc=master.getRange('BN4').values[0][0];
  for(const [label,overrides]of [['double plywood price',{ply_gbp:savedControls.ply_gbp*2}],['zero packing materials',{ply_gbp:0,foam_gbp:0,consumables_gbp:0,procurement_gbp:0}]]){
   for(const [key,value]of Object.entries(overrides))control(key).values=[[value]];
   await book.recalculate();
   const a={...savedControls,...overrides},[w,h,d]=first.packed_cm;
   const area=2*(w*h+w*d+h*d)/10000;
   const subtotal=area*(1+a.reinforcement)*a.ply_gbp/a.ply_m2*(1+a.waste)+area*a.foam_gbp/a.foam_m2*(1+a.waste)+a.consumables_gbp+a.procurement_gbp;
   const pack=ceil(subtotal*(1+a.contingency)/a.rounding_gbp)*a.rounding_gbp;
   const net=ceil((retail+pack)*fx),minimum=ceil(net/(1-com)),asking=ceil(minimum/(1-disc));
   if(read('saatchi_packaging_allowance_gbp')!==pack||read('saatchi_asking_price_usd')!==asking)throw Error('Changed packing rate did not recalculate correctly');
   cases.push({label,packing_gbp:pack,asking_usd:asking});
   for(const [key,value]of Object.entries(savedControls))control(key).values=[[value]];
  }
  const dim=master.getRange(plan.headers.saatchi_width_cm+row),savedDim=dim.values[0][0],savedFormula=dim.formulas[0][0];
  dim.values=[[null]];await book.recalculate();
  if(read('saatchi_packaging_allowance_gbp')!=='n.a.'||read('saatchi_asking_price_usd')!=='n.a.')throw Error('Missing dimension produced a false numeric price');
  cases.push({label:'missing width',packing_gbp:read('saatchi_packaging_allowance_gbp'),asking_usd:read('saatchi_asking_price_usd')});
  if(savedFormula)dim.formulas=[[savedFormula]];else dim.values=[[savedDim]];
  await book.recalculate();verify();
  const errors=await book.inspect({kind:'match',range:"'Channel Details'!P2:AK194",searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!',options:{useRegex:true,maxResults:30},summary:'Saatchi packing formula errors'});
  await fs.writeFile(out+'/formula-error-scan.ndjson',errors.ndjson);
  await fs.writeFile(out+'/calculation-verification.json',JSON.stringify({status:'PASS',affected_cells:plan.patches.length,cases,valid_estimates:180,missing_dimension_holds:1},null,2));
  await(await SpreadsheetFile.exportXlsx(book)).save(out+'/authored.xlsx');
 }
 const prefix=final?'final':'after';
 await render('Wall Sculptures',plan.headers.saatchi_net_target_usd+'117:'+plan.headers.saatchi_profit_after_discount_gbp+'117',prefix+'-crater-prices');
 await render('Channel Details','P1:X6',prefix+'-packing-inputs');
 await render('Channel Details','Z113:AK115',prefix+'-packing-costs');
 console.log(JSON.stringify({status:final?'FINAL_RENDERED':'AUTHORED',cells:plan.patches.length}));
}
