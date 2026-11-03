// Info Pixaroma - starter buttons.
//
// A starter sets the button (title, icon, colour) and, when the note is still
// empty, writes the empty headings of that kind of note. Picked from what
// workflow notes usually carry. Offered once when a node is dropped, and later
// from the right-click menu.

import { app } from "../../../scripts/app.js";
import { renderIconHTML } from "../note/icons.mjs";
import { readCfg, writeCfg, iconUrl, inkFor, unitWidth, M, clampS, NODE } from "./core.mjs";
import { isVueNodes } from "../shared/nodes2.mjs";
import { isLiveNode } from "../shared/live_node.mjs";

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

// sections: [icon, heading, kind ("ol" | "ul" | "p"), lines[]]
export const STARTERS = [
  { id: "readme", name: "Read me", icon: "info", color: "#f66744",
    h1: "READ ME", intro: "What this workflow makes, in one or two lines.",
    sections: [
      ["to-do", "How to use", "ol", ["First step", "Second step", "Press Run"]],
      ["checkmark", "What you need", "ul", ["Models (see the Models button)", "Custom nodes, if any"]],
    ] },
  { id: "models", name: "Models", title: "Download Models", icon: "download-model", color: "#f66744",
    h1: "MODELS", intro: "Download each file and put it in the folder written under it.",
    sections: [
      ["download-model", "Diffusion model", "p", ["File name, size and folder."]],
      ["download-model", "Text encoder", "p", ["File name, size and folder."]],
      ["download-model", "VAE", "p", ["File name, size and folder."]],
    ] },
  { id: "nodes", name: "Nodes", title: "Nodes Info", icon: "node-v5", color: "#3d7cc9",
    h1: "NODES", intro: "What the nodes in this workflow do.",
    sections: [
      ["node-v5", "Custom nodes to install", "ul", ["Name, and where to get it"]],
      ["node-v6", "What each node does", "ul", ["Node name: what it does"]],
      ["edit", "Nodes you change", "ul", ["Node name: what to set"]],
    ] },
  { id: "settings", name: "Settings", icon: "gear", color: "#2a9d8f",
    h1: "SETTINGS", intro: "The settings that give the best results.",
    sections: [
      ["gear", "Best settings", "ul", ["Steps:", "CFG:", "Sampler and scheduler:"]],
      ["image", "Sizes that work", "ul", ["Width x height"]],
      ["idea", "What to try changing", "ul", ["Setting: what it changes"]],
    ] },
  { id: "prompt", name: "Prompt tips", icon: "prompt", color: "#8a5cc7",
    h1: "PROMPT TIPS", intro: "How to write a prompt for this model.",
    sections: [
      ["prompt", "How to write a prompt", "p", ["What to describe first, and in what order."]],
      ["question-v2", "Example prompts", "ul", ["An example prompt"]],
      ["idea", "Words that help", "ul", ["A word or phrase, and what it does"]],
    ] },
  { id: "runtimes", name: "Run times", title: "Run Times", icon: "run-timer", color: "#3f9a4f",
    h1: "RUN TIMES", intro: "How long a run takes, and how much memory it needs.",
    sections: [
      ["run-timer", "Time per size", "ul", ["1024 x 1024: seconds, on your card"]],
      ["model-v4", "VRAM and RAM", "ul", ["About ... GB of VRAM"]],
      ["attention", "Low VRAM", "ul", ["What to change on a smaller card"]],
    ] },
  { id: "tips", name: "Tips", icon: "idea", color: "#c9921a",
    h1: "TIPS", intro: "Small things that make a big difference.",
    sections: [
      ["idea", "Tips and tricks", "ul", ["A tip"]],
      ["checkmark", "What works best", "ul", ["What gave the best results"]],
    ] },
  { id: "attention", name: "Attention", icon: "attention", color: "#c0392b",
    h1: "READ BEFORE RUN", intro: "Things to check before you press Run.",
    sections: [
      ["attention", "Before you run", "ul", ["Something to check"]],
      ["question-v2", "Known problems and fixes", "ul", ["Problem: how to fix it"]],
    ] },
  { id: "links", name: "Links", icon: "link", color: "#4a6fa5",
    h1: "LINKS", intro: "Add buttons with the editor's YouTube, Discord and Button tools.",
    sections: [
      ["link", "Video tutorial", "p", ["A YouTube button for the video."]],
      ["link", "Model page", "p", ["A button for the model's page."]],
      ["link", "Community", "p", ["A Discord button."]],
    ] },
  { id: "blank", name: "Blank", title: "Info", icon: "notebook", color: "#3a3a3a", h1: null, sections: [] },
];

export function starterById(id) {
  return STARTERS.find((s) => s.id === id) || null;
}

