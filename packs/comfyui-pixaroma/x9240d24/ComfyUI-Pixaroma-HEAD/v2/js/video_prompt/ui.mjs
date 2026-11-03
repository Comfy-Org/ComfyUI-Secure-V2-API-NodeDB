// Video Prompt Pixaroma - the node face.
//
// ONE DOM widget in both renderers, so there is no per-renderer UI to rebuild
// on a live renderer flip (the failure that hit Switch and Mute Switch). The
// only renderer branch in the whole node is the size clamp, which is
// Classic-only because in Nodes 2.0 the rendered size lives in the Vue layout
// store and clamping node.size desyncs the two.
//
// Layout, top to bottom, is the order the work happens in: what mode am I in,
// what is my idea, how long, then the answer, then the buttons. Generate is the
// LAST thing and sits bottom right, because that is where the cursor already is
// after reading the output.

import { app } from "../../../scripts/app.js";
import { pixAsset } from "../shared/api_url.mjs";
import { ACC, installNodeAccent } from "../shared/node_settings.mjs";
import { applyAdaptiveCanvasOnly } from "../shared/nodes2.mjs";
import { installCanvasZoomPassthrough } from "../shared/canvas_zoom.mjs";
import { installNativeTextMenu } from "../shared/native_text_menu.mjs";
import { installResizeFloor } from "../shared/resize_floor.mjs";
import { notifyGraphChanged } from "../shared/graph_changed.mjs";
// The themed seed question (no cycle: ai_prompt never imports video_prompt).
import { askName } from "../ai_prompt/settings.mjs";
import { textSize } from "../shared/text_size.mjs";
import { followSpellcheck } from "../shared/spellcheck.mjs";
import {
  IDEA_SHARE_DEFAULT, IDEA_SHARE_MAX, IDEA_SHARE_MIN,
  MODE_HINTS, MODE_LABELS, SEED_RANDOM, displaySeed, looksSpoken, modeOf,
  readLast, readState, rollSeed, writeLast, writeState,
} from "./core.mjs";

const ROOT_CLASS = "pix-vp-root";
const WIDGET_TYPE = "pixaroma_video_prompt";   // namespaced so Nodes 2.0 does not
                                            // match a registered Vue widget and
                                            // orphan our element
export const WIDGET_MIN_H = 330;

// The tier names the face draws before the server has answered. Shipped and
// user lists are both four tiers today; this only has to stop the chip row
// being empty for the first few hundred milliseconds.
const FALLBACK_TIERS = ["5 seconds", "8 seconds", "10 seconds", "15 seconds"];
const TIER_CACHE = new Map();   // mode -> [names]

export function cacheTiers(mode, names) {
  if (Array.isArray(names) && names.length) TIER_CACHE.set(mode, names.slice());
}
function tiersFor(mode) {
  return TIER_CACHE.get(mode) || FALLBACK_TIERS;
}

// The cache used to be filled ONLY by opening the settings panel, so a user who
// had edited or renamed their tiers saw the SHIPPED names on the face until
// they opened the gear - and clicking the third chip then wrote a tier_name
// that did not exist on disk. Fetch once per page instead, the first time any
// face is built, so the chips are right from the start.
let _tierFetch = null;
function primeTiers(node) {
  if (_tierFetch) return;
  _tierFetch = import("./api.mjs")
    .then((api) => api.fetchAll())
    .then((data) => {
      // RETRY on failure, or one bad first fetch reinstates the exact bug this
      // was added to fix, for the whole page session. fetchAll never rejects
      // (it returns {ok:false}), so the catch below is dead for that path.
      // Reloading the browser while ComfyUI is still starting does this
      // routinely on Desktop.
      if (!data?.ok) { _tierFetch = null; return; }
      let changed = false;
      for (const mode of Object.keys(data.modes || {})) {
        const names = (data.modes[mode]?.durations || []).map((t) => t.name);
        if (names.length) { cacheTiers(mode, names); changed = true; }
      }
      // Repaint every face already on the canvas, not just the one that asked.
      if (changed) {
        for (const n of window.app?.graph?._nodes || []) {
          if (n?._pixVpEls) renderFace(n);
        }
      }
    })
    .catch(() => { _tierFetch = null; });   // let the next node try again
}

/** "8 seconds" -> "8s". Falls back to the whole name so a hand-renamed tier
 *  still shows something meaningful rather than an empty chip. */
function shortTier(name) {
  const m = /^\s*(\d+(?:\.\d+)?)/.exec(String(name || ""));
  return m ? m[1] + "s" : String(name || "?");
}

