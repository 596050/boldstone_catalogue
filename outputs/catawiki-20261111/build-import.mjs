import fs from 'node:fs/promises';
import path from 'node:path';
import { Workbook } from '@oai/artifact-tool';

const out = path.dirname(new URL(import.meta.url).pathname);
const {headers, rows} = JSON.parse(await fs.readFile(path.join(out, 'import-matrix.json'), 'utf8'));
const review = JSON.parse(await fs.readFile(path.join(out, 'product-review.json'), 'utf8'));
const workbook = Workbook.create();
const sheet = workbook.worksheets.add('Catawiki draft');
sheet.getRangeByIndexes(0, 0, rows.length + 1, headers.length).values = [headers, ...rows];
sheet.showGridLines = false;
sheet.getRange('A1:E7').format.font = {name:'Arial', size:10};
sheet.getRange('A1:E1').format = {fill:'#34473A', font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},wrapText:true};
sheet.getRange('A1:E7').format.columnWidth = 25;
sheet.getRange('A1:E1').format.rowHeight = 52;
sheet.freezePanes.freezeRows(1);
workbook.recalculate();
const check = await workbook.inspect({kind:'table', range:'Catawiki draft!A1:E4', include:'values,formulas', tableMaxRows:4,tableMaxCols:5,maxChars:2500});
await fs.writeFile(path.join(out,'artifact-inspection.ndjson'),check.ndjson);
const preview = await workbook.render({sheetName:'Catawiki draft',range:'A1:E7',scale:1.5,format:'png'});
await fs.writeFile(path.join(out,'import-preview.png'),new Uint8Array(await preview.arrayBuffer()));
// The supplied API documents XLSX export but no CSV exporter. Serialize the
// Artifact-authored values with RFC4180 quoting to preserve the official template.
const authored = sheet.getRangeByIndexes(0,0,rows.length+1,headers.length).values;
const quote = v => '"' + String(v ?? '').replaceAll('"','""') + '"';
const csv = authored.map(r=>r.map(quote).join(',')).join('\r\n') + '\r\n';
await fs.writeFile(path.join(out,'catawiki-new-lots-174-DRAFT-NOT-FOR-UPLOAD.csv'),csv);

