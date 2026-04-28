const ui = {
  prompt: document.getElementById("prompt"),
  analyzeBtn: document.getElementById("analyzeBtn"),
  forgetBtn: document.getElementById("forgetBtn"),
  output: document.getElementById("output"),
  provider: document.getElementById("provider"),
  apiKey: document.getElementById("apiKey"),
  model: document.getElementById("model"),
  scopeMode: document.getElementById("scopeMode"),
  focusMode: document.getElementById("focusMode"),
  memoryMode: document.getElementById("memoryMode"),
  privacyPause: document.getElementById("privacyPause"),
  privacyAccess: document.getElementById("privacyAccess"),
  blockedDomains: document.getElementById("blockedDomains"),
  advancedMode: document.getElementById("advancedMode"),
  advancedBox: document.getElementById("advancedBox"),
  baseUrl: document.getElementById("baseUrl"),
  systemPrompt: document.getElementById("systemPrompt"),
  testBtn: document.getElementById("testBtn"),
  saveBtn: document.getElementById("saveBtn"),
  showShort: document.getElementById("showShort"),
  showDetailed: document.getElementById("showDetailed"),
  showSteps: document.getElementById("showSteps"),
  showCode: document.getElementById("showCode"),
  contextRing: document.getElementById("contextRing"),
  devMode: document.getElementById("devMode"),
  debugLog: document.getElementById("debugLog"),
  status: document.getElementById("status")
};

const state = {
  apiKeys: { openai: "", gemini: "" },
  modelsByProvider: { openai: [], gemini: [] },
  selectedModels: { openai: "gpt-4o-mini", gemini: "gemini-1.5-flash" },
  customBaseUrls: { openai: "https://api.openai.com/v1/chat/completions", gemini: "https://generativelanguage.googleapis.com/v1beta" },
  lastResult: null,
  debugLogs: []
};

let autoSaveTimer = null;

init().catch((err) => setStatus(`Init failed: ${err.message}`, true));

chrome.runtime.onMessage.addListener((message) => {
  if (message?.type === "QUICK_ACTION_RESULT") {
    state.lastResult = message.payload;
    renderResponse("detailed");
    renderContextRing(message.payload?.contextRing || {});
    logDebug("Quick action response received.", message.payload);
  }
});

ui.provider.addEventListener("change", async () => {
  ui.apiKey.value = state.apiKeys[currentProvider()] || "";
  await loadModelsForProvider(currentProvider(), true);
  toggleAdvancedUi();
  queueAutoSave();
});

ui.apiKey.addEventListener("input", () => {
  state.apiKeys[currentProvider()] = ui.apiKey.value.trim();
  queueAutoSave();
});

ui.model.addEventListener("change", () => {
  state.selectedModels[currentProvider()] = ui.model.value;
  queueAutoSave();
});

[ui.scopeMode, ui.focusMode, ui.memoryMode, ui.systemPrompt, ui.blockedDomains].forEach((el) => {
  el.addEventListener("input", queueAutoSave);
});
[ui.privacyPause, ui.privacyAccess, ui.advancedMode].forEach((el) => {
  el.addEventListener("change", () => {
    toggleAdvancedUi();
    queueAutoSave();
  });
});

ui.baseUrl.addEventListener("input", () => {
  state.customBaseUrls.openai = ui.baseUrl.value.trim();
  queueAutoSave();
});

ui.testBtn.addEventListener("click", async () => {
  try {
    setStatus("Testing API key...");
    const response = await chrome.runtime.sendMessage({
      type: "TEST_API_KEY",
      payload: { provider: currentProvider(), apiKey: ui.apiKey.value.trim() }
    });

    if (!response?.ok) throw new Error(response?.error || "Connection failed");
    setStatus(`${response.result.message} (${response.result.modelsCount} Modelle gefunden)`);
    await loadModelsForProvider(currentProvider(), true);
  } catch (error) {
    setStatus(error.message || "Connection failed", true);
  }
});