let _cssDone = false;
export function injectCSS() {
  if (_cssDone) return;
  _cssDone = true;
  const style = document.createElement("style");
  style.id = "pixaroma-h3-prompt-css";
  style.textContent = `
  .${ROOT_CLASS}{
    display:flex; flex-direction:column; gap:6px;
    box-sizing:border-box; width:100%; padding:2px 0 0;
    font:12px 'Segoe UI', sans-serif; color:#ddd;
    min-height:0;                       /* the floor is installResizeFloor's job */
  }
  /* Nodes 2.0 paints its own panel behind the widget; a solid background here
     would sit on top of the node's own colour. */
  .${ROOT_CLASS} *{ box-sizing:border-box; }

  .pix-vp-banner{
    display:flex; align-items:center; gap:7px; flex:none;
    padding:6px 9px; border-radius:4px;
    background:color-mix(in srgb, ${ACC} 10%, transparent);
    border:1px solid color-mix(in srgb, ${ACC} 35%, transparent);
  }
  /* NO icon on the left of this banner. It used to carry the gear glyph purely
     as decoration, which put a fake gear next to the real settings gear at the
     other end of the same row - so the row appeared to have two settings
     buttons. The mode is written in words; it does not need a picture, and
     there is no icon in the bundled set that would mean "mode" anyway. */
  .pix-vp-blabel{ color:#eee; font-size:11px; }
  .pix-vp-bhint{ margin-left:auto; color:#888; font-size:10px; }
  .pix-vp-gear{
    flex:none; width:14px; height:14px; padding:0; margin:0 0 0 2px;
    background:none; border:none; cursor:pointer; line-height:0;
  }
  .pix-vp-gear::before{
    content:""; display:block; width:100%; height:100%; background:#aaa;
    -webkit-mask:url("${pixAsset("icons/note/gear.svg")}") center/contain no-repeat;
    mask:url("${pixAsset("icons/note/gear.svg")}") center/contain no-repeat;
  }
  .pix-vp-gear:hover::before{ background:${ACC}; }

  .pix-vp-caprow{ display:flex; align-items:center; gap:8px; flex:none; }
  .pix-vp-caption{ flex:none; color:${ACC}; font-size:10px; letter-spacing:.4px; }
  /* A word, not a glyph. An arrow character is drawn by the operating system and
     lands on a different baseline on Windows, Mac and Linux (the reason the gear
     is a bundled SVG, convention #28), and there is no expand icon in the
     bundled set. */
  .pix-vp-expand{
    margin-left:auto; background:none; border:none; padding:0;
    cursor:pointer; color:#777; font:10px 'Segoe UI', sans-serif;
    letter-spacing:.3px;
  }
  .pix-vp-expand:hover{ color:${ACC}; }

  .pix-vp-idea, .pix-vp-out{
    width:100%; background:#1d1d1d; color:#e0e0e0;
    border:1px solid #333; border-radius:4px; padding:6px 8px;
    font:12px monospace; font-size:${textSize(12)}; resize:none; outline:none;
  }
  /* THE TWO BOXES SHARE THE NODE'S SPARE HEIGHT. flex-basis 0 makes the two grow
     numbers a pure ratio, so dragging the node taller grows BOTH - which is what
     the idea box used to be missing, sitting at a fixed 52px while the prompt
     box absorbed every pixel. renderFace writes the two variables from the
     stored share; the fallbacks here are what an un-rendered node shows. */
  .pix-vp-idea{
    flex:var(--pix-vp-idea-grow,320) 1 0; min-height:44px;
  }
  .pix-vp-idea:focus{ border-color:${ACC}; }
  /* The PROMPT readout is a preview, not an input. It wears Prompt Pixaroma's
     read-only surface (.pix-prm-expand): a LIGHTER, raised panel instead of the
     sunken dark field an editable box uses, and NO accent on focus - a focus
     ring is the strongest "you can type here" cue there is, and this box is
     readOnly. Reported alongside the AI Prompt one. Still selectable and
     copyable; cursor:text says so. Declared before the .is-error / .is-stale
     rules below, so those still win on their border and opacity. */
  .pix-vp-out{
    flex:var(--pix-vp-out-grow,680) 1 0; min-height:64px; line-height:1.45;
    font-size:${textSize(11)}; color:#d8d8d8; cursor:text;
    background:#2d2d2d; border-color:#3a3a3a;
  }

  /* The grab strip under the idea box. Negative margins so a 9px target costs
     about 1px of layout inside the 6px row gap it already sits in. */
  .pix-vp-grip{
    flex:none; height:9px; margin:-5px 0 -3px; width:100%;
    display:flex; align-items:center; justify-content:center;
    cursor:ns-resize; touch-action:none;
  }
  /* #555 rather than the #444 the chip borders use: this one has to be FOUND,
     not just noticed once you are looking at it. */
  .pix-vp-grip::before{
    content:""; display:block; width:36px; height:2px; border-radius:1px;
    background:#555;
  }
  .pix-vp-grip:hover::before, .pix-vp-grip.is-dragging::before{ background:${ACC}; }

  .pix-vp-tip{
    flex:none; display:flex; align-items:center; gap:5px;
    color:#777; font-size:10px; line-height:1.3;
  }
  .pix-vp-tip b{ color:${ACC}; font-weight:400; }

  .pix-vp-controls{ display:flex; align-items:center; gap:6px; flex:none; }
  .pix-vp-tiers{ display:flex; gap:4px; flex:1 1 auto; min-width:0; }
  .pix-vp-chip{
    flex:1 1 0; min-width:0; text-align:center; cursor:pointer;
    background:#1d1d1d; border:1px solid #444; border-radius:4px;
    padding:5px 2px; color:#888; font-size:11px; font-family:inherit;
    white-space:nowrap; overflow:hidden;
  }
  .pix-vp-chip:hover{ border-color:${ACC}; color:#ddd; }
  .pix-vp-chip.is-on{ background:${ACC}; border-color:${ACC}; color:#fff; }
  /* 5s is the tightest fit for a speaking idea, so it is marked when the idea
     asks for speech. It measured 0/6 until the tier's checklist was trimmed to
     five items, and 5/6 after; 8s and 10s are 6/6. Marked, never blocked - it
     is a guess about the user's text, and a dropped line costs one re-roll. */
  .pix-vp-chip.is-warn{ border-color:#c9a227; color:#c9a227; }
  .pix-vp-chip.is-warn.is-on{ background:#c9a227; border-color:#c9a227; color:#1d1d1d; }

  .pix-vp-seedwrap{
    display:flex; align-items:center; flex:none;
    background:#1d1d1d; border:1px solid #444; border-radius:4px; overflow:hidden;
  }
  .pix-vp-seed{
    background:none; border:none; cursor:pointer; padding:5px 7px;
    color:#ccc; font:10px monospace; max-width:92px; overflow:hidden;
    text-overflow:ellipsis; white-space:nowrap;
  }
  .pix-vp-seed:hover{ color:${ACC}; }
  .pix-vp-seedmode{
    background:none; border:none; border-left:1px solid #444; cursor:pointer;
    padding:5px 6px; color:#888; font:10px 'Segoe UI', sans-serif;
  }
  .pix-vp-seedmode:hover{ color:${ACC}; }
  .pix-vp-seedmode.is-on{ background:${ACC}; color:#fff; }

  .pix-vp-readhead{
    display:flex; align-items:center; justify-content:space-between; flex:none;
  }
  .pix-vp-readhead .k{ color:${ACC}; font-size:10px; letter-spacing:.4px; }
  .pix-vp-readhead .v{ color:#777; font-size:10px; }
  /* A failure reads as a message, not as a prompt. Amber rather than red: it is
     almost always a setup step the user has not done yet, not a crash. */
  .pix-vp-readhead .v.is-error{ color:#e0a33a; }
  .pix-vp-out.is-error{ color:#e0a33a; border-color:#7a5a20; }
  /* the shown prompt no longer matches the idea/tier/seed on the node */
  .pix-vp-readhead .v.is-stale{ color:#9a8f5a; }
  .pix-vp-out.is-stale{ opacity:.6; }

  /* wrap: the Nodes 2.0 body is narrower than Classic's, so a three-button row
     sized for Classic spills out of the right edge without this. */
  .pix-vp-actions{ display:flex; align-items:center; gap:6px; flex:none; flex-wrap:wrap; }
  .pix-vp-spacer{ flex:1 1 auto; min-width:0; }
  .pix-vp-btn{
    box-sizing:border-box; cursor:pointer; user-select:none;
    background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.15);
    border-radius:4px; padding:6px 12px;
    color:rgba(255,255,255,0.7); font:11px 'Segoe UI', sans-serif;
  }
  .pix-vp-btn:hover{ background:${ACC}; border-color:${ACC}; color:#fff; }
  .pix-vp-btn:disabled, .pix-vp-btn:disabled:hover{
    background:rgba(255,255,255,0.02); border-color:rgba(255,255,255,0.08);
    color:rgba(255,255,255,0.28); cursor:default;
  }
  .pix-vp-btn.pix-vp-primary{
    background:${ACC}; border-color:${ACC}; color:#fff; padding:6px 15px;
  }
  .pix-vp-btn.pix-vp-primary:hover{ filter:brightness(1.12); }
  /* A STATE toggle, not an action, so it reads as filled-when-on like the seed
     mode badge and the tier chips rather than as another thing to press. */
  .pix-vp-btn.pix-vp-vram.is-on{
    background:${ACC}; border-color:${ACC}; color:#fff;
  }
  /* a wired CLIP makes it do nothing - say so visually, not just in the title */
  .pix-vp-btn.pix-vp-vram.is-inert{ opacity:.4; }
  /* literal glyph, never a \\XXXX CSS escape - JS reads that as an illegal
     octal escape inside a template literal and the whole module fails to load */
  .pix-vp-btn.pix-vp-vram.is-on::before{ content:"✓ "; }
  /* higher specificity than :hover so the green survives a still-hovered cursor */
  .pix-vp-btn.is-flashing, .pix-vp-btn.is-flashing:hover{
    background:#3ec371; border-color:#3ec371; color:#fff;
  }
  `;
  document.head.appendChild(style);
}

