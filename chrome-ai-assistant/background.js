const PROVIDERS = {
  openai: {
    label: "OpenAI",
    defaultModel: "gpt-4o-mini",
    defaultBaseUrl: "https://api.openai.com/v1/chat/completions"
  },
  gemini: {
    label: "Google Gemini",
    defaultModel: "gemini-1.5-flash",
    defaultBaseUrl: "https://generativelanguage.googleapis.com/v1beta"
  }
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
      .catch((error) => sendResponse({ ok: false, error: toErrorMessage(error) }));
    return true;
  }

  if (message?.type === "GET_API_SETTINGS") {
    getApiSettings()
      .then((settings) => sendResponse({ ok: true, settings }))
      .catch((error) => sendResponse({ ok: false, error: toErrorMessage(error) }));
    return true;
  }

  if (message?.type === "SAVE_API_SETTINGS") {
    saveApiSettings(message.payload)
      .then((settings) => sendResponse({ ok: true, settings }))
      .catch((error) => sendResponse({ ok: false, error: toErrorMessage(error) }));
    return true;
  }

  if (message?.type === "LIST_MODELS") {
    listModels(message.payload)
      .then((models) => sendResponse({ ok: true, models }))
      .catch((error) => sendResponse({ ok: false, error: toErrorMessage(error) }));
    return true;
  }

  if (message?.type === "TEST_API_KEY") {
    testApiKey(message.payload)
      .then((result) => sendResponse({ ok: true, result }))
      .catch((error) => sendResponse({ ok: false, error: toErrorMessage(error) }));
    return true;
  }

  return false;
});

async function getApiSettings() {
  const data = await chrome.storage.sync.get([
    "provider",
    "apiKeys",
    "models",
    "systemPrompt",
    "advancedMode",
    "customBaseUrls",
    "lastWorking"
  ]);

  const provider = sanitizeProvider(data.provider);
  const settings = {
    provider,
    apiKeys: normalizeApiKeys(data.apiKeys),
    models: normalizeModels(data.models),
    systemPrompt: String(data.systemPrompt || defaultSystemPrompt()).trim() || defaultSystemPrompt(),
    advancedMode: Boolean(data.advancedMode),
    customBaseUrls: normalizeBaseUrls(data.customBaseUrls),
    lastWorking: data.lastWorking || null
  };

  return settings;
}

async function saveApiSettings(payload = {}) {
  const current = await getApiSettings();
  const provider = sanitizeProvider(payload.provider || current.provider);

  const next = {
    ...current,
    provider,
    apiKeys: {
      ...current.apiKeys,
      ...normalizeApiKeys(payload.apiKeys)
    },
    models: {
      ...current.models,
      ...normalizeModels(payload.models)
    },
    systemPrompt: String(payload.systemPrompt ?? current.systemPrompt).trim() || defaultSystemPrompt(),
    advancedMode: payload.advancedMode ?? current.advancedMode,
    customBaseUrls: {
      ...current.customBaseUrls,
      ...normalizeBaseUrls(payload.customBaseUrls)
    }
  };

  await chrome.storage.sync.set(next);
  return next;
}

async function handleAnalyzeVisibleContent(message) {
  const { visibleText, pageTitle, url, userPrompt } = message.payload || {};
  if (!visibleText || !String(visibleText).trim()) {
    throw new Error("No visible page content was captured.");
  }

  const settings = await getApiSettings();
  const provider = settings.provider;
  const apiKey = settings.apiKeys[provider];

  if (!apiKey) {
    throw new Error(`Missing API key for ${PROVIDERS[provider].label}.`);
  }

  const prompt = createPrompt({ visibleText, pageTitle, url, userPrompt });
  const model = settings.models[provider] || defaultModel(provider);

  const result = provider === "gemini"
    ? await callGemini({ apiKey, model, systemPrompt: settings.systemPrompt }, prompt)
    : await callOpenAI({ apiKey, model, systemPrompt: settings.systemPrompt, baseUrl: resolveOpenAIBaseUrl(settings) }, prompt);

  await chrome.storage.sync.set({
    lastWorking: {
      provider,
      model,
      at: new Date().toISOString()
    }
  });

  return {
    text: result.text,
    model,
    provider,
    generatedAt: new Date().toISOString()
  };
}

