import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {FileBlob, SpreadsheetFile, Workbook} from '@oai/artifact-tool';

const work = path.dirname(new URL(import.meta.url).pathname);
const root = '/Users/tprice/Documents/boldstone';
const packetPath = path.join(root, 'sculpture-catalogue/components/reconciliation/acanthus-native-availability-2026-10-25/workbook-cutoff-packet.json');
const packet = JSON.parse(await fs.readFile(packetPath, 'utf8'));
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
for (const [key, hashKey] of [['source_workbook','source_workbook_sha256'],['overlay_path','overlay_sha256'],['register_path','register_sha256']]) {
  if (sha(await fs.readFile(packet[key])) !== packet[hashKey]) throw new Error('Input changed: '+key);
}
const mode = process.argv[2] || 'baseline';
if (mode === 'timestamp-check') {
  const test=Workbook.create();
  const sheet=test.worksheets.add('Literal check');
  const source='2026-10-25T18:14:51.884978+00:00';
  sheet.getRange('A1:A3').setNumberFormat('@');
  sheet.getRange('A1:A3').values=[[source],["'"+source],['UTC: '+source]];
  console.log(JSON.stringify(sheet.getRange('A1:A3').values));
  process.exit(0);
}
const finalReadback = mode === 'final-readback';
console.log('Importing '+(finalReadback ? 'v3' : 'v2')+' for '+mode);
const wb = await SpreadsheetFile.importXlsx(await FileBlob.load(finalReadback ? packet.output_workbook : packet.source_workbook));
console.log('Import complete');
await fs.mkdir(path.join(work, 'previews'), {recursive:true});
const render = async (label, sheetName, range, scale=1) => {
  const blob = await wb.render({sheetName, range, scale, format:'png'});
  const destination = path.join(work, 'previews', label+'.png');
  await fs.writeFile(destination, new Uint8Array(await blob.arrayBuffer()));
  console.log('Rendered '+label);
  return {path:destination, sheetName, range};
};
if (mode === 'baseline') {
  console.log(wb.help('range.hyperlink', {include:'index,examples,notes',maxChars:2500}).ndjson);
  const inspections = [];
  for (const [sheetId,range] of [['Wall Sculptures','L8:M12'],['Products','Z6:AC9'],['Overview','A12:C13']]) {
    inspections.push((await wb.inspect({kind:'region',sheetId,range,maxChars:2200,tableMaxRows:6,tableMaxCols:5,tableMaxCellChars:130})).ndjson);
  }
  await fs.writeFile(path.join(work,'baseline-inspection.ndjson'), inspections.join('\n'));
  await render('before-wall-links','Wall Sculptures','L8:M12');
  await render('before-product-image-status','Products','Z6:AC9');
  await render('before-wall-availability','Wall Sculptures','Y8:AC12',0.8);
  process.exit(0);
}
if (finalReadback) {
  const checks = JSON.parse(await fs.readFile(path.join(work,'authoring-receipt.json'),'utf8'));
  for (const change of checks.cell_changes) {
    const value = wb.worksheets.getItem(change.sheet).getRange(change.cell).values[0][0];
    if (value !== change.after) throw new Error('Final metadata mismatch '+change.sheet+'!'+change.cell);
  }
  const s = wb.worksheets.getItem('Native Availability');
  for (const [cell,value] of Object.entries({B6:6360,B7:5,B8:6355,B30:345})) {
    if (s.getRange(cell).values[0][0] !== value) throw new Error('Final value mismatch '+cell);
  }
  const previews=[];
  for (const [label,sheetName,range,scale] of [
    ['final-native-opening','Native Availability','A1:E17',0.8],
    ['final-native-survivors','Native Availability','A20:I25',0.65],
    ['final-product-status','Products','Z6:AC9',1],
    ['final-wall-links','Wall Sculptures','L8:M12',1],
    ['final-wall-availability','Wall Sculptures','Y8:AC12',0.8],
    ['final-overview-count','Overview','A11:C14',0.8],
    ['final-guide-qualification','Guide and sources','A17:B19',0.8],
  ]) previews.push(await render(label,sheetName,range,scale));
  const inspection = await wb.inspect({kind:'region',sheetId:'Native Availability',range:'A6:F17',maxChars:4500,tableMaxRows:12,tableMaxCols:6,tableMaxCellChars:120});
  await fs.writeFile(path.join(work,'final-native-inspection.ndjson'),inspection.ndjson);
  await fs.writeFile(path.join(work,'final-readback.json'),JSON.stringify({status:'PASS_SAVED_XLSX_REOPENED',metadata_cells:checks.cell_changes.length,summary_values:{baseline:6360,deleted:5,adjusted:6355,cutoff:345},previews},null,2)+'\n');
  console.log('Final readback passed');
  process.exit(0);
}
if (mode !== 'edit') throw new Error('Unknown mode '+mode);

