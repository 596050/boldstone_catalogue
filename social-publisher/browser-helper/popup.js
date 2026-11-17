import { BRIDGE } from "./bridge-config.js";

document.getElementById("check").addEventListener("click", async () => {
  const output = document.getElementById("result");
  try {
    output.textContent = "Connecting to the local uploader…";
    let permission;
    try { permission = await navigator.permissions.query({name:"loopback-network"}); } catch (_) { /* Older Chrome names differ. */ }
    if (permission?.state === "denied") throw new Error("Allow loopback access for this extension in Chrome site settings, then connect again.");
    const response = await fetch(BRIDGE.baseURL + "/health", {
      credentials:"omit", cache:"no-store", targetAddressSpace:"loopback",
      headers:{Authorization:"Bearer " + BRIDGE.token}, signal:AbortSignal.timeout(15000)
    });
    if (!response.ok) throw new Error("Start publisher.py helper-serve, then connect again. Local response: " + response.status);
    const health = await response.json();
    if (health.version !== "1.0.0" || health.extension_id !== chrome.runtime.id || health.bind !== "127.0.0.1") throw new Error("The local uploader identity did not match.");
    await chrome.storage.local.set({bridgeConnected:true});
    const result = await chrome.runtime.sendMessage({type:"check"});
    output.textContent = result?.ok ? JSON.stringify(result.health, null, 2) : result?.error || "The helper did not respond. Check the local publisher.";
  } catch (error) { output.textContent = String(error.message || error); }
});