async function listModels(payload = {}) {
  const provider = sanitizeProvider(payload.provider);
  const apiKey = String(payload.apiKey || "").trim();

  if (!apiKey) {
    throw new Error(`Bitte API-Key für ${PROVIDERS[provider].label} eingeben.`);
  }

  if (provider === "gemini") {
    const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models?key=${encodeURIComponent(apiKey)}`);
    if (!response.ok) throw await buildApiError(response, provider);

    const data = await response.json();
    const models = (data.models || [])
      .map((m) => m.name?.replace(/^models\//, ""))
      .filter(Boolean)
      .filter((name) => name.includes("gemini"));

    return uniqueSorted(models);
  }

  const response = await fetch("https://api.openai.com/v1/models", {
    headers: { Authorization: `Bearer ${apiKey}` }
  });
  if (!response.ok) throw await buildApiError(response, provider);

  const data = await response.json();
  const models = (data.data || [])
    .map((m) => m.id)
    .filter(Boolean)
    .filter((id) => id.startsWith("gpt") || id.includes("o"));

  return uniqueSorted(models);
}

async function testApiKey(payload = {}) {
  const provider = sanitizeProvider(payload.provider);
  const apiKey = String(payload.apiKey || "").trim();

  if (!apiKey) {
    throw new Error("API-Key fehlt.");
  }

  const models = await listModels({ provider, apiKey });
  if (!models.length) {
    throw new Error("API-Key ist gültig, aber es wurden keine nutzbaren Modelle gefunden.");
  }

  return { message: `Verbindung zu ${PROVIDERS[provider].label} erfolgreich.`, modelsCount: models.length };
}

async function callOpenAI(config, prompt) {
  const response = await fetch(config.baseUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${config.apiKey}`
    },
    body: JSON.stringify({
      model: config.model,
      messages: [
        { role: "system", content: config.systemPrompt },
        { role: "user", content: prompt }
      ],
      temperature: 0.3
    })
  });

  if (!response.ok) throw await buildApiError(response, "openai");
  const data = await response.json();
  const text = data?.choices?.[0]?.message?.content?.trim();
  if (!text) throw new Error("AI response was empty.");
  return { text };
}

async function callGemini(config, prompt) {
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(config.model)}:generateContent?key=${encodeURIComponent(config.apiKey)}`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      systemInstruction: { parts: [{ text: config.systemPrompt }] },
      contents: [{ role: "user", parts: [{ text: prompt }] }],
      generationConfig: { temperature: 0.3 }
    })
  });

  if (!response.ok) throw await buildApiError(response, "gemini");
  const data = await response.json();
  const text = data?.candidates?.[0]?.content?.parts?.map((p) => p.text).filter(Boolean).join("\n")?.trim();
  if (!text) throw new Error("AI response was empty.");
  return { text };
}

async function buildApiError(response, provider) {
  const raw = await response.text();
  const parsed = safeJsonParse(raw);
  const apiCode = String(parsed?.error?.code || parsed?.error?.status || "");
  const apiMessage = parsed?.error?.message || parsed?.message || "Unknown API error";
  const short = explainApiError({ status: response.status, apiCode });

  return new Error(`${short} (HTTP ${response.status}${apiCode ? ` / ${apiCode}` : ""}). ${apiMessage.slice(0, 220)}`);
}

function explainApiError({ status, apiCode }) {
  const code = apiCode.toLowerCase();

  if (code.includes("model_not_found") || code.includes("not found") || code.includes("unsupported model")) {
    return "Das gewählte Modell gehört nicht zum Provider";
  }

  if (status === 404) {
    return "Endpoint und Modell passen nicht zusammen";
  }

  if (status === 400 || code.includes("invalid_argument")) return "Ungültige Anfrage: Modell oder Request-Format prüfen";
  if (status === 401 || code.includes("unauth") || code.includes("invalid_api_key")) return "API-Key ungültig, unlizenziert oder abgelaufen";
  if (status === 403 || code.includes("permission") || code.includes("forbidden")) return "Keine Berechtigung für dieses Modell/Projekt";
  if (status === 408 || status === 504 || code.includes("timeout")) return "Timeout beim AI-Dienst";
  if (status === 409) return "Konflikt/gleichzeitige Anfrage – bitte erneut versuchen";
  if (status === 413 || code.includes("context_length")) return "Anfrage zu groß (Kontext/Payload reduzieren)";
  if (status === 415) return "Ungültiger Content-Type";
  if (status === 422) return "Ungültige Felder in der Anfrage";
  if (status === 429 || code.includes("quota") || code.includes("rate_limit") || code.includes("resource_exhausted")) {
    return "Rate-Limit oder Kontingent erreicht (Billing/Quota prüfen)";
  }
  if (status >= 500) return "AI-Dienst aktuell nicht verfügbar – bitte später erneut versuchen";

  return "Unbekannter API-Fehler";
}

function resolveOpenAIBaseUrl(settings) {
  if (!settings.advancedMode) {
    return PROVIDERS.openai.defaultBaseUrl;
  }

  return settings.customBaseUrls?.openai || PROVIDERS.openai.defaultBaseUrl;
}

function normalizeApiKeys(input = {}) {
  return {
    openai: String(input.openai || "").trim(),
    gemini: String(input.gemini || "").trim()
  };
}

function normalizeModels(input = {}) {
  return {
    openai: String(input.openai || defaultModel("openai")).trim() || defaultModel("openai"),
    gemini: String(input.gemini || defaultModel("gemini")).trim() || defaultModel("gemini")
  };
}

function normalizeBaseUrls(input = {}) {
  return {
    openai: String(input.openai || PROVIDERS.openai.defaultBaseUrl).trim() || PROVIDERS.openai.defaultBaseUrl,
    gemini: PROVIDERS.gemini.defaultBaseUrl
  };
}

function sanitizeProvider(input) {
  return input === "gemini" ? "gemini" : "openai";
}

function defaultModel(provider) {
  return PROVIDERS[sanitizeProvider(provider)].defaultModel;
}

function uniqueSorted(arr) {
  return [...new Set(arr)].sort((a, b) => a.localeCompare(b));
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

function toErrorMessage(error) {
  return error instanceof Error ? error.message : String(error || "Unknown error");
}
