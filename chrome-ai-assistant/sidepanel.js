const ui = {
  prompt: document.getElementById("prompt"),
  analyzeBtn: document.getElementById("analyzeBtn"),
  output: document.getElementById("output"),
  provider: document.getElementById("provider"),
  apiKey: document.getElementById("apiKey"),
  model: document.getElementById("model"),
  testBtn: document.getElementById("testBtn"),
  saveBtn: document.getElementById("saveBtn"),
  advancedMode: document.getElementById("advancedMode"),
  advancedBox: document.getElementById("advancedBox"),
  baseUrl: document.getElementById("baseUrl"),
  systemPrompt: document.getElementById("systemPrompt"),
  status: document.getElementById("status")
};

const state = {
  apiKeys: { openai: "", gemini: "" },
  modelsByProvider: { openai: [], gemini: [] },
  selectedModels: { openai: "gpt-4o-mini", gemini: "gemini-1.5-flash" },
  customBaseUrls: { openai: "https://api.openai.com/v1/chat/completions", gemini: "https://generativelanguage.googleapis.com/v1beta" }
};

let autoSaveTimer = null;

init().catch((err) => setStatus(`Init failed: ${err.message}`, true));

ui.provider.addEventListener("change", async () => {
  await onProviderChange();
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

ui.systemPrompt.addEventListener("input", queueAutoSave);
ui.advancedMode.addEventListener("change", () => {
  toggleAdvancedUi();
  queueAutoSave();
});
ui.baseUrl.addEventListener("input", () => {
  state.customBaseUrls.openai = ui.baseUrl.value.trim();
  queueAutoSave();
});

ui.testBtn.addEventListener("click", async () => {
  try {
    setStatus("Testing API key...");
    const provider = currentProvider();
    const apiKey = ui.apiKey.value.trim();
    const response = await chrome.runtime.sendMessage({ type: "TEST_API_KEY", payload: { provider, apiKey } });

    if (!response?.ok) {
      throw new Error(response?.error || "Connection test failed");
    }

    setStatus(`${response.result.message} (${response.result.modelsCount} Modelle gefunden)`);
    await loadModelsForProvider(provider, true);
  } catch (error) {
    setStatus(error.message || "Connection test failed", true);
  }
});

ui.analyzeBtn.addEventListener("click", async () => {
  setStatus("Collecting visible content from active tab...");
  ui.output.textContent = "Thinking...";

  try {
    const tab = await getActiveTab();
    const contentResponse = await collectVisibleContent(tab);

    if (!contentResponse?.ok) {
      throw new Error("Could not read visible content from this tab.");
    }

    await saveSettings();

    const aiResponse = await chrome.runtime.sendMessage({
      type: "AI_ANALYZE_VISIBLE_CONTENT",
      payload: {
        ...contentResponse.payload,
        userPrompt: ui.prompt.value.trim()
      }
    });

    if (!aiResponse?.ok) {
      throw new Error(aiResponse?.error || "Unknown AI error");
    }

    const { text, model, provider, generatedAt } = aiResponse.result;
    ui.output.textContent = `${text}\n\n— ${provider}/${model} @ ${new Date(generatedAt).toLocaleTimeString()}`;
    setStatus("Done. The page remained active while AI ran in the side panel.");
  } catch (error) {
    ui.output.textContent = "No response.";
    setStatus(error.message || "Failed to analyze page", true);
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

async function init() {
  const response = await chrome.runtime.sendMessage({ type: "GET_API_SETTINGS" });
  if (!response?.ok) {
    throw new Error(response?.error || "Unable to load settings");
  }

  const { provider, apiKeys, models, customBaseUrls, systemPrompt, advancedMode } = response.settings;
  state.apiKeys = { ...state.apiKeys, ...(apiKeys || {}) };
  state.selectedModels = { ...state.selectedModels, ...(models || {}) };
  state.customBaseUrls = { ...state.customBaseUrls, ...(customBaseUrls || {}) };

  ui.provider.value = provider || "openai";
  ui.apiKey.value = state.apiKeys[currentProvider()] || "";
  ui.systemPrompt.value = systemPrompt || "";
  ui.advancedMode.checked = Boolean(advancedMode);
  ui.baseUrl.value = state.customBaseUrls.openai || "https://api.openai.com/v1/chat/completions";

  toggleAdvancedUi();
  await loadModelsForProvider(currentProvider(), false);
}

async function onProviderChange() {
  const provider = currentProvider();
  ui.apiKey.value = state.apiKeys[provider] || "";
  await loadModelsForProvider(provider, false);
}

async function loadModelsForProvider(provider, forceReload) {
  const apiKey = (state.apiKeys[provider] || "").trim();

  if (!apiKey) {
    const defaultModel = provider === "gemini" ? "gemini-1.5-flash" : "gpt-4o-mini";
    state.modelsByProvider[provider] = [defaultModel];
    state.selectedModels[provider] = defaultModel;
    renderModelOptions(provider);
    setStatus(`Bitte API-Key für ${provider.toUpperCase()} eintragen, um echte Modelle zu laden.`, true);
    return;
  }

  if (!forceReload && state.modelsByProvider[provider]?.length) {
    renderModelOptions(provider);
    return;
  }

  setStatus(`Lade Modelle für ${provider.toUpperCase()}...`);
  const response = await chrome.runtime.sendMessage({ type: "LIST_MODELS", payload: { provider, apiKey } });
  if (!response?.ok) {
    throw new Error(response?.error || "Model list could not be loaded.");
  }

  const models = response.models || [];
  if (!models.length) {
    throw new Error("Keine gültigen Modelle vom Provider zurückgegeben.");
  }

  state.modelsByProvider[provider] = models;
  const previousModel = state.selectedModels[provider];
  state.selectedModels[provider] = models.includes(previousModel) ? previousModel : models[0];

  renderModelOptions(provider);
  setStatus(`Modelle geladen (${models.length}).`);
}

function renderModelOptions(provider) {
  const models = state.modelsByProvider[provider] || [];
  const selected = state.selectedModels[provider];

  ui.model.innerHTML = "";
  for (const model of models) {
    const option = document.createElement("option");
    option.value = model;
    option.textContent = model;
    ui.model.appendChild(option);
  }

  if (models.includes(selected)) {
    ui.model.value = selected;
  } else if (models.length) {
    ui.model.value = models[0];
    state.selectedModels[provider] = models[0];
  }
}

async function saveSettings() {
  const provider = currentProvider();
  state.apiKeys[provider] = ui.apiKey.value.trim();
  state.selectedModels[provider] = ui.model.value;
  state.customBaseUrls.openai = ui.baseUrl.value.trim();

  const response = await chrome.runtime.sendMessage({
    type: "SAVE_API_SETTINGS",
    payload: {
      provider,
      apiKeys: state.apiKeys,
      models: state.selectedModels,
      customBaseUrls: state.customBaseUrls,
      advancedMode: ui.advancedMode.checked,
      systemPrompt: ui.systemPrompt.value
    }
  });

  if (!response?.ok) {
    throw new Error(response?.error || "Could not save settings");
  }
}

function toggleAdvancedUi() {
  const shouldShow = ui.advancedMode.checked && currentProvider() === "openai";
  ui.advancedBox.classList.toggle("hidden", !shouldShow);
}

function queueAutoSave() {
  clearTimeout(autoSaveTimer);
  autoSaveTimer = setTimeout(async () => {
    try {
      await saveSettings();
    } catch {
      // silent autosave errors; explicit save/test shows visible errors
    }
  }, 600);
}

function currentProvider() {
  return ui.provider.value === "gemini" ? "gemini" : "openai";
}

async function getActiveTab() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tabs.length || !tabs[0].id) {
    throw new Error("No active tab found.");
  }

  return tabs[0];
}

async function collectVisibleContent(tab) {
  if (!isScriptableUrl(tab.url || "")) {
    throw new Error("This tab cannot be analyzed (e.g. chrome://, extension pages, or Chrome Web Store).");
  }

  try {
    return await chrome.tabs.sendMessage(tab.id, { type: "COLLECT_VISIBLE_CONTENT" });
  } catch (error) {
    const errorMessage = String(error?.message || error);
    const noReceiver =
      errorMessage.includes("Receiving end does not exist") ||
      errorMessage.includes("Could not establish connection");

    if (!noReceiver) {
      throw error;
    }

    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ["content-script.js"]
    });

    return chrome.tabs.sendMessage(tab.id, { type: "COLLECT_VISIBLE_CONTENT" });
  }
}

function isScriptableUrl(url) {
  if (!url) return false;

  const blockedPrefixes = ["chrome://", "chrome-extension://", "edge://", "about:"];
  if (blockedPrefixes.some((prefix) => url.startsWith(prefix))) {
    return false;
  }

  return !url.includes("chrome.google.com/webstore");
}

function setStatus(message, isError = false) {
  ui.status.textContent = message;
  ui.status.style.color = isError ? "#fca5a5" : "#86efac";
}
