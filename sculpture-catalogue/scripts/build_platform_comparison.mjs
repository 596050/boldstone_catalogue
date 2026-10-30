import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';

const project=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const data=JSON.parse(await fs.readFile(path.join(project,'evidence/platform_comparison_2026-10-16.json'),'utf8'));
const dropbox=JSON.parse(await fs.readFile(path.join(project,'evidence/platform_dropbox_mapping_2026-10-16.json'),'utf8'));
const outputDir=path.join(project,'outputs/platform-comparison-2026-10-16');
const previewDir=path.join(project,'reviews/platform-comparison');
await fs.mkdir(outputDir,{recursive:true});await fs.mkdir(previewDir,{recursive:true});
const wb=Workbook.create();const sheets={};
for(const name of ['Dropbox Mapping','Matched Products','Squarespace Only','Shopify Only','Historical Shopify','Squarespace Records','Shopify Records'])sheets[name]=wb.worksheets.add(name);
const font='Arial',ink='#263B32',muted='#64736B',green='#304B3D';
const column=n=>{let s='';for(n++;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;};
const literal=x=>typeof x==='string'&&x.startsWith('=')?"'"+x:x??null;
const numeric=value=>value===''?null:Number(value);
function makeTable(name,title,context,headers,rows,widths,{headerRow=6,wrap=[],numbers=[],decimals=[],headerHeight=42,freezeColumns=1,notes=[]}={}){
 const sh=sheets[name],last=headerRow+rows.length;
 sh.showGridLines=false;
 sh.getRangeByIndexes(0,0,last,headers.length).format.font={name:font,size:10,color:ink};
 sh.getRangeByIndexes(0,0,last,headers.length).format.verticalAlignment='center';
 sh.getRange('A2').values=[[title]];sh.getRange('A2').format.font={name:font,size:15,bold:true,color:ink};
 sh.getRange('A3').values=[[context]];sh.getRange('A3').format.font={name:font,size:10,italic:true,color:muted};
 for(const [address,value] of notes){sh.getRange(address).values=[[value]];sh.getRange(address).format.font={name:font,size:10,color:muted};}
 sh.getRangeByIndexes(headerRow-1,0,1,headers.length).values=[headers];
 sh.getRangeByIndexes(headerRow,0,rows.length,headers.length).values=rows.map(row=>row.map(literal));
 const tbl=sh.tables.add(`A${headerRow}:${column(headers.length-1)}${last}`,true,'Tbl_'+name.replaceAll(' ',''));tbl.style='TableStyleLight1';tbl.showFilterButton=true;
 sh.getRangeByIndexes(headerRow-1,0,1,headers.length).format={fill:green,font:{name:font,size:10,bold:true,color:'#FFFFFF'},wrapText:true,verticalAlignment:'center',horizontalAlignment:'center',rowHeight:headerHeight};
 sh.getRangeByIndexes(headerRow,0,rows.length,headers.length).format.rowHeight=30;
 for(let c=0;c<headers.length;c++)sh.getRangeByIndexes(0,c,last,1).format.columnWidth=widths[c]??26;
 for(const c of wrap)sh.getRangeByIndexes(headerRow,c,rows.length,1).format.wrapText=true;
 for(const c of numbers)sh.getRangeByIndexes(headerRow,c,rows.length,1).setNumberFormat('#,##0');
 for(const c of decimals)sh.getRangeByIndexes(headerRow,c,rows.length,1).setNumberFormat('#,##0.00');
 for(let r=0;r<rows.length;r++){
  const lines=Math.max(1,...wrap.map(c=>String(rows[r][c]??'').split('\n').reduce((sum,line)=>sum+Math.max(1,Math.ceil(line.length/Math.max(14,(widths[c]??26)*.95))),0)));
  if(lines>1)sh.getRangeByIndexes(headerRow+r,0,1,headers.length).format.rowHeight=Math.min(409,Math.max(30,lines*13+10));
 }
 sh.freezePanes.freezeRows(headerRow);if(freezeColumns)sh.freezePanes.freezeColumns(freezeColumns);
 return {sh,first:headerRow+1,last,rows:rows.length,headers,values:rows};
}

const matchRows=data.matches.map(r=>[r.match_id,r.sku,r.sq_title,r.sh_title,r.sq_id,r.sh_handle,r.sq_price,r.sh_price,r.price_comparison,r.title_comparison,r.description_comparison,r.sq_variant_rows,r.sh_source_rows,r.sq_visible,r.sq_stock,r.sh_status,r.basis,r.sq_url,r.sq_csv_record,r.sh_csv_record]);
const matches=makeTable('Matched Products','Squarespace and Shopify product matches','Wall sculptures. Squarespace: 15 October 2026 export. Shopify: preserved historical wall export checked 11 October 2026.',
 ['Match ID','Shared SKU','Squarespace product','Shopify product','Squarespace product ID','Shopify handle','Squarespace price','Shopify price','Numeric price comparison','Title comparison','Description comparison','Squarespace variant rows','Shopify product / image rows','Squarespace visible','Squarespace stock','Shopify status','Match basis','Squarespace source URL','Squarespace CSV record','Shopify CSV record'],matchRows,[16,30,57,57,36,48,22,22,38,23,57,22,23,23,25,21,82,120,24,24],{headerRow:11,wrap:[1,2,3,5,8,9,10,16,17],numbers:[11,12],decimals:[6,7],notes:[['A9','Confirmed matches use unique identical nonblank SKUs. Prices retain unencoded export currency; descriptions are compared after HTML and whitespace normalization.']]});
matches.sh.tabColor=green;

const ssOnlyRows=data.squarespace_only.map(r=>[r.title,r.sku,r.sq_id,r.reason,r.candidate,r.variant_rows,numeric(r.raw.Price),r.raw.Stock,r.raw.Visible,r.raw.Weight,r.raw.Length,r.raw.Width,r.raw.Height,r.plain_description,r.raw['Product URL'],r.csv_record,r.source_row]);
const ssOnly=makeTable('Squarespace Only','Squarespace products without a confirmed Shopify match','43 distinct product IDs. Additional variants remain with their parent product in Squarespace Records. Repeated SKUs remain separate products.',
 ['Squarespace product','SKU','Product ID','Unmatched reason','Possible relationship requiring review','Native variant rows','Native price','Native stock','Visible','Native weight (unit unencoded)','Native length (unit unencoded)','Native width (unit unencoded)','Native height (unit unencoded)','Description as plain text','Product slug','CSV record','Source workbook row'],ssOnlyRows,[70,32,37,105,110,21,20,23,15,27,27,27,27,175,95,18,23],{wrap:[0,1,3,4,13,14],numbers:[5,16],decimals:[6]});
ssOnly.sh.getRange(`D${ssOnly.first}:D${ssOnly.last}`).conditionalFormats.add('containsText',{text:'another distinct',format:{fill:'#FFF0CF',font:{color:'#775211'}}});

const shOnlyRows=data.shopify_only.map(r=>[r.title,r.handle,r.sku,r.raw.Status,numeric(r.raw['Variant Price']),numeric(r.raw['Variant Grams']),r.reason,r.candidate,r.raw['Image Src'],r.csv_record,r.source_row]);
const shOnly=makeTable('Shopify Only','Shopify products without a confirmed Squarespace match','Main historical wall export. Zero draft price/weight are preserved source values. Complete native fields appear in Shopify Records.',
 ['Shopify product','Handle','SKU','Status','Native price','Variant grams','Unmatched reason','Possible relationship requiring review','Source image URL','CSV record','Source workbook row'],shOnlyRows,[36,30,23,18,22,22,100,120,150,18,23],{wrap:[0,6,7,8],numbers:[5,10],decimals:[4]});
shOnly.sh.getRange(`G${shOnly.first}:G${shOnly.last}`).conditionalFormats.add('containsText',{text:'Blank',format:{fill:'#FFF0CF',font:{color:'#775211'}}});

function sourceWidth(name){
 if(['Description','Body (HTML)'].includes(name))return 180;
 if(['Hosted Image URLs','Image Src','Variant Image'].includes(name))return 180;
 if(['Title','SEO Title','SEO Description','Tags'].includes(name))return 85;
 if(/Option.*Value/.test(name))return 78;
 if(/Product ID|Variant ID|Handle/.test(name))return 43;
 if(name.length>45)return 52;
 return Math.max(22,Math.min(44,Math.ceil(name.length*.8)+5));
}
const oldPrefix=['Shopify source title','Dataset version','Cross-platform status','Related Squarespace ID','Related Squarespace title','Historical relationship evidence','Original source sheet','Source workbook row','Source fidelity'];
const oldRows=data.historical.map(r=>[r.title,r.version,r.status,r.related_sq,r.related_sq_title,r.lineage,r.source_sheet,r.source_row,r.source_fidelity,...data.old_schema.map(k=>r.raw[k])]);
const historical=makeTable('Historical Shopify','Older Shopify records and candidate links','Nine version-specific records: one exact-SKU match and eight candidates. Source values come from preserved older/seed transcriptions.',
 [...oldPrefix,...data.old_schema],oldRows,[55,24,51,36,65,100,27,23,110,...data.old_schema.map(sourceWidth)],{wrap:[0,2,4,5,8,...data.old_schema.map((_,i)=>i+oldPrefix.length)],numbers:[7],headerHeight:62});
historical.sh.getRange(`C${historical.first}:C${historical.last}`).conditionalFormats.add('containsText',{text:'Candidate',format:{fill:'#FFF0CF',font:{color:'#775211'}}});

const ssPrefix=['Resolved parent title','Main comparison status','Match ID','Resolved parent product ID','Matching Shopify handle','Native row role','CSV record','Source workbook row'];
const ssRawRows=data.ss_rows.map(r=>[r.parent_title,r.status,r.match_id,r.parent_id,r.sh_handle,r.record_kind,r.csv_record,r.source_row,...data.ss_schema.map(k=>r.values[k])]);
const sqRecords=makeTable('Squarespace Records','All native Squarespace wall records','Source: '+data.source_workbook+' / SS Wall Variants. All 34 native columns, including blanks, are preserved.',
 [...ssPrefix,...data.ss_schema],ssRawRows,[70,26,16,37,52,34,18,23,...data.ss_schema.map(sourceWidth)],{wrap:[0,4,5,...data.ss_schema.map((_,i)=>i+ssPrefix.length)],numbers:[7],headerHeight:62,notes:[['A4','223 rows = 80 product headers/primary variants plus 143 additional variants. Native Weight, Length, Width and Height do not encode their measurement units.']]});
const shPrefix=['Resolved parent title','Main comparison status','Match ID','Matching Squarespace product ID','Native row role','CSV record','Source workbook row'];
const shRawRows=data.sh_rows.map(r=>[r.parent_title,r.status,r.match_id,r.sq_id,r.record_kind,r.csv_record,r.source_row,...data.sh_schema.map(k=>r.values[k])]);
const shRecords=makeTable('Shopify Records','All native Shopify main wall records','Source: '+data.source_workbook+' / SH Source Rows. All 95 native columns, including blanks, are preserved.',
 [...shPrefix,...data.sh_schema],shRawRows,[70,26,16,39,34,18,23,...data.sh_schema.map(sourceWidth)],{wrap:[0,4,...data.sh_schema.map((_,i)=>i+shPrefix.length)],numbers:[6],headerHeight:76,notes:[['A4','117 rows = 38 product headers/primary variants plus 79 image continuation rows. Historical export status is retained; current live store state was not inspected.']]});

const list=values=>values.join('\n');
const mapRows=dropbox.records.map(r=>[r.match_id,r.sku,r.sq_title,r.status,list(r.family_names),list(r.group_names),r.source_parts,r.component_state,list(r.member_paths),list(r.member_folder_ids),list(r.group_ids),list(r.file_paths),list(r.file_ids),list(r.family_paths),list(r.family_ids),list(r.gallery_paths),list(r.gallery_file_ids),r.source_each_cm,r.source_overall_cm,r.source_finish,r.cautions,r.next_action,r.sq_id,r.sh_handle]);
const mapping=makeTable('Dropbox Mapping','Matched platform records mapped to Dropbox','Current Dropbox metadata checked '+dropbox.checked_utc+'. Source images were checked against the reviewed file hashes.',
 ['Match ID','Shared SKU','Platform product','Dropbox evidence level','Family-folder references','Confirmed image member / arrangement folder','Source component count','Individual component identification','Current member / arrangement path','Stable member folder ID','Register group ID','Reviewed source image path','Stable source file ID','Current family-folder paths','Stable family folder IDs','Gallery-only folder reference','Gallery-only source file ID','Source component dimensions (cm)','Source overall dimensions (cm)','Source finish','Scope and cautions','Next action','Squarespace product ID','Shopify handle'],mapRows,[16,30,65,62,48,76,21,110,165,45,27,190,45,165,45,165,45,65,65,75,190,140,37,52],{headerRow:11,wrap:[1,2,3,4,5,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,23],numbers:[6],headerHeight:54,notes:[['A8','Link the sale arrangement to separate component identities. A matched set photograph does not identify every individual sculpture or every other file in its folder.'],['A9','Component counts, dimensions and finishes below are source claims for the native offer. Family references and gallery-only photographs do not transfer those specifications to a folder.']]});
mapping.sh.tabColor=green;
mapping.sh.getRange('A5:D5').values=[['Platform product pairs',null,'Member / arrangement image links',null]];
mapping.sh.getRange('A7:D7').values=[['Family references only',null,'Gallery references only',null]];
mapping.sh.getRange('B5').formulas=[[`=COUNTA('Dropbox Mapping'!A${mapping.first}:A${mapping.last})`]];
mapping.sh.getRange('D5').formulas=[[`=COUNTIFS('Dropbox Mapping'!D${mapping.first}:D${mapping.last},"Member / arrangement image confirmed")`]];
mapping.sh.getRange('B7').formulas=[[`=COUNTIFS('Dropbox Mapping'!D${mapping.first}:D${mapping.last},"Family reference only; individual unresolved")`]];
mapping.sh.getRange('D7').formulas=[[`=COUNTIFS('Dropbox Mapping'!D${mapping.first}:D${mapping.last},"Gallery reference only; arrangement unresolved")`]];
for(const address of ['B5','D5','B7','D7']){mapping.sh.getRange(address).format.font={name:font,size:13,bold:true,color:ink};mapping.sh.getRange(address).format.horizontalAlignment='center';mapping.sh.getRange(address).setNumberFormat('#,##0');}
mapping.sh.getRange(`D${mapping.first}:D${mapping.last}`).conditionalFormats.add('containsText',{text:'unresolved',format:{fill:'#FFF0CF',font:{color:'#775211'}}});
mapping.sh.getRange(`H${mapping.first}:H${mapping.last}`).conditionalFormats.add('containsText',{text:'still require',format:{fill:'#FFF0CF',font:{color:'#775211'}}});

matches.sh.getRange('A5:G7').values=[
 ['Source population','Products','Confirmed matches','Unmatched','Source native rows','Matched native rows','Unmatched native rows'],
 ['Squarespace',null,null,null,null,null,null],
 ['Shopify main',null,null,null,null,null,null]
];
matches.sh.getRange('A5:G5').format={font:{name:font,size:10,bold:true,color:ink},wrapText:true,rowHeight:32};
matches.sh.getRange('A6:G7').format.rowHeight=28;
matches.sh.getRange('B6:G7').setNumberFormat('#,##0');
matches.sh.getRange('B6:G7').format.horizontalAlignment='center';
matches.sh.getRange('B6:G7').format.font={name:font,size:12,bold:true,color:ink};
matches.sh.getRange('A8').values=[['Historical Shopify: nine separate records, including one exact-SKU match and eight candidates. These versions are excluded from the main product totals above.']];
matches.sh.getRange('A8:A9').format.font={name:font,size:10,italic:true,color:muted};
matches.sh.getRange('B6').formulas=[[`=COUNTIFS('Squarespace Records'!F${sqRecords.first}:F${sqRecords.last},"Product / primary variant")`]];
matches.sh.getRange('C6').formulas=[[`=COUNTA('Matched Products'!A${matches.first}:A${matches.last})`]];
matches.sh.getRange('D6').formulas=[[`=COUNTA('Squarespace Only'!A${ssOnly.first}:A${ssOnly.last})`]];
matches.sh.getRange('E6').formulas=[[`=COUNTA('Squarespace Records'!A${sqRecords.first}:A${sqRecords.last})`]];
matches.sh.getRange('F6').formulas=[[`=COUNTIFS('Squarespace Records'!B${sqRecords.first}:B${sqRecords.last},"Matched")`]];
matches.sh.getRange('G6').formulas=[[`=COUNTIFS('Squarespace Records'!B${sqRecords.first}:B${sqRecords.last},"Squarespace only")`]];
matches.sh.getRange('B7').formulas=[[`=COUNTIFS('Shopify Records'!E${shRecords.first}:E${shRecords.last},"Product / primary variant")`]];
matches.sh.getRange('C7').formulas=[['=C6']];
matches.sh.getRange('D7').formulas=[[`=COUNTA('Shopify Only'!A${shOnly.first}:A${shOnly.last})`]];
matches.sh.getRange('E7').formulas=[[`=COUNTA('Shopify Records'!A${shRecords.first}:A${shRecords.last})`]];
matches.sh.getRange('F7').formulas=[[`=COUNTIFS('Shopify Records'!B${shRecords.first}:B${shRecords.last},"Matched")`]];
matches.sh.getRange('G7').formulas=[[`=COUNTIFS('Shopify Records'!B${shRecords.first}:B${shRecords.last},"Shopify only")`]];

wb.recalculate();
console.log((await wb.inspect({kind:'table',range:'Dropbox Mapping!A5:D7',include:'values,formulas',tableMaxRows:3,tableMaxCols:4,maxChars:1800})).ndjson);
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:20},summary:'Formula error scan',maxChars:1000})).ndjson);
// The six existing sheets retain the same values, formulas and formatting.
// Render the newly added mapping view and its source/applicability columns.
const ranges={'Dropbox Mapping':['A1:H16','A27:H32','I11:Q16','R11:V16']};
for(const [name,rr] of Object.entries(ranges))for(let i=0;i<rr.length;i++){
 const image=await wb.render({sheetName:name,range:rr[i],scale:1,format:'png'});
 await fs.writeFile(path.join(previewDir,name.replaceAll(' ','_')+'_'+(i+1)+'.png'),new Uint8Array(await image.arrayBuffer()));
}
const output=path.join(outputDir,'Boldstone_Squarespace_Shopify_Matched_Unmatched_2026-10-16.xlsx');
await (await SpreadsheetFile.exportXlsx(wb)).save(output);
const manifest={output,source_sha256:data.source_sha256,counts:data.counts,sheets:{
 'Dropbox Mapping':{first:mapping.first,count:mapping.rows,headers:mapping.headers},
 'Matched Products':{first:matches.first,count:matches.rows,headers:matches.headers},
 'Squarespace Only':{first:ssOnly.first,count:ssOnly.rows,headers:ssOnly.headers},
 'Shopify Only':{first:shOnly.first,count:shOnly.rows,headers:shOnly.headers},
 'Historical Shopify':{first:historical.first,count:historical.rows,headers:historical.headers,prefix:oldPrefix.length},
 'Squarespace Records':{first:sqRecords.first,count:sqRecords.rows,headers:sqRecords.headers,prefix:ssPrefix.length},
 'Shopify Records':{first:shRecords.first,count:shRecords.rows,headers:shRecords.headers,prefix:shPrefix.length}
},dropbox_mapping_counts:dropbox.counts};
await fs.writeFile(path.join(project,'evidence/platform_comparison_export.json'),JSON.stringify(manifest));
console.log(JSON.stringify({output,sheets:Object.keys(sheets).length,counts:data.counts}));
