function isElementVisible(el) {
  if (!el || !(el instanceof Element)) return false;
  const style = window.getComputedStyle(el);
  if (style.display === "none" || style.visibility === "hidden" || Number(style.opacity) === 0) return false;
  const rect = el.getBoundingClientRect();
  if (rect.width < 1 || rect.height < 1) return false;
  return rect.bottom > 0 && rect.right > 0 && rect.top < window.innerHeight && rect.left < window.innerWidth;
}

function extractVisibleText(maxChars = 12000) {
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const chunks = [];
  let total = 0;

  while (walker.nextNode()) {
    const node = walker.currentNode;
    const value = (node.nodeValue || "").replace(/\s+/g, " ").trim();
    if (!value) continue;
    const parent = node.parentElement;
    if (!parent || !isElementVisible(parent)) continue;
    chunks.push(value);
    total += value.length + 1;
    if (total >= maxChars) break;
  }

  return chunks.join("\n");
}

function getSelectedText() {
  return window.getSelection?.()?.toString().trim() || "";
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "COLLECT_VISIBLE_CONTENT") {
    sendResponse({
      ok: true,
      payload: {
        visibleText: extractVisibleText(),
        selectedText: getSelectedText(),
        pageTitle: document.title,
        url: location.href,
        capturedAt: new Date().toISOString()
      }
    });
    return false;
  }

  return false;
});

// Floating selection actions
const toolbar = document.createElement("div");
toolbar.style.cssText = `
  position: fixed;
  z-index: 2147483647;
  background: #111827;
  color: #fff;
  border: 1px solid #334155;
  border-radius: 8px;
  padding: 6px;
  display: none;
  gap: 4px;
  font: 12px system-ui;
`;

const actions = [
  ["Erklären", "Erkläre den markierten Text einfach."],
  ["Zusammenfassen", "Fasse den markierten Text kurz zusammen."],
  ["Übersetzen", "Übersetze den markierten Text ins Deutsche."],
  ["Fix Code", "Analysiere und verbessere den markierten Code."]
];

actions.forEach(([label, prompt]) => {
  const btn = document.createElement("button");
  btn.textContent = label;
  btn.style.cssText = "background:#1f2937;color:white;border:1px solid #475569;border-radius:6px;padding:4px 6px;cursor:pointer;";
  btn.addEventListener("click", async () => {
    const selectedText = getSelectedText();
    if (!selectedText) return;
    await chrome.runtime.sendMessage({
      type: "QUICK_SELECTION_ACTION",
      payload: { prompt, selectedText }
    });
    hideToolbar();
  });
  toolbar.appendChild(btn);
});

document.documentElement.appendChild(toolbar);

function showToolbar(x, y) {
  toolbar.style.left = `${Math.min(x, window.innerWidth - 280)}px`;
  toolbar.style.top = `${Math.max(8, y - 42)}px`;
  toolbar.style.display = "flex";
}

function hideToolbar() {
  toolbar.style.display = "none";
}

document.addEventListener("mouseup", (e) => {
  const selectedText = getSelectedText();
  if (!selectedText || selectedText.length < 3) {
    hideToolbar();
    return;
  }
  showToolbar(e.clientX, e.clientY);
});

document.addEventListener("scroll", hideToolbar, true);
document.addEventListener("mousedown", (e) => {
  if (!toolbar.contains(e.target)) hideToolbar();
});
