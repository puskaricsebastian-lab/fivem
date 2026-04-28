const DEFAULT_MODEL = "gpt-4o-mini";

chrome.runtime.onInstalled.addListener(() => {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
});

chrome.tabs.onActivated.addListener(async ({ tabId }) => {
  await chrome.sidePanel.setOptions({ tabId, path: "sidepanel.html", enabled: true });
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "AI_ANALYZE_VISIBLE_CONTENT") {
    handleAnalyzeVisibleContent(message)
      .then((result) => sendResponse({ ok: true, result }))
      .catch((error) =>
        sendResponse({
          ok: false,
          error: error instanceof Error ? error.message : "Unknown AI request failure"
        })
      );

    return true;
  }

  if (message?.type === "GET_API_SETTINGS") {
    getApiSettings()
      .then((settings) => sendResponse({ ok: true, settings }))
      .catch((error) =>
        sendResponse({
          ok: false,
          error: error instanceof Error ? error.message : "Unable to load settings"
        })
      );

    return true;
  }

  if (message?.type === "SAVE_API_SETTINGS") {
    saveApiSettings(message.payload)
      .then(() => sendResponse({ ok: true }))
      .catch((error) =>
        sendResponse({
          ok: false,
          error: error instanceof Error ? error.message : "Unable to save settings"
        })
      );

    return true;
  }

  return false;
});

async function getApiSettings() {
  const { apiKey = "", model = DEFAULT_MODEL, systemPrompt = defaultSystemPrompt() } =
    await chrome.storage.sync.get(["apiKey", "model", "systemPrompt"]);

  return { apiKey, model, systemPrompt };
}

async function saveApiSettings(payload = {}) {
  const safePayload = {
    apiKey: String(payload.apiKey ?? "").trim(),
    model: String(payload.model ?? DEFAULT_MODEL).trim() || DEFAULT_MODEL,
    systemPrompt: String(payload.systemPrompt ?? defaultSystemPrompt()).trim() || defaultSystemPrompt()
  };

  await chrome.storage.sync.set(safePayload);
}

async function handleAnalyzeVisibleContent(message) {
  const { visibleText, pageTitle, url, userPrompt } = message.payload || {};

  if (!visibleText || !String(visibleText).trim()) {
    throw new Error("No visible page content was captured.");
  }

  const { apiKey, model, systemPrompt } = await getApiSettings();
  if (!apiKey) {
    throw new Error("Missing API key. Open side panel settings and add your API key.");
  }

  const body = {
    model: model || DEFAULT_MODEL,
    messages: [
      {
        role: "system",
        content: systemPrompt || defaultSystemPrompt()
      },
      {
        role: "user",
        content: [
          `User request: ${userPrompt || "Summarize and explain what matters."}`,
          `Page title: ${pageTitle || "(unknown)"}`,
          `URL: ${url || "(unknown)"}`,
          "Visible page content:",
          visibleText
        ].join("\n\n")
      }
    ],
    temperature: 0.3
  };

  const response = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`
    },
    body: JSON.stringify(body)
  });

  if (!response.ok) {
    throw await buildApiError(response);
  }

  const data = await response.json();
  const text = data?.choices?.[0]?.message?.content?.trim();

  if (!text) {
    throw new Error("AI response was empty.");
  }

  return {
    text,
    model: body.model,
    generatedAt: new Date().toISOString()
  };
}

async function buildApiError(response) {
  const raw = await response.text();
  let parsed;

  try {
    parsed = JSON.parse(raw);
  } catch {
    parsed = null;
  }

  const apiMessage = parsed?.error?.message || "Unknown API error";
  const apiCode = parsed?.error?.code || "";

  if (response.status === 429 || apiCode === "insufficient_quota") {
    return new Error(
      "AI quota reached (429/insufficient_quota). Check your provider billing/quota, then retry. " +
        "You can also switch to a different API key/model in Settings."
    );
  }

  if (response.status === 401) {
    return new Error("Unauthorized (401). Your API key is invalid, expired, or lacks access to the selected model.");
  }

  if (response.status === 403) {
    return new Error("Forbidden (403). Your account may not have permission for this model or endpoint.");
  }

  return new Error(`AI API error (${response.status}): ${apiMessage.slice(0, 300)}`);
}

function defaultSystemPrompt() {
  return [
    "You are an assistant embedded in a browser side panel.",
    "Provide concise, practical help grounded in the user's currently visible page.",
    "If information is unclear from visible content, say so explicitly."
  ].join(" ");
}