// ---------------------------------------------------------------------------
// Build
// ---------------------------------------------------------------------------
function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
}

function flash(button, label) {
  if (!button) return;
  // Cache the ORIGINAL once and cancel any pending restore. Clicking Copy twice
  // inside the 700ms window used to capture "Copied" as the original, so the
  // button read "Copied" for the rest of the session - and not even green, so
  // it just looked broken. Nothing in renderFace rewrites button labels.
  clearTimeout(button._pixFlashT);
  if (button._pixFlashOrig == null) button._pixFlashOrig = button.textContent;
  button.classList.add("is-flashing");
  if (label) button.textContent = label;
  button._pixFlashT = setTimeout(() => {
    button.classList.remove("is-flashing");
    if (button._pixFlashOrig != null) button.textContent = button._pixFlashOrig;
    button._pixFlashOrig = null;
    button._pixFlashT = null;
  }, 700);
}

async function copyText(text, button) {
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
    flash(button, "Copied");
    return;
  } catch (e) {
    // http on a LAN address is not a secure context, so the clipboard API is
    // missing entirely. Same fallback Seed Pixaroma's Copy carries.
  }
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
    flash(button, "Copied");
  } catch (e) {
    console.error("[Pixaroma.VideoPrompt] copy failed", e);
  }
}

