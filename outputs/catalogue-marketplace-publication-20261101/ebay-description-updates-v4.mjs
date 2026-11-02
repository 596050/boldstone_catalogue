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
        const ax=await tab.getAXState({emit:false,disableDiffing:true});
        const line=ax.split('\n').find(x=>/text entry area.*Description: undefined/.test(x));
        const index=Number(line?.trim().match(/^(\d+)/)?.[1]);
        if(!index)throw Error('Native description input unavailable');
        await tab.click(index);
        await tab.pressKey(null,'super+a');
        await tab.typeText(null,after);
        await tab.pressKey(null,'Tab');
        await tab.getAXState({emit:false});
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
  async function verify(limit=15, repairMissing=false) {
    const path=`${directory}/ebay-${account}-description-readbacks.json`;
    const receipts=JSON.parse(await fs.readFile(path,'utf8').catch(()=>'[]'));
    const started=Date.now(),checked=[];
    for(let n=0;n<limit;n++) {
      const {record,before,sku,position,total}=await readCurrent();
      const companion=record.description_text.split('\n').find(x=>x.startsWith('Companion pieces:'));
      const required=[custom,...(record.surface_effect?[variation]:[]),...(companion?[companion]:[])];
      const missing=required.filter(x=>!normalise(before).includes(normalise(x)));
      if((before.match(/designer Sally Price/g)||[]).length!==1)
        throw Error('Saved customisation missing or repeated: '+sku);
      if(missing.length) {
        if(!repairMissing)throw Error('Saved disclosure missing or repeated: '+sku);
        const repairPath=`${directory}/ebay-${account}-description-repairs.json`;
        const repairs=JSON.parse(await fs.readFile(repairPath,'utf8').catch(()=>'[]'));
        const repair={sku,position,before,missing,status:'REPAIR_NEEDED',at:new Date().toISOString()};
        const ri=repairs.findIndex(r=>r.sku===sku);
        if(ri>=0)repairs[ri]=repair;else repairs.push(repair);
        await write(repairPath,repairs);
        if(position===total)return {checked,total_verified:receipts.length,complete:false,last_needs_repair:sku};
        await run(1);
        repairs.find(r=>r.sku===sku).status='REPAIRED_STAGED_REOPEN_REQUIRED';
        await write(repairPath,repairs);
        if(Date.now()-started>40000)break;
        continue;
      }
      const receipt={account,sku,position,total,description:before,
        status:'SAVED_DRAFT_REOPENED_ALL_REQUIRED_DISCLOSURES_PRESENT',at:new Date().toISOString()};
      const prior=receipts.findIndex(r=>r.sku===sku);
      if(prior>=0)receipts[prior]=receipt;else receipts.push(receipt);
      await write(path,receipts);checked.push(sku);
      if(position===total)return {checked,total_verified:receipts.length,complete:true};
      // No field edits: next is the native navigation control for this dialog.
      await tab.playwright.getByRole('button',{name:'Save and next',exact:true}).press('Enter');
      await tab.getAXState({emit:false});
      const next=await readCurrent();
      if(next.position!==position+1)throw Error('Verification navigation changed unexpectedly');
      if(Date.now()-started>40000)break;
    }
    return {checked,total_verified:receipts.length,complete:false};
  }
  return {run,readCurrent,verify};
}