// The note body for a starter: plain Note HTML (the sanitizer's own tags and
// classes), so the editor treats it exactly like text typed by hand.
export function starterContent(st) {
  if (!st || !st.h1) return "";
  const ic = (id) => renderIconHTML(id, st.color);
  let html = `<h1>${esc(st.h1)}</h1>`;
  if (st.intro) html += `<p>${esc(st.intro)}</p>`;
  html += `<hr>`;
  for (const [icon, heading, kind, lines] of st.sections) {
    html += `<h3>${ic(icon)}${esc(heading)}</h3>`;
    if (kind === "p") html += lines.map((l) => `<p>${esc(l)}</p>`).join("");
    else html += `<${kind}>${lines.map((l) => `<li>${esc(l)}</li>`).join("")}</${kind}>`;
  }
  return html;
}

// One starter as a SECTION of a longer note (the editor's Template button):
// its heading becomes an h2 with the starter's icon, then the same empty
// headings starterContent writes. `rule` puts a line above it, to separate it
// from what is already in the note.
export function starterSection(st, rule = false) {
  if (!st || !st.h1) return "";
  const ic = (id) => renderIconHTML(id, st.color);
  let html = rule ? "<hr>" : "";
  html += `<h2>${ic(st.icon)}${esc(st.h1)}</h2>`;
  if (st.intro) html += `<p>${esc(st.intro)}</p>`;
  for (const [icon, heading, kind, lines] of st.sections) {
    html += `<h3>${ic(icon)}${esc(heading)}</h3>`;
    if (kind === "p") html += lines.map((l) => `<p>${esc(l)}</p>`).join("");
    else html += `<${kind}>${lines.map((l) => `<li>${esc(l)}</li>`).join("")}</${kind}>`;
  }
  return html;
}

// Current scale of the button, from its width (both renderers carry the scale
// in the width).
export function currentScale(node, info) {
  return clampS((node.size?.[0] || 0) / unitWidth(info));
}

// Make the button hug its content again at the SAME scale, after the title or
// icon changed. A user action only (it writes node.size).
export function refitToContent(node, oldInfo, newInfo) {
  try {
    const s = currentScale(node, oldInfo);
    const w = Math.round(unitWidth(newInfo) * s);
    if (isVueNodes()) {
      // Nodes 2.0 takes a width write; the height follows the content.
      node.setSize?.([w, node.size[1]]);
    } else {
      node.size[0] = w;
      node.size[1] = Math.round(M.h * s);
    }
    node.setDirtyCanvas?.(true, true);
  } catch (_e) {}
}

// Apply a starter. The note text is only written when the note is still empty,
// so a starter can never wipe what someone wrote.
export function applyStarter(node, st) {
  if (!node || !st) return;
  const cfg = readCfg(node);
  const oldInfo = cfg.info;
  // Spread the current info: the window size and text size stay.
  const info = { ...oldInfo, title: st.title || st.name, icon: st.icon, color: st.color };
  const next = { ...cfg, info };
  if (!String(cfg.content || "").trim()) next.content = starterContent(st);
  refitToContent(node, oldInfo, info);
  writeCfg(node, next);
}

// ── The "start from" popup, shown when a node is dropped ────────────────────
let _pop = null;
let _popCleanup = null;

const CSS = [
  ".pix-info-start{position:fixed;z-index:10020;width:340px;background:#252525;border:1px solid #444;border-radius:10px;box-shadow:0 10px 30px rgba(0,0,0,.6);padding:10px;font-family:'Segoe UI',system-ui,sans-serif;color:#ddd;}",
  ".pix-info-start-h{display:flex;align-items:center;justify-content:space-between;font-size:11px;font-weight:700;color:#999;letter-spacing:.05em;margin:0 2px 8px;}",
  ".pix-info-start-x{border:0;background:transparent;color:#999;font-size:14px;cursor:pointer;padding:0 4px;line-height:1;}",
  ".pix-info-start-x:hover{color:#fff;}",
  ".pix-info-start-g{display:grid;grid-template-columns:1fr 1fr;gap:6px;}",
  ".pix-info-start-o{display:flex;align-items:center;gap:8px;padding:6px 8px;border-radius:6px;background:#1d1d1d;border:1px solid transparent;font:inherit;font-size:12.5px;color:#ddd;cursor:pointer;text-align:left;}",
  ".pix-info-start-o:hover,.pix-info-start-o:focus-visible{border-color:#f66744;outline:none;color:#fff;}",
  ".pix-info-start-sq{width:22px;height:22px;border-radius:6px;display:flex;align-items:center;justify-content:center;flex:none;}",
  ".pix-info-start-ic{width:14px;height:14px;display:block;-webkit-mask:var(--i) center/contain no-repeat;mask:var(--i) center/contain no-repeat;}",
  ".pix-info-start-f{font-size:11px;color:#888;margin:8px 2px 0;}",
].join("\n");
let _cssDone = false;
function injectCSS() {
  if (_cssDone) return;
  _cssDone = true;
  const s = document.createElement("style");
  s.setAttribute("data-pixaroma-info-start", "1");
  s.textContent = CSS;
  document.head.appendChild(s);
}

