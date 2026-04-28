const DEFAULTS = {
  provider: "openai",
  model: "gpt-4o-mini",
  systemPrompt: defaultSystemPrompt(),
  baseUrl: "https://api.openai.com/v1/chat/completions"
};

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
  const data = await chrome.storage.sync.get(["apiKey", "provider", "model", "systemPrompt", "baseUrl"]);

  return {
    apiKey: data.apiKey || "",
    provider: sanitizeProvider(data.provider),
    model: data.model || DEFAULTS.model,
    systemPrompt: data.systemPrompt || DEFAULTS.systemPrompt,
    baseUrl: data.baseUrl || DEFAULTS.baseUrl
  };
}

async function saveApiSettings(payload = {}) {
  const provider = sanitizeProvider(payload.provider);
  const safePayload = {
    apiKey: String(payload.apiKey ?? "").trim(),
    provider,
    model: String(payload.model ?? defaultModelByProvider(provider)).trim() || defaultModelByProvider(provider),
    systemPrompt: String(payload.systemPrompt ?? defaultSystemPrompt()).trim() || defaultSystemPrompt(),
    baseUrl: String(payload.baseUrl ?? DEFAULTS.baseUrl).trim() || DEFAULTS.baseUrl
  };

  await chrome.storage.sync.set(safePayload);
}

async function handleAnalyzeVisibleContent(message) {
  const { visibleText, pageTitle, url, userPrompt } = message.payload || {};

  if (!visibleText || !String(visibleText).trim()) {
    throw new Error("No visible page content was captured.");
  }

  const settings = await getApiSettings();
  if (!settings.apiKey) {
    throw new Error("Missing API key. Open side panel settings and add your API key.");
  }

  const prompt = createPrompt({ visibleText, pageTitle, url, userPrompt });
  const result = await callProvider(settings, prompt);

  return {
    text: result.text,
    model: settings.model,
    provider: settings.provider,
    generatedAt: new Date().toISOString()
  };
}

async function callProvider(settings, prompt) {
  if (settings.provider === "gemini") {
    return callGemini(settings, prompt);
  }

  return callOpenAICompatible(settings, prompt);
}

async function callOpenAICompatible(settings, prompt) {
  const response = await fetch(settings.baseUrl || DEFAULTS.baseUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${settings.apiKey}`
    },
    body: JSON.stringify({
      model: settings.model,
      messages: [
        { role: "system", content: settings.systemPrompt },
        { role: "user", content: prompt }
      ],
      temperature: 0.3
    })
  });

  if (!response.ok) {
    throw await buildApiError(response, settings.provider);
  }

  const data = await response.json();
  const text = data?.choices?.[0]?.message?.content?.trim();
  if (!text) throw new Error("AI response was empty.");

  return { text };
}

async function callGemini(settings, prompt) {
  const model = settings.model || defaultModelByProvider("gemini");
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent?key=${encodeURIComponent(settings.apiKey)}`;

  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      systemInstruction: {
        parts: [{ text: settings.systemPrompt }]
      },
      contents: [{ role: "user", parts: [{ text: prompt }] }],
      generationConfig: { temperature: 0.3 }
    })
  });

  if (!response.ok) {
    throw await buildApiError(response, settings.provider);
  }

  const data = await response.json();
  const text = data?.candidates?.[0]?.content?.parts?.map((p) => p.text).filter(Boolean).join("\n")?.trim();
  if (!text) throw new Error("AI response was empty.");

  return { text };
}

async function buildApiError(response, provider) {
  const raw = await response.text();
  const parsed = safeJsonParse(raw);

  const apiCode = parsed?.error?.code || parsed?.error?.status || "";
  const apiMessage =
    parsed?.error?.message ||
    parsed?.message ||
    "Unknown API error";

  const short = explainApiError({ status: response.status, apiCode, provider });
  return new Error(`${short} (HTTP ${response.status}${apiCode ? ` / ${apiCode}` : ""}). ${apiMessage.slice(0, 240)}`);
}

function explainApiError({ status, apiCode, provider }) {
  const code = String(apiCode || "").toLowerCase();

  if (status === 400 || code.includes("invalid_argument") || code.includes("bad_request")) {
    return "Ungültige Anfrage: Modellname, Endpoint oder Request-Format passt nicht";
  }

  if (status === 401 || code.includes("unauth") || code.includes("invalid_api_key")) {
    return "API-Key ungültig/nicht lizenziert oder ohne Zugriff";
  }

  if (status === 403 || code.includes("permission") || code.includes("forbidden")) {
    return "Zugriff verweigert: Dein Key/Projekt hat keine Berechtigung für dieses Modell";
  }

  if (status === 404 || code.includes("not_found") || code.includes("model_not_found")) {
    return "Nicht gefunden: Endpoint oder Modell existiert nicht";
  }

  if (status === 408 || status === 504 || code.includes("deadline") || code.includes("timeout")) {
    return "Timeout: Der AI-Dienst hat nicht rechtzeitig geantwortet";
  }

  if (status === 409 || code.includes("conflict") || code.includes("aborted")) {
    return "Konflikt: Anfrage konnte aktuell nicht verarbeitet werden, bitte erneut versuchen";
  }

  if (status === 413 || code.includes("context_length") || code.includes("request_too_large")) {
    return "Anfrage zu groß: Zu viel Inhalt im Prompt/Kontext";
  }

  if (status === 415) {
    return "Unsupported Media Type: Content-Type oder Format ist falsch";
  }

  if (status === 422 || code.includes("unprocessable")) {
    return "Validierungsfehler: Ein Feld fehlt oder hat ein ungültiges Format";
  }

  if (status === 429 || code.includes("rate_limit") || code.includes("quota") || code.includes("resource_exhausted")) {
    return "Rate-Limit/Quota erreicht: Kontingent oder Billing prüfen";
  }

  if (status === 500 || code.includes("internal")) {
    return `${providerLabel(provider)}-Serverfehler: Bitte später erneut versuchen`;
  }

  if (status === 502 || status === 503) {
    return `${providerLabel(provider)} ist gerade temporär nicht verfügbar`;
  }

  return "Unbekannter API-Fehler";
}

function createPrompt({ visibleText, pageTitle, url, userPrompt }) {
  return [
    `User request: ${userPrompt || "Summarize and explain what matters."}`,
    `Page title: ${pageTitle || "(unknown)"}`,
    `URL: ${url || "(unknown)"}`,
    "Visible page content:",
    visibleText
  ].join("\n\n");
}

function sanitizeProvider(input) {
  const value = String(input || "").trim().toLowerCase();
  if (value === "gemini") return "gemini";
  if (value === "openai_compatible") return "openai_compatible";
  return "openai";
}

function defaultModelByProvider(provider) {
  if (provider === "gemini") return "gemini-1.5-flash";
  return "gpt-4o-mini";
}

function providerLabel(provider) {
  if (provider === "gemini") return "Gemini";
  if (provider === "openai_compatible") return "OpenAI-compatible";
  return "OpenAI";
}

function safeJsonParse(value) {
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}

function defaultSystemPrompt() {
  return [
    "You are an assistant embedded in a browser side panel.",
    "Provide concise, practical help grounded in the user's currently visible page.",
    "If information is unclear from visible content, say so explicitly."
  ].join(" ");
}
