import { app } from "../../../scripts/app.js";
import { BRAND, applyAdaptiveCanvasOnly,
  installCanvasZoomPassthrough, installNativeTextMenu, installNodeAccent, registerNodeAccent,
} from "../shared/index.mjs";
import { runTab, eachRestoredOutput } from "../shared/run_tab.mjs";
import { textSize } from "../shared/text_size.mjs";

// Resize clamp - user verified 210 x 118 as the smallest comfortable
// size for a compact label/readout. WIDGET_MIN_H is kept smaller than
// MIN_H so the DOM widget itself doesn't force a larger ComfyUI natural
// floor; MIN_H is what the resize handle enforces. Saved workflows /
// duplicates keep their size because configure() runs after nodeCreated
// (Vue Compat #8) and overrides our DEFAULT.
const MIN_W = 210;
const MIN_H = 118;
const WIDGET_MIN_H = 80;
// Default = minimum, so fresh-on-canvas drops are compact and the user
// grows the node only when they want more reading room.
const DEFAULT_W = 210;
const DEFAULT_H = 118;
const PLACEHOLDER = "text...";

// One-shot CSS injection. The hover-reveal needs a CSS selector
// (.pix-st-wrap:hover .pix-st-copy), so we can't do it with inline styles.
let _cssInjected = false;
function injectCSS() {
  if (_cssInjected) return;
  _cssInjected = true;
  const style = document.createElement("style");
  style.textContent = `
    .pix-st-copy {
      position: absolute;
      bottom: 8px;
      right: 14px;
      font: 11px 'Segoe UI', -apple-system, sans-serif;
      padding: 2px 8px;
      background: rgba(20, 20, 20, 0.92);
      color: var(--pix-acc,#f66744);
      border: 1px solid var(--pix-acc,#f66744);
      border-radius: 3px;
      cursor: pointer;
      opacity: 0;
      pointer-events: none;
      transition: opacity 0.12s, background 0.12s, color 0.12s;
      z-index: 2;
      user-select: none;
    }
    .pix-st-wrap:hover .pix-st-copy {
      opacity: 0.9;
      pointer-events: auto;
    }
    .pix-st-copy:hover {
      opacity: 1 !important;
      background: var(--pix-acc,#f66744);
      color: #fff;
    }
    .pix-st-copy.copied {
      opacity: 1 !important;
      background: #2e7d32;
      border-color: #2e7d32;
      color: #fff;
    }
  `;
  document.head.appendChild(style);
}

// A run's text into the box (the widget is serialized, so it survives a tab
// switch and a reload).
function showRunText(node, output) {
  const text = (output?.text || []).join("\n");
  if (node._pixTextEl) node._pixTextEl.value = text;
  if (node._pixTextWidget) node._pixTextWidget.value = text;
}

