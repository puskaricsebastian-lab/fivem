const ui = {
  prompt: document.getElementById("prompt"),
  analyzeBtn: document.getElementById("analyzeBtn"),
  output: document.getElementById("output"),
  provider: document.getElementById("provider"),
  apiKey: document.getElementById("apiKey"),
  model: document.getElementById("model"),
  baseUrl: document.getElementById("baseUrl"),
  systemPrompt: document.getElementById("systemPrompt"),
  saveBtn: document.getElementById("saveBtn"),
  status: document.getElementById("status")
};

init().catch((err) => setStatus(`Init failed: ${err.message}`, true));

ui.provider.addEventListener("change", () => {
  applyProviderHints(ui.provider.value);
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
    const response = await chrome.runtime.sendMessage({
      type: "SAVE_API_SETTINGS",
      payload: {
        provider: ui.provider.value,
        apiKey: ui.apiKey.value,
        model: ui.model.value,
        baseUrl: ui.baseUrl.value,
        systemPrompt: ui.systemPrompt.value
      }
    });

    if (!response?.ok) {
      throw new Error(response?.error || "Could not save settings");
    }

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

  const { provider, apiKey, model, baseUrl, systemPrompt } = response.settings;
  ui.provider.value = provider || "openai";
  ui.apiKey.value = apiKey || "";
  ui.model.value = model || "";
  ui.baseUrl.value = baseUrl || "https://api.openai.com/v1/chat/completions";
  ui.systemPrompt.value = systemPrompt || "";
  applyProviderHints(ui.provider.value);
}

function applyProviderHints(provider) {
  if (provider === "gemini") {
    ui.model.placeholder = "gemini-1.5-flash";
    ui.baseUrl.disabled = true;
    ui.baseUrl.title = "Für Gemini wird der Google-Endpoint automatisch verwendet.";
    return;
  }

  ui.baseUrl.disabled = false;
  ui.baseUrl.title = "Nur für OpenAI/OpenAI-compatible verwendet.";
  if (provider === "openai_compatible") {
    ui.model.placeholder = "your-model-name";
    ui.baseUrl.placeholder = "https://your-provider/v1/chat/completions";
  } else {
    ui.model.placeholder = "gpt-4o-mini";
    ui.baseUrl.placeholder = "https://api.openai.com/v1/chat/completions";
  }
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
