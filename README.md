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

## API key integration

1. Open side panel.
2. In **Settings**, paste your AI API key.
3. Optionally set model (default: `gpt-4o-mini`) and system prompt.
4. Click **Save Settings** (stored via `chrome.storage.sync`).
5. Click **Analyze Visible Page** to run.

## AI backend notes

- Background script currently calls OpenAI-compatible endpoint:
  - `POST https://api.openai.com/v1/chat/completions`
- To use Gemini or another provider, replace fetch call in `background.js` while keeping message flow intact.

## Security notes

- API key is stored in Chrome extension synced storage for demo convenience.
- For production, proxy API calls through your backend to avoid exposing provider keys client-side.

## Troubleshooting

If you see `Could not establish connection. Receiving end does not exist.`:

- The active tab is often a non-scriptable page (`chrome://*`, extension pages, Chrome Web Store), or
- the content script was not attached yet (for example right after extension reload).

This project now retries by programmatically injecting `content-script.js` once on supported tabs.
