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

const CONTEXT_MENU_IDS = {
  explain: "focussafe_explain",
  summarize: "focussafe_summarize",
  translate: "focussafe_translate",
  fixCode: "focussafe_fix_code",
  google: "focussafe_google"
};

chrome.runtime.onInstalled.addListener(async () => {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
  await createContextMenus();
});

chrome.tabs.onActivated.addListener(async ({ tabId }) => {
  await chrome.sidePanel.setOptions({ tabId, path: "sidepanel.html", enabled: true });
});

chrome.commands.onCommand.addListener(async (command) => {
  const tab = await getActiveTab();
  if (!tab?.id) return;

  if (command === "toggle_assistant") {
    await chrome.sidePanel.open({ tabId: tab.id });
    return;
  }

  if (command === "analyze_selection") {
    const selectedText = await readSelectionFromTab(tab.id);
    if (!selectedText) return;
    await runQuickAction(tab, "Erkläre den markierten Text kurz und verständlich.", selectedText);
    return;
  }

  if (command === "capture_and_analyze") {
    const image = await chrome.tabs.captureVisibleTab(tab.windowId, { format: "png" });
    await runQuickAction(tab, "Analysiere den sichtbaren Bildschirminhalt aus dem Screenshot.", "", image);
  }
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (!tab?.id) return;
  const selection = info.selectionText || "";

  if (info.menuItemId === CONTEXT_MENU_IDS.google) {
    await chrome.tabs.create({ url: `https://www.google.com/search?q=${encodeURIComponent(selection)}` });
    return;
  }

  const promptByAction = {
    [CONTEXT_MENU_IDS.explain]: "Erkläre den markierten Text einfach.",
    [CONTEXT_MENU_IDS.summarize]: "Fasse den markierten Text prägnant zusammen.",
    [CONTEXT_MENU_IDS.translate]: "Übersetze den markierten Text ins Deutsche.",
    [CONTEXT_MENU_IDS.fixCode]: "Analysiere und verbessere den markierten Code."
  };

  const prompt = promptByAction[info.menuItemId];
  if (prompt) {
    await runQuickAction(tab, prompt, selection);
  }
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  const responder = async () => {
    if (message?.type === "AI_ANALYZE_VISIBLE_CONTENT") {
      const result = await handleAnalyzeVisibleContent(message);
      return { ok: true, result };
    }

    if (message?.type === "GET_API_SETTINGS") {
      const settings = await getApiSettings();
      return { ok: true, settings };
    }

    if (message?.type === "SAVE_API_SETTINGS") {
      const settings = await saveApiSettings(message.payload);
      return { ok: true, settings };
    }

    if (message?.type === "LIST_MODELS") {
      const models = await listModels(message.payload);
      return { ok: true, models };
    }

    if (message?.type === "TEST_API_KEY") {
      const result = await testApiKey(message.payload);
      return { ok: true, result };
    }

    if (message?.type === "FORGET_PAGE") {
      await forgetPage(message.payload?.url);
      return { ok: true };
    }

    if (message?.type === "QUICK_SELECTION_ACTION") {
      const tabId = sender?.tab?.id;
      if (!tabId) return { ok: false, error: "No sender tab." };
      const tab = await chrome.tabs.get(tabId);
      await runQuickAction(tab, message.payload?.prompt || "Erkläre den markierten Text.", message.payload?.selectedText || "");
      return { ok: true };
    }

    return { ok: false, error: "Unknown message type." };
  };

  responder()
    .then(sendResponse)
    .catch((error) => sendResponse({ ok: false, error: toErrorMessage(error) }));

  return true;
});