// ---------------------------------------------------------------------------
// How tall is the idea box
// ---------------------------------------------------------------------------
/** Push the stored split onto the two CSS variables the flex rules read.
 *  DOM only - it writes no state, so it is safe on the load path. */
function applyShare(node) {
  const root = node?._pixVpEls?.root;
  if (!root) return;
  const share = readState(node).idea_share;
  // x1000 rather than a fraction: flex-grow takes a number, and integers keep
  // the two sides exactly complementary with no float dust.
  root.style.setProperty("--pix-vp-idea-grow", String(Math.round(share * 1000)));
  root.style.setProperty("--pix-vp-out-grow", String(1000 - Math.round(share * 1000)));
}

/**
 * Drag the bottom edge of the idea box.
 *
 * Both defences from convention #20, and neither is optional: `setPointerCapture`
 * keeps the move events coming when the cursor leaves the node, and the
 * buttons-are-up guard ends the drag when the release goes missing (the pointer
 * leaves the viewport, something else takes capture). Without them the grip
 * follows the cursor forever with no way to put it down, and a synthetic test
 * cannot reproduce that - it only ever shows up under a real mouse.
 *
 * Only the RATIO is written, and every measurement is a screen-pixel rect, so
 * the canvas zoom cancels out: dragging works the same at 40% and at 200%.
 */
function installIdeaGrip(node, grip, idea, out) {
  let pid = null;
  let startY = 0;
  let startH = 0;
  let total = 0;

  const end = () => {
    if (pid == null) return;          // idempotent - the buttons guard calls it too
    try { grip.releasePointerCapture(pid); } catch (e) { /* already released */ }
    pid = null;
    grip.classList.remove("is-dragging");
    // A drag ends on pointerup, so the pack-wide change net (which listens for
    // click and change) never sees it. This is the explicit call convention #31
    // asks for, or the new height is never recorded and is silently lost.
    notifyGraphChanged();
  };

  grip.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    // Stop LiteGraph starting a node drag under us. The node body would
    // otherwise move while the grip is being pulled.
    e.preventDefault();
    e.stopPropagation();
    const a = idea.getBoundingClientRect().height;
    const b = out.getBoundingClientRect().height;
    if (!(a > 0 && b > 0)) return;    // not laid out yet - a ratio of 0 is not one
    pid = e.pointerId;
    startY = e.clientY;
    startH = a;
    total = a + b;
    grip.classList.add("is-dragging");
    try { grip.setPointerCapture(pid); } catch (e2) { /* capture is a nicety */ }
  });

  grip.addEventListener("pointermove", (e) => {
    if (pid == null) return;
    if (!(e.buttons & 1)) { end(); return; }
    const px = startH + (e.clientY - startY);
    const share = Math.max(IDEA_SHARE_MIN, Math.min(IDEA_SHARE_MAX, px / total));
    writeState(node, { idea_share: share });
    applyShare(node);
  });

  grip.addEventListener("pointerup", end);
  grip.addEventListener("pointercancel", end);
  grip.addEventListener("lostpointercapture", end);

  grip.addEventListener("dblclick", (e) => {
    e.stopPropagation();
    writeState(node, { idea_share: IDEA_SHARE_DEFAULT });
    applyShare(node);
    notifyGraphChanged();
  });
}

