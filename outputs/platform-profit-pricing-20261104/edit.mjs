import fs from 'node:fs/promises';
import path from 'node:path';
import {FileBlob, SpreadsheetFile} from '@oai/artifact-tool';

const out=path.resolve(process.argv[2]);
const plan=JSON.parse(await fs.readFile(path.join(out,'profit-pricing-plan.json'),'utf8'));
const preview=process.argv.includes('--preview');
const final=process.argv.includes('--verify-final');
const book=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(out,final?'catalogue_wall_sculptures.xlsx':'previous-catalogue.xlsx')));
const master=book.worksheets.getItem('Wall Sculptures');
const saveImage=async(range,name)=>{
 const blob=await book.render({sheetName:'Wall Sculptures',range,scale:1.15,format:'png'});
 await fs.writeFile(path.join(out,name+'.png'),new Uint8Array(await blob.arrayBuffer()));
};
if(preview){
 await saveImage('JD7:JH10','before-chairish');
 console.log((await book.inspect({kind:'region',sheetId:'Wall Sculptures',range:'BG3:BJ4',maxChars:1200,tableMaxRows:2,tableMaxCols:4})).ndjson);
 process.exit(0);
}
if(!final){
 master.getRangeByIndexes(6,plan.first_master_column-1,182,plan.added_master_columns.length).format={font:{name:'Calibri',size:11},wrapText:true,verticalAlignment:'top',columnWidth:32};
 for(const p of plan.patches){
  const range=master.getRange(p.cell);range.values=[[p.value]];
  if(p.format==='header')range.format={fill:'#586F50',font:{name:'Calibri',size:11,bold:true,color:'#FFFFFF'},wrapText:true};
  else if(p.format&&p.format!=='text')range.format.numberFormat=p.format;
 }
 for(const s of plan.settings){
  const c=plan.headers[s.key];
  master.getRange(c+'3:'+c+'4').format={font:{name:'Calibri',size:11},wrapText:true,verticalAlignment:'top',columnWidth:32};
  master.getRange(c+'3').format={fill:'#586F50',font:{name:'Calibri',size:11,bold:true,color:'#FFFFFF'},wrapText:true};
  master.getRange(c+'4').format.font={color:'#0000FF'};
 }
 for(const p of plan.patches)if(p.formula)master.getRange(p.cell).formulas=[[p.formula]];
 await book.recalculate();
 const failures=[];
 for(const p of plan.patches){
  const got=master.getRange(p.cell).values[0][0];
  if(typeof p.value==='number'?typeof got!=='number'||Math.abs(got-p.value)>.011:got!==p.value)failures.push({cell:p.cell,expected:p.value,got});
 }
 if(failures.length)throw Error(JSON.stringify(failures.slice(0,15)));
 const row=plan.records[0].row,baseline=plan.records[0].baseline_price_gbp;
 const read=k=>master.getRange(plan.headers[k]+row).values[0][0];
 const ctrl=k=>master.getRange(plan.headers[k]+'4');
 const cases=[];
 for(const [commission,discount,payout,tax,fee] of [[.3,.6,.03,.2,2],[.25,.5,0,0,0],[.15,.4,.02,.2,3]]){
  ctrl('faire_opening_commission').values=[[commission]];ctrl('faire_retailer_discount').values=[[discount]];
  ctrl('faire_payout_fee_allowance').values=[[payout]];ctrl('pricing_fee_tax_reserve').values=[[tax]];ctrl('faire_fixed_fee_gbp').values=[[fee]];
  await book.recalculate();
  const expectedW=Math.ceil(((baseline+fee*(1+tax)+.05)/(1-(commission+payout)*(1+tax))-1e-9)*100)/100;
  const actualW=read('faire_wholesale_price_gbp'),net=read('faire_net_after_fees_gbp'),retail=read('faire_retail_reference_gbp');
  if(Math.abs(actualW-expectedW)>.001||net<baseline||retail*(1-discount)+.001<actualW)throw Error('Changed-rate calculation failed');
  cases.push({commission,discount,payout,tax,fee,wholesale:actualW,net,retail});
 }
 for(const s of plan.settings)ctrl(s.key).values=[[s.value]];
 await book.recalculate();
 const errors=await book.inspect({kind:'match',range:`'Wall Sculptures'!${plan.headers[plan.added_master_columns[0]]}3:${plan.headers[plan.added_master_columns.at(-1)]}188`,searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!',options:{useRegex:true,maxResults:30},summary:'New pricing formula errors'});
 await fs.writeFile(path.join(out,'formula-error-scan.ndjson'),errors.ndjson);
 await fs.writeFile(path.join(out,'calculation-verification.json'),JSON.stringify({status:'PASS',cells_read_back:plan.patches.length,changed_input_cases:cases},null,2));
 await(await SpreadsheetFile.exportXlsx(book)).save(path.join(out,'authored.xlsx'));
}
for(const [start,end,label]of[
 ['faire_wholesale_price_gbp','faire_profit_after_fees_gbp','faire-prices'],
 ['wholesale_wholesale_price_gbp','wholesale_profit_after_fees_gbp','wholesale-prices'],
 ['auction_reserve_floor_gbp','auction_net_at_reserve_gbp','auction-prices'],
 ['chairish_asking_price_usd','chairish_auction_reserve_usd','chairish-prices'],
 ['pricing_fee_tax_reserve','pricing_fx_allowance','pricing-reserves']]){
 const a=plan.headers[start],b=plan.headers[end];
 await saveImage(`${a}${label==='pricing-reserves'?3:7}:${b}${label==='pricing-reserves'?4:10}`,(final?'final-':'')+label);
}
console.log(JSON.stringify({status:final?'FINAL_RENDERED':'AUTHORED',cells:plan.patches.length}));