async function createContextMenus() {
  await chrome.contextMenus.removeAll();
  chrome.contextMenus.create({ id: CONTEXT_MENU_IDS.explain, title: "FocusSafe: Erklären", contexts: ["selection"] });
  chrome.contextMenus.create({ id: CONTEXT_MENU_IDS.summarize, title: "FocusSafe: Zusammenfassen", contexts: ["selection"] });
  chrome.contextMenus.create({ id: CONTEXT_MENU_IDS.translate, title: "FocusSafe: Übersetzen", contexts: ["selection"] });
  chrome.contextMenus.create({ id: CONTEXT_MENU_IDS.fixCode, title: "FocusSafe: Fix Code", contexts: ["selection"] });
  chrome.contextMenus.create({ id: CONTEXT_MENU_IDS.google, title: "FocusSafe: Google it", contexts: ["selection"] });
}

async function runQuickAction(tab, userPrompt, selectedText = "", screenshotDataUrl = "") {
  const payload = {
    visibleText: await collectVisibleTextWithFallback(tab.id),
    selectedText,
    screenshotDataUrl,
    pageTitle: tab.title,
    url: tab.url,
    userPrompt
  };

  try {
    const result = await handleAnalyzeVisibleContent({ payload });
    await chrome.storage.local.set({ lastQuickActionResult: result });
    await chrome.sidePanel.open({ tabId: tab.id });
    await chrome.runtime.sendMessage({ type: "QUICK_ACTION_RESULT", payload: result });
  } catch {
    // keep hotkey/context menu non-blocking
  }
}

async function getApiSettings() {
  const data = await chrome.storage.sync.get([
    "provider",
    "apiKeys",
    "models",
    "systemPrompt",
    "advancedMode",
    "customBaseUrls",
    "focusMode",
    "scopeMode",
    "privacy",
    "memory",
    "lastWorking"
  ]);

  return {
    provider: sanitizeProvider(data.provider),
    apiKeys: normalizeApiKeys(data.apiKeys),
    models: normalizeModels(data.models),
    systemPrompt: String(data.systemPrompt || defaultSystemPrompt()).trim() || defaultSystemPrompt(),
    advancedMode: Boolean(data.advancedMode),
    customBaseUrls: normalizeBaseUrls(data.customBaseUrls),
    focusMode: sanitizeFocusMode(data.focusMode),
    scopeMode: sanitizeScopeMode(data.scopeMode),
    privacy: normalizePrivacy(data.privacy),
    memory: normalizeMemory(data.memory),
    lastWorking: data.lastWorking || null
  };
}

async function saveApiSettings(payload = {}) {
  const current = await getApiSettings();
  const next = {
    ...current,
    provider: sanitizeProvider(payload.provider || current.provider),
    apiKeys: { ...current.apiKeys, ...normalizeApiKeys(payload.apiKeys) },
    models: { ...current.models, ...normalizeModels(payload.models) },
    systemPrompt: String(payload.systemPrompt ?? current.systemPrompt).trim() || defaultSystemPrompt(),
    advancedMode: payload.advancedMode ?? current.advancedMode,
    customBaseUrls: { ...current.customBaseUrls, ...normalizeBaseUrls(payload.customBaseUrls) },
    focusMode: sanitizeFocusMode(payload.focusMode ?? current.focusMode),
    scopeMode: sanitizeScopeMode(payload.scopeMode ?? current.scopeMode),
    privacy: normalizePrivacy(payload.privacy ?? current.privacy),
    memory: normalizeMemory(payload.memory ?? current.memory)
  };

  await chrome.storage.sync.set(next);
  return next;
}