/**
 * Edit the idea in the full-screen box.
 *
 * Reuses the editor the formulas already use rather than building a second one.
 * The import is DYNAMIC because settings.mjs imports this module for cacheTiers,
 * so a static import here would be a cycle - and it is a LITERAL specifier, which
 * is what the cache-bust middleware can stamp (a computed one would load a second
 * unstamped copy of the module).
 */
async function openIdeaEditor(node) {
  try {
    const { openEditor } = await import("./settings.mjs");
    openEditor("Your idea", readState(node).idea, (text) => {
      writeState(node, { idea: text });
      renderFace(node);
      notifyGraphChanged();
      return true;
    }, { spellcheck: true, owner: node });
  } catch (e) {
    console.error("[Pixaroma.VideoPrompt] could not open the idea editor", e);
  }
}

export function buildFace(node, openPanel) {
  if (node._pixVpRoot) return node._pixVpRoot;

  const root = el("div", ROOT_CLASS);

  // banner
  const banner = el("div", "pix-vp-banner");
  const blabel = el("span", "pix-vp-blabel", "Text to video");
  const bhint = el("span", "pix-vp-bhint", "");
  const gear = el("button", "pix-vp-gear");
  gear.title = "Video Prompt settings";
  gear.addEventListener("click", (e) => {
    e.stopPropagation();
    openPanel?.(node);
  });
  banner.append(blabel, bhint, gear);

  // idea
  const caprow = el("div", "pix-vp-caprow");
  const caption = el("span", "pix-vp-caption", "YOUR IDEA");
  const expand = el("button", "pix-vp-expand", "Expand");
  expand.title = "Write the idea in a full-screen box";
  expand.addEventListener("click", (e) => {
    e.stopPropagation();
    openIdeaEditor(node);
  });
  caprow.append(caption, expand);
  const idea = el("textarea", "pix-vp-idea");
  idea.placeholder = "she smiles and says: come and see this";
  followSpellcheck(idea);
  idea.addEventListener("input", () => {
    writeState(node, { idea: idea.value });
    renderFace(node);
  });
  const grip = el("div", "pix-vp-grip");
  grip.title = "Drag to make the idea box taller or shorter. "
    + "Double-click to put it back.";

  const tip = el("div", "pix-vp-tip");
  tip.innerHTML = "<b>Tip</b> put spoken words at the end of your idea";

  // tiers + seed
  const controls = el("div", "pix-vp-controls");
  const tiers = el("div", "pix-vp-tiers");
  const seedWrap = el("div", "pix-vp-seedwrap");
  const seedBtn = el("button", "pix-vp-seed", "0");
  seedBtn.title = "Click to type a seed";
  // Themed, not window.prompt: ComfyUI Desktop does not implement that at all,
  // so the chip was dead there with nothing shown (ai-prompt.md #19). The write
  // now lands after an await, past the click the change net records, so it
  // reports itself.
  seedBtn.addEventListener("click", async (e) => {
    e.stopPropagation();
    const st = readState(node);
    const entered = await askName("Seed", "Type the seed number to use:", String(st.seed));
    if (entered == null) return;
    const n = Math.trunc(Number(entered));
    if (!Number.isFinite(n) || n < 0) return;
    writeState(node, { seed: n });
    renderFace(node);
    notifyGraphChanged();
  });
  const seedMode = el("button", "pix-vp-seedmode", "F");
  seedMode.addEventListener("click", (e) => {
    e.stopPropagation();
    const st = readState(node);
    writeState(node, {
      seed_mode: st.seed_mode === SEED_RANDOM ? "fixed" : SEED_RANDOM,
    });
    renderFace(node);
  });
  seedWrap.append(seedBtn, seedMode);
  controls.append(tiers, seedWrap);

  // readout
  const readhead = el("div", "pix-vp-readhead");
  const rk = el("span", "k", "PROMPT");
  const rv = el("span", "v", "");
  readhead.append(rk, rv);
  const out = el("textarea", "pix-vp-out");
  out.readOnly = true;
  out.placeholder = "press Generate to write the prompt";

  // actions
  const actions = el("div", "pix-vp-actions");
  const reroll = el("button", "pix-vp-btn", "Re-roll");
  reroll.title = "New seed, then generate";
  reroll.addEventListener("click", (e) => {
    e.stopPropagation();
    writeState(node, { seed: rollSeed() });
    renderFace(node);
    app.queuePrompt?.(0, 1);
  });
  const copy = el("button", "pix-vp-btn", "Copy");
  copy.title = "Copy the finished prompt to the clipboard";
  copy.addEventListener("click", (e) => {
    e.stopPropagation();
    copyText(out.value, copy);
  });
  // On the FACE rather than buried in settings, because it is a per-workflow
  // decision: off while you are only writing prompts, on when this node sits in
  // front of an H3 video model that wants the memory.
  const vram = el("button", "pix-vp-btn pix-vp-vram", "Free VRAM");
  vram.addEventListener("click", (e) => {
    e.stopPropagation();
    const st = readState(node);
    writeState(node, { release_model: !st.release_model });
    renderFace(node);
  });
  const spacer = el("span", "pix-vp-spacer");
  const gen = el("button", "pix-vp-btn pix-vp-primary", "Generate");
  // Honest about what it does. This node is meant to sit in front of a video
  // model, so "Generate" rendering a whole video is an expensive surprise -
  // and Re-roll, whose entire purpose is to be pressed repeatedly, would do it
  // again each time.
  gen.title = "Queues the whole workflow, the same as pressing Run. "
    + "Mute the video part while you are writing prompts, or every press "
    + "renders a video too.";
  gen.addEventListener("click", (e) => {
    e.stopPropagation();
    app.queuePrompt?.(0, 1);
  });
  actions.append(reroll, copy, vram, spacer, gen);

  root.append(banner, caprow, idea, grip, tip, controls, readhead, out, actions);
  installIdeaGrip(node, grip, idea, out);

  const widget = node.addDOMWidget(WIDGET_TYPE, WIDGET_TYPE, root, {
    serialize: false,
    hideOnZoom: false,
    getMinHeight: () => WIDGET_MIN_H,
  });
  // BOTH flags. options.serialize keeps the widget out of the PROMPT;
  // widget.serialize (top level) is what LGraphNode.serialize checks, and
  // without it the node writes a meaningless widgets_values: [""] into every
  // saved workflow. Twelve other DOM-widget nodes in this pack set both.
  widget.serialize = false;
  // Adaptive, not a literal true: canvasOnly:true keeps it out of the legacy
  // Parameters tab but would also exclude it from the Nodes 2.0 body entirely.
  applyAdaptiveCanvasOnly(widget);
  // Without this the wheel stops zooming the canvas while the cursor is over
  // this node (convention #17). Nothing errors; zoom just silently dies.
  installCanvasZoomPassthrough(root);
  // Cut/Copy/Paste in the idea box and the prompt readout, rather than the node
  // menu (reported against Prompt Stack 2026-08-13; every text node has it).
  installNativeTextMenu(root);
  installNodeAccent(node, root);
  // Pins a min-height ONLY while a resize handle is dragged, so the fixed rows
  // cannot be squashed out of the frame, and nothing ever writes a
  // content-derived size on the load path.
  node._pixVpFloorOff = installResizeFloor(root, () => WIDGET_MIN_H);

  node._pixVpRoot = root;
  node._pixVpEls = {
    root, blabel, bhint, idea, tip, tiers, seedBtn, seedMode, out, rv,
    copy, reroll, gen, vram,
  };
  node._pixVpWidget = widget;
  primeTiers(node);
  return root;
}

