// Executed only in functions.exec with the authenticated tools object.
// Returns an async bounded dispatcher. Filesystem IPC contains no credentials.
(async function dispatchWindow(seconds = 45) {
  const base = '/Users/tprice/Library/Application Support/BoldstoneImageProcessing/connector-rpc';
  const deadline = Date.now() + seconds * 1000;
  let calls = 0;
  let nodeSerial=Promise.resolve();
  const node = (code, title) => {
    const pending=nodeSerial.then(async()=>{
      const result = await tools.mcp__node_repl__js({code, title, timeout_ms: 15000});
      if (result.isError) throw new Error('Local dispatcher filesystem operation failed');
      const block = result.content.find(x => x.type === 'text');
      return block?.text || '';
    });
    nodeSerial=pending.catch(()=>{});
    return pending;
  };
  const writeFile = async (path, value) => node(
    `var rpcFs=await import('node:fs/promises'); await rpcFs.mkdir(${JSON.stringify(base+'/receipts')},{recursive:true,mode:0o700}); await rpcFs.writeFile(${JSON.stringify(path)},JSON.stringify(${JSON.stringify(value)}),{mode:0o600}); console.log('saved');`,
    'Record connected operation result'
  );
  const parse = result => {
    if (result.structuredContent) return result.structuredContent;
    for (const block of result.content || []) {
      if (block.type === 'text') {
        try { return JSON.parse(block.text); } catch (_) {}
      }
    }
    throw new Error('Unrecognized connected result');
  };
  const claim = async (limit) => {
    const raw = await node(`
      var rpcFs=await import('node:fs/promises');
      var rpcBase=${JSON.stringify(base)};
      var rpcNames=(await rpcFs.readdir(rpcBase+'/requests')).filter(x=>/^[a-f0-9]{32}\\.json$/.test(x)).sort();
      var rpcClaimed=[];
      for(var rpcName of rpcNames){
        if(rpcClaimed.length>=${limit})break;
        var rpcQueued=JSON.parse(await rpcFs.readFile(rpcBase+'/requests/'+rpcName,'utf8'));
        if((rpcQueued.not_before_ms||0)>Date.now())continue;
        await rpcFs.rename(rpcBase+'/requests/'+rpcName,rpcBase+'/inflight/'+rpcName);
        rpcClaimed.push(rpcQueued);
      }
      console.log(JSON.stringify(rpcClaimed));`, 'Read queued conversion requests');
    return JSON.parse(raw);
  };
  const execute = async request => {
    const {method,args,id} = request;
    const allowed = load('conversionDispatcherAllowlist');
    if (!allowed) throw new Error('Dispatcher allowlist not loaded');
    const validPath = value => allowed.paths.includes(value) || allowed.ids.includes(value);
    if(method==='metadata') {
      const folders=load('conversionRecentFolderMetadata')||{};
      const recent=folders[args.path_or_file_id];
      if(recent && Date.now()-recent.time<30000) {
        return {result:{...recent.result,conversion_folder_cache:{observed_at:recent.time,max_age_ms:30000}}};
      }
    }
    if(method!=='download') {
      const slot=Math.max(Date.now(),load('conversionNextApiSlot')||0);
      store('conversionNextApiSlot',slot+1000);
      if(slot>Date.now())await new Promise(resolve=>setTimeout(resolve,slot-Date.now()));
    }
    let response;
    if(method==='who_am_i') response=await tools.mcp__codex_apps__dropbox_who_am_i({});
    else if(method==='metadata') {
      if(!validPath(args.path_or_file_id)) throw new Error('Metadata request outside exact manifest');
      response=await tools.mcp__codex_apps__dropbox_get_file_metadata(args);
      if(response.isError && response.content?.some(x=>x.type==='text' && /^\[NOT_FOUND\]/.test(x.text.trim()))) return {result:null};
      if(!response.isError && parse(response).metadata_type==='folder') {
        const folders=load('conversionRecentFolderMetadata')||{};
        folders[args.path_or_file_id]={time:Date.now(),result:parse(response)};
        store('conversionRecentFolderMetadata',folders);
      }
    } else if(method==='download_link') {
      if(!args.entries.every(value=>allowed.ids.includes(value))) throw new Error('Download outside exact manifest');
      response=await tools.mcp__codex_apps__dropbox_download_link(args);
      if(!response.isError) {
        const issued=load('conversionIssuedLinks')||{};
        for(const entry of parse(response).entries) issued[entry.download_url]=entry.id;
        store('conversionIssuedLinks',issued);
      }
    } else if(method==='download') {
      const issued=load('conversionIssuedLinks')||{};
      if(issued[args.download_url]!==args.file_id)throw new Error('Download URL was not issued for this file');
      const validDestination=allowed.uploads.some(x=>['original.bmp','downloaded-output.jpg'].some(name=>x.source_file.replace(/converted\.jpg$/,name)===args.destination));
      if(!validDestination)throw new Error('Download destination outside exact local manifest');
      delete issued[args.download_url];store('conversionIssuedLinks',issued);
      const downloaded=await node(`var rpcDownloadResponse=await fetch(${JSON.stringify(args.download_url)});if(!rpcDownloadResponse.ok)throw new Error('Download failed');var rpcDownloadBytes=Buffer.from(await rpcDownloadResponse.arrayBuffer());var rpcDownloadFs=await import('node:fs/promises');await rpcDownloadFs.writeFile(${JSON.stringify(args.destination)},rpcDownloadBytes,{mode:0o600});console.log(JSON.stringify({size:rpcDownloadBytes.length}));`,'Download authorized conversion bytes');
      return {result:JSON.parse(downloaded)};
    } else if(method==='upload') {
      const bound=allowed.uploads.find(x=>x.destination_path===args.destination_path && x.source_file===args.source_file);
      if(!bound) throw new Error('Upload outside exact manifest');
      response=await tools.mcp__codex_apps__dropbox_upload_file(args);
      await writeFile(base+'/receipts/'+id+'-submission.json',response);
      if(response.isError) return {error:'UPLOAD_TOOL_ERROR'};
      let result=parse(response);
      while(result.status==='in_progress') {
        await new Promise(resolve=>setTimeout(resolve,Math.max(1000,result.recommended_poll_after_ms||1000)));
        response=await tools.mcp__codex_apps__dropbox_check_upload_file_status({operation_id:result.operation_id,wait_ms:5000});
        await writeFile(base+'/receipts/'+id+'-poll.json',response);
        if(response.isError) return {error:'UPLOAD_POLL_ERROR'};
        result=parse(response);
      }
      if(result.status!=='completed') return {error:'UPLOAD_TERMINAL_SUCCESS_MISSING'};
      const current=load('conversionDispatcherAllowlist');
      current.ids.push(result.file.file_id);
      store('conversionDispatcherAllowlist',current);
    } else throw new Error('Unsupported dispatcher method');
    calls++;
    if(response.isError) {
      const texts=response.content?.filter(x=>x.type==='text').map(x=>x.text).join(' ')||'';
      await writeFile(base+'/receipts/'+id+'-tool-error.json',{method,args,error_code:response.structuredContent?.error_code,text:texts.replace(/https?:\/\/\S+/g,'[url omitted]')});
      if(/RATE_LIMIT|RESOURCE_EXHAUSTED|Too many requests/i.test(texts)) {
        store('conversionDispatcherBackoffUntil',Date.now()+60000);
        await writeFile(base+'/receipts/'+id+'-rate-limit.json',{method,error_code:response.structuredContent?.error_code,text:texts.replace(/https?:\/\/\S+/g,'[url omitted]')});
        return {error:'CONNECTOR_RATE_LIMITED',retry_after_ms:60000};
      }
      if(['who_am_i','metadata','download_link'].includes(method) && !/PERMISSION_DENIED|UNAUTHENTICATED|INVALID_TOKEN/i.test(texts) && (request.retry_count||0)<3) {
        return {error:'CONNECTED_TRANSIENT_READ_ERROR',retry_after_ms:5000};
      }
      return {error:'CONNECTED_TOOL_ERROR'};
    }
    return {result:parse(response)};
  };
  const pending=new Set();
  const serve=async request=>{
    let value;
    try{value=await execute(request);}catch(_){value={error:'DISPATCHER_CALL_FAILED'};}
    if(value.retry_after_ms && ['who_am_i','metadata','download_link'].includes(request.method) && (request.retry_count||0)<5) {
      const retry={...request,retry_count:(request.retry_count||0)+1,not_before_ms:Date.now()+value.retry_after_ms};
      await node(`var rpcFs=await import('node:fs/promises');var rpcBase=${JSON.stringify(base)};await rpcFs.writeFile(rpcBase+'/inflight/'+${JSON.stringify(request.id)}+'.json',JSON.stringify(${JSON.stringify(retry)}),{mode:0o600});await rpcFs.rename(rpcBase+'/inflight/'+${JSON.stringify(request.id)}+'.json',rpcBase+'/requests/'+${JSON.stringify(request.id)}+'.json');console.log('Read deferred until rate limit clears.');`,'Defer a rate-limited read');
      return;
    }
    const payload=[{id:request.id,method:request.method,value}];
    await node(`
      var rpcFs=await import('node:fs/promises');var rpcBase=${JSON.stringify(base)};
      for(var rpcItem of ${JSON.stringify(payload)}){
        var rpcResponsePath=rpcBase+'/responses/'+rpcItem.id+'.json';
        await rpcFs.writeFile(rpcResponsePath+'.tmp',JSON.stringify(rpcItem.value),{mode:0o600});
        await rpcFs.rename(rpcResponsePath+'.tmp',rpcResponsePath);
        var rpcSafe=JSON.parse(JSON.stringify(rpcItem.value,(key,value)=>key==='download_url'?undefined:value));
        await rpcFs.writeFile(rpcBase+'/receipts/'+rpcItem.id+'-result.json',JSON.stringify({method:rpcItem.method,...rpcSafe}),{mode:0o600});
        await rpcFs.unlink(rpcBase+'/inflight/'+rpcItem.id+'.json');
      }
      console.log('delivered');`, 'Deliver verified connector response');
  };
  while(Date.now()<deadline) {
    const backoff=load('conversionDispatcherBackoffUntil')||0;
    if(backoff>Date.now()) {await new Promise(resolve=>setTimeout(resolve,Math.min(1000,backoff-Date.now(),Math.max(0,deadline-Date.now()))));continue;}
    if(pending.size>=2){await Promise.race(pending);continue;}
    const requests=await claim(2-pending.size);
    if(!requests.length) {
      await Promise.race([...pending,new Promise(resolve=>setTimeout(resolve,100))]);
      continue;
    }
    for(const request of requests){
      let task;
      task=serve(request).finally(()=>pending.delete(task));
      pending.add(task);
    }
  }
  await Promise.allSettled(pending);
  const status=await node(`var rpcFs=await import('node:fs/promises');console.log(await rpcFs.readFile('/Users/tprice/Library/Application Support/BoldstoneImageProcessing/conversion-status.json','utf8'));`,'Read conversion progress');
  const progress=JSON.parse(status);
  text({calls,state:progress.state,counts:progress.execution_counts,quality:progress.jpeg_quality,originals_deleted:progress.source_files_deleted,backoff_remaining_ms:Math.max(0,(load('conversionDispatcherBackoffUntil')||0)-Date.now())});
  return progress;
})
