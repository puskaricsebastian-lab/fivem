function isElementVisible(el) {
  if (!el || !(el instanceof Element)) {
    return false;
  }

  const style = window.getComputedStyle(el);
  if (style.display === "none" || style.visibility === "hidden" || Number(style.opacity) === 0) {
    return false;
  }

  const rect = el.getBoundingClientRect();
  if (rect.width < 1 || rect.height < 1) {
    return false;
  }

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

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "COLLECT_VISIBLE_CONTENT") {
    const visibleText = extractVisibleText();
    sendResponse({
      ok: true,
      payload: {
        visibleText,
        pageTitle: document.title,
        url: location.href,
        capturedAt: new Date().toISOString()
      }
    });

    return false;
  }

  return false;
});