const overlay = JSON.parse(await fs.readFile(packet.overlay_path,'utf8'));
const original = JSON.parse(await fs.readFile(path.join(work,'baseline-analysis.json'),'utf8'));
const originalValue = (sheet,cell) => original.sheets.find(s=>s.name===sheet).cells[cell];
const changes = [
  ['Wall Sculptures','A6','Coverage: 80 reviewed Squarespace listings + 1 wall-scope review / 224 variants; 38 Shopify listings / variants. Dropbox baseline: 6,360 files / 442 folders; 6,355 files after these five deletions only. See Native Availability.'],
  ['Wall Sculptures','L11','Folder\n(image deleted)'],
  ['Wall Sculptures','AC11','Historical role: Available. Primary 001 deleted; no replacement primary selected. Files 001/002 deleted; 2 of 4 baseline file associations remain after these deletions. See Native Availability.'],
  ['Wall Sculptures','AC12','Primary 002 survives. Gallery 001/003/004 deleted; 4 of 7 baseline file associations remain after these deletions. Other associations include context and qualified candidates. See Native Availability.'],
  ['Products','AA8','Historical role: Available. Primary 001 deleted; no replacement primary selected. See Native Availability.'],
  ['Products','AA9','Primary 002 survives. Gallery 001/003/004 deleted. See Native Availability.'],
  ['Products','AB8','Folder\n(image deleted)'],
  ['Overview','C12','Baseline: 6,360 scoped files + 330 history references. Scoped files after these five deletions only: 6,355. See Native Availability.'],
  ['Guide and sources','B18',originalValue('Guide and sources','B18')+'\nNative Availability: five deletions through event 345. Source IDs/URLs/counts retained. Flower primary opens its folder; Moon 002 survives.'],
];
const cellChanges=[];
for (const [sheet,cell,after] of changes) {
  const range=wb.worksheets.getItem(sheet).getRange(cell);
  const before=range.values[0][0];
  if (before!==originalValue(sheet,cell)) throw new Error('Baseline metadata mismatch '+sheet+'!'+cell);
  range.values=[[after]];
  cellChanges.push({sheet,cell,before,after});
}

const native=wb.worksheets.add('Native Availability');
native.showGridLines=false;
native.tabColor='#536F55';
native.getRange('A1:AE38').format={font:{name:'Arial',size:10,color:'#293238'},verticalAlignment:'top'};
native.getRange('A2').values=[['Native image availability']];
native.getRange('A2').format={font:{name:'Arial',size:16,bold:true,color:'#253A49'},rowHeight:26};
native.getRange('A3').values=[['Five owner-confirmed deletions · 25 October 2026 · review event cutoff 345']];
native.getRange('A4').values=[['Historical source records remain intact. Only the deleted Flower primary link changes to its current containing folder.']];
native.getRange('A3:A4').format.font={name:'Arial',size:10,italic:true,color:'#596770'};
native.getRange('A6:B8').values=[['Baseline scoped Dropbox files',6360],['Confirmed deleted files',null],['Files after these five deletions',null]];
native.getRange('B7').formulas=[['=COUNTA(F13:F17)']];
native.getRange('B8').formulas=[['=B6-B7']];
native.getRange('B6:B8').setNumberFormat('#,##0');
native.getRange('B6:B8').format.font={name:'Arial',size:11,bold:true,color:'#253A49'};
native.getRange('C6').values=[['   Baseline adjusted for these five files only; no new full-library scan.']];
native.getRange('C7').values=[['   442 folders remain in the baseline; these deletions removed no folders.']];
native.getRange('C8').values=[['   Flower: replacement primary not selected. Acanthus and Moon: primary 002 survives.']];
native.getRange('C6:C8').format.font={name:'Arial',size:10,color:'#596770'};
native.getRange('A10').values=[['Deleted files']];
native.getRange('A10').format.font={name:'Arial',size:11,bold:true,color:'#253A49'};

