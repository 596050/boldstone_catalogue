import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const out=path.dirname(fileURLToPath(import.meta.url));
const receiptName=process.argv[2]||'published-readback.json';
const receipt=JSON.parse(await fs.readFile(path.join(out,receiptName),'utf8'));
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const file=receipt.workbook;
if(sha(await fs.readFile(file))!==receipt.workbook_sha256)throw Error('Publication changed before workbook readback');
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(file));
const sheet=wb.worksheets.getItem('Photo Coverage');
const ids=sheet.getRange('A8:A250').values;
const offset=ids.findIndex(row=>row[0]==='BSI-7B6291B7C7F9');
if(offset<0)throw Error('Strata row missing');
const row=offset+8;
const range=sheet.getRange('A'+row+':V'+row);
const vals=range.values[0],forms=range.formulas[0];
for(const [col,want] of [[2,'Available'],[5,'Available'],[8,'Optional / no fixed set'],[12,'id:cnqzTNngPVsAAAAAAAueFw'],[13,'id:cnqzTNngPVsAAAAAAAyjGQ'],[14,receipt.reference.file_id],[15,receipt.reference.folder_id]]){
 if(vals[col]!==want)throw Error('Unexpected Photo Coverage column '+col+': '+vals[col]);
}
const nativeLinks=JSON.parse(await fs.readFile(path.join(out,'native-hyperlink-check.json'),'utf8'));
if(nativeLinks.status!=='PASS_NATIVE_HYPERLINK_TARGETS'||nativeLinks.workbook_sha256!==receipt.workbook_sha256||nativeLinks.row!==row)throw Error('Saved native hyperlink checks do not match this workbook');
if(nativeLinks.targets['G'+row]!==receipt.reference.image_url||nativeLinks.targets['H'+row]!==receipt.reference.folder_url)throw Error('Current containing-folder hyperlink mismatch');
const inspection=await wb.inspect({kind:'table',range:'Photo Coverage!A'+row+':V'+row,include:'values,formulas',tableMaxRows:1,tableMaxCols:22,maxChars:6000});
if(sha(await fs.readFile(file))!==receipt.workbook_sha256)throw Error('Workbook changed during readback');
await fs.writeFile(path.join(out,receipt.prepared?'prepared-workbook-artifact-readback.json':'workbook-artifact-readback.json'),JSON.stringify({status:'PASS_READ_ONLY_ARTIFACT_ROLE_AND_LINK_CHECK',file,sha256:receipt.workbook_sha256,prepared:receipt.prepared||false,sheet:'Photo Coverage',row,range:'A'+row+':V'+row,inspection:inspection.ndjson,workbook_modified:false,workbook_exported:false},null,2));
console.log(JSON.stringify({status:'PASS_READ_ONLY_ARTIFACT_ROLE_AND_LINK_CHECK',row,sha256:receipt.workbook_sha256}));