async function handleAnalyzeVisibleContent(message) {
  const settings = await getApiSettings();
  if (settings.privacy.paused) {
    throw new Error("Privacy Pause ist aktiv. Deaktiviere Pause, um KI-Zugriff zu erlauben.");
  }

  const payload = message.payload || {};
  const tabUrl = payload.url || "";
  if (isBlockedByPrivacy(settings.privacy.blockedDomains, tabUrl)) {
    throw new Error("Diese Seite ist im Privacy Panel blockiert.");
  }

  const provider = settings.provider;
  const apiKey = settings.apiKeys[provider];
  if (!apiKey) {
    throw new Error(`Missing API key for ${PROVIDERS[provider].label}.`);
  }

  const model = settings.models[provider] || defaultModel(provider);
  const context = await buildContextPayload(settings, payload);
  const result = provider === "gemini"
    ? await callGemini({ apiKey, model, systemPrompt: settings.systemPrompt }, context)
    : await callOpenAI({ apiKey, model, systemPrompt: settings.systemPrompt, baseUrl: resolveOpenAIBaseUrl(settings) }, context);

  await rememberInteraction(settings, { url: tabUrl, title: payload.pageTitle, prompt: payload.userPrompt, model, provider });

  return {
    ...result,
    model,
    provider,
    generatedAt: new Date().toISOString(),
    contextRing: context.contextRing
  };
}

async function buildContextPayload(settings, payload) {
  const scopeMode = settings.scopeMode;
  const userPrompt = payload.userPrompt || "Summarize and explain what matters.";
  const selectedText = (payload.selectedText || "").trim();
  const visibleText = String(payload.visibleText || "").trim();
  const screenshotDataUrl = payload.screenshotDataUrl || "";

  let bodyByScope = "";
  if (scopeMode === "chat") {
    bodyByScope = "Kein Seitenkontext. Arbeite nur mit dem Prompt.";
  } else if (scopeMode === "tab") {
    bodyByScope = visibleText || "Kein sichtbarer Tab-Text verfügbar.";
  } else if (scopeMode === "screen" || scopeMode === "region") {
    bodyByScope = visibleText || "Kein Text für Screen/Region vorhanden.";
  } else {
    bodyByScope = selectedText || visibleText || "Kein Kontext verfügbar.";
  }

  const promptHistory = (settings.memory.recentPrompts || []).slice(-3);

  const contextRing = {
    activeSelection: selectedText.slice(0, 1000),
    currentTab: visibleText.slice(0, 4000),
    recentActions: promptHistory,
    backgroundKnowledge: payload.pageTitle || ""
  };

  const combined = [
    `Scope Mode: ${scopeMode}`,
    `User request: ${userPrompt}`,
    `Page title: ${payload.pageTitle || "(unknown)"}`,
    `URL: ${payload.url || "(unknown)"}`,
    selectedText ? `Selected text (highest priority):\n${selectedText}` : "",
    `Context body:\n${bodyByScope}`,
    promptHistory.length ? `Last prompts:\n${promptHistory.join("\n---\n")}` : "",
    screenshotDataUrl ? "Screenshot attached as data URL (truncated)." : ""
  ].filter(Boolean).join("\n\n");

  return { text: combined.slice(0, 16000), screenshotDataUrl: screenshotDataUrl.slice(0, 4000), contextRing };
}

async function rememberInteraction(settings, entry) {
  const memoryMode = settings.memory.mode;
  if (memoryMode === "session") {
    const local = await chrome.storage.local.get(["sessionPrompts"]);
    const sessionPrompts = [...(local.sessionPrompts || []), entry.prompt].slice(-10);
    await chrome.storage.local.set({ sessionPrompts });
  } else if (memoryMode === "persistent") {
    const recentPrompts = [...(settings.memory.recentPrompts || []), entry.prompt].slice(-10);
    await chrome.storage.sync.set({
      memory: {
        ...settings.memory,
        recentPrompts,
        lastPages: [...(settings.memory.lastPages || []), entry.url].slice(-10)
      },
      lastWorking: { provider: entry.provider, model: entry.model, at: new Date().toISOString() }
    });
  }
}

async function forgetPage(url) {
  const settings = await getApiSettings();
  const filteredPages = (settings.memory.lastPages || []).filter((p) => p !== url);
  await chrome.storage.sync.set({
    memory: {
      ...settings.memory,
      lastPages: filteredPages
    }
  });
}

