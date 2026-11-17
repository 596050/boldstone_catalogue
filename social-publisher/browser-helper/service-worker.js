import { BRIDGE } from "./bridge-config.js";
import { uploadPhoto } from "./page-upload.js";

const VERSION = "1.0.0";
let currentWork;
async function api(path, options = {}) {
  const response = await fetch(BRIDGE.baseURL + path, {
    ...options, credentials:"omit", cache:"no-store", targetAddressSpace:"loopback",
    headers:{Authorization:"Bearer " + BRIDGE.token, "Content-Type":"application/json", ...(options.headers || {})},
    signal:AbortSignal.timeout(10000)
  });
  if (!response.ok) throw new Error("BRIDGE_HTTP_" + response.status);
  return response;
}
async function post(path, body, lease) {
  return (await api(path, {method:"POST", body:JSON.stringify(body), headers:lease ? {"X-Upload-Lease":lease} : {}})).json();
}
function encode(bytes) {
  let binary = "";
  for (let offset = 0; offset < bytes.length; offset += 32768) binary += String.fromCharCode(...bytes.subarray(offset, offset + 32768));
  return btoa(binary);
}
async function acknowledgePending() {
  const {pendingAck} = await chrome.storage.local.get("pendingAck");
  if (!pendingAck) return;
  await post("/result/" + pendingAck.request_id, pendingAck.result, pendingAck.lease);
  await chrome.storage.local.remove("pendingAck");
}
async function processOne(candidate) {
  const request = await post("/claim/" + candidate.request_id, {version:VERSION});
  let result;
  let injectionAttempted = false;
  try {
    const tab = await chrome.tabs.get(request.tab_id);
    const window = await chrome.windows.get(tab.windowId);
    if (tab.incognito || window.type !== "normal" || tab.windowId !== request.window_id || tab.url !== request.expected_url) throw new Error("TAB_CONTEXT_CHANGED");
    if (window.focused && tab.active) throw new Error("FOREGROUND_TAB_PAUSED");
    if (!["https://business.facebook.com", "https://www.linkedin.com"].includes(new URL(tab.url).origin)) throw new Error("WRONG_DESTINATION");
    const media = new Uint8Array(await (await api("/media/" + request.request_id, {headers:{"X-Upload-Lease":request.lease}})).arrayBuffer());
    const {lease, ...pageRequest} = request;
    injectionAttempted = true;
    const injected = await chrome.scripting.executeScript({
      target:{tabId:tab.id}, world:"MAIN", func:uploadPhoto,
      args:[{...pageRequest, base64:encode(media)}]
    });
    result = injected.find(value => value.frameId === 0)?.result;
    if (!result || result.request_id !== request.request_id) throw new Error("UPLOAD_RESULT_MISSING");
  } catch (error) {
    // Once injection has been attempted, never assume a lost result means that
    // the page did not receive the photograph. The local queue retains the lease.
    result = {ok:false, request_id:request.request_id, sha256:request.sha256,
      phase:injectionAttempted ? "OUTCOME_UNKNOWN" : "NOT_STARTED", code:"HELPER_ERROR", detail:String(error.message || error).slice(0,500)};
  }
  const pendingAck = {request_id:request.request_id, lease:request.lease, result};
  await chrome.storage.local.set({pendingAck});
  await acknowledgePending();
}
async function work() {
  await acknowledgePending();
  await post("/hello", {version:VERSION, extension_id:chrome.runtime.id});
  const deadline = Date.now() + 24000;
  let completed = false;
  while (Date.now() < deadline) {
    const {next} = await (await api("/next")).json();
    if (next) { await processOne(next); completed = true; }
    else if (completed) await new Promise(resolve => setTimeout(resolve, 750));
    else break;
  }
}
async function wake() {
  if (currentWork) return currentWork;
  currentWork = (async () => {
    const {bridgeConnected} = await chrome.storage.local.get("bridgeConnected");
    if (!bridgeConnected) return;
    await work();
  })().catch(async error => {
    await chrome.storage.local.set({lastError:String(error.message || error), checked_at:new Date().toISOString()});
  }).finally(() => { currentWork = undefined; });
  return currentWork;
}
async function schedule() {
  await chrome.alarms.create("boldstone-uploader", {periodInMinutes:0.5});
  await wake();
}
chrome.runtime.onInstalled.addListener(schedule);
chrome.runtime.onStartup.addListener(schedule);
chrome.alarms.onAlarm.addListener(alarm => { if (alarm.name === "boldstone-uploader") void wake(); });
chrome.runtime.onMessage.addListener((message, sender, respond) => {
  if (sender.id !== chrome.runtime.id || !sender.url?.startsWith("chrome-extension://" + chrome.runtime.id + "/")) return false;
  if (message?.type !== "check") return false;
  (async () => {
    await wake();
    try { respond({ok:true, health:await (await api("/health")).json()}); }
    catch (error) { respond({ok:false, error:String(error.message || error)}); }
  })();
  return true;
});