ui.saveBtn.addEventListener("click", async () => {
  try {
    await saveSettings();
    setStatus("Settings saved.");
  } catch (error) {
    setStatus(error.message || "Save failed", true);
  }
});

ui.analyzeBtn.addEventListener("click", async () => {
  setStatus("Collecting visible content...");
  try {
    const tab = await getActiveTab();
    const contentResponse = await collectVisibleContent(tab);
    if (!contentResponse?.ok) throw new Error("Could not read page content.");

    await saveSettings();
    const aiResponse = await chrome.runtime.sendMessage({
      type: "AI_ANALYZE_VISIBLE_CONTENT",
      payload: {
        ...contentResponse.payload,
        userPrompt: ui.prompt.value.trim()
      }
    });

    if (!aiResponse?.ok) throw new Error(aiResponse?.error || "Unknown AI error");

    state.lastResult = aiResponse.result;
    renderResponse("detailed");
    renderContextRing(aiResponse.result.contextRing || {});
    setStatus("Done.");
    logDebug("Analyze response", aiResponse.result);
  } catch (error) {
    setStatus(error.message || "Analyze failed", true);
  }
});

ui.forgetBtn.addEventListener("click", async () => {
  const tab = await getActiveTab();
  const url = tab.url || "";
  await chrome.runtime.sendMessage({ type: "FORGET_PAGE", payload: { url } });
  setStatus("Diese Seite wurde aus Memory entfernt.");
});

ui.showShort.addEventListener("click", () => renderResponse("short"));
ui.showDetailed.addEventListener("click", () => renderResponse("detailed"));
ui.showSteps.addEventListener("click", () => renderResponse("steps"));
ui.showCode.addEventListener("click", () => renderResponse("code"));
ui.devMode.addEventListener("change", () => {
  ui.debugLog.classList.toggle("hidden", !ui.devMode.checked);
  if (ui.devMode.checked) ui.debugLog.textContent = state.debugLogs.join("\n\n") || "No logs yet.";
});

async function init() {
  const response = await chrome.runtime.sendMessage({ type: "GET_API_SETTINGS" });
  if (!response?.ok) throw new Error(response?.error || "Unable to load settings");

  const s = response.settings;
  state.apiKeys = { ...state.apiKeys, ...(s.apiKeys || {}) };
  state.selectedModels = { ...state.selectedModels, ...(s.models || {}) };
  state.customBaseUrls = { ...state.customBaseUrls, ...(s.customBaseUrls || {}) };

  ui.provider.value = s.provider || "openai";
  ui.apiKey.value = state.apiKeys[currentProvider()] || "";
  ui.scopeMode.value = s.scopeMode || "tab";
  ui.focusMode.value = s.focusMode || "assist";
  ui.memoryMode.value = s.memory?.mode || "session";
  ui.privacyPause.checked = Boolean(s.privacy?.paused);
  ui.privacyAccess.value = s.privacy?.access || "tab";
  ui.blockedDomains.value = (s.privacy?.blockedDomains || []).join(", ");
  ui.advancedMode.checked = Boolean(s.advancedMode);
  ui.baseUrl.value = state.customBaseUrls.openai || "https://api.openai.com/v1/chat/completions";
  ui.systemPrompt.value = s.systemPrompt || "";

  toggleAdvancedUi();
  await loadModelsForProvider(currentProvider(), false);

  const local = await chrome.storage.local.get(["lastQuickActionResult"]);
  if (local.lastQuickActionResult) {
    state.lastResult = local.lastQuickActionResult;
    renderResponse("detailed");
    renderContextRing(local.lastQuickActionResult.contextRing || {});
  }
}

