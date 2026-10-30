import fs from 'node:fs/promises';
import {SpreadsheetFile,FileBlob} from '@oai/artifact-tool';
const base='/Users/tprice/Documents/boldstone/sculpture-catalogue/components/parallel-reviews/matched-listing-finalization-20261025-B';
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load('/Users/tprice/Documents/boldstone/sculpture-catalogue/outputs/01a13fe6-495b-7253-b923-31823b4cbca8/matched-listing-2026-10-25/Boldstone_Matched_Product_List_2026-10-25.xlsx'));
for(const [sheet,range,name] of [['Products','G1:P11','Products-right'],['Changes','E33:H37','Changes-face-sizes'],['Listing matches','G1:N10','Listing-matches-right'],['Source associations','G1:L10','Source-associations-right']]){
 const b=await wb.render({sheetName:sheet,range,scale:1,format:'png'});
 await fs.writeFile(`${base}/previews/${name}.png`,new Uint8Array(await b.arrayBuffer()));
}
console.log('Saved columns and face-size change previews ready.');