// ---------------------------------------------------------------------------
// Render
// ---------------------------------------------------------------------------
export function renderFace(node) {
  const els = node?._pixVpEls;
  // Guard on the ELEMENTS, never on root.isConnected: on the very first render
  // the widget root has not been parented yet, and an isConnected gate skips
  // that render and then never runs again, leaving the node blank forever.
  if (!els) return;

  const st = readState(node);
  const mode = modeOf(node);

  // The saved split, re-applied on every paint so a workflow load lands on the
  // user's own height. Style only, so it can never dirty a clean workflow.
  applyShare(node);

  els.blabel.textContent = MODE_LABELS[mode] || mode;
  els.bhint.textContent = MODE_HINTS[mode] || "";

  if (els.idea.value !== st.idea) els.idea.value = st.idea;

  // tier chips
  const names = tiersFor(mode);
  const warnSpeech = st.speech_hint && looksSpoken(st.idea);
  const chosenName = st.tier_name && names.includes(st.tier_name)
    ? st.tier_name
    : names[Math.max(0, Math.min(names.length - 1, st.tier_index))] || names[0];

  if (els.tiers.childElementCount !== names.length) els.tiers.replaceChildren();
  names.forEach((name, i) => {
    let chip = els.tiers.children[i];
    if (!chip) {
      chip = el("button", "pix-vp-chip");
      chip.addEventListener("click", (e) => {
        e.stopPropagation();
        const list = tiersFor(modeOf(node));
        writeState(node, { tier_index: i, tier_name: list[i] || "" });
        renderFace(node);
      });
      els.tiers.appendChild(chip);
    }
    chip.textContent = shortTier(name);
    const on = name === chosenName;
    const warn = warnSpeech && /^\s*5\b/.test(name);
    chip.classList.toggle("is-on", on);
    chip.classList.toggle("is-warn", warn);
    // The chips do TWO jobs, and one of them can be switched off, so say which
    // are live rather than leaving the user to guess.
    const jobs = st.length_block
      ? name + " - sets how long the video is, and how much the model writes"
      : name + " - sets how long the video is (the length instructions are off)";
    chip.title = warn
      ? name + " - talking ideas come out better at 8 seconds or more"
      : jobs;
  });

  // tip line doubles as the speech warning, so there is no extra row to make
  // the node taller when it fires
  if (warnSpeech && /^\s*5\b/.test(chosenName)) {
    els.tip.innerHTML = "<b>Note</b> talking ideas need 8 seconds or more";
  } else {
    els.tip.innerHTML = "<b>Tip</b> put spoken words at the end of your idea";
  }

  // seed
  els.seedBtn.textContent = String(displaySeed(node));
  const random = st.seed_mode === SEED_RANDOM;
  els.seedMode.textContent = random ? "R" : "F";
  els.seedMode.classList.toggle("is-on", random);
  els.seedMode.title = random
    ? "Random: a new seed every run. Click for Fixed."
    : "Fixed: the same seed every run, so the result is repeatable. Click for Random.";
  // NOT disabled in Random mode. A disabled button receives no hover events in
  // Chrome, so its tooltip never shows and the user gets a dead control with no
  // explanation. In Random mode a plain Run already rolls a fresh seed, which
  // is exactly what this button promises, so leaving it enabled is honest.
  els.reroll.title = (random
    ? "Generate again with a new seed (Random mode already rolls one each run)"
    : "New seed, then generate")
    + ". Queues the whole workflow, so mute the video part while writing prompts.";

  // readout. From node.properties, so it is still here after a workflow tab
  // switch - which rebuilds every node object (core.mjs, LAST_PROP). Reading it
  // here also means the load path restores it with no extra hook.
  const last = readLast(node);
  let stale = false;
  if (last && typeof last.text === "string") {
    if (els.out.value !== last.text) els.out.value = last.text;
    if (last.error) {
      els.rv.textContent = "did not run";
    } else {
      // Lead with what the RUN reported, not what the node currently shows.
      // If they disagree - a muted image loader, a renamed tier - this line is
      // the only place it is visible.
      const bits = [];
      if (last.ranMode) bits.push(last.ranMode);
      if (last.ranTier) bits.push(last.ranTier);
      if (last.ranFrames) bits.push(last.ranFrames + "f");
      if (last.words) bits.push(last.words + " words");
      if (last.elapsed) bits.push(last.elapsed + "s");
      stale = (last.forIdea !== undefined && last.forIdea !== st.idea)
        || (last.forTier !== undefined && last.forTier !== st.tier_name)
        // The length switch changes the prompt as much as the tier does, and it
        // lives in the panel, so it is the easiest of the four to change and
        // then forget. Undefined on results from before this was stamped, so
        // an old readout simply keeps its previous behaviour.
        || (last.forLengthBlock !== undefined && last.forLengthBlock !== st.length_block)
        || (last.forSeed != null && st.seed_mode !== SEED_RANDOM && last.forSeed !== st.seed);
      if (stale) bits.push("changed since this ran");
      els.rv.textContent = bits.join(" · ");
    }
  } else {
    els.rv.textContent = "";
  }
  // Dimmed, not disabled: copying the previous prompt on purpose is legitimate.
  els.out.classList.toggle("is-stale", stale && !last?.error);
  els.rv.classList.toggle("is-stale", stale && !last?.error);
  els.out.classList.toggle("is-error", !!last?.error);
  els.rv.classList.toggle("is-error", !!last?.error);
  // Never offer to copy a FAILURE. The message lives in the same readout, so
  // without the error check Copy stayed enabled and put "[Pixaroma] Video
  // Prompt: ..." on the clipboard while flashing green "Copied".
  els.copy.disabled = !els.out.value || !!last?.error;

  // Free VRAM. A wired CLIP makes this do NOTHING - that model belongs to the
  // Load CLIP node and may be shared, so it is not ours to unload. The button
  // used to keep painting its filled "on" state and promising an unload that
  // could not happen, which the help documented and the face contradicted.
  const clipWired = (node.inputs || []).some(
    (i) => i && i.name === "clip" && i.link != null);
  els.vram.classList.toggle("is-on", st.release_model && !clipWired);
  els.vram.classList.toggle("is-inert", clipWired);
  els.vram.title = clipWired
    ? "Does nothing while a Load CLIP node is wired in: that model belongs to "
      + "the loader and may be shared, so it is not this node's to unload."
    : st.release_model
      ? "On: the language model is unloaded as soon as the prompt is written, so "
        + "a video model downstream gets the memory. The prompt is already "
        + "finished by then, so nothing is lost. The next generate reloads it."
      : "Off: the language model stays in memory, so generating again is "
        + "instant. Turn this on when this node sits in front of a video model.";
}

