/* Public DOM only, in Chrome's AppleScript isolated world. No cookies, tokens,
 * internal framework stores, private APIs, OS input or native pickers. */
(function (request) {
  "use strict";
  const fail = (code, detail = code) => { const e = new Error(detail); e.code = code; throw e; };
  const norm = s => String(s || "").replace(/[\u200b\uFEFF]/g, "").replace(/\u00a0/g, " ").replace(/\s+/g, " ").trim();
  const visible = e => !!e.getClientRects().length && getComputedStyle(e).visibility!=="hidden";
  const painted = e => {
    if (!visible(e)) return false;
    for (let v=e;v;v=v.parentElement) {
      const style=getComputedStyle(v);
      if (style.visibility==="hidden" || style.opacity==="0") return false;
    }
    return true;
  };
  const label = e => norm(e.getAttribute("aria-label") || e.innerText || e.getAttribute("title") || e.getAttribute("placeholder") || Array.from(e.labels||[]).map(l=>l.innerText).join(" "));
  const noURLs = s => norm(String(s).replace(/https?:\/\/[^\s<>]+/g, ""));
  const text = e => e.isContentEditable ? e.innerText : ("value" in e ? e.value : e.innerText);
  const all = spec => {
    if (!spec || !spec.selector || /^(?:html|body|\*)$/.test(spec.selector.trim())) fail("UNSCOPED_LOCATOR");
    let result = Array.from(document.querySelectorAll(spec.selector));
    if (!spec.hidden) result = result.filter(visible);
    if (spec.painted) result=result.filter(painted);
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
    const value = e.getAttribute("aria-checked") ?? e.getAttribute("aria-selected");
    if (value !== "true" && value !== "false") fail("CHECKED_STATE_UNAVAILABLE");
    return value === "true";
  };
  const enabled = e => !e.disabled && e.getAttribute("aria-disabled") !== "true";
  const assertChecks = checks => {
    const receipts = [];
    for (const check of checks || []) {
      if (check.absent) {
        if ([].concat(check.locator).some(spec=>all(spec).length)) fail("UNFINISHED_DIALOG");
        receipts.push({absent:true});continue;
      }
      if (check.if_exists && !exists(check.locator)) {receipts.push({optional_control_absent:true});continue;}
      const e = locate(check.locator);
      if (check.text !== undefined && norm(text(e)) !== norm(check.text)) fail("TEXT_READBACK_CHANGED");
      if (check.contains && !norm(text(e)).includes(norm(check.contains))) fail("TEXT_READBACK_CHANGED");
      if (check.not_contains && norm(text(e)).includes(norm(check.not_contains))) fail("WRONG_SELECTED_ACCOUNT");
      if (check.checked !== undefined && checked(e) !== check.checked) fail("WRONG_SELECTED_ACCOUNT");
      if (check.image && !(e.tagName === "IMG" && e.complete && e.naturalWidth > 0)) fail("PHOTO_NOT_LOADED");
      if (check.alt_text!==undefined && norm(e.getAttribute('alt'))!==norm(check.alt_text)) fail("PHOTO_ALT_TEXT_CHANGED");
      if (check.tag_receipt) {
        const tag=globalThis.__boldstoneProductTag;
        if (!tag || tag.job!==request.job || tag.sha256!==request.mediaSha256 || tag.name!==check.tag_receipt.name || tag.price_text!==check.tag_receipt.price_text || tag.url!==location.href) fail("PRODUCT_TAG_RECEIPT_MISSING");
      }
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
    if (op === "navigate") {
      const target = new URL(request.url);
      if (target.protocol !== "https:") fail("WRONG_DESTINATION");
      location.assign(target.href);
      return JSON.stringify({ok:true,status:"NAVIGATION_REQUESTED"});
    }
    if (op === "begin_job") {
      if (!request.job) fail("UPLOAD_JOB_MISSING");
      const old=document.documentElement.getAttribute("data-boldstone-job");
      if (old && old!==request.job) fail("UPLOAD_JOB_CHANGED");
      document.documentElement.setAttribute("data-boldstone-job",request.job);
      return JSON.stringify({ok:true,job:request.job});
    }
    if (op === "snapshot") {
      let scope = request.scope ? locate(request.scope) : request.fullDocument ? document.body : document.querySelector("main") || document.querySelector('[role="main"]') || document.body;
      if (Number.isInteger(request.scopeUp) && request.scopeUp>0 && request.scopeUp<=4) for(let i=0;i<request.scopeUp && scope.parentElement;i++) scope=scope.parentElement;
      if (!scope) fail("READBACK_SCOPE_MISSING");
      return JSON.stringify({ok:true, url:location.href, title:document.title, text:scope.innerText.slice(0,30000),
        ...(request.includeHTML ? {html:scope.outerHTML.slice(0,50000)} : {}),
        activeElement:document.activeElement?.outerHTML.slice(0,2000),
        icons:Array.from(scope.querySelectorAll('svg[aria-label]')).filter(visible).map(e=>({label:e.getAttribute('aria-label'),html:e.outerHTML.slice(0,1400),parent:e.parentElement?.outerHTML.slice(0,2000)})),
        inputs:Array.from(document.querySelectorAll('input')).filter(visible).map(e=>({html:e.outerHTML,value:e.value,focus:e===document.activeElement})),
        dialogs:Array.from(document.querySelectorAll('[role="dialog"],dialog[open]')).filter(visible).map(e=>({text:e.innerText.slice(0,1500),html:e.outerHTML.slice(0,800),ancestors:Array.from((function*(v){for(let i=0;v&&i<8;i++,v=v.parentElement)yield v;})(e)).map(v=>({tag:v.tagName,cls:v.className,ariaHidden:v.getAttribute('aria-hidden'),style:v.getAttribute('style'),opacity:getComputedStyle(v).opacity,visibility:getComputedStyle(v).visibility,pointerEvents:getComputedStyle(v).pointerEvents}))})),
        controls:Array.from(scope.querySelectorAll('button,[role="button"],input,textarea,[contenteditable="true"],[role="checkbox"],[role="combobox"],[role="option"],[role="tab"]')).filter(visible).map(e=>({tag:e.tagName,id:e.id,role:e.getAttribute("role"),name:label(e),text:norm(e.innerText).slice(0,800),type:e.type,testid:e.getAttribute("data-testid"),placeholder:e.getAttribute("placeholder"),disabled:!enabled(e),checked:e.matches('input[type="checkbox"],input[type="radio"]')?!!e.checked:e.getAttribute("aria-checked"),selected:e.getAttribute("aria-selected"),expanded:e.getAttribute("aria-expanded"),haspopup:e.getAttribute("aria-haspopup")})),
        fileInputs:Array.from(document.querySelectorAll('input[type="file"]')).map(e=>({id:e.id,name:e.name,accept:e.accept,multiple:e.multiple,testid:e.getAttribute("data-testid")})),
        images:Array.from(scope.querySelectorAll('img')).filter(visible).map(e=>({src:e.currentSrc||e.src,alt:e.alt,width:e.naturalWidth,height:e.naturalHeight,html:e.outerHTML,parent:e.parentElement?.outerHTML.slice(0,1800)})),
        editors:Array.from(document.querySelectorAll('[contenteditable],textarea,[role=textbox]')).map(e=>({tag:e.tagName,role:e.getAttribute('role'),label:label(e),editable:e.getAttribute('contenteditable'),text:e.innerText,value:e.value,html:e.outerHTML.slice(0,6000)})),
        links:Array.from(scope.querySelectorAll('a[href]')).filter(visible).map(e=>({text:label(e),href:e.href}))});
    }
    if (op === "exists") return JSON.stringify({ok:true, exists:exists(request.locator)});
    if (op === "clean_state") {
      const fields = [].concat(request.caption).flatMap(all);
      const previews = [].concat(request.preview).flatMap(all);
      return JSON.stringify({ok:true,clean:fields.every(e=>!norm(text(e))) && previews.length===0,
        caption_count:fields.length,nonempty_caption_count:fields.filter(e=>norm(text(e))).length,preview_count:previews.length});
    }
    if (op === "assert") return JSON.stringify({ok:true, checks:assertChecks(request.checks)});
    if (op === "attest_product_tag") {
      const tag=request.tag,media=globalThis.__boldstoneMedia;
      if (!tag?.name || !tag.price_text || !request.job || !media?.committed || media.job!==request.job || media.sha256!==request.mediaSha256) fail("PRODUCT_TAG_CONTEXT_MISSING");
      const heading=locate(request.heading), panel=locate(request.panel);
      if (!panel.contains(heading) || norm(heading.innerText)!==norm(tag.name) || norm(heading.parentElement.innerText)!==norm(tag.name+" "+tag.price_text) || [].concat(request.markers).flatMap(all).length!==1) fail("PRODUCT_TAG_SELECTION_MISMATCH");
      const proof={job:request.job,sha256:request.mediaSha256,name:tag.name,price_text:tag.price_text,url:location.href,selected_count:1,persisted_editor_readback:true};
      globalThis.__boldstoneProductTag=proof;
      return JSON.stringify({ok:true,product_tag:proof});
    }
    if (op === "click") {
      const e = locate(request.locator);
      if (!enabled(e)) fail("CONTROL_DISABLED");
      const opensComposer = ["Start a post", "Create post", "Manage post", "Edit post", "Edit Post"].includes(label(e));
      const opensPostMenu = /^Actions for this post(?: by .+)?$/.test(label(e)) && e.getAttribute("aria-haspopup") === "menu";
      if ((!opensComposer && !opensPostMenu && /\b(publish|post|share|send|schedule|boost|promote|ad)\b/i.test(label(e))) || e.matches('input[type="file"]')) fail("GUARDED_ACTION_REQUIRED");
      if (/^(add (?:photos?|videos?|media)|select from computer|upload(?: photos?| videos?)?)$/i.test(label(e))) fail("NATIVE_PICKER_FORBIDDEN");
      if (request.method==="mouse") {
        const r=e.getBoundingClientRect(), p={bubbles:true,cancelable:true,button:0,clientX:r.left+r.width/2,clientY:r.top+r.height/2};
        e.dispatchEvent(new MouseEvent("mousedown",{...p,buttons:1}));
        e.dispatchEvent(new MouseEvent("mouseup",{...p,buttons:0}));
        e.dispatchEvent(new MouseEvent("click",{...p,buttons:0}));
      } else e.click();
      return JSON.stringify({ok:true, clicked:label(e)});
    }
    if (op === "click_photo_point") {
      const e=locate(request.locator);
      if (e.tagName!=="IMG" || !e.complete || e.naturalWidth<=0) fail("PHOTO_NOT_LOADED");
      const x=request.x, y=request.y;
      if (!Number.isFinite(x) || !Number.isFinite(y) || x<=0 || x>=1 || y<=0 || y>=1) fail("PHOTO_POINT_INVALID");
      assertChecks(request.checks);
      const r=e.getBoundingClientRect();
      const target=request.target ? locate(request.target) : e;
      if (target!==e && (target.tagName!=="BUTTON" || label(target) || !e.closest('[role="dialog"]') || target.closest('[role="dialog"]')!==e.closest('[role="dialog"]'))) fail("PHOTO_POINT_TARGET_INVALID");
      target.dispatchEvent(new MouseEvent("click",{bubbles:true,cancelable:true,clientX:r.left+r.width*x,clientY:r.top+r.height*y}));
      return JSON.stringify({ok:true,photo_point:{x,y},width:e.naturalWidth,height:e.naturalHeight});
    }
    if (op === "prepare_upload") {
      const e=locate(request.locator);
      if (!new Set(["Add photo/video","Media","Photo","Select from computer"]).has(label(e))) fail("UPLOAD_CONTROL_REQUIRED");
      if (navigator.userActivation.isActive) fail("USER_ACTIVATION_ACTIVE");
      // With no transient user activation Chrome cannot open a native picker.
      // The site's handler may still render its ordinary hidden file input.
      e.click();
      return JSON.stringify({ok:true,status:"UPLOAD_CONTROL_PREPARED_WITHOUT_USER_ACTIVATION"});
    }
    if (op === "set_text") {
      const e = locate(request.locator);
      if (!enabled(e)) fail("CONTROL_DISABLED");
      if (!e.isContentEditable && !e.matches('textarea,input[type="text"],input[type="search"],input:not([type])')) fail("TEXT_FIELD_REQUIRED");
      if (request.focus) e.focus({preventScroll:true});
      if (norm(text(e)) !== norm(request.value)) {
        if (e.isContentEditable) {
          e.focus({preventScroll:true});
          const range = document.createRange(); range.selectNodeContents(e);
          const selection = window.getSelection(); selection.removeAllRanges(); selection.addRange(range);
          if (request.method === "paste") {
            const clipboard = new DataTransfer(); clipboard.setData("text/plain",request.value);
            const event = new ClipboardEvent("paste",{bubbles:true,cancelable:true,clipboardData:clipboard});
            e.dispatchEvent(event);
            if (!event.defaultPrevented) fail("EDITOR_REJECTED_PASTE");
          } else if (!document.execCommand("insertText", false, request.value)) fail("EDITOR_REJECTED_INPUT");
        } else {
          const prototype = e.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
          const setter = Object.getOwnPropertyDescriptor(prototype,"value").set;
          setter.call(e,request.value);
          e.dispatchEvent(new InputEvent("input",{bubbles:true,inputType:"insertText",data:request.value}));
          e.dispatchEvent(new Event("change",{bubbles:true}));
        }
      }
      if (norm(text(e)) !== norm(request.value)) fail("EDITOR_READBACK_FAILED");
      if (request.typeahead) {
        if (e.tagName!=="INPUT" || e.getAttribute("role")!=="combobox" || e.type!=="text") fail("TYPEAHEAD_INPUT_REQUIRED");
        e.dispatchEvent(new FocusEvent("focus",{bubbles:false}));
        e.dispatchEvent(new FocusEvent("focusin",{bubbles:true}));
        e.dispatchEvent(new KeyboardEvent("keydown",{key:"ArrowDown",code:"ArrowDown",keyCode:40,which:40,bubbles:true,cancelable:true}));
        e.dispatchEvent(new KeyboardEvent("keyup",{key:"ArrowDown",code:"ArrowDown",keyCode:40,which:40,bubbles:true,cancelable:true}));
      }
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
      assertChecks(request.checks);
      const e = locate(request.locator);
      if (request.method !== "drop" && !e.matches('input[type="file"]')) fail("FILE_INPUT_REQUIRED");
      globalThis.__boldstoneMedia = {job:request.job,expected:request.mediaSha256,name:request.name,type:request.type,
        size:request.size,chunks:[],status:"RECEIVING",committed:false,locator:request.locator,method:request.method||"input"};
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
      return JSON.stringify({ok:true,status:m && m.job===request.job?m.status:"MISSING",sha256:m?.sha256,committed:!!m?.committed,method:m?.method});
    }
    if (op === "adopt_upload") {
      const r=request.receipt;
      if (!r || !/^[a-f0-9]{32}$/.test(r.request_id) || r.ok!==true || r.phase!=="FILE_EVENTS_DISPATCHED" ||
          r.method!=="chrome-main-world-file-input" || r.sha256!==request.mediaSha256) fail("UPLOAD_HELPER_RECEIPT_INVALID");
      const stored=JSON.parse(document.documentElement.getAttribute("data-boldstone-upload-"+r.request_id)||"null");
      if (!stored || stored.ok!==true || ["request_id","phase","sha256","name","size","method"].some(key=>stored[key]!==r[key])) fail("UPLOAD_HELPER_DOCUMENT_MISMATCH");
      const e=locate(request.preview);
      if (!(e.tagName==="IMG" && e.complete && e.naturalWidth>0)) fail("PHOTO_NOT_LOADED");
      globalThis.__boldstoneMedia={job:request.job,sha256:r.sha256,committed:true,status:"PHOTO_PREVIEW_CONFIRMED",method:"helper",receipt_id:r.request_id};
      return JSON.stringify({ok:true,status:"PHOTO_PREVIEW_CONFIRMED",sha256:r.sha256,receipt_id:r.request_id,
        photo:{src:e.currentSrc||e.src,width:e.naturalWidth,height:e.naturalHeight}});
    }
    if (op === "upload_commit") {
      const m = globalThis.__boldstoneMedia;
      if (!m || m.job !== request.job || m.status !== "HASH_VERIFIED" || m.sha256 !== request.mediaSha256) fail("UPLOAD_HASH_NOT_VERIFIED");
      assertChecks(request.checks);
      const e = locate(m.locator);
      const transfer = new DataTransfer(); transfer.items.add(m.file);
      if (m.method === "drop") {
        m.transfer=transfer;
        e.dispatchEvent(new DragEvent("dragenter",{bubbles:true,cancelable:true,dataTransfer:transfer}));
        return JSON.stringify({ok:true,status:"DRAG_ENTERED",sha256:m.sha256});
      } else {
        e.files = transfer.files;
        if (e.files.length !== 1 || e.files[0].size !== m.size || e.files[0].name !== m.name) fail("FILE_INPUT_READBACK_FAILED");
        e.dispatchEvent(new Event("input",{bubbles:true})); e.dispatchEvent(new Event("change",{bubbles:true}));
      }
      m.committed = true; m.chunks = []; delete m.file;
      return JSON.stringify({ok:true,status:"FILE_INPUT_COMMITTED",sha256:m.sha256,name:m.name,size:m.size});
    }
    if (op === "upload_drop") {
      const m=globalThis.__boldstoneMedia;
      if (!m || m.job!==request.job || !m.transfer || m.sha256!==request.mediaSha256) fail("UPLOAD_CONTEXT_LOST");
      assertChecks(request.checks);
      const e=locate(request.locator || m.locator);
      const type=request.phase==="over"?"dragover":"drop";
      e.dispatchEvent(new DragEvent(type,{bubbles:true,cancelable:true,dataTransfer:m.transfer}));
      if (type==="drop") {m.committed=true;m.chunks=[];delete m.file;delete m.transfer;}
      return JSON.stringify({ok:true,status:type==="drop"?"DROP_DISPATCHED_UNCONFIRMED":"DRAG_OVER_SENT"});
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
      const candidates = Array.from(root.querySelectorAll(request.photoSelector));
      let authoredPhotos = [];
      if (request.linkedinPhotoAlt !== undefined) {
        const page = new URL(location.href);
        if (page.protocol!=="https:" || page.hostname!=="www.linkedin.com" || !/^\/feed\/update\/urn:li:activity:\d+\/?$/.test(page.pathname) || !norm(request.linkedinPhotoAlt)) fail("NATIVE_PHOTO_SCOPE_MISSING");
        authoredPhotos = Array.from(root.querySelectorAll('img')).filter(e=>{
          if (norm(e.getAttribute('alt'))!==norm(request.linkedinPhotoAlt)) return false;
          try {
            const source = new URL(e.currentSrc || e.src || e.getAttribute('src'));
            return source.protocol==='https:' && source.hostname==='media.licdn.com' &&
              source.pathname.startsWith('/dms/image/') && source.pathname.split('/').some(part=>part.startsWith('feedshare-'));
          } catch { return false; }
        });
      }
      const photos = [...new Set([...candidates,...authoredPhotos])].filter(visible).filter(e=>e.tagName==="IMG" && e.complete && e.naturalWidth>0);
      if (photos.length !== 1) fail("NATIVE_PHOTO_MISMATCH", "Expected exactly one loaded post photograph");
      return JSON.stringify({ok:true,url:location.href,text:captionRoot.innerText,caption_verified:true,author_verified:true,photo_verified:true,
        authors:authors.map(e=>norm(e.innerText || e.getAttribute("alt"))),
        photo:{src:photos[0].currentSrc || photos[0].src,width:photos[0].naturalWidth,height:photos[0].naturalHeight,
          alt:photos[0].getAttribute('alt')||'',identity_method:authoredPhotos.includes(photos[0])?'exact authored alt and native LinkedIn feedshare image':'calibrated post photo selector'},
        links:Array.from(captionRoot.querySelectorAll('a[href]')).map(e=>e.href)});
    }
    fail("UNSUPPORTED_OPERATION");
  } catch (error) {
    return JSON.stringify({ok:false,code:error.code||"DOM_ERROR",detail:String(error.message || error)});
  }
})