async function listModels(payload = {}) {
  const provider = sanitizeProvider(payload.provider);
  const apiKey = String(payload.apiKey || "").trim();

  if (!apiKey) {
    throw new Error(`Bitte API-Key für ${PROVIDERS[provider].label} eingeben.`);
  }

  if (provider === "gemini") {
    const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models?key=${encodeURIComponent(apiKey)}`);
    if (!response.ok) throw await buildApiError(response);

    const data = await response.json();
    return uniqueSorted(
      (data.models || [])
        .map((m) => m.name?.replace(/^models\//, ""))
        .filter(Boolean)
        .filter((name) => name.includes("gemini"))
    );
  }

  const response = await fetch("https://api.openai.com/v1/models", {
    headers: { Authorization: `Bearer ${apiKey}` }
  });
  if (!response.ok) throw await buildApiError(response);

  const data = await response.json();
  return uniqueSorted((data.data || []).map((m) => m.id).filter((id) => id?.startsWith("gpt") || id?.includes("o")));
}

async function testApiKey(payload = {}) {
  const models = await listModels(payload);
  if (!models.length) {
    throw new Error("API-Key ist gültig, aber es wurden keine nutzbaren Modelle gefunden.");
  }

  const provider = sanitizeProvider(payload.provider);
  return {
    message: `Verbindung zu ${PROVIDERS[provider].label} erfolgreich.`,
    modelsCount: models.length
  };
}

async function callOpenAI(config, contextPayload) {
  const response = await fetch(config.baseUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${config.apiKey}`
    },
    body: JSON.stringify({
      model: config.model,
      messages: [
        { role: "system", content: `${config.systemPrompt} Return JSON with keys: short,detailed,steps,code.` },
        { role: "user", content: contextPayload.text }
      ],
      temperature: 0.3
    })
  });

  if (!response.ok) throw await buildApiError(response);
  const data = await response.json();
  const raw = data?.choices?.[0]?.message?.content?.trim();
  if (!raw) throw new Error("AI response was empty.");

  const parsed = tryParseJsonAnswer(raw);
  return {
    short: parsed.short || raw,
    detailed: parsed.detailed || raw,
    steps: parsed.steps || raw,
    code: parsed.code || "Kein Code vorgeschlagen.",
    text: parsed.detailed || raw
  };
}