const esc = s => String(s ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const card = r => `<article data-search="${esc((r.title+' '+r.sku+' '+r.family).toLowerCase())}">
<h2>${esc(r.title)}</h2><p>${esc(r.product_id)} · ${esc(r.sku)} · ${esc(r.family)}</p>
<p><strong>${esc(r.status)}</strong>${r.existing_lot_id?` · <a href="https://www.catawiki.com/en/v/lot/${r.existing_lot_id}/edit">Existing lot ${r.existing_lot_id}</a>`:''}</p>
<p>${esc(r.dimensions)} · ${esc(r.weight)}<br>${esc(r.material_finish)}</p>
<p>Catalogue retail £${r.retail_gbp.toFixed(2)} (€${r.retail_eur_reference.toFixed(2)} reference). Fee-protected hammer floor: €${r.fee_protected_hammer_floor_eur_planning} (planning only).</p>
${r.catawiki_target_price_gbp!=null?`<p><strong>Catawiki proposed price: £${r.catawiki_target_price_gbp.toFixed(2)} / €${r.catawiki_target_price_eur}.</strong> Includes the owner-requested £100 uplift. Expert valuation and native submission remain pending.</p>`:''}
<p>${r.photo_candidate_count} selected non-in-situ photo candidates. Every candidate needs Catawiki photo review.</p>
<div class="photos">${r.photo_candidates.map(p=>`<a href="${esc(p.url)}" target="_blank"><img loading="lazy" src="${esc(p.url)}?format=300w" alt="${esc(p.alt||p.name)}" title="${esc(p.name)}"></a>`).join('')}</div>
<details><summary>Checks and prepared description</summary><ul>${r.issues.map(x=>`<li>${esc(x)}</li>`).join('')}</ul><p class="desc">${esc(r.draft.Description)}</p><p><a href="${esc(r.website)}" target="_blank">Current website listing</a></p></details></article>`;
const doc = `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Boldstone Catawiki preparation</title>
<style>body{font:16px/1.5 Arial,sans-serif;color:#26332b;background:#f5f5ef;margin:0}main{max-width:1150px;margin:auto;padding:24px}h1{font-size:30px}h2{font-size:22px;margin-bottom:4px}.notice{padding:18px;background:#fff0d7;border-left:4px solid #b56d1d}article{background:white;border:1px solid #d7ddd3;margin:18px 0;padding:20px;border-radius:8px}input{padding:12px;font-size:16px;width:min(90%,600px)}.photos{display:flex;gap:8px;flex-wrap:wrap}.photos img{width:130px;height:150px;object-fit:contain;background:#fafaf8}.desc{white-space:pre-wrap}a{color:#285b40}summary{cursor:pointer}table{border-collapse:collapse}td,th{border-bottom:1px solid #ccc;padding:6px 16px;text-align:left}</style>
<main><h1>Boldstone Catawiki preparation</h1><p>Checked 11 November 2026. All 176 website publication products accounted for. No upload or terms acceptance performed.</p>
<div class="notice"><strong>Submission is paused at the required decisions.</strong> Uploading valid CSV rows sends them directly to experts and agrees to the Terms of Use, including exclusive Catawiki listing. Existing sales channels have not been withdrawn. The CSV is incomplete and must not be uploaded as-is.</div>
<p>Catawiki proposed prices now use catalogue retail plus £100, with linked EUR targets. These are seller proposals for expert review. Baseline retail comparisons below exclude the Catawiki uplift.</p>
<table><tr><th>Check</th><th>Count</th></tr><tr><td>Existing drafts, update in place</td><td>2</td></tr><tr><td>New rows prepared locally</td><td>174</td></tr><tr><td>Baseline retail equivalent below €100</td><td>${review.counts.retail_eur_below_100}</td></tr><tr><td>Baseline retail equivalent below €200</td><td>${review.counts.retail_eur_below_200}</td></tr><tr><td>Fewer than five selected non-in-situ photo candidates</td><td>${review.counts.fewer_than_five_selected_photo_candidates}</td></tr></table>
<p>EUR reference: ECB ${esc(review.currency.date)}, £${esc(review.currency.gbp_per_eur)} per €1. Hammer-floor planning uses current retail proceeds, 12.5% seller commission plus banded fees, a conservative 20% fee-VAT allowance and 3% currency allowance. Packing and delivery are separate. These figures are not expert valuations or entered reserves.</p>
<p>Signature, cast date/era, physical condition, actual-item photography, shipping and ownership/exclusivity need confirmation. Saatchi-only editions and years were not copied. Ancient-culture and provenance fields are left blank as inapplicable to contemporary direct-from-brand reliefs.</p>
<p><a href="https://www.catawiki.com/en/help/submitting-lots/how-to-submit-multiple-bulk-objects-at-once">Bulk submission guide</a> · <a href="${esc(review.official_guidelines)}">Artwork and photo guidelines</a> · <a href="${esc(review.reserve_rule)}">Reserve policy</a></p>
<label>Find a sculpture <input id="search" placeholder="Name, family or SKU"></label><section>${review.products.map(card).join('')}</section>
<script>document.querySelector('#search').addEventListener('input',e=>{let q=e.target.value.toLowerCase();document.querySelectorAll('article').forEach(a=>a.hidden=!a.dataset.search.includes(q))})</script></main></html>`;
await fs.writeFile(path.join(out,'review.html'),doc);
console.log(JSON.stringify({newRows:rows.length,columns:headers.length,products:review.products.length,csv:'catawiki-new-lots-174-DRAFT-NOT-FOR-UPLOAD.csv'}));
