const ui = {
  prompt: document.getElementById("prompt"),
  analyzeBtn: document.getElementById("analyzeBtn"),
  output: document.getElementById("output"),
  apiKey: document.getElementById("apiKey"),
  model: document.getElementById("model"),
  systemPrompt: document.getElementById("systemPrompt"),
  saveBtn: document.getElementById("saveBtn"),
  status: document.getElementById("status")
};

init().catch((err) => setStatus(`Init failed: ${err.message}`, true));

ui.analyzeBtn.addEventListener("click", async () => {
  setStatus("Collecting visible content from active tab...");
  ui.output.textContent = "Thinking...";

  try {
    const tab = await getActiveTab();
    const contentResponse = await chrome.tabs.sendMessage(tab.id, { type: "COLLECT_VISIBLE_CONTENT" });

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

    const { text, model, generatedAt } = aiResponse.result;
    ui.output.textContent = `${text}\n\n— ${model} @ ${new Date(generatedAt).toLocaleTimeString()}`;
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
        apiKey: ui.apiKey.value,
        model: ui.model.value,
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

  const { apiKey, model, systemPrompt } = response.settings;
  ui.apiKey.value = apiKey || "";
  ui.model.value = model || "";
  ui.systemPrompt.value = systemPrompt || "";
}

async function getActiveTab() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tabs.length || !tabs[0].id) {
    throw new Error("No active tab found.");
  }

  return tabs[0];
}

function setStatus(message, isError = false) {
  ui.status.textContent = message;
  ui.status.style.color = isError ? "#fca5a5" : "#86efac";
}