async function callGemini(config, contextPayload) {
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(config.model)}:generateContent?key=${encodeURIComponent(config.apiKey)}`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      systemInstruction: { parts: [{ text: `${config.systemPrompt} Return JSON with keys: short,detailed,steps,code.` }] },
      contents: [{ role: "user", parts: [{ text: contextPayload.text }] }],
      generationConfig: { temperature: 0.3 }
    })
  });

  if (!response.ok) throw await buildApiError(response);
  const data = await response.json();
  const raw = data?.candidates?.[0]?.content?.parts?.map((p) => p.text).filter(Boolean).join("\n")?.trim();
  if (!raw) throw new Error("AI response was empty.");

  const parsed = tryParseJsonAnswer(raw);
  return {
    short: parsed.short || raw,
    detailed: parsed.detailed || raw,
    steps: parsed.steps || raw,
    code: parsed.code || "Kein Code vorgeschlagen.",
    text: parsed.detailed || raw
  };
}

async function buildApiError(response) {
  const raw = await response.text();
  const parsed = safeJsonParse(raw);
  const apiCode = String(parsed?.error?.code || parsed?.error?.status || "");
  const apiMessage = parsed?.error?.message || parsed?.message || "Unknown API error";
  const short = explainApiError({ status: response.status, apiCode });
  return new Error(`${short} (HTTP ${response.status}${apiCode ? ` / ${apiCode}` : ""}). ${apiMessage.slice(0, 220)}`);
}

function explainApiError({ status, apiCode }) {
  const code = String(apiCode || "").toLowerCase();
  if (code.includes("model_not_found") || code.includes("unsupported model")) return "Das gewählte Modell gehört nicht zum Provider";
  if (status === 404) return "Endpoint und Modell passen nicht zusammen";
  if (status === 400 || code.includes("invalid_argument")) return "Ungültige Anfrage: Modell oder Request-Format prüfen";
  if (status === 401 || code.includes("unauth") || code.includes("invalid_api_key")) return "API-Key ungültig, unlizenziert oder abgelaufen";
  if (status === 403 || code.includes("permission") || code.includes("forbidden")) return "Keine Berechtigung für dieses Modell/Projekt";
  if (status === 429 || code.includes("quota") || code.includes("rate_limit") || code.includes("resource_exhausted")) return "Rate-Limit oder Kontingent erreicht (Billing/Quota prüfen)";
  if (status >= 500) return "AI-Dienst aktuell nicht verfügbar – bitte später erneut versuchen";
  return "Unbekannter API-Fehler";
}

async function collectVisibleTextWithFallback(tabId) {
  try {
    const response = await chrome.tabs.sendMessage(tabId, { type: "COLLECT_VISIBLE_CONTENT" });
    return response?.payload?.visibleText || "";
  } catch {
    await chrome.scripting.executeScript({ target: { tabId }, files: ["content-script.js"] });
    const response = await chrome.tabs.sendMessage(tabId, { type: "COLLECT_VISIBLE_CONTENT" });
    return response?.payload?.visibleText || "";
  }
}

async function readSelectionFromTab(tabId) {
  try {
    const [{ result }] = await chrome.scripting.executeScript({
      target: { tabId },
      func: () => window.getSelection()?.toString() || ""
    });
    return result || "";
  } catch {
    return "";
  }
}

async function getActiveTab() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  return tabs[0];
}

function tryParseJsonAnswer(raw) {
  const cleaned = raw.replace(/^```json/, "").replace(/^```/, "").replace(/```$/, "").trim();
  return safeJsonParse(cleaned) || {};
}

function sanitizeProvider(input) {
  return input === "gemini" ? "gemini" : "openai";
}

function sanitizeFocusMode(input) {
  return ["focus", "silent", "assist"].includes(input) ? input : "assist";
}

function sanitizeScopeMode(input) {
  return ["chat", "tab", "screen", "region"].includes(input) ? input : "tab";
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

function normalizePrivacy(input = {}) {
  return {
    paused: Boolean(input.paused),
    access: ["tab", "full"].includes(input.access) ? input.access : "tab",
    blockedDomains: Array.isArray(input.blockedDomains) ? input.blockedDomains.map((x) => String(x).trim()).filter(Boolean) : []
  };
}

function normalizeMemory(input = {}) {
  return {
    mode: ["off", "session", "persistent"].includes(input.mode) ? input.mode : "session",
    recentPrompts: Array.isArray(input.recentPrompts) ? input.recentPrompts.slice(-10) : [],
    lastPages: Array.isArray(input.lastPages) ? input.lastPages.slice(-10) : []
  };
}

function defaultModel(provider) {
  return PROVIDERS[sanitizeProvider(provider)].defaultModel;
}

function defaultSystemPrompt() {
  return [
    "You are an assistant embedded in a browser side panel.",
    "Provide concise, practical help grounded in the user's context.",
    "If information is unclear from visible content, say so explicitly."
  ].join(" ");
}

function resolveOpenAIBaseUrl(settings) {
  if (!settings.advancedMode) return PROVIDERS.openai.defaultBaseUrl;
  return settings.customBaseUrls?.openai || PROVIDERS.openai.defaultBaseUrl;
}

function uniqueSorted(arr) {
  return [...new Set(arr)].sort((a, b) => a.localeCompare(b));
}

function safeJsonParse(value) {
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}

function isBlockedByPrivacy(blockedDomains, tabUrl) {
  try {
    const host = new URL(tabUrl).hostname;
    return blockedDomains.some((entry) => host.includes(entry));
  } catch {
    return false;
  }
}

function toErrorMessage(error) {
  return error instanceof Error ? error.message : String(error || "Unknown error");
}