/**
 * Show a failure IN THE READOUT.
 *
 * ComfyUI's error toast says only "This node threw an error during execution",
 * with the real message hidden behind a View details click - so a user who
 * picked the wrong model saw nothing that told them what to do. The readout is
 * where they are already looking.
 *
 * Persisted like applyResult (core.mjs, LAST_PROP), so a tab switch does not
 * throw the message away and leave an unexplained empty box.
 *
 * It stamps NO `for*` fields on purpose: a failure has nothing to be stale
 * against, and renderFace only computes staleness on the success branch.
 */
export function applyError(node, message) {
  const text = String(message || "").trim() ||
    "The node failed, but ComfyUI did not say why. Check the console.";
  writeLast(node, { text, words: 0, error: true });
  renderFace(node);
}

/**
 * Called from the executed listener in index.js. Kept on node.properties
 * (core.mjs, LAST_PROP) so a workflow tab switch does not throw the written
 * prompt away - it is outside the injected state, so it can neither reach
 * Python nor change the node's cache signature.
 *
 * ⚠️ KEEP mode_label / tier / frames. The node already reports what it ACTUALLY
 * did, and throwing that away hid the worst bug in this node: mute or bypass
 * the image loader and the banner still reads "First frame, 1 image wired"
 * while the TEXT-TO-VIDEO formula runs with no picture at all. graphToPrompt
 * drops an input whose origin node is muted, so Python sees first_frame=None,
 * but the face only ever looked at the wire. The result is a confident,
 * well-formed prompt for a scene the model never saw, with no error.
 *
 * Showing the reported mode in the readout meta makes that self-evident, and
 * it also makes a renamed tier and a stale readout diagnosable in the same
 * line. The idea/tier/seed are stamped so renderFace can say when the result
 * no longer matches what is on the node.
 */
