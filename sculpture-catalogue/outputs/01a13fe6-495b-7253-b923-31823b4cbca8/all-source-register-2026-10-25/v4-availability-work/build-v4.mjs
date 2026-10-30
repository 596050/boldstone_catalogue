import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {Workbook, FileBlob, SpreadsheetFile} from '@oai/artifact-tool';

const work = path.dirname(new URL(import.meta.url).pathname);
const root = '/Users/tprice/Documents/boldstone';
const packetPath = path.join(root, 'sculpture-catalogue/components/reconciliation/six-native-deletions-and-app-review-2026-10-25/workbook-cutoff-packet.json');
const packet = JSON.parse(await fs.readFile(packetPath, 'utf8'));
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
for (const [key, hashKey] of [['baseline_workbook','baseline_workbook_sha256'],['overlay_path','overlay_sha256']]) {
  if (sha(await fs.readFile(packet[key])) !== packet[hashKey]) throw new Error('Input changed: '+key);
}
const mode = process.argv[2] || 'baseline';
await fs.mkdir(path.join(work,'previews'),{recursive:true});
const render = async (wb, label, sheetName, range, scale=0.8) => {
  const blob = await wb.render({sheetName,range,scale,format:'png'});
  const output=path.join(work,'previews',label+'.png');
  await fs.writeFile(output,new Uint8Array(await blob.arrayBuffer()));
  console.log('Rendered '+label);
  return {path:output,sheetName,range};
};
if (mode === 'baseline' || mode === 'final-readback') {
  console.log('Importing '+mode);
  const wb = await SpreadsheetFile.importXlsx(await FileBlob.load(mode==='baseline'?packet.baseline_workbook:packet.output_workbook));
  console.log('Import complete');
  const previews=[];
  if(mode==='baseline') {
    previews.push(await render(wb,'before-icarus-product','Products','Z99:AC101'));
    previews.push(await render(wb,'before-icarus-wall','Wall Sculptures','AC8:AC10'));
  } else {
    const a=JSON.parse(await fs.readFile(path.join(work,'authoring-receipt.json'),'utf8'));
    for(const c of a.cell_changes) if(wb.worksheets.getItem(c.sheet).getRange(c.cell).values[0][0]!==c.after)throw new Error('Metadata mismatch '+c.sheet+'!'+c.cell);
    for(const [cell,value] of Object.entries({B6:6360,B7:6,B8:6354,B30:347}))if(wb.worksheets.getItem('Native Availability').getRange(cell).values[0][0]!==value)throw new Error('Count mismatch '+cell);
    for(const [label,sheet,range,scale] of [
      ['final-native-opening','Native Availability','A1:E18',0.8],
      ['final-native-survivors','Native Availability','A20:I26',0.65],
      ['final-icarus-product','Products','Z99:AC101',0.8],
      ['final-icarus-wall','Wall Sculptures','AC8:AC10',0.8],
      ['final-overview','Overview','A11:C14',0.8],
      ['final-guide','Guide and sources','A17:B19',0.8],
      ['final-coverage','Wall Sculptures','A6:F6',0.8]
    ]) previews.push(await render(wb,label,sheet,range,scale));
  }
  await fs.writeFile(path.join(work,mode+'.json'),JSON.stringify({status:'PASS_SAVED_XLSX_REOPENED',previews},null,2)+'\n');
  process.exit(0);
}
if(mode!=='edit')throw new Error('Unknown mode '+mode);
const overlay=JSON.parse(await fs.readFile(packet.overlay_path,'utf8'));
const baseline=JSON.parse(await fs.readFile(path.join(work,'baseline-analysis.json'),'utf8'));
const old=(sheet,cell)=>baseline.sheets.find(s=>s.name===sheet).cells[cell];
const changes=[
  ['Wall Sculptures','A6',old('Wall Sculptures','A6').replace('6,355','6,354').replace('five deletions','six deletions')],
  ['Wall Sculptures','AC9','Primary 010 survives. Gallery 007 deleted; 12 of 13 baseline file associations remain after this deletion. Other associations include context and qualified candidates. See Native Availability.'],
  ['Products','AA100','Primary 010 survives. Gallery 007 deleted. See Native Availability.'],
  ['Overview','C12',old('Overview','C12').replace('6,355','6,354').replace('five deletions','six deletions')],
  ['Guide and sources','B18',old('Guide and sources','B18').split('\nNative Availability:')[0]+'\nNative Availability: six verified deletions in snapshot 347 (last native event 342). Source IDs/URLs/counts retained. Flower opens its folder; Moon 002 and Icarus 010 survive.'],
];
// Artifact authors only the declared metadata and availability worksheet. The
// preservation adapter transfers these into v3 without reserializing source data.
const wb=Workbook.create();
for(const name of [...new Set(changes.map(x=>x[0]))])wb.worksheets.add(name);
const cellChanges=changes.map(([sheet,cell,after])=>{
  wb.worksheets.getItem(sheet).getRange(cell).values=[[after]];
  return {sheet,cell,before:old(sheet,cell),after};
});
const native=wb.worksheets.add('Native Availability');
native.showGridLines=false;
native.tabColor='#536F55';
native.getRange('A1:AE38').format={font:{name:'Arial',size:10,color:'#293238'},verticalAlignment:'top'};
native.getRange('A2').values=[['Native image availability']];
native.getRange('A2').format={font:{name:'Arial',size:16,bold:true,color:'#253A49'},rowHeight:26};
native.getRange('A3').values=[['Six owner-confirmed deletions - 25 October 2026 - snapshot 347; last native event 342']];
native.getRange('A4').values=[['Historical source records remain intact. Existing Flower folder links and all other primary image links are retained.']];
native.getRange('A3:A4').format.font={name:'Arial',size:10,italic:true,color:'#596770'};
native.getRange('A6:B8').values=[['Baseline scoped Dropbox files',6360],['Confirmed deleted files',null],['Files after these six deletions',null]];
native.getRange('B7').formulas=[['=COUNTA(F13:F18)']];
native.getRange('B8').formulas=[['=B6-B7']];
native.getRange('B6:B8').setNumberFormat('#,##0');
native.getRange('B6:B8').format.font={name:'Arial',size:11,bold:true,color:'#253A49'};
native.getRange('C6').values=[['   Baseline adjusted for these six files only; no new full-library scan.']];
native.getRange('C7').values=[['   442 folders remain in the baseline; these deletions removed no folders.']];
native.getRange('C8').values=[['   Flower: no replacement selected. Acanthus and Moon 002 and Icarus 010 survive.']];
native.getRange('C6:C8').format.font={name:'Arial',size:10,color:'#596770'};
native.getRange('A10').values=[['Deleted files']];
native.getRange('A10').format.font={name:'Arial',size:11,bold:true,color:'#253A49'};
const oldReceipt=JSON.parse(await fs.readFile(path.join(work,'../v3-availability-work/authoring-receipt.json'),'utf8'));
const columns=oldReceipt.deleted_columns;
const rows=[...overlay.rows].sort((a,b)=>a.name.localeCompare(b.name));
const type=r=>r.name.includes('abstract-cave')?'icarus':r.name.includes('acanthus-flower')?'flower':'moon';
const sculpture=r=>({icarus:'Icarus / Abstract Cave Paintings 1',flower:'Acanthus Flower',moon:'Acanthus Full / Acanthus and Moon'})[type(r)];
const findEvidence=suffix=>{const p=Object.keys(overlay.source_evidence).find(p=>p.endsWith(suffix));if(!p)throw new Error('Missing evidence '+suffix);return p;};
const oldNative=findEvidence('/acanthus-native-availability-2026-10-25/native-inspection.json');
const newNative=findEvidence('/six-native-deletions-and-app-review-2026-10-25/native-inspection.json');
const nativeLinks=[];
const previewUrl=p=>'https://www.dropbox.com/preview'+p.replace(/^ns:\d+\/\//,'/').split('/').map(encodeURIComponent).join('/');
const data=rows.map((r,i)=>{
  const t=type(r), primary=r.source_master_example_option_ids.length>0;
  const receipt=findEvidence(t==='icarus'?'/specification-completion-20261025/before-live-state.json':t==='flower'?'/acanthus-flower-deletion-readback-20261025.json':'/acanthus-and-moon-white-deletion-readback-20261025.json');
  const inspection=t==='icarus'?newNative:oldNative;
  nativeLinks.push({cell:'E'+(i+13),target:r.folder_url,display:'Open folder'},{cell:'S'+(i+13),target:receipt,display:receipt},{cell:'U'+(i+13),target:inspection,display:inspection});
  const effect=primary?'Historical primary deleted; replacement not selected':t==='icarus'?'Gallery image only; primary 010 survives':t==='flower'?'Gallery image only; Flower primary 001 also deleted':'Gallery image only; primary 002 survives';
  return [r.name,sculpture(r),'Deleted - absence verified',effect,'Open folder',r.file_id,r.revision_at_deletion,r.folder_id,r.historical_image_url,r.historical_path,r.bytes_at_deletion,'UTC: '+r.user_confirmation_utc,'UTC: '+r.deletion_readback_utc,'UTC: '+r.independent_native_readback.checked_utc,347,r.operation_id,r.batch_id,r.reason,receipt,overlay.source_evidence[receipt],inspection,overlay.source_evidence[inspection],r.content_hash_at_deletion,r.root_connector_lookup??r.independent_native_readback.scope,r.audit_events.map(x=>x.id).join(', '),r.source_master_example_option_ids.join('\n'),r.same_folder_option_ids.join('\n'),'Yes','No',r.status,primary?previewUrl(r.historical_path):''];
});
native.getRange('A12:AE12').values=[columns];
native.getRange('A13:AE18').setNumberFormat('@');
native.getRange('A13:AE18').values=data;
native.getRange('K13:K18').setNumberFormat('#,##0');
native.getRange('O13:O18').setNumberFormat('0');
const deletedTable=native.tables.add('A12:AE18',true,'NativeAvailabilityDeletedFiles');
deletedTable.style='TableStyleLight1';deletedTable.showFilterButton=true;
const header={fill:'#354A59',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},wrapText:true,horizontalAlignment:'center',verticalAlignment:'center',rowHeight:44};
native.getRange('A12:AE12').format=header;
native.getRange('A13:E18').format.wrapText=true;
native.getRange('X13:AD18').format.wrapText=true;
native.getRange('A13:AE18').format.rowHeight=44;
const linkFont={name:'Arial',size:10,color:'#145D87',underline:'single'};
for(const c of ['E','S','U'])native.getRange(c+'13:'+c+'18').format.font=linkFont;
native.getRange('A20').values=[['Verified surviving reference files in the three checked folders']];
native.getRange('A20').format.font={name:'Arial',size:11,bold:true,color:'#253A49'};
const survivorColumns=oldReceipt.survivor_columns;
native.getRange('A22:I22').values=[survivorColumns];
const survivors=overlay.remaining_verified_files.map(x=>x.metadata).sort((a,b)=>a.name.localeCompare(b.name));
const survivorData=survivors.map((r,i)=>{
  const folder=rows.find(x=>type(x)===type(r)).folder_url;
  const image=previewUrl(r.path_display);
  nativeLinks.push({cell:'E'+(i+23),target:folder,display:'Open folder'},{cell:'I'+(i+23),target:image,display:image});
  return [r.name,sculpture(r),'Available - metadata verified',[overlay.surviving_master_example.file_id,'id:cnqzTNngPVsAAAAAAAt_oA'].includes(r.id)?'Existing master primary retained':'Not selected as a new master primary','Open folder',r.id,r.rev,r.size,image];
});
native.getRange('A23:I26').values=survivorData;
native.getRange('H23:H26').setNumberFormat('#,##0');
const survivingTable=native.tables.add('A22:I26',true,'NativeAvailabilitySurvivingFiles');
survivingTable.style='TableStyleLight1';
native.getRange('A22:I22').format=header;
native.getRange('A23:E26').format.wrapText=true;
native.getRange('A23:I26').format.rowHeight=44;
for(const c of ['E','I'])native.getRange(c+'23:'+c+'26').format.font=linkFont;
native.getRange('A28').values=[['Scope and provenance']];
native.getRange('A28').format.font={name:'Arial',size:11,bold:true,color:'#253A49'};
const provenance=[
  ['Scope','Six confirmed deletions only; latest native event 342. Source inventories, identities, specifications and app reviews are retained. Icarus 007 was outside the previous five-ID review set; its deletion preceded snapshot 345.'],
  ['Review event cutoff',347],
  ['Availability record UTC','UTC: '+overlay.recorded_utc],
  ['Availability evidence',packet.overlay_path],
  ['Availability SHA256',packet.overlay_sha256],
  ['Workbook baseline',packet.baseline_workbook],
  ['Workbook baseline SHA256',packet.baseline_workbook_sha256],
  ['Cutoff packet',packetPath],
  ['Cutoff packet SHA256',sha(await fs.readFile(packetPath))],
  ['Folder child-list checks','All three direct lists completed with has_more=false: Flower 1 file, Acanthus and Moon White 2, Abstract Cave Paintings 1 White 10. Four reference files shown above; other surviving Icarus files remain in the source inventory.'],
];
native.getRange('A29:B38').setNumberFormat('@');native.getRange('A29:B38').values=provenance;
native.getRange('B30').setNumberFormat('0');
const col=n=>{let s='';for(let k=n+1;k;k=Math.floor((k-1)/26))s=String.fromCharCode(65+(k-1)%26)+s;return s;};
const widths=[54,44,31,48,20,42,29,42,122,116,20,39,39,39,18,43,43,23,122,70,122,70,70,95,22,36,36,27,28,72,122];
for(let i=0;i<widths.length;i++)native.getRange(col(i)+'1:'+col(i)+'38').format.columnWidth=widths[i];
native.freezePanes.freezeRows(12);native.freezePanes.freezeColumns(2);
wb.recalculate();
for(const [cell,expected] of Object.entries({B6:6360,B7:6,B8:6354,B30:347}))if(native.getRange(cell).values[0][0]!==expected)throw new Error('Calculation mismatch '+cell);
for(let i=0;i<data.length;i++)for(let j=0;j<data[i].length;j++)if((native.getRange(col(j)+(i+13)).values[0][0]??'')!==(data[i][j]??''))throw new Error('Value mismatch '+col(j)+(i+13));
const errors=await wb.inspect({kind:'match',sheetId:'Native Availability',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},maxChars:2500});
await fs.writeFile(path.join(work,'formula-scan.ndjson'),errors.ndjson);
await (await SpreadsheetFile.exportXlsx(wb)).save(path.join(work,'authored-stage.xlsx'));
const receipt={status:'PASS_ARTIFACT_AUTHORED',baseline_sha256:packet.baseline_workbook_sha256,packet_sha256:sha(await fs.readFile(packetPath)),overlay_sha256:packet.overlay_sha256,cell_changes:cellChanges,hyperlink_changes:[],native_links:nativeLinks,deleted_columns:columns,deleted_rows:data,survivor_columns:survivorColumns,survivor_rows:survivorData,provenance,expected_summary:{baseline:6360,deleted:6,adjusted:6354,cutoff:347,last_native_event:342},native_hyperlinks_via_preservation_adapter:true};
await fs.writeFile(path.join(work,'authoring-receipt.json'),JSON.stringify(receipt,null,2)+'\n');
console.log('Artifact-authored stage saved: 5 metadata cells, 6 deleted files and 4 surviving references.');
