/* Runs through Chrome's public scripting API in the page's MAIN world.
 * Only DOM file controls are used. No app stores, cookies, access tokens,
 * network APIs, browser focus commands or Publish controls are accessed. */
export async function uploadPhoto(request) {
  const normalize = value => String(value || "").replace(/\s+/g, " ").trim();
  const visible = element => !!element.getClientRects().length && getComputedStyle(element).visibility !== "hidden";
  const label = element => normalize(element.getAttribute("aria-label") || element.innerText || element.getAttribute("title") || element.getAttribute("placeholder") || Array.from(element.labels||[]).map(label=>label.innerText).join(" "));
  const fail = (code, detail = code) => { const error = new Error(detail); error.code = code; throw error; };
  const locate = specifications => {
    for (const spec of [].concat(specifications || [])) {
      if (!spec.selector || /^(?:html|body|\*)$/.test(spec.selector.trim())) fail("UNSCOPED_LOCATOR");
      let matches = Array.from(document.querySelectorAll(spec.selector));
      if (!spec.hidden) matches = matches.filter(visible);
      if (spec.name !== undefined) matches = matches.filter(element => label(element) === normalize(spec.name));
      if (spec.text !== undefined) matches = matches.filter(element => normalize(element.innerText) === normalize(spec.text));
      if (spec.contains) matches = matches.filter(element => [].concat(spec.contains).every(part => normalize(element.innerText).includes(normalize(part))));
      if (matches.length > 1) fail("AMBIGUOUS_CONTROL");
      if (matches.length === 1) return matches[0];
    }
    fail("UPLOAD_CONTROL_MISSING");
  };
  const checkContext = () => {
    if (location.href !== request.expected_url) fail("TAB_NAVIGATED_EXTERNALLY");
    if (document.hasFocus()) fail("FOREGROUND_TAB_PAUSED");
    if (document.documentElement.getAttribute("data-boldstone-publisher") !== request.owner) fail("TAB_OWNERSHIP_LOST");
    if (document.documentElement.getAttribute("data-boldstone-job") !== request.job_id) fail("UPLOAD_JOB_CHANGED");
    if (/\/(?:checkpoint|challenge|login|authwall)(?:\/|$)/.test(location.pathname)) fail("ACCOUNT_ACTION_REQUIRED");
    if (!Number.isFinite(request.expires_at) || Date.now() > request.expires_at * 1000) fail("UPLOAD_REQUEST_EXPIRED");
  };
  const checkGuards = () => {
    for (const guard of request.guards || []) {
      let element;
      try { element = locate(guard.locator); } catch (error) {
        if (guard.if_exists && error.code === "UPLOAD_CONTROL_MISSING") continue;
        throw error;
      }
      const value = normalize(element.innerText || element.value);
      if (guard.contains && !value.includes(normalize(guard.contains))) fail("WRONG_SELECTED_ACCOUNT");
      if (guard.not_contains && value.includes(normalize(guard.not_contains))) fail("WRONG_SELECTED_ACCOUNT");
      if (guard.checked !== undefined) {
        const input = element.matches('input[type="checkbox"],input[type="radio"]') ? element : element.querySelector('input[type="checkbox"],input[type="radio"]');
        const selected = input ? !!input.checked : (element.getAttribute("aria-checked") ?? element.getAttribute("aria-selected"));
        if (selected !== guard.checked && selected !== String(guard.checked)) fail("WRONG_SELECTED_ACCOUNT");
      }
    }
  };
  let phase = "NOT_STARTED";
  let restore = () => {};
  let timer;
  try {
    checkContext();
    checkGuards();
    if (!/^[a-f0-9]{32}$/.test(request.request_id) || !/^[a-f0-9]{64}$/.test(request.sha256)) fail("UPLOAD_REQUEST_INVALID");
    const marker = "data-boldstone-upload-" + request.request_id;
    const old = document.documentElement.getAttribute(marker);
    if (old) {
      const previous = JSON.parse(old);
      if (previous.sha256 !== request.sha256) fail("UPLOAD_RECEIPT_CHANGED");
      if (previous.ok) return previous;
      fail("UPLOAD_OUTCOME_UNKNOWN", "A prior file event may have run; inspect the composer before another upload");
    }
    if (!["image/png", "image/jpeg"].includes(request.mime_type) || request.size <= 0 || request.size > 15000000) fail("MEDIA_FORMAT");
    const binary = atob(request.base64);
    const bytes = Uint8Array.from(binary, character => character.charCodeAt(0));
    if (bytes.length !== request.size) fail("MEDIA_SIZE_CHANGED");
    const hashBuffer = await crypto.subtle.digest("SHA-256", bytes);
    const hash = Array.from(new Uint8Array(hashBuffer), value => value.toString(16).padStart(2, "0")).join("");
    if (hash !== request.sha256) fail("MEDIA_HASH_CHANGED");
    checkContext();
    checkGuards();
    const file = new File([bytes], request.name, {type: request.mime_type});
    const transfer = new DataTransfer();
    transfer.items.add(file);
    let resolveInput, rejectInput;
    const captured = new Promise((resolve, reject) => { resolveInput = resolve; rejectInput = reject; });
    let supplied = false;
    const accepts = input => {
      const types = (input.accept || "").toLowerCase().split(",").map(value => value.trim()).filter(Boolean);
      const suffix = request.mime_type === "image/png" ? ".png" : ".jpg";
      return !types.length || types.some(type => type === "image/*" || type === request.mime_type || type === suffix || (suffix === ".jpg" && type === ".jpeg"));
    };
    const supply = input => {
      if (supplied) return;
      try {
        checkContext();
        if (!(input instanceof HTMLInputElement) || input.type !== "file" || !accepts(input)) fail("WRONG_FILE_INPUT");
        supplied = true;
        phase = "FILE_ASSIGNMENT_ATTEMPTED";
        document.documentElement.setAttribute(marker, JSON.stringify({ok:false, phase, sha256:hash}));
        input.files = transfer.files;
        if (input.files.length !== 1 || input.files[0].name !== request.name || input.files[0].size !== request.size) fail("FILE_INPUT_READBACK_FAILED");
        // Some sites create a detached input and register its handler after click().
        // The microtask lets that handler finish registering without a native picker.
        queueMicrotask(() => {
          try {
            checkContext();
            checkGuards();
            phase = "FILE_EVENTS_DISPATCHED";
            document.documentElement.setAttribute(marker, JSON.stringify({ok:false, phase, sha256:hash}));
            input.dispatchEvent(new Event("input", {bubbles:true}));
            input.dispatchEvent(new Event("change", {bubbles:true}));
            resolveInput({accept:input.accept || "", input_count:input.files.length});
          } catch (error) { rejectInput(error); }
        });
      } catch (error) { rejectInput(error); }
    };
    const descriptors = [];
    const patch = (prototype, property) => {
      const original = prototype[property];
      if (typeof original !== "function") return;
      const own = Object.getOwnPropertyDescriptor(prototype, property);
      descriptors.push({prototype, property, own});
      Object.defineProperty(prototype, property, {configurable:true, writable:true, value:function (...args) {
        if (this instanceof HTMLInputElement && this.type === "file") { supply(this); return; }
        return original.apply(this, args);
      }});
    };
    restore = () => {
      for (const {prototype, property, own} of descriptors.reverse()) {
        if (own) Object.defineProperty(prototype, property, own);
        else delete prototype[property];
      }
    };
    patch(HTMLElement.prototype, "click");
    patch(HTMLInputElement.prototype, "click");
    patch(HTMLInputElement.prototype, "showPicker");
    const trigger = locate(request.trigger);
    const directInput = trigger instanceof HTMLInputElement && trigger.type === "file";
    if (!directInput && !new Set(["Media", "Photo", "Add photo/video", "Add photos", "Upload photos", "Select from computer", "Upload from computer"]).has(label(trigger))) fail("UPLOAD_CONTROL_REQUIRED");
    if (trigger.disabled || trigger.getAttribute("aria-disabled") === "true") fail("UPLOAD_CONTROL_DISABLED");
    if (directInput) supply(trigger);
    else trigger.click();
    const timeout = new Promise((_, reject) => {
      timer = setTimeout(() => { const error = new Error("The control did not create a usable file input"); error.code = "FILE_INPUT_NOT_CREATED"; reject(error); }, Math.min(15000, Math.max(250, request.timeout_ms || 12000)));
    });
    const metadata = await Promise.race([captured, timeout]);
    checkContext();
    const result = {ok:true, phase, request_id:request.request_id, sha256:hash, name:request.name,
      size:request.size, mime_type:request.mime_type, method:"chrome-main-world-file-input", ...metadata};
    document.documentElement.setAttribute(marker, JSON.stringify(result));
    return result;
  } catch (error) {
    return {ok:false, phase, request_id:request.request_id, sha256:request.sha256,
      code:error.code || "UPLOAD_ERROR", detail:String(error.message || error).slice(0,500)};
  } finally {
    clearTimeout(timer);
    restore();
  }
}