export function applyResult(node, payload, elapsed) {
  const st = readState(node);
  writeLast(node, {
    text: typeof payload?.text === "string" ? payload.text : "",
    words: Number(payload?.words) || 0,
    seed: payload?.seed,
    elapsed: elapsed != null ? elapsed : undefined,
    // what the RUN actually used, straight from Python
    ranMode: typeof payload?.mode_label === "string" ? payload.mode_label : "",
    ranTier: typeof payload?.tier === "string" ? payload.tier : "",
    ranFrames: Number(payload?.frames) || 0,
    // what the node held at the moment the result arrived, to spot drift later
    forIdea: st.idea,
    forTier: st.tier_name,
    forLengthBlock: st.length_block,
    forSeed: st.seed_mode === SEED_RANDOM ? null : st.seed,
  });
  if (Number.isFinite(Number(payload?.seed))) {
    node._pixVpLastSeed = Number(payload.seed);
  }
  renderFace(node);
}

export function destroyFace(node) {
  try { node._pixVpFloorOff?.(); } catch (e) { /* already gone */ }
  node._pixVpFloorOff = null;
  // Drop the widget from node.widgets too, not just our own reference. Without
  // this a rebuild (which is what a renderer flip does) appends a SECOND widget
  // and the node grows a duplicate body every time the renderer is toggled.
  if (Array.isArray(node.widgets) && node._pixVpWidget) {
    const i = node.widgets.indexOf(node._pixVpWidget);
    if (i !== -1) node.widgets.splice(i, 1);
  }
  node._pixVpRoot?.remove();
  node._pixVpRoot = null;
  node._pixVpEls = null;
  node._pixVpWidget = null;
}

// ⚠️ DO NOT ADD a rebuild-on-renderer-change hook here. It was tried and
// REVERTED 2026-08-12: this node has ONE DOM widget in both renderers, so a
// live flip has nothing to swap and ComfyUI re-parents the element itself.
//
// The rebuild actively made things worse - ComfyUI owns the .dom-widget wrapper
// around our root, so building a second one leaked a root per flip (1 -> 2 -> 4
// -> 6 across three round trips, five left behind after deleting the node).
//
// The phantom that prompted it was a test artifact. The control is what settled
// it: flip the renderer with Show Text and Save Video on the canvas too, and
// compare. All three behave identically - connected and correctly sized in both
// directions. RUN THAT CONTROL FIRST next time.
