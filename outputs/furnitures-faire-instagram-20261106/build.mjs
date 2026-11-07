import fs from 'node:fs/promises';
import path from 'node:path';
import {Workbook,SpreadsheetFile,FileBlob} from '@oai/artifact-tool';
const out=path.dirname(new URL(import.meta.url).pathname);
const mode=process.argv[2];
if(mode==='--import'){
 const plan=JSON.parse(await fs.readFile(path.join(out,'furnitures-upload-plan.json'),'utf8'));
 const wb=Workbook.create(),s=wb.worksheets.add('Products');
 const matrix=[plan.headers,...plan.rows];
 const range=s.getRangeByIndexes(0,0,matrix.length,plan.headers.length);range.values=matrix;
 range.format={font:{name:'Arial',size:11},columnWidth:24,rowHeight:28,verticalAlignment:'center'};
 s.getRange('A1:X1').format={fill:'#586F50',font:{name:'Arial',size:11,bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:45};
 s.getRange('C:C').format.columnWidth=65;s.getRange('J2:J177').format.numberFormat='0.00';
 s.showGridLines=false;s.freezePanes.freezeRows(1);
 await wb.recalculate();
 if(JSON.stringify(range.values)!==JSON.stringify(matrix))throw Error('Import matrix mismatch');
 const quote=v=>'"'+String(v??'').replaceAll('"','""')+'"';
 const csv=rows=>'\ufeff'+rows.map(r=>r.map(quote).join(',')).join('\r\n')+'\r\n';
 await fs.writeFile(path.join(out,'furnitures-products.csv'),csv(range.values));
 const testIndex=plan.records.findIndex(r=>r.title==='Boldstone Acanthus Bloom - White Wall sculpture');
 if(testIndex<0)throw Error('Test product missing');
 await fs.writeFile(path.join(out,'furnitures-first-product.csv'),csv([matrix[0],matrix[testIndex+1]]));
 await fs.writeFile(path.join(out,'furnitures-remaining-175.csv'),csv([matrix[0],...matrix.slice(1).filter((_,i)=>i!==testIndex)]));
 const im=await wb.render({sheetName:'Products',range:'A1:E5',scale:1,format:'png'});
 await fs.writeFile(path.join(out,'import-preview.png'),new Uint8Array(await im.arrayBuffer()));
 console.log(JSON.stringify({status:'PASS_AUTHORED_CSV',products:matrix.length-1,test_sku:plan.records[testIndex].sku}));
}else if(mode==='--preview'){
 const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(out,'previous-catalogue.xlsx')));
 const im=await wb.render({sheetName:'Wall Sculptures',range:'QT7:QX10',scale:1,format:'png'});
 await fs.writeFile(path.join(out,'catalogue-before.png'),new Uint8Array(await im.arrayBuffer()));
 console.log((await wb.inspect({kind:'region',sheetId:'Wall Sculptures',range:'QT7:QX10',maxChars:1800,tableMaxRows:4,tableMaxCols:5})).ndjson);
}else if(mode==='--final-preview'){
 const plan=JSON.parse(await fs.readFile(path.join(out,'catalogue-plan.json'),'utf8'));
 const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(out,'catalogue_wall_sculptures.xlsx')));
 console.log((await wb.inspect({kind:'region',sheetId:'Wall Sculptures',range:'UX7:UY10',maxChars:1500,tableMaxRows:4,tableMaxCols:2})).ndjson);
 console.log((await wb.inspect({kind:'computedStyle',sheetId:'Wall Sculptures',range:'UX8:UX9',maxChars:2200})).ndjson);
 for(const [first,last,name] of [['faire_native_product_name','faire_native_retail_gbp','final-faire'],['furnitures_native_price_gbp','furnitures_commission_rate','final-furnitures']]){
  const im=await wb.render({sheetName:'Wall Sculptures',range:plan.headers[first]+'7:'+plan.headers[last]+'10',scale:1,format:'png'});
  await fs.writeFile(path.join(out,name+'.png'),new Uint8Array(await im.arrayBuffer()));
 }
 console.log('Final preserved workbook rendered');
}else if(mode==='--catalogue'){
 const plan=JSON.parse(await fs.readFile(path.join(out,'catalogue-plan.json'),'utf8'));
 const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(out,'previous-catalogue.xlsx')));
 const s=wb.worksheets.getItem('Wall Sculptures');
 s.getRangeByIndexes(6,plan.first_added_column-1,182,plan.added_headers.length).format={font:{name:'Calibri',size:11},wrapText:true,verticalAlignment:'top',columnWidth:32,numberFormat:'@'};
 s.getRangeByIndexes(6,plan.first_added_column-1,1,plan.added_headers.length).format={fill:'#586F50',font:{name:'Calibri',size:11,bold:true,color:'#FFFFFF'},rowHeight:75};
 for(const p of plan.patches)s.getRange(p.cell).values=[[p.value]];
 for(const h of plan.numeric_headers)s.getRange(`${plan.headers[h]}8:${plan.headers[h]}188`).format.numberFormat='0.00';
 s.getRange(`${plan.headers.furnitures_commission_rate}8:${plan.headers.furnitures_commission_rate}188`).format.numberFormat='0.00%';
 await wb.recalculate();
 for(const p of plan.patches)if(s.getRange(p.cell).values[0][0]!==p.value)throw Error('Authored value mismatch '+p.cell);
 await(await SpreadsheetFile.exportXlsx(wb)).save(path.join(out,'authored.xlsx'));
 const im=await wb.render({sheetName:'Wall Sculptures',range:plan.preview_range,scale:1,format:'png'});
 await fs.writeFile(path.join(out,'catalogue-preview.png'),new Uint8Array(await im.arrayBuffer()));
 console.log(JSON.stringify({status:'CATALOGUE_AUTHORED',patches:plan.patches.length}));
}else throw Error('Choose --import, --preview or --catalogue');
