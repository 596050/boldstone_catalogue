// Invoked only inside cua_repl. All browser interactions use the documented
// native Computer Use API; no cookies, private endpoints or page-state writes.
// Native saves are provisional until the two native status exports reconcile.
(function createChairishPriceUpdater(app, fs, out) {
  const observe = () => app.getAXState({disableDiffing:true, emit:false});
  const node = (state, re) => {
    const line=state.split('\n').find(x=>re.test(x));
    if(!line) throw Error('Expected visible field missing: '+re);
    return Number(line.trim().match(/^\d+/)[0]);
  };
  const identity = (state, r) => state.includes('SKU (Optional), Value: '+r.sku);
  const price = state => Number(state.match(/stepper .*Asking Price, Value: ([\d.]+)/)?.[1]);
  async function navigate(r) {
    let state=await observe();
    if(state.includes('Leave site? Changes that you made may not be saved.')) throw Error('Unexpected pre-existing unsaved dialog');
    if(identity(state,r)) return;
    await app.setValue(node(state,/text field \(settable\) Address and search bar/),r.url);
    await app.getAXState({emit:false});
    await app.pressKey('Return');
    await app.getAXState({emit:false});
  }
  async function ready(r) {
    for(let n=0;n<8;n++) {
      let state=await observe();
      if(identity(state,r)&&/stepper .*Asking Price, Value:/.test(state)) return state;
      if(state.includes('Leave site? Changes that you made may not be saved.')) {
        // The only navigation requested here reloads our own known price edit.
        await app.click(node(state,/button Leave,/));
        await app.getAXState({emit:false});
      } else await app.getScreenshot({emit:false});
    }
    throw Error('Requested product has not loaded: '+r.sku);
  }
  async function click(re,r) {
    for(let n=0;n<3;n++) {
      const state=await observe();
      if(!identity(state,r)) throw Error('Product identity changed before action: '+r.sku);
      try {
        await app.click(node(state,re));
        return await app.getAXState({emit:false});
      } catch(e) {
        if(!String(e).includes('element ID is no longer valid')) throw e;
        await app.getAXState({emit:false});
      }
    }
    throw Error('Controls are still changing: '+r.sku);
  }
  async function one(r, receipts) {
    let stage='navigate';
    try {
      await navigate(r);
      let state=await ready(r);
      stage='price';
      if(price(state)!==r.asking_usd) {
        let focus=await click(/stepper .*Asking Price,/,r);
        if(!/The focused UI element is \d+ stepper .*Asking Price/.test(focus)) {
          // Chairish's fixed header can cover an AX-scrolled input.
          await app.scroll([1000,600],'up',0.35);
          await app.getAXState({emit:false});
          focus=await click(/stepper .*Asking Price,/,r);
        }
        if(!/The focused UI element is \d+ stepper .*Asking Price/.test(focus)) throw Error('Input focus not verified');
        await app.pressKey('super+a');
        await app.getAXState({emit:false});
        await app.paste(String(r.asking_usd));
        await app.getAXState({emit:false});
      }
      state=await observe();
      if(price(state)!==r.asking_usd) throw Error('Entered price differs');
      stage='auction';
      if(!state.includes('Set Minimum, Value: 60%')) {
        await click(/pop-up button Set Minimum,/,r);
        const menu=await observe();
        const options=menu.split('\n');
        const option=options.filter(x=>/^\s*\d+ (?:\(selected\) )?60%, ID: menuItemSelected:/.test(x)).at(-1)
          || options.find(x=>/^\s*\d+ 60%$/.test(x));
        if(!option) throw Error('60 percent option missing');
        await app.click(Number(option.trim().match(/^\d+/)[0]));
        await app.getAXState({emit:false});
      }
      stage='save';
      state=await observe();
      if(!identity(state,r)||price(state)!==r.asking_usd||!state.includes('Set Minimum, Value: 60%')) throw Error('Pre-save verification failed');
      const draft=state.includes('text DRAFT');
      await click(draft?/button SAVE$/:/button SUBMIT CHANGES$/,r);
      for(let n=0;n<8;n++) {
        state=await observe();
        if(!/button \(disabled\) (?:SAVE|SUBMIT CHANGES)/.test(state)) break;
        await app.getScreenshot({emit:false});
      }
      if(/button \(disabled\) (?:SAVE|SUBMIT CHANGES)/.test(state)) throw Error('Save response pending; reconcile before retrying');
      const receipt={sku:r.sku,native_id:r.native_id,asking_usd:r.asking_usd,auction_reserve_usd:r.auction_reserve_usd,status:'SAVE_ACK_FINAL_EXPORT_PENDING',prior_status:draft?'DRAFT':'PENDING_REVIEW'};
      receipts.push(receipt);
      await fs.writeFile(out+'/chairish-price-receipts.json',JSON.stringify(receipts,null,2));
      return receipt;
    } catch(e) {throw Error(stage+': '+String(e));}
  }
  return {
    async batch(maximum=3) {
      const packet=JSON.parse(await fs.readFile(out+'/chairish-price-updates.json','utf8'));
      const receipts=JSON.parse(await fs.readFile(out+'/chairish-price-receipts.json','utf8'));
      const pending=packet.records.filter(r=>!receipts.some(x=>x.sku===r.sku)).slice(0,maximum);
      const results=[];
      for(const r of pending) {
        try {results.push(await one(r,receipts));}
        catch(e) {results.push({stopped:r.sku,native_id:r.native_id,error:String(e)});break;}
      }
      return {saved:receipts.length,total:packet.records.length,results};
    }
  };
})
