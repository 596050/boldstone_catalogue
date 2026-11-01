import fs from 'node:fs/promises';
import {Workbook} from '@oai/artifact-tool';
const out=new URL('.',import.meta.url), input=JSON.parse(await fs.readFile(new URL('channel-supplement-manifest.json',out),'utf8'));
const quote=v=>'"'+String(v??'').replaceAll('"','""')+'"';
for(const channel of ['meta','google']){
 const data=input[channel],book=Workbook.create(),sheet=book.worksheets.add(channel);
 const matrix=[data.headers,...data.rows.map(r=>data.headers.map(h=>r[h]))];
 sheet.getRangeByIndexes(0,0,matrix.length,data.headers.length).values=matrix;
 const read=sheet.getRangeByIndexes(0,0,matrix.length,data.headers.length).values;
 for(let r=0;r<read.length;r++)for(let c=0;c<data.headers.length;c++)if(String(read[r][c]??'')!==String(matrix[r][c]??''))throw Error('Cell mismatch');
 await fs.writeFile(new URL(channel+'-wall-sculptures-supplement.csv',out),read.map(r=>r.map(quote).join(',')).join('\r\n')+'\r\n');
 if(channel==='google'){await fs.writeFile(new URL('google-wall-sculptures-supplement.tsv',out),read.map(r=>r.map(v=>String(v??'').replace(/[\t\r\n]+/g,' ')).join('\t')).join('\r\n')+'\r\n');}
}
console.log(JSON.stringify({products:176,channels:['meta','google']}));
