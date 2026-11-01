import fs from 'node:fs/promises';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {FileBlob, SpreadsheetFile, Workbook} from '@oai/artifact-tool';

const out = path.dirname(new URL(import.meta.url).pathname);
const read = async p => JSON.parse(await fs.readFile(p, 'utf8'));
const tik = await read(path.resolve(out, '../marketplace-completion-20261101/tiktok-prepared-catalogue.json'));
const ebay = await read(path.resolve(out, '../marketplace-completion-20261101/ebay-in6192-prepared.json'));
const weights = await read(path.resolve(out, '../shipping-checkout-20261031/weight-change-manifest.json'));
const weightMap = new Map(weights.rows.map(r=>[r.catalogue_id,r]));
const plain = html => html.replace(/<\/(p|li|h[1-6])>/gi,'\n\n').replace(/<br\s*\/?\s*>/gi,'\n').replace(/<[^>]+>/g,'').replace(/&amp;/g,'&').replace(/&nbsp;/g,' ').replace(/&#39;/g,"'").replace(/&quot;/g,'"').trim();
const urlSmall = value => {const u=new URL(value);u.searchParams.set('format','1000w');return u.href;};
const reports = {source_cutoff:15209,tiktok:{existing_draft:'1729973194318977364',records:[]},ebay:{account:'in6192',records:[]}};
async function buildEbay() {
  const ebTemplate=await fs.readFile('/Users/tprice/Downloads/eBay-draft-listing-template-Nov-1-2026-0-58-3.csv','utf8');
  const ebWb=await Workbook.fromCSV(ebTemplate,{sheetName:'eBay drafts'});
  const ebSh=ebWb.worksheets.getItem('eBay drafts');
  const pre=await ebWb.render({sheetName:'eBay drafts',range:'A5:D6',scale:1,format:'png'});
  await fs.writeFile(path.join(out,'ebay-template-before.png'),new Uint8Array(await pre.arrayBuffer()));
  const esc = s => String(s??'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
  const ebRows=ebay.records.map(r=>{
    if(r.title.length>80)throw new Error('Title too long: '+r.title);
    const photos=[...new Set(r.photos.map(p=>p.url))].slice(0,24);
    const description=r.description.split(/\n\n+/).map(p=>'<p>'+esc(p).replace(/\n/g,'<br>')+'</p>').join('');
    reports.ebay.records.push({catalogue_id:r.catalogue_id,sku:r.sku,title:r.title,price_gbp:Number(r.price_gbp),photos:photos.length,state:'Draft',handling_days_required:10});
    return ['Draft',r.sku,'553',r.title,'',Number(r.price_gbp),1,photos.join('|'),'NEW',description,'FixedPrice'];
  });
  ebSh.getRangeByIndexes(5,0,ebRows.length,11).values=ebRows;
  ebWb.recalculate();
  const ebValues=ebSh.getRangeByIndexes(0,0,162,11).values;
  const csvValue=v=>'"'+String(v??'').replace(/"/g,'""')+'"';
  await fs.writeFile(path.join(out,'ebay-in6192-157-wall-sculpture-drafts.csv'),'\ufeff'+ebValues.map(r=>r.map(csvValue).join(',')).join('\r\n')+'\r\n');
  await fs.writeFile(path.join(out,'ebay-import-manifest.json'),JSON.stringify(reports.ebay,null,2));
  console.log('eBay rows: '+ebRows.length);
}
if(process.argv.includes('--ebay-only')) {await buildEbay();process.exit(0);}
const ttAllRecords = tik.records.filter(r=>r.catalogue_id!=='BSI-59530C6155C2');
if(ttAllRecords.length!==175 || ebay.records.length!==157)throw new Error('Unexpected source counts');
const batchStart=Number(process.argv.find(x=>x.startsWith('--batch-start='))?.split('=')[1]||0);
const batchCount=Number(process.argv.find(x=>x.startsWith('--batch-count='))?.split('=')[1]||175);
const ttRecords=ttAllRecords.slice(batchStart,batchStart+batchCount);
const ttOutputName=`tiktok-${ttRecords.length}-wall-sculpture-drafts-${batchStart+1}.xlsx`;
for(const records of [ttRecords,ebay.records])if(new Set(records.map(r=>r.sku)).size!==records.length)throw new Error('Duplicate SKU');
const nativeTemplate='/Users/tprice/Downloads/Tiktoksellercenter_Home Supplies_20261101_Hanging Decor_template.xlsx';
// TikTok's conditional formatting covers millions of unused cells. Import a bounded
// working copy, then preserve the original native workbook parts around the authored cells.
execFileSync('python3',['-c',`import sys,zipfile,xml.etree.ElementTree as E
src,dst=sys.argv[1:]; ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
with zipfile.ZipFile(src) as z,zipfile.ZipFile(dst,'w',zipfile.ZIP_DEFLATED) as o:
 for p in z.namelist():
  b=z.read(p)
  if p.startswith('xl/worksheets/sheet') and p.endswith('.xml'):
   r=E.fromstring(b)
   for tag in ['conditionalFormatting','dataValidations']:
    for e in r.findall('s:'+tag,ns):r.remove(e)
   data=r.find('s:sheetData',ns)
   if data is not None:
    for row in list(data):
     if int(row.attrib['r'])>181:data.remove(row)
   b=E.tostring(r,encoding='utf-8',xml_declaration=True)
  o.writestr(p,b)
`,nativeTemplate,path.join(out,'bounded-template.xlsx')]);
console.log('Importing bounded TikTok template');
const wb = await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(out,'bounded-template.xlsx')));
const sh = wb.worksheets.getItem('Template');
{
  const pre=await wb.render({sheetName:'Template',range:'A3:D7',scale:0.75,format:'png'});
  await fs.writeFile(path.join(out,'template-before.png'),new Uint8Array(await pre.arrayBuffer()));
  if(process.argv.includes('--inspect')) {console.log(JSON.stringify(sh.getRange('A1:AT1').values));process.exit(0);}
}
const ttRows=ttRecords.map(r=>{
  const w=weightMap.get(r.catalogue_id);if(!w||!Number(w.shipping_kg))throw new Error('No approved packed weight: '+r.catalogue_id);
  const unique=[...new Map(r.photos.map(p=>[p.url,p])).values()];
  // Keep the primary first, then ensure contextual pictures survive the platform's nine-image limit.
  const photos=[...unique.filter(p=>p.role==='primary'),...unique.filter(p=>p.role==='in_situ'),...unique.filter(p=>!['primary','in_situ'].includes(p.role))].slice(0,9);
  if(!photos.length)throw new Error('No image: '+r.catalogue_id);
  const row=Array(46).fill('');
  row[0]='Home Decor/Hanging Decor';row[1]='No Brand';row[2]=r.title;row[3]=plain(r.description_html);
  photos.forEach((p,i)=>row[4+i]=urlSmall(p.url));
  row[20]=Math.round(Number(w.shipping_kg)*1000);row[25]=Number(r.price_gbp);row[26]=1;row[27]=r.sku;row[45]='Draft(2)';
  if(/\bGFRC\b|Royal Mail/i.test(row[3]))throw new Error('Unwanted public wording');
  reports.tiktok.records.push({catalogue_id:r.catalogue_id,sku:r.sku,title:r.title,price_gbp:row[25],packed_grams:row[20],photos:photos.length,source_photos:unique.length,omitted_images:unique.filter(p=>!photos.includes(p)).map(p=>p.url),state:'Draft(2)',handling_days_required:r.handling_working_days_required});
  return row;
});
sh.getRangeByIndexes(6,0,ttRows.length,46).values=ttRows;
wb.recalculate();
await fs.writeFile(path.join(out,'tiktok-inspection.txt'),String(await wb.inspect({kind:'table',range:'Template!A7:D9',include:'values,formulas',maxChars:1800})));
const after=await wb.render({sheetName:'Template',range:'A3:C9',scale:0.75,format:'png'});
await fs.writeFile(path.join(out,'template-after.png'),new Uint8Array(await after.arrayBuffer()));
await (await SpreadsheetFile.exportXlsx(wb)).save(path.join(out,'tiktok-authored-values.xlsx'));
execFileSync('python3',['-c',`import sys,zipfile,xml.etree.ElementTree as E,copy
src,authored,dst,end=sys.argv[1:]; u='http://schemas.openxmlformats.org/spreadsheetml/2006/main';ns={'s':u};q=lambda t:'{'+u+'}'+t
with zipfile.ZipFile(src) as z,zipfile.ZipFile(authored) as a,zipfile.ZipFile(dst,'w',zipfile.ZIP_DEFLATED) as o:
 s=[]
 if 'xl/sharedStrings.xml' in a.namelist():s=[''.join(e.itertext()) for e in E.fromstring(a.read('xl/sharedStrings.xml')).findall('s:si',ns)]
 ar=E.fromstring(a.read('xl/worksheets/sheet1.xml')); rr=E.fromstring(z.read('xl/worksheets/sheet1.xml')); data=rr.find('s:sheetData',ns)
 old={int(row.attrib['r']):row for row in data}
 for row in ar.findall('s:sheetData/s:row',ns):
  n=int(row.attrib['r'])
  if not 7<=n<=int(end):continue
  new=copy.deepcopy(row)
  for c in new:
   c.attrib.pop('s',None)
   if c.attrib.get('t')=='s':
    v=c.find('s:v',ns);vtext=s[int(v.text)];c.remove(v);c.set('t','inlineStr');t=E.SubElement(E.SubElement(c,q('is')),q('t'));t.text=vtext;t.set('{http://www.w3.org/XML/1998/namespace}space','preserve')
  if n in old:data.remove(old[n])
  data.append(new)
 data[:]=sorted(data,key=lambda e:int(e.attrib['r']))
 rr.find('s:dimension',ns).set('ref','A1:AT2000')
 for p in z.namelist():o.writestr(p,E.tostring(rr,encoding='utf-8',xml_declaration=True) if p=='xl/worksheets/sheet1.xml' else z.read(p))
`,nativeTemplate,path.join(out,'tiktok-authored-values.xlsx'),path.join(out,ttOutputName),String(ttRecords.length+6)]);

await buildEbay();
await fs.writeFile(path.join(out,`import-manifest-${batchStart+1}-${ttRecords.length}.json`),JSON.stringify(reports,null,2));
console.log(JSON.stringify({tiktok:ttRows.length,ebay:ebay.records.length,tiktok_photos_truncated:reports.tiktok.records.filter(r=>r.omitted_images.length).length,tiktok_oversize_weight:reports.tiktok.records.filter(r=>r.packed_grams>30000).length}));