app.registerExtension({
  name: "Pixaroma.ShowText",

  // A Run that ended while another workflow tab was open (js/shared/run_tab.mjs).
  onNodeOutputsUpdated(nodeOutputs) {
    eachRestoredOutput(nodeOutputs, "PixaromaShowText", (node, output) => showRunText(node, output));
  },

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== "PixaromaShowText") return;

    const origOnNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      origOnNodeCreated?.apply(this, arguments);
      injectCSS();

      const wrap = document.createElement("div");
      wrap.className = "pix-st-wrap";
      wrap.style.cssText = `
        position: relative;
        width: 100%;
        height: 100%;
        box-sizing: border-box;
        margin: 0;
        padding: 0;
        display: flex;
      `;

      const ta = document.createElement("textarea");
      ta.readOnly = true;
      ta.placeholder = PLACEHOLDER;
      ta.spellcheck = false;
      // Interior styling matches Prompt Pack / Text Pixaroma for visual
      // consistency across the three text nodes. Border stays #333 by
      // default (no permanent orange ring) since this is a display node
      // and the orange Copy button on hover already signals interactivity.
      ta.style.cssText = `
        flex: 1;
        width: 100%;
        height: 100%;
        box-sizing: border-box;
        background: #1d1d1d;
        color: #e0e0e0;
        border: 1px solid #333;
        border-radius: 4px;
        padding: 6px 8px;
        margin: 0;
        font-family: monospace;
        font-size: ${textSize(12)};
        line-height: 1.35;
        resize: none;
        outline: none;
        white-space: pre-wrap;
        overflow: auto;
      `;
      wrap.appendChild(ta);

      const copyBtn = document.createElement("button");
      copyBtn.className = "pix-st-copy";
      copyBtn.type = "button";
      copyBtn.textContent = "Copy";
      copyBtn.title = "Copy text to clipboard";
      copyBtn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const text = ta.value || "";
        if (!text) return;
        try {
          if (navigator.clipboard?.writeText) {
            await navigator.clipboard.writeText(text);
          } else {
            ta.select();
            document.execCommand("copy");
          }
          copyBtn.textContent = "Copied";
          copyBtn.classList.add("copied");
          clearTimeout(copyBtn._resetTimer);
          copyBtn._resetTimer = setTimeout(() => {
            copyBtn.textContent = "Copy";
            copyBtn.classList.remove("copied");
          }, 1200);
        } catch (err) {
          console.error("[PixaromaShowText] copy failed", err);
        }
      });
      wrap.appendChild(copyBtn);

      this._pixTextEl = ta;

      // Widget TYPE must NOT collide with a Nodes 2.0 registered widget type
      // (customtext / textarea / multiline / string / etc. all map to native
      // Vue components in widgetRegistry.ts). A registered type makes Nodes 2.0
      // render ITS OWN Vue widget and orphan our DOM element off-screen (our
      // value lands on a detached node). A unique type falls through to
      // WidgetDOM.vue, which re-parents OUR element. See CLAUDE.md Nodes 2.0.
      installCanvasZoomPassthrough(wrap);
      installNativeTextMenu(wrap);   // Copy / Select all in the readout
      installNodeAccent(this, wrap);   // the face follows this node's accent colour
      const widget = this.addDOMWidget("text", "pixaroma_showtext", wrap, {
        // canvasOnly is set ADAPTIVELY below (applyAdaptiveCanvasOnly):
        // true in legacy (hide from Parameters tab, Vue Compat #15), false
        // in Nodes 2.0 (else shouldRenderAsVue excludes it → empty body).
        getValue: () => ta.value,
        setValue: (v) => {
          ta.value = v == null ? "" : String(v);
        },
        serialize: true,
        // WIDGET_MIN_H (not MIN_H) so the DOM widget itself doesn't
        // force ComfyUI's natural floor above the explicit MIN_H clamp.
        getMinHeight: () => WIDGET_MIN_H,
      });
      applyAdaptiveCanvasOnly(widget);
      this._pixTextWidget = widget;

      // Set default size unconditionally on fresh placement. configure()
      // runs AFTER nodeCreated (Vue Compat #8) and restores the saved
      // size for workflow load + duplicate, so existing workflows keep
      // their size. Mutating size[0/1] instead of replacing the array
      // plays nicely with any reactive proxy Vue may have on node.size.
      this.size[0] = DEFAULT_W;
      this.size[1] = DEFAULT_H;
    };

    nodeType.prototype.onExecuted = function (output) {
      // Core calls this on the OPEN tab's node with the run's id. A Run that
      // ended while another workflow tab is open belongs to that tab (decided
      // once the message's listeners ran); core hands it back when that tab
      // opens again: onNodeOutputsUpdated above (js/shared/run_tab.mjs).
      queueMicrotask(() => {
        if (runTab(output) === "other") return;
        showRunText(this, output);
      });
    };

    const origOnResize = nodeType.prototype.onResize;
    nodeType.prototype.onResize = function (size) {
      origOnResize?.call(this, size);
      this.size[0] = Math.max(this.size[0], MIN_W);
      this.size[1] = Math.max(this.size[1], MIN_H);
    };

    // Self-heal min size on every paint (Preview Image Pattern #11 + UI
    // conventions #7). Belt-and-braces with onResize because Vue Compat
    // #13 + Align Pattern #6 mean some resize paths bypass onResize and
    // the Copy button can clip past the node frame after grow-then-shrink.
    const origDraw = nodeType.prototype.onDrawForeground;
    nodeType.prototype.onDrawForeground = function (ctx) {
      if (origDraw) origDraw.call(this, ctx);
      if (this.flags?.collapsed) return;
      if (this.size[0] < MIN_W) this.size[0] = MIN_W;
      if (this.size[1] < MIN_H) this.size[1] = MIN_H;
    };
  },
});

// The colour option: gives this node a right-click "Show Text settings" entry, the
// gear in the selection toolbar, and the shared colour panel behind both.
registerNodeAccent("PixaromaShowText", { title: "Show Text" });
