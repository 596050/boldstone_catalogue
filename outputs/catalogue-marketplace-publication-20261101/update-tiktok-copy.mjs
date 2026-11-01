import fs from 'node:fs/promises';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const out=path.dirname(new URL(import.meta.url).pathname);
const source='/Users/tprice/Downloads/Tiktoksellercenter_batchedit_20261101_basic_information_template.xlsx';
const bounded=path.join(out,'tiktok-edit-bounded.xlsx');
execFileSync('python3',['-c',`import sys,zipfile,xml.etree.ElementTree as E
src,dst=sys.argv[1:];ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
with zipfile.ZipFile(src) as z,zipfile.ZipFile(dst,'w',zipfile.ZIP_DEFLATED) as o:
 for p in z.namelist():
  b=z.read(p)
  if p.startswith('xl/worksheets/sheet') and p.endswith('.xml'):
   r=E.fromstring(b)
   for tag in ['conditionalFormatting','dataValidations']:
    for e in r.findall('s:'+tag,ns):r.remove(e)
   b=E.tostring(r,encoding='utf-8',xml_declaration=True)
  o.writestr(p,b)
`,source,bounded]);
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(bounded));
const sh=wb.worksheets.getItem('Template');
const preview=await wb.render({sheetName:'Template',range:'D3:F7',scale:0.7,format:'png'});
await fs.writeFile(path.join(out,'tiktok-edit-before.png'),new Uint8Array(await preview.arrayBuffer()));
if(process.argv.includes('--preview-only'))process.exit(0);
const records=JSON.parse(await fs.readFile(path.join(out,'current-prepared-catalogue.json'),'utf8')).records;
const norm=t=>t.replace(/\s*\|?\s*Wall Sculpture$/i,'').trim().replace(/[–—]/g,'-').toLowerCase();
const bytitle=new Map(records.map(r=>[norm(r.title),r]));
const rows=sh.getRange('A6:G169').values;
const matches=rows.map((row,i)=>{const rec=bytitle.get(norm(String(row[3])));if(!rec)throw Error('No match '+row[3]);if(!/^\d{18,19}$/.test(String(row[0])))throw Error('Invalid existing product ID');if(row[6]!=='true'&&row[6]!==true)throw Error('Not a draft');return {row:i+6,product_id:String(row[0]),catalogue_id:rec.catalogue_id,sku:rec.sku,title:row[3],status:row[4],draft_tab:row[6],description:rec.description_html};});
if(matches.length!==164||new Set(matches.map(r=>r.product_id)).size!==164||new Set(matches.map(r=>r.catalogue_id)).size!==164)throw Error('Duplicate or missing product');
sh.getRange('F6:F169').values=matches.map(r=>[r.description]);
wb.recalculate();
const after=await wb.render({sheetName:'Template',range:'D3:F7',scale:0.7,format:'png'});
await fs.writeFile(path.join(out,'tiktok-edit-after.png'),new Uint8Array(await after.arrayBuffer()));
const authored=path.join(out,'tiktok-edit-authored.xlsx');
await (await SpreadsheetFile.exportXlsx(wb)).save(authored);
const target=path.join(out,'tiktok-existing-164-material-update.xlsx');
// Transplant only the authored description cells, retaining TikTok metadata and all other cells.
execFileSync('python3',['-c',`import sys,zipfile,xml.etree.ElementTree as E,copy
src,authored,dst=sys.argv[1:];u='http://schemas.openxmlformats.org/spreadsheetml/2006/main';ns={'s':u};q=lambda s:'{'+u+'}'+s
with zipfile.ZipFile(src) as z,zipfile.ZipFile(authored) as a,zipfile.ZipFile(dst,'w',zipfile.ZIP_DEFLATED) as o:
 ss=[]
 if 'xl/sharedStrings.xml' in a.namelist():ss=[''.join(e.itertext()) for e in E.fromstring(a.read('xl/sharedStrings.xml')).findall('s:si',ns)]
 r=E.fromstring(z.read('xl/worksheets/sheet1.xml')); ar=E.fromstring(a.read('xl/worksheets/sheet1.xml'))
 cells={c.attrib['r']:c for c in ar.findall('s:sheetData/s:row/s:c',ns)}
 count=0
 for row in r.findall('s:sheetData/s:row',ns):
  n=int(row.attrib['r'])
  if n<6:continue
  addr='F'+str(n);old=next(c for c in row if c.attrib.get('r')==addr);new=copy.deepcopy(cells[addr]);new.attrib['s']=old.attrib.get('s','0')
  if new.attrib.get('t')=='s':
   v=new.find('s:v',ns);txt=ss[int(v.text)];new.remove(v);new.set('t','inlineStr');t=E.SubElement(E.SubElement(new,q('is')),q('t'));t.text=txt;t.set('{http://www.w3.org/XML/1998/namespace}space','preserve')
  idx=list(row).index(old);row.remove(old);row.insert(idx,new);count+=1
 assert count==164,count
 for p in z.namelist():o.writestr(p,E.tostring(r,encoding='utf-8',xml_declaration=True) if p=='xl/worksheets/sheet1.xml' else z.read(p))
`,source,authored,target]);
await fs.writeFile(path.join(out,'tiktok-material-update-manifest.json'),JSON.stringify({source,target,changed_column:'F',count:164,records:matches},null,2));
console.log(JSON.stringify({target,updated_descriptions:164,status_untouched:true,draft_marker_preserved:true}));
