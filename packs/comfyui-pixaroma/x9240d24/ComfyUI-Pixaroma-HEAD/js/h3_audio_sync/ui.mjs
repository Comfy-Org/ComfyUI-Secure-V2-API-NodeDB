// H3 Audio Sync Pixaroma - the node face.
//
// Deliberately just a readout. The trimming belongs to Load Audio Pixaroma and
// the clip length belongs to the latent, so there is nothing here for a control
// to change: what this node needs to do is TELL you what it found, and it can
// only know that once it has seen inside the latent, which happens on a run.

import { ACC, openNodeSettings } from "../shared/node_settings.mjs";
import { pixAsset } from "../shared/api_url.mjs";

const ROOT = "pix-h3s-root";
let _cssDone = false;

export function injectCSS() {
  if (_cssDone) return;
  _cssDone = true;
  const css = `
  .${ROOT}{
    box-sizing:border-box; width:100%; height:100%; display:flex; flex-direction:column;
    justify-content:center; padding:0 8px 4px; font:12px 'Segoe UI',sans-serif;
    background:transparent; overflow:hidden; position:relative;
  }
  /* Convention #28: the bundled gear svg as a mask, never the emoji, so it is
     the same shape on every operating system and matches the toolbar gear. */
  .${ROOT} .gear{
    position:absolute; top:2px; right:6px; padding:3px; cursor:pointer;
    display:flex; align-items:center; justify-content:center;
  }
  .${ROOT} .gear::before{
    content:""; display:block; width:13px; height:13px; background:#8b8b8b;
    -webkit-mask:url(${pixAsset("icons/note/gear.svg")}) center/contain no-repeat;
    mask:url(${pixAsset("icons/note/gear.svg")}) center/contain no-repeat;
  }
  .${ROOT} .gear:hover::before{ background:${ACC}; }
  .${ROOT} .out{
    background:rgba(0,0,0,0.25); border-radius:4px; padding:7px 9px;
    font-size:11px; line-height:1.5; color:#aaa;
  }
  .${ROOT} .out.warn{ box-shadow:inset 2px 0 0 #f2b134; }
  .${ROOT} .out.over{ box-shadow:inset 2px 0 0 #e05252; }
  .${ROOT} .out.ok{ box-shadow:inset 2px 0 0 #5fce7f; }
  .${ROOT} .hd{ color:#ccc; }
  .${ROOT} .dt{ color:#8b8b8b; }
  .${ROOT} .dt.ok{ color:#5fce7f; }
  .${ROOT} .dt.warn{ color:#f2b134; }
  .${ROOT} .dt.over{ color:#e05252; }
  .${ROOT} .idle{ color:rgba(255,255,255,0.4); }
  .${ROOT} .idle b{ color:${ACC}; font-weight:400; }
  `;
  const el = document.createElement("style");
  el.textContent = css;
  document.head.appendChild(el);
}

export function buildFace(node) {
  injectCSS();
  const root = document.createElement("div");
  root.className = ROOT;

  // The settings hold the 15 second guard, so there has to be a visible way in.
  // openNodeSettings is the shared entry point: this node has no panel of its
  // own, it rides on the generic one built from its registered rows.
  const gear = document.createElement("div");
  gear.className = "gear";
  gear.title = "Settings for this node";
  gear.addEventListener("click", (e) => { e.stopPropagation(); openNodeSettings(node); });

  const out = document.createElement("div");
  out.className = "out";
  root.append(gear, out);
  root.addEventListener("contextmenu", (e) => {
    e.preventDefault();
    e.stopPropagation();
    openNodeSettings(node);
  });
  node._pixH3sEls = { root, out };
  return root;
}

export function renderFace(node) {
  const els = node?._pixH3sEls;
  // Guard on the ELEMENTS existing, NOT on isConnected. The first render runs
  // from a queueMicrotask in onNodeCreated, and at that point ComfyUI has not
  // attached the widget element yet - so an isConnected gate skipped it and
  // nothing ever re-rendered, leaving the readout permanently blank. Writing
  // text into a detached element is free and correct; destroyFace nulls _els,
  // which is the real protection against painting a torn-down widget.
  if (!els) return;
  const run = node._pixH3sRun;
  const out = els.out;
  out.textContent = "";

  if (!run) {
    const idle = document.createElement("div");
    idle.className = "idle";
    idle.textContent = "Run once and this will show the clip length, your track "
      + "length, and whether the two match.";
    out.className = "out";
    out.appendChild(idle);
    return;
  }

  const hd = document.createElement("div");
  hd.className = "hd";
  hd.textContent = run.head || "";
  const dt = document.createElement("div");
  dt.className = "dt " + (run.level || "");
  dt.textContent = run.detail || "";
  out.className = "out " + (run.level || "");
  out.append(hd, dt);
}

export function destroyFace(node) {
  if (node) { node._pixH3sEls = null; node._pixH3sRun = null; }
}
