# FocusSafe AI Chrome Extension

A complete Manifest V3 Chrome extension that reads **visible content** from the current page and sends it to an AI backend, while keeping interaction in a **Chrome Side Panel** so the browsing flow stays uninterrupted.

## Project structure

- `chrome-ai-assistant/manifest.json`
- `chrome-ai-assistant/background.js`
- `chrome-ai-assistant/content-script.js`
- `chrome-ai-assistant/sidepanel.html`
- `chrome-ai-assistant/sidepanel.css`
- `chrome-ai-assistant/sidepanel.js`

## Why this preserves focus

- Uses Chrome's native `side_panel` surface, not a new tab or external app window.
- `openPanelOnActionClick: true` opens assistant beside the current tab.
- Content extraction happens via content script on the current page.
- AI processing runs in the extension service worker.
- User can keep reading and interacting with the page while AI response is generated in side panel.

## Setup and run

1. Open `chrome://extensions`.
2. Enable **Developer mode**.
3. Click **Load unpacked**.
4. Select `chrome-ai-assistant/` directory.
5. Pin extension and click icon once to open side panel.

## API key/provider integration

Supported providers:

- OpenAI (`sk-...`)
- Google Gemini (`AIza...`)
- OpenAI-compatible providers (custom endpoint)

In Settings:

1. Choose provider.
2. Enter API key.
3. Enter model.
4. (Optional) For **OpenAI-compatible**, set your custom chat completions URL.
5. Save settings and run **Analyze Visible Page**.

## Error explanations (short)

The extension maps common API errors to clear messages:

- `400`: request format/model/endpoint invalid
- `401`: API key invalid/unlicensed/no access
- `403`: permission denied for model/project
- `404`: endpoint or model not found
- `408/504`: timeout
- `409`: temporary conflict
- `413`: request too large
- `415`: unsupported content type
- `422`: validation failed
- `429`: rate-limit or quota exceeded
- `5xx`: provider temporary/server error

## Troubleshooting

If you see `Could not establish connection. Receiving end does not exist.`:

- The active tab is often a non-scriptable page (`chrome://*`, extension pages, Chrome Web Store), or
- the content script was not attached yet (for example right after extension reload).

This project retries by programmatically injecting `content-script.js` once on supported tabs.

## Support

Discord profile:

- Username: `brezxxx.`
- User ID: `1359978831070625875`
- Link: https://discord.com/users/1359978831070625875