const columns=['File','Sculpture','Availability','Effect on master primary','Current folder','Stable file ID','Revision at deletion','Actual folder ID','Historical image URL','Historical path','Bytes at deletion','Confirmed UTC','Deletion readback UTC','Independent readback UTC','Review cutoff','Operation ID','Batch ID','Reason','Deletion receipt','Receipt SHA256','Native inspection receipt','Native inspection SHA256','Content hash at deletion','Native lookup result','Audit event IDs','Source master option ID','Same-folder option ID','Historical records retained','Replacement primary selected','Machine status','Former primary action URL'];
const col=n=>{let s='';for(let k=n+1;k;k=Math.floor((k-1)/26))s=String.fromCharCode(65+(k-1)%26)+s;return s;};
const rows=[...overlay.rows].sort((a,b)=>a.name.localeCompare(b.name));
const nativeReceipt=Object.keys(overlay.source_evidence).find(p=>p.endsWith('/native-inspection.json'));
const nativeLinks=[];
const previewUrl=path => 'https://www.dropbox.com/preview'+path.replace(/^ns:\d+\/\//,'/').split('/').map(encodeURIComponent).join('/');
const data=rows.map((r,i)=>{
  const flower=r.name.includes('acanthus-flower');
  const sourceReceipt=Object.keys(overlay.source_evidence).find(p=>p.endsWith(flower?'/acanthus-flower-deletion-readback-20261025.json':'/acanthus-and-moon-white-deletion-readback-20261025.json'));
  nativeLinks.push({cell:'E'+(i+13),target:r.folder_url,display:'Open folder'});
  nativeLinks.push({cell:'S'+(i+13),target:sourceReceipt,display:sourceReceipt});
  nativeLinks.push({cell:'U'+(i+13),target:nativeReceipt,display:nativeReceipt});
  const primary=r.source_master_example_option_ids.length>0;
  return [r.name,flower?'Acanthus Flower':'Acanthus Full / Acanthus and Moon','Deleted — absence verified',primary?'Historical primary deleted; replacement not selected':'Gallery image only; '+(flower?'Flower primary 001 also deleted':'primary 002 survives'),'Open folder',r.file_id,r.revision_at_deletion,r.folder_id,r.historical_image_url,r.historical_path,r.bytes_at_deletion,'UTC: '+r.user_confirmation_utc,'UTC: '+r.deletion_readback_utc,'UTC: '+r.independent_native_readback.checked_utc,345,r.operation_id,r.batch_id,r.reason,sourceReceipt,overlay.source_evidence[sourceReceipt],nativeReceipt,overlay.source_evidence[nativeReceipt],r.content_hash_at_deletion,r.root_connector_lookup,r.audit_events.map(x=>x.id).join(', '),r.source_master_example_option_ids.join('\n'),r.same_folder_option_ids.join('\n'),'Yes','No',r.status,primary?previewUrl(r.historical_path):''];
});
native.getRange('A12:AE12').values=[columns];
native.getRange('A13:AE17').setNumberFormat('@');
native.getRange('A13:AE17').values=data;
native.getRange('K13:K17').setNumberFormat('#,##0');
native.getRange('O13:O17').setNumberFormat('0');
const deletions=native.tables.add('A12:AE17',true,'NativeAvailabilityDeletedFiles');
deletions.style='TableStyleLight1';
deletions.showFilterButton=true;
native.getRange('A12:AE12').format={fill:'#354A59',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},wrapText:true,horizontalAlignment:'center',verticalAlignment:'center',rowHeight:44};
native.getRange('A13:E17').format.wrapText=true;
native.getRange('X13:AD17').format.wrapText=true;
native.getRange('A13:AE17').format.rowHeight=36;
native.getRange('E13:E17').format.font={name:'Arial',size:10,color:'#145D87',underline:'single'};
native.getRange('S13:S17').format.font={name:'Arial',size:10,color:'#145D87',underline:'single'};
native.getRange('U13:U17').format.font={name:'Arial',size:10,color:'#145D87',underline:'single'};

native.getRange('A20').values=[['Surviving files in the two checked folders']];
native.getRange('A20').format.font={name:'Arial',size:11,bold:true,color:'#253A49'};
const survivorColumns=['File','Sculpture','Availability','Master primary status','Current folder','Stable file ID','Revision','Bytes','Current image URL'];
native.getRange('A22:I22').values=[survivorColumns];
const survivors=overlay.remaining_verified_files.map(x=>x.metadata).sort((a,b)=>a.name.localeCompare(b.name));
const survivorData=survivors.map((r,i)=>{
  const flower=r.name.includes('acanthus-flower');
  const folder=rows.find(x=>x.name.includes(flower?'acanthus-flower':'acanthus-and-moon')).folder_url;
  const image='https://www.dropbox.com/preview'+r.path_display.split('/').map(encodeURIComponent).join('/');
  nativeLinks.push({cell:'E'+(i+23),target:folder,display:'Open folder'});
  nativeLinks.push({cell:'I'+(i+23),target:image,display:image});
  return [r.name,flower?'Acanthus Flower':'Acanthus Full / Acanthus and Moon','Available — metadata verified',r.id===overlay.surviving_master_example.file_id?'Existing master primary retained':'Not selected as a new master primary','Open folder',r.id,r.rev,r.size,image];
});
native.getRange('A23:I25').values=survivorData;
native.getRange('H23:H25').setNumberFormat('#,##0');
const survivingTable=native.tables.add('A22:I25',true,'NativeAvailabilitySurvivingFiles');
survivingTable.style='TableStyleLight1';
native.getRange('A22:I22').format={fill:'#354A59',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},wrapText:true,horizontalAlignment:'center',verticalAlignment:'center',rowHeight:44};
native.getRange('A23:E25').format.wrapText=true;
native.getRange('A23:I25').format.rowHeight=36;
native.getRange('E23:E25').format.font={name:'Arial',size:10,color:'#145D87',underline:'single'};
native.getRange('I23:I25').format.font={name:'Arial',size:10,color:'#145D87',underline:'single'};

