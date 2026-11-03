// Open a url in a new browser tab, with no way back into the ComfyUI window.
//
// NEVER `const w = window.open(url, "_blank", "noopener"); if (!w) "Popup blocked"`.
// With "noopener" the browser returns null EVEN WHEN THE TAB OPENS (the HTML spec
// says so), so that check told the user "Popup blocked" on every click while the
// picture opened behind it (Save Image, Preview Image and Pause Image did this,
// measured 2026-10-15). An <a target="_blank" rel="noopener"> click opens the same
// tab with the same isolation; XY Plot's Open already worked this way.
//
// It gives no reliable "was it blocked" answer, so callers show no blocked message.
// Call it straight from the click (a user gesture), never after an await.

export function openUrlInNewTab(url) {
  const a = document.createElement("a");
  a.href = url;
  a.target = "_blank";
  a.rel = "noopener";
  a.style.display = "none";
  document.body.appendChild(a);
  a.click();
  a.remove();
}
