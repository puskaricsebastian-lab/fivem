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

## Provider settings

Supported providers:

- OpenAI
- Google Gemini

Features:

- Separate API keys per provider
- Model dropdown (no manual model typing)
- Dynamic model loading (`/v1/models` for OpenAI, `listModels` for Gemini)
- Test Connection button
- Auto-save for settings
- Optional Advanced Mode for custom OpenAI endpoint only

## Error explanations

The extension maps common API errors to clearer messages, for example:

- "Das gewählte Modell gehört nicht zum Provider"
- "Endpoint und Modell passen nicht zusammen"
- "API-Key ungültig, unlizenziert oder abgelaufen"
- "Rate-Limit oder Kontingent erreicht"

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