async function loadModelsForProvider(provider, forceReload) {
  const apiKey = (state.apiKeys[provider] || "").trim();
  if (!apiKey) {
    const fallback = provider === "gemini" ? "gemini-1.5-flash" : "gpt-4o-mini";
    state.modelsByProvider[provider] = [fallback];
    state.selectedModels[provider] = fallback;
    renderModelOptions(provider);
    return;
  }

  if (!forceReload && state.modelsByProvider[provider]?.length) {
    renderModelOptions(provider);
    return;
  }

  const response = await chrome.runtime.sendMessage({ type: "LIST_MODELS", payload: { provider, apiKey } });
  if (!response?.ok) throw new Error(response?.error || "Model loading failed");

  const models = response.models || [];
  if (!models.length) throw new Error("Keine Modelle gefunden.");
  state.modelsByProvider[provider] = models;
  state.selectedModels[provider] = models.includes(state.selectedModels[provider]) ? state.selectedModels[provider] : models[0];
  renderModelOptions(provider);
}

function renderModelOptions(provider) {
  ui.model.innerHTML = "";
  for (const m of state.modelsByProvider[provider] || []) {
    const option = document.createElement("option");
    option.value = m;
    option.textContent = m;
    ui.model.appendChild(option);
  }
  ui.model.value = state.selectedModels[provider] || ui.model.options[0]?.value || "";
}

async function saveSettings() {
  const provider = currentProvider();
  state.apiKeys[provider] = ui.apiKey.value.trim();
  state.selectedModels[provider] = ui.model.value;
  state.customBaseUrls.openai = ui.baseUrl.value.trim();

  const payload = {
    provider,
    apiKeys: state.apiKeys,
    models: state.selectedModels,
    customBaseUrls: state.customBaseUrls,
    advancedMode: ui.advancedMode.checked,
    systemPrompt: ui.systemPrompt.value,
    scopeMode: ui.scopeMode.value,
    focusMode: ui.focusMode.value,
    privacy: {
      paused: ui.privacyPause.checked,
      access: ui.privacyAccess.value,
      blockedDomains: ui.blockedDomains.value.split(",").map((x) => x.trim()).filter(Boolean)
    },
    memory: { mode: ui.memoryMode.value }
  };

  const response = await chrome.runtime.sendMessage({ type: "SAVE_API_SETTINGS", payload });
  if (!response?.ok) throw new Error(response?.error || "Could not save settings");
}

function toggleAdvancedUi() {
  const show = ui.advancedMode.checked && currentProvider() === "openai";
  ui.advancedBox.classList.toggle("hidden", !show);
}

function renderResponse(mode) {
  if (!state.lastResult) {
    ui.output.textContent = "No response yet.";
    return;
  }
  ui.output.textContent = state.lastResult[mode] || state.lastResult.text || "No response.";
}

function renderContextRing(ring) {
  ui.contextRing.textContent = JSON.stringify(ring, null, 2);
}

function queueAutoSave() {
  clearTimeout(autoSaveTimer);
  autoSaveTimer = setTimeout(async () => {
    try {
      await saveSettings();
    } catch {
      // ignore autosave errors
    }
  }, 600);
}

function currentProvider() {
  return ui.provider.value === "gemini" ? "gemini" : "openai";
}

async function getActiveTab() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tabs.length || !tabs[0].id) throw new Error("No active tab found.");
  return tabs[0];
}

async function collectVisibleContent(tab) {
  try {
    return await chrome.tabs.sendMessage(tab.id, { type: "COLLECT_VISIBLE_CONTENT" });
  } catch {
    await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["content-script.js"] });
    return chrome.tabs.sendMessage(tab.id, { type: "COLLECT_VISIBLE_CONTENT" });
  }
}

function setStatus(message, isError = false) {
  ui.status.textContent = message;
  ui.status.style.color = isError ? "#fca5a5" : "#86efac";
}

function logDebug(label, obj) {
  const line = `[${new Date().toISOString()}] ${label}\n${JSON.stringify(obj || {}, null, 2)}`;
  state.debugLogs.push(line);
  state.debugLogs = state.debugLogs.slice(-20);
  if (ui.devMode.checked) ui.debugLog.textContent = state.debugLogs.join("\n\n");
}
