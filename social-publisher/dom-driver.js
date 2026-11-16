/* Public DOM only, in Chrome's AppleScript isolated world. No cookies, tokens,
 * internal framework stores, private APIs, keyboard events or native pickers. */
(function (request) {
  "use strict";
  const fail = (code, detail = code) => { const e = new Error(detail); e.code = code; throw e; };
  const norm = s => String(s || "").replace(/\u00a0/g, " ").replace(/\s+/g, " ").trim();
  const visible = e => !!e.getClientRects().length && getComputedStyle(e).visibility !== "hidden";
  const label = e => norm(e.getAttribute("aria-label") || e.innerText || e.getAttribute("title") || e.getAttribute("placeholder"));
  const noURLs = s => norm(String(s).replace(/https?:\/\/[^\s<>]+/g, ""));
  const text = e => e.isContentEditable ? e.innerText : ("value" in e ? e.value : e.innerText);
  const all = spec => {
    if (!spec || !spec.selector || /^(?:html|body|\*)$/.test(spec.selector.trim())) fail("UNSCOPED_LOCATOR");
    let result = Array.from(document.querySelectorAll(spec.selector));
    if (!spec.hidden) result = result.filter(visible);
    if (spec.name !== undefined) result = result.filter(e => label(e) === norm(spec.name));
    if (spec.text !== undefined) result = result.filter(e => norm(e.innerText) === norm(spec.text));
    if (spec.contains) result = result.filter(e => [].concat(spec.contains).every(s => norm(e.innerText).includes(norm(s))));
    if (spec.within) result = result.filter(e => {const parent=e.closest(spec.within.selector);return parent && [].concat(spec.within.contains).every(s=>norm(parent.innerText).includes(norm(s)));});
    if (spec.descendant_attribute) { const a=spec.descendant_attribute; result=result.filter(e=>Array.from(e.querySelectorAll(a.selector)).some(child=>norm(child.getAttribute(a.attribute)).includes(norm(a.contains)))); }
    return result;
  };
  const locate = specs => {
    for (const spec of [].concat(specs || [])) {
      const matches = all(spec);
      if (matches.length > 1) fail("AMBIGUOUS_CONTROL", `${spec.selector}: ${matches.length} matches`);
      if (matches.length === 1) return matches[0];
    }
    fail("CONTROL_MISSING", JSON.stringify(specs));
  };
  const exists = specs => { try { locate(specs); return true; } catch (e) { if (e.code === "CONTROL_MISSING") return false; throw e; } };
  const checked = e => {
    const input = e.matches('input[type="checkbox"],input[type="radio"]') ? e : e.querySelector('input[type="checkbox"],input[type="radio"]');
    if (input) return !!input.checked;
    const value = e.getAttribute("aria-checked");
    if (value !== "true" && value !== "false") fail("CHECKED_STATE_UNAVAILABLE");
    return value === "true";
  };
  const enabled = e => !e.disabled && e.getAttribute("aria-disabled") !== "true";
  const assertChecks = checks => {
    const receipts = [];
    for (const check of checks || []) {
      const e = locate(check.locator);
      if (check.text !== undefined && norm(text(e)) !== norm(check.text)) fail("TEXT_READBACK_CHANGED");
      if (check.contains && !norm(text(e)).includes(norm(check.contains))) fail("TEXT_READBACK_CHANGED");
      if (check.checked !== undefined && checked(e) !== check.checked) fail("WRONG_SELECTED_ACCOUNT");
      if (check.image && !(e.tagName === "IMG" && e.complete && e.naturalWidth > 0)) fail("PHOTO_NOT_LOADED");
      receipts.push({label: label(e), text: norm(text(e)).slice(0, 800), image: !!check.image});
    }
    return receipts;
  };
  const sensitiveRoute = () => /\/(checkpoint|challenge|login|accounts\/login|authwall)(\/|$)/.test(location.pathname);
  const confirmContext = mutation => {
    if (location.href !== request.expectedURL) fail("TAB_NAVIGATED_EXTERNALLY");
    if (sensitiveRoute()) fail("ACCOUNT_ACTION_REQUIRED");
    if (mutation) {
      if (document.hasFocus()) fail("FOREGROUND_TAB_PAUSED");
      if (document.documentElement.getAttribute("data-boldstone-publisher") !== request.owner) fail("TAB_OWNERSHIP_LOST");
    }
  };
  const ready = () => {
    const checks = assertChecks(request.checks);
    if (!globalThis.__boldstoneMedia || globalThis.__boldstoneMedia.job !== request.job ||
        globalThis.__boldstoneMedia.sha256 !== request.mediaSha256 || !globalThis.__boldstoneMedia.committed) fail("MEDIA_RECEIPT_MISSING");
    const button = locate(request.submit);
    if (!enabled(button)) fail("SUBMIT_DISABLED");
    return {checks, submitLabel: label(button)};
  };
  try {
    const op = request.op;
    const readonly = ["probe", "snapshot", "exists", "assert", "discover", "readback", "upload_status", "clean_state"].includes(op);
    confirmContext(!readonly && op !== "claim");
    if (op === "probe") return JSON.stringify({ok:true, url:location.href, title:document.title, ready:document.readyState,
      hasFocus:document.hasFocus(), dataTransfer:typeof DataTransfer === "function", file:typeof File === "function",
      selfProfileEditable:!!document.querySelector('a[href="/accounts/edit/"]'),
      instagramPostLinks:Array.from(document.querySelectorAll('a[href]')).map(e=>e.href).filter(u=>/^https:\/\/www\.instagram\.com\/(?:[^/]+\/)?(?:p|reel)\//.test(u)).slice(0,20)});
    if (op === "claim") {
      if (document.hasFocus()) fail("FOREGROUND_TAB_PAUSED");
      const old = document.documentElement.getAttribute("data-boldstone-publisher");
      if (old && old !== request.owner) fail("TAB_ALREADY_OWNED");
      document.documentElement.setAttribute("data-boldstone-publisher", request.owner);
      return JSON.stringify({ok:true, claimed:true});
    }
    if (op === "snapshot") {
      const scope = request.scope ? locate(request.scope) : document.querySelector("main") || document.querySelector('[role="main"]');
      if (!scope) fail("READBACK_SCOPE_MISSING");
      return JSON.stringify({ok:true, url:location.href, title:document.title, text:scope.innerText.slice(0,30000),
        controls:Array.from(scope.querySelectorAll('button,[role="button"],input,textarea,[contenteditable="true"],[role="checkbox"]')).filter(visible).map(e=>({tag:e.tagName,id:e.id,role:e.getAttribute("role"),name:label(e),type:e.type,testid:e.getAttribute("data-testid"),placeholder:e.getAttribute("placeholder"),disabled:!enabled(e),checked:e.getAttribute("aria-checked")})),
        fileInputs:Array.from(document.querySelectorAll('input[type="file"]')).map(e=>({id:e.id,name:e.name,accept:e.accept,multiple:e.multiple,testid:e.getAttribute("data-testid")})),
        links:Array.from(scope.querySelectorAll('a[href]')).filter(visible).map(e=>({text:label(e),href:e.href}))});
    }
    if (op === "exists") return JSON.stringify({ok:true, exists:exists(request.locator)});
    if (op === "clean_state") {
      const fields = [].concat(request.caption).flatMap(all);
      const previews = [].concat(request.preview).flatMap(all);
      return JSON.stringify({ok:true,clean:fields.every(e=>!norm(text(e))) && previews.length===0});
    }
    if (op === "assert") return JSON.stringify({ok:true, checks:assertChecks(request.checks)});
    if (op === "click") {
      const e = locate(request.locator);
      if (!enabled(e)) fail("CONTROL_DISABLED");
      if (/\b(publish|post|share|send|schedule)\b/i.test(label(e)) || e.matches('input[type="file"]')) fail("GUARDED_ACTION_REQUIRED");
      if (/^(add (?:photos?|videos?|media)|select from computer|upload(?: photos?| videos?)?)$/i.test(label(e))) fail("NATIVE_PICKER_FORBIDDEN");
      e.click();
      return JSON.stringify({ok:true, clicked:label(e)});
    }
    if (op === "set_text") {
      const e = locate(request.locator);
      if (!enabled(e)) fail("CONTROL_DISABLED");
      if (!e.isContentEditable && !e.matches('textarea,input[type="text"],input[type="search"],input:not([type])')) fail("TEXT_FIELD_REQUIRED");
      if (norm(text(e)) !== norm(request.value)) {
        if (e.isContentEditable) {
          e.focus({preventScroll:true});
          const range = document.createRange(); range.selectNodeContents(e);
          const selection = window.getSelection(); selection.removeAllRanges(); selection.addRange(range);
          if (!document.execCommand("insertText", false, request.value)) fail("EDITOR_REJECTED_INPUT");
        } else {
          const prototype = e.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
          const setter = Object.getOwnPropertyDescriptor(prototype,"value").set;
          setter.call(e,request.value);
          e.dispatchEvent(new InputEvent("input",{bubbles:true,inputType:"insertText",data:request.value}));
          e.dispatchEvent(new Event("change",{bubbles:true}));
        }
      }
      if (norm(text(e)) !== norm(request.value)) fail("EDITOR_READBACK_FAILED");
      return JSON.stringify({ok:true, value:text(e)});
    }
    if (op === "set_checked") {
      const e = locate(request.locator);
      if (checked(e) !== request.value) {
        if (!enabled(e)) fail("CONTROL_DISABLED");
        e.click();
      }
      if (checked(e) !== request.value) fail("CHECKBOX_READBACK_FAILED");
      return JSON.stringify({ok:true, checked:checked(e)});
    }
    if (op === "upload_begin") {
      const e = locate(request.locator);
      if (!e.matches('input[type="file"]')) fail("FILE_INPUT_REQUIRED");
      globalThis.__boldstoneMedia = {job:request.job,expected:request.mediaSha256,name:request.name,type:request.type,
        size:request.size,chunks:[],status:"RECEIVING",committed:false,locator:request.locator};
      return JSON.stringify({ok:true,status:"RECEIVING"});
    }
    if (op === "upload_chunk") {
      const m = globalThis.__boldstoneMedia;
      if (!m || m.job !== request.job || m.status !== "RECEIVING") fail("UPLOAD_CONTEXT_LOST");
      if (request.index > m.chunks.length) fail("UPLOAD_CHUNK_GAP");
      if (m.chunks[request.index] && m.chunks[request.index] !== request.data) fail("UPLOAD_CHUNK_CHANGED");
      m.chunks[request.index] = request.data;
      return JSON.stringify({ok:true,index:request.index});
    }
    if (op === "upload_finish") {
      const m = globalThis.__boldstoneMedia;
      if (!m || m.job !== request.job || m.chunks.length !== request.chunks) fail("UPLOAD_INCOMPLETE");
      const parts = m.chunks.map(s=>Uint8Array.from(atob(s), c=>c.charCodeAt(0)));
      m.file = new File(parts,m.name,{type:m.type});
      if (m.file.size !== m.size) fail("UPLOAD_SIZE_CHANGED");
      m.status = "HASHING";
      m.file.arrayBuffer().then(b=>crypto.subtle.digest("SHA-256",b)).then(hash=>{
        m.sha256 = Array.from(new Uint8Array(hash),b=>b.toString(16).padStart(2,"0")).join("");
        m.status = m.sha256 === m.expected ? "HASH_VERIFIED" : "HASH_MISMATCH";
      }).catch(()=>{m.status="HASH_FAILED";});
      return JSON.stringify({ok:true,status:m.status});
    }
    if (op === "upload_status") {
      const m = globalThis.__boldstoneMedia;
      return JSON.stringify({ok:true,status:m && m.job===request.job?m.status:"MISSING",sha256:m?.sha256,committed:!!m?.committed});
    }
    if (op === "upload_commit") {
      const m = globalThis.__boldstoneMedia;
      if (!m || m.job !== request.job || m.status !== "HASH_VERIFIED" || m.sha256 !== request.mediaSha256) fail("UPLOAD_HASH_NOT_VERIFIED");
      const e = locate(m.locator);
      const transfer = new DataTransfer(); transfer.items.add(m.file); e.files = transfer.files;
      if (e.files.length !== 1 || e.files[0].size !== m.size || e.files[0].name !== m.name) fail("FILE_INPUT_READBACK_FAILED");
      e.dispatchEvent(new Event("input",{bubbles:true})); e.dispatchEvent(new Event("change",{bubbles:true}));
      m.committed = true; m.chunks = []; delete m.file;
      return JSON.stringify({ok:true,status:"FILE_INPUT_COMMITTED",sha256:m.sha256,name:m.name,size:m.size});
    }
    if (op === "ready" || op === "submit") {
      const result = ready();
      if (op === "submit") {
        const marker = "data-boldstone-submission-" + request.job;
        if (document.documentElement.hasAttribute(marker)) fail("SUBMIT_ALREADY_CLICKED");
        document.documentElement.setAttribute(marker,"attempted"); // before invoking the handler
        locate(request.submit).click();
      }
      return JSON.stringify({ok:true,status:op==="submit"?"CLICKED_UNCONFIRMED":"READY",...result});
    }
    if (op === "discover") {
      const re = new RegExp(request.pattern);
      const roots = request.roots ? [].concat(request.roots).flatMap(all) : [document.querySelector("main") || document.querySelector('[role="main"]')].filter(Boolean);
      const found = [...new Set(roots.flatMap(root=>[...(root.matches('a[href]')?[root]:[]),...Array.from(root.querySelectorAll('a[href]'))].filter(visible).map(e=>e.href)).filter(u=>re.test(u)))];
      if (found.length > 1) fail("AMBIGUOUS_NATIVE_POST", "More than one native post matches; supply the exact permalink for reconciliation");
      return JSON.stringify({ok:true,url:found[0]||null});
    }
    if (op === "readback") {
      const root = locate(request.root);
      if (!request.captionSelectors?.length) fail("NATIVE_CAPTION_SCOPE_MISSING");
      let captionRoot;
      for (const selector of request.captionSelectors) {
        if (/^(?:html|body|\*|article|main)$/.test(selector.trim())) fail("NATIVE_CAPTION_SCOPE_MISSING");
        const matches=Array.from(root.querySelectorAll(selector)).filter(visible).filter(e=>noURLs(e.innerText).includes(noURLs(request.caption)));
        if (matches.length>1) fail("AMBIGUOUS_NATIVE_CAPTION");
        if (matches.length===1) {captionRoot=matches[0];break;}
      }
      if (!captionRoot) fail("NATIVE_CAPTION_MISMATCH");
      const authors = [].concat(request.author).flatMap(spec=>Array.from(root.querySelectorAll(spec.selector)).filter(visible).filter(e=>norm(e.innerText || e.getAttribute("alt") || e.getAttribute("aria-label"))===norm(spec.name)));
      if (!authors.length) fail("NATIVE_AUTHOR_MISMATCH");
      const photos = Array.from(root.querySelectorAll(request.photoSelector)).filter(visible).filter(e=>e.tagName==="IMG" && e.complete && e.naturalWidth>0);
      if (photos.length !== 1) fail("NATIVE_PHOTO_MISMATCH", "Expected exactly one loaded post photograph");
      return JSON.stringify({ok:true,url:location.href,text:captionRoot.innerText,caption_verified:true,author_verified:true,photo_verified:true,
        authors:authors.map(e=>norm(e.innerText || e.getAttribute("alt"))),
        photo:{src:photos[0].currentSrc || photos[0].src,width:photos[0].naturalWidth,height:photos[0].naturalHeight},
        links:Array.from(captionRoot.querySelectorAll('a[href]')).map(e=>e.href)});
    }
    fail("UNSUPPORTED_OPERATION");
  } catch (error) {
    return JSON.stringify({ok:false,code:error.code||"DOM_ERROR",detail:String(error.message || error)});
  }
})
