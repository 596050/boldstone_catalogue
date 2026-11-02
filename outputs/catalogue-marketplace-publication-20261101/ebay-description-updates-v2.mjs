// Run only inside cua_repl, against an already opened native bulk editor.
// Existing drafts only: this helper never submits or creates listings.
import fs from 'node:fs/promises';

export function ebayDescriptionUpdates({tab, records, directory, account}) {
  const editor = tab.playwright.frameLocator('#se-rte-frame__textEditor').getByRole('textbox');
  const journalPath = `${directory}/ebay-${account}-description-journal.json`;
  const intentPath = `${directory}/ebay-${account}-description-intent.json`;
  const normalise = value => value.trim().replace(/\s+/g,' ');
  const paragraphs = value => value.split(/\n+/).map(x=>x.trim()).filter(Boolean);
  const write = async (path,data) => {
    await fs.writeFile(path+'.tmp',JSON.stringify(data,null,2)+'\n');
    await fs.rename(path+'.tmp',path);
  };
  const custom = 'All designs can be customised. Completely new commissions can also be created in collaboration with designer Sally Price.';
  const variation = 'Each piece is handmade. The surface-effect pattern will vary and will differ from the photographs.';
  async function readCurrent() {
    await editor.waitFor({state:'visible',timeoutMs:15000});
    const dialog = await tab.playwright.getByRole('dialog').innerText();
    const position = dialog.match(/(\d+) of (\d+) listings/);
    if(!position) throw Error('Expected native per-listing description editor');
    const before = await editor.innerText();
    const sku = before.match(/Model:[^\n]*\(([^()\s]+)\)/)?.[1];
    const record = records.find(r=>r.sku===sku);
    if(!record || !dialog.includes(record.ebay_title)) throw Error('Unknown or mismatched native model '+sku);
    return {sku,position:Number(position[1]),total:Number(position[2]),before,record};
  }
  async function run(limit=15) {
    const journal = JSON.parse(await fs.readFile(journalPath,'utf8').catch(()=>'[]'));
    const started = Date.now(), changed=[];
    for(let n=0;n<limit;n++) {
      const current = await readCurrent();
      const {record,before,sku,position,total}=current;
      if(position===total) return {processed:changed,total_staged:journal.length,last_item:current};
      const companion = record.description_text.split('\n').find(x=>x.startsWith('Companion pieces:'));
      const needed = [custom,...(record.surface_effect?[variation]:[]),...(companion?[companion]:[])];
      const additions = needed.filter(line=>!normalise(before).includes(normalise(line)));
      if(before.includes('Companion pieces:') && companion && !normalise(before).includes(normalise(companion)))
        throw Error('Existing companion wording differs; review '+sku);
      const after = [...paragraphs(before),...additions].join('\n');
      if((after.match(/designer Sally Price/g)||[]).length!==1)throw Error('Customisation duplicate '+sku);
      const intent={account,workspace:await tab.url(),sku,position,total,before,after,
        phase:'PREPARED',at:new Date().toISOString()};
      await write(intentPath,intent);
      if(additions.length) {
        // Single newlines become paragraphs in this editor; double newlines
        // create unwanted blank paragraphs on every save.
        await editor.fill(after);
        await editor.press('Tab');
        const entered=await editor.innerText();
        if(normalise(entered)!==normalise(after))throw Error('Input did not match '+sku);
      }
      await write(intentPath,{...intent,phase:'SAVE_AND_NEXT_REQUESTED'});
      await tab.playwright.getByRole('button',{name:'Save and next',exact:true}).press('Enter');
      await tab.getAXState({emit:false});
      const next=await readCurrent();
      if(next.position!==position+1 || next.sku===sku)throw Error('Next listing not reached; reconcile '+sku);
      const receipt={...intent,phase:'STAGED_IN_BULK_EDITOR',changed:additions.length>0,next_sku:next.sku};
      const prior=journal.findIndex(r=>r.sku===sku);
      if(prior>=0)journal[prior]=receipt;else journal.push(receipt);
      await write(journalPath,journal);
      changed.push(sku);
      if(Date.now()-started>40000)break;
    }
    return {processed:changed,total_staged:journal.length};
  }
  return {run,readCurrent};
}
