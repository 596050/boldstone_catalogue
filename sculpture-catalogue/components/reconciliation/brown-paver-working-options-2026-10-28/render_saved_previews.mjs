import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const h=path.dirname(fileURLToPath(import.meta.url));
const plans=JSON.parse(await fs.readFile(path.join(h,'workbook-edit-plan.json'),'utf8')).plans;
const onlyLabel=process.argv.find(x=>x.startsWith('--only-label='))?.slice('--only-label='.length);
for(const p of plans){
  if(process.argv[2]&&process.argv[2]!==p.key)continue;
  const b=await SpreadsheetFile.importXlsx(await FileBlob.load(p.output));
  for(const[sheetName,range,label]of p.previews){
    if(onlyLabel&&label!==onlyLabel)continue;
    const s=b.worksheets.getItem(sheetName),r=s.getRange(range),forms=r.formulas;
    // Render the independently verified saved friendly-name caches. The SDK
    // cannot calculate HYPERLINK. This display-only copy is never exported.
    for(let row=0;row<forms.length;row++)for(let col=0;col<forms[row].length;col++){
      const m=String(forms[row][col]||'').match(/^=?HYPERLINK\("(?:[^"]|"")*","((?:[^"]|"")*)"\)$/i);
      if(m)r.getCell(row,col).values=[[m[1].replaceAll('""','"')]];
    }
    const blob=await b.render({sheetName,range,scale:1.2,format:'png'});
    await fs.writeFile(path.join(h,'previews','saved-'+label+'.png'),new Uint8Array(await blob.arrayBuffer()));
  }
  console.log(p.key+' SAVED_NATIVE_DISPLAY_RENDERED_NO_EXPORT');
}