native.getRange('A28').values=[['Scope and provenance']];
native.getRange('A28').format.font={name:'Arial',size:11,bold:true,color:'#253A49'};
const provenance=[
  ['Scope','Five confirmed deletions only. The source inventories, product identities, specifications and app review choices are retained at their recorded versions.'],
  ['Review event cutoff',345],
  ['Availability record UTC','UTC: '+overlay.recorded_utc],
  ['Availability evidence',packet.overlay_path],
  ['Availability SHA256',packet.overlay_sha256],
  ['Workbook baseline',packet.source_workbook],
  ['Workbook baseline SHA256',packet.source_workbook_sha256],
  ['Cutoff packet',packetPath],
  ['Cutoff packet SHA256',sha(await fs.readFile(packetPath))],
  ['Folder child-list checks','Both direct folder lists completed with has_more=false; Flower has 1 surviving file, Acanthus and Moon White has 2.'],
];
native.getRange('A29:B38').setNumberFormat('@');
native.getRange('A29:B38').values=provenance;
native.getRange('B30').setNumberFormat('0');
const widths=[54,44,31,48,20,42,29,42,122,116,20,39,39,39,18,43,43,23,122,70,122,70,70,95,22,36,36,27,28,72,122];
for(let i=0;i<widths.length;i++)native.getRange(col(i)+'1:'+col(i)+'38').format.columnWidth=widths[i];
native.freezePanes.freezeRows(12);
native.freezePanes.freezeColumns(2);

wb.recalculate();
for(const [cell,expected] of Object.entries({B6:6360,B7:5,B8:6355,B30:345}))if(native.getRange(cell).values[0][0]!==expected)throw new Error('Calculation mismatch '+cell);
for(let i=0;i<data.length;i++)for(let j=0;j<data[i].length;j++){
  const got=native.getRange(col(j)+(i+13)).values[0][0];
  if((got??'')!==(data[i][j]??''))throw new Error('Authored value mismatch '+col(j)+(i+13));
}
const errors=await wb.inspect({kind:'match',sheetId:'Native Availability',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},maxChars:2500});
await fs.writeFile(path.join(work,'formula-scan.ndjson'),errors.ndjson);
await (await SpreadsheetFile.exportXlsx(wb)).save(path.join(work,'authored-stage.xlsx'));
const flower=rows.find(r=>r.source_master_example_option_ids.length>0);
const hyperlinkChanges=[
  {sheet:'Wall Sculptures',cell:'L11',before:previewUrl(flower.historical_path),after:flower.folder_url,display:'Folder\n(image deleted)'},
  {sheet:'Products',cell:'AB8',before:previewUrl(flower.historical_path),after:flower.folder_url,display:'Folder\n(image deleted)'},
];
const receipt={status:'PASS_ARTIFACT_AUTHORED',source_sha256:packet.source_workbook_sha256,packet_sha256:sha(await fs.readFile(packetPath)),overlay_sha256:packet.overlay_sha256,cell_changes:cellChanges,hyperlink_changes:hyperlinkChanges,native_links:nativeLinks,new_sheet:'Native Availability',deleted_columns:columns,deleted_rows:data,survivor_columns:survivorColumns,survivor_rows:survivorData,provenance,expected_summary:{baseline:6360,deleted:5,adjusted:6355,cutoff:345},native_hyperlinks_via_preservation_adapter:true};
await fs.writeFile(path.join(work,'authoring-receipt.json'),JSON.stringify(receipt,null,2)+'\n');
console.log('Artifact-authored stage saved; '+cellChanges.length+' metadata cells, 5 deletion rows, 3 surviving files.');