export function closeStarterPopup() {
  try { _popCleanup?.(); } catch (_e) {}
  _popCleanup = null;
  if (_pop) { try { _pop.remove(); } catch (_e) {} }
  _pop = null;
}
export function starterPopupOpen() { return !!(_pop && _pop.isConnected); }

// Where the node is on screen, in both renderers.
export function nodeScreenRect(node) {
  try {
    if (isVueNodes()) {
      const el = document.querySelector(`.lg-node[data-node-id="${node.id}"]`);
      if (el && node._pixInfoRoot && el.contains(node._pixInfoRoot)) return el.getBoundingClientRect();
    }
    const c = app.canvas;
    const r = c.canvas.getBoundingClientRect();
    const ds = c.ds;
    const x = r.left + (node.pos[0] + ds.offset[0]) * ds.scale;
    const y = r.top + (node.pos[1] + ds.offset[1]) * ds.scale;
    return { left: x, top: y, right: x + node.size[0] * ds.scale, bottom: y + node.size[1] * ds.scale,
      width: node.size[0] * ds.scale, height: node.size[1] * ds.scale };
  } catch (_e) {
    return { left: 200, top: 200, right: 300, bottom: 240, width: 100, height: 40 };
  }
}

export function showStarterPopup(node) {
  closeStarterPopup();
  injectCSS();
  const pop = document.createElement("div");
  pop.className = "pix-info-start";
  const head = document.createElement("div");
  head.className = "pix-info-start-h";
  head.textContent = "START FROM";
  const x = document.createElement("button");
  x.type = "button";
  x.className = "pix-info-start-x";
  x.title = "Keep a plain Info button";
  x.textContent = "✕";
  x.addEventListener("click", () => closeStarterPopup());
  head.appendChild(x);
  pop.appendChild(head);
  const grid = document.createElement("div");
  grid.className = "pix-info-start-g";
  for (const st of STARTERS) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "pix-info-start-o";
    b.title = st.h1 ? `${st.name}: sets the button and writes the empty headings` : "A plain button with an empty note";
    const sq = document.createElement("span");
    sq.className = "pix-info-start-sq";
    sq.style.background = st.color;
    const ic = document.createElement("span");
    ic.className = "pix-info-start-ic";
    ic.style.setProperty("--i", `url("${iconUrl(st.icon)}")`);
    ic.style.background = inkFor(st.color);
    sq.appendChild(ic);
    b.appendChild(sq);
    b.appendChild(document.createTextNode(st.name));
    b.addEventListener("click", () => {
      closeStarterPopup();
      if (isLiveNode(node)) applyStarter(node, st);
    });
    grid.appendChild(b);
  }
  pop.appendChild(grid);
  const foot = document.createElement("div");
  foot.className = "pix-info-start-f";
  foot.textContent = "Change anything later: right-click the button, Edit.";
  pop.appendChild(foot);
  document.body.appendChild(pop);
  _pop = pop;

  // Beside the node, kept on screen.
  const r = nodeScreenRect(node);
  const pw = pop.offsetWidth, ph = pop.offsetHeight;
  let left = r.right + 12;
  if (left + pw > window.innerWidth - 8) left = r.left - pw - 12;
  if (left < 8) left = Math.max(8, Math.min(window.innerWidth - pw - 8, r.left));
  let top = Math.max(8, Math.min(window.innerHeight - ph - 8, r.top));
  pop.style.left = `${Math.round(left)}px`;
  pop.style.top = `${Math.round(top)}px`;

  // Close on a click elsewhere, Esc, or when the node goes away.
  const onDown = (e) => { if (!pop.contains(e.target)) closeStarterPopup(); };
  const onKey = (e) => {
    if (e.key === "Escape") { e.stopPropagation(); closeStarterPopup(); }
  };
  const poll = setInterval(() => { if (!isLiveNode(node) || !node.graph) closeStarterPopup(); }, 400);
  const t = setTimeout(() => {
    document.addEventListener("pointerdown", onDown, true);
    window.addEventListener("keydown", onKey, true);
  }, 0);
  _popCleanup = () => {
    clearTimeout(t);
    clearInterval(poll);
    document.removeEventListener("pointerdown", onDown, true);
    window.removeEventListener("keydown", onKey, true);
  };
  requestAnimationFrame(() => { try { grid.firstChild?.focus({ preventScroll: true }); } catch (_e) {} });
}

export { NODE };
