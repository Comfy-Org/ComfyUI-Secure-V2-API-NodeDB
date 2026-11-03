// Prompt Pack Pixaroma - CSS injection + DOM building.
//
// Layout:
//   .pix-pp-root
//     .pix-pp-tawrap               (textarea wrapper)
//       .pix-pp-ta                 (the textarea)
//     .pix-pp-bottombar            (bottom strip)
//       .pix-pp-actions            (Copy all / Replace / Clear buttons)
//         .pix-pp-actbtn           (each action button)
//       .pix-pp-counter            (small pill on the right)
//
// The split-mode pills ARE in the DOM (.pix-pp-modebar at the top). They
// used to be canvas-painted at the slot-row Y by an onDrawForeground hook,
// which Nodes 2.0 never calls, so they moved into the widget body.
//
// The pills, their labels and the split behaviour ALL come from core.mjs's
// MODES table - never hard-code a mode here.

import { MODES, parsePrompts } from "./core.mjs";
import { textSize } from "../shared/text_size.mjs";
import { followSpellcheck } from "../shared/spellcheck.mjs";

const BRAND = "#f66744";

let _cssInjected = false;
export function injectCSS() {
  if (_cssInjected) return;
  _cssInjected = true;
  const style = document.createElement("style");
  style.id = "pix-pp-css";
  style.textContent = `
    .pix-pp-root {
      display: flex;
      flex-direction: column;
      gap: 6px;
      padding: 6px;
      width: 100%;
      /* NO height:100% - it collapses to 0 under the Nodes 2.0 resize-floor
         measurement and lets the bottom button row spill outside the node when
         squished. The .pix-pp-tawrap min-height:100px gives the root a real
         natural floor instead. The host wrapper still flex:1-fills the body in
         Nodes 2.0, and legacy sizes the element, so the textarea still fills. */
      box-sizing: border-box;
      color: #e0e0e0;
      font: 12px sans-serif;
    }
    /* Split-mode pills — a DOM segmented toggle at the top of the body,
       one per entry in core.mjs's MODES. (Were canvas-painted on the slot
       row; moved to DOM so they render in Nodes 2.0. Style matches the
       .pix-pp-actbtn family.) */
    .pix-pp-modebar {
      display: flex;
      /* Three pills now. The Nodes 2.0 body is narrower than Classic, so let
         them wrap onto a second line rather than squeezing their labels to
         nothing (node UI convention: action rows wrap, they do not clip). */
      flex-wrap: wrap;
      gap: 4px;
      flex: 0 0 auto;
      user-select: none;
    }
    .pix-pp-modepill {
      flex: 1 1 auto;
      min-width: 64px;
      box-sizing: border-box;
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid rgba(255, 255, 255, 0.15);
      border-radius: 4px;
      color: rgba(255, 255, 255, 0.85);
      cursor: pointer;
      font: 11px sans-serif;
      padding: 4px 0;
      text-align: center;
      transition: background 0.1s, color 0.1s, border-color 0.1s;
    }
    .pix-pp-modepill:hover { background: var(--pix-acc,#f66744); border-color: var(--pix-acc,#f66744); color: #fff; }
    .pix-pp-modepill.active { background: var(--pix-acc,#f66744); border-color: var(--pix-acc,#f66744); color: #fff; }
    .pix-pp-tawrap {
      position: relative;
      flex: 1 1 auto;
      min-height: 100px;
      display: flex;
    }
    .pix-pp-ta {
      flex: 1 1 auto;
      width: 100%;
      height: 100%;
      box-sizing: border-box;
      background: #1d1d1d;
      color: #e0e0e0;
      border: 1px solid #333;
      border-radius: 4px;
      padding: 6px 8px;
      font: 12px monospace;
      font-size: ${textSize(12)};
      resize: none;
      outline: none;
    }
    .pix-pp-ta:focus { border-color: var(--pix-acc,#f66744); }
    .pix-pp-bottombar {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      flex: 0 0 auto;
      gap: 8px;
      padding: 0 2px;
    }
    /* Action buttons (Copy all / Replace / Clear). Semi-transparent
       white overlay default so the button blends with whatever node
       colour the user picks. Hover = full BRAND orange fill (not just
       orange border) so the click target is unambiguous. */
    .pix-pp-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
      /* 0 1 auto + min-width:0 so this button group can SHRINK below its
         content width when the node is narrow - that's what forces the buttons
         to wrap instead of the last one (Clear) spilling out the right edge.
         flex:0 0 auto sized it to content (no wrap). */
      flex: 0 1 auto;
      min-width: 0;
      /* Stop text selection bleeding from the textarea into the button
         labels when the user drag-selects to the edge of the field. */
      user-select: none;
    }
    .pix-pp-actbtn {
      /* box-sizing: border-box so min-width includes padding + border -
         otherwise content-box adds an extra 26px per button (24 padding
         + 2 border) and the bottom row overflows even at the clamp. */
      box-sizing: border-box;
      /* min-width keeps all three buttons the same size when the label
         briefly changes to "Copied" / "Pasted" so the row never reflows
         under the cursor. 86px fits the widest label ("Copy all") with
         padding included. */
      min-width: 86px;
      user-select: none;
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid rgba(255, 255, 255, 0.15);
      border-radius: 4px;
      color: rgba(255, 255, 255, 0.85);
      cursor: pointer;
      font: 11px sans-serif;
      padding: 4px 12px;
      transition: background 0.1s, color 0.1s, border-color 0.1s;
    }
    .pix-pp-actbtn:hover {
      background: var(--pix-acc,#f66744);
      border-color: var(--pix-acc,#f66744);
      color: #fff;
    }
    .pix-pp-actbtn[disabled] {
      color: rgba(255, 255, 255, 0.3);
      cursor: default;
      background: rgba(255, 255, 255, 0.02);
      border-color: rgba(255, 255, 255, 0.08);
    }
    .pix-pp-actbtn[disabled]:hover {
      background: rgba(255, 255, 255, 0.02);
      border-color: rgba(255, 255, 255, 0.08);
      color: rgba(255, 255, 255, 0.3);
    }
    /* Success flash - shown after a successful Copy / Replace. Higher
       specificity (including the hover variant) so the green wins even
       when the mouse is still on the button after the click. Same green
       Show Text Pixaroma uses for its Copy feedback. */
    .pix-pp-actbtn.is-flashing,
    .pix-pp-actbtn.is-flashing:hover {
      background: #3ec371;
      border-color: #3ec371;
      color: #fff;
    }
    .pix-pp-counter {
      font: 10px sans-serif;
      color: rgba(255, 255, 255, 0.6);
      background: rgba(255, 255, 255, 0.05);
      padding: 2px 8px;
      border-radius: 10px;
      user-select: none;
      white-space: nowrap;
    }
    .pix-pp-counter.active {
      color: var(--pix-acc,#f66744);
      background: rgba(0, 0, 0, 0.25);
      border: 1px solid var(--pix-acc,#f66744);
    }
    .pix-pp-counter.empty {
      color: rgba(255, 255, 255, 0.3);
    }
    /* (Confirm-dialog CSS removed - Clear is now instant per spec.) */
  `;
  document.head.appendChild(style);
}

// Build the static DOM tree. Returns the root element: the split-mode pill
// bar, the textarea, and a bottom bar with three action buttons + counter.
// All of it is DOM - nothing here is canvas-painted (see the module header).
export function buildRoot() {
  const root = document.createElement("div");
  root.className = "pix-pp-root";

  // Split-mode pills — DOM segmented toggle at the top, one per MODES entry.
  const modebar = document.createElement("div");
  modebar.className = "pix-pp-modebar";
  // Built from core.mjs's MODES so the pills, the labels and the actual
  // splitting can never disagree, and so a fifth separator is one table entry.
  const pills = MODES.map((m) => {
    const pill = document.createElement("button");
    pill.type = "button";
    pill.className = "pix-pp-modepill";
    pill.textContent = m.label;
    pill.dataset.mode = m.id;
    pill.title = m.title;
    modebar.appendChild(pill);
    return pill;
  });

  const tawrap = document.createElement("div");
  tawrap.className = "pix-pp-tawrap";

  const ta = document.createElement("textarea");
  ta.className = "pix-pp-ta";
  ta.placeholder = "Paste your prompts here...\n\nPick the pill that matches how they are separated.\nA file from Save Text Pixaroma? Pick the same one you chose there.";
  followSpellcheck(ta);

  tawrap.appendChild(ta);

  const bottombar = document.createElement("div");
  bottombar.className = "pix-pp-bottombar";

  // Three action buttons on the left of the bottom bar - mirrors Text
  // Pixaroma's button trio but in the bottom row instead of the top.
  const actions = document.createElement("div");
  actions.className = "pix-pp-actions";

  const copyBtn = document.createElement("button");
  copyBtn.type = "button";
  copyBtn.className = "pix-pp-actbtn";
  copyBtn.textContent = "Copy all";
  copyBtn.title = "Copy the entire textarea content to the clipboard";

  const replaceBtn = document.createElement("button");
  replaceBtn.type = "button";
  replaceBtn.className = "pix-pp-actbtn";
  replaceBtn.textContent = "Replace";
  replaceBtn.title = "Replace the textarea with text from the clipboard (image / empty clipboard shows a toast and leaves the text alone)";

  const clearBtn = document.createElement("button");
  clearBtn.type = "button";
  clearBtn.className = "pix-pp-actbtn";
  clearBtn.textContent = "Clear";
  clearBtn.title = "Empty the textarea instantly (no confirm)";
  clearBtn.disabled = true;

  actions.append(copyBtn, replaceBtn, clearBtn);

  const counter = document.createElement("div");
  counter.className = "pix-pp-counter empty";
  counter.textContent = "0 prompts";
  counter.title = "How many prompts are in the box right now. During a run it counts down how many are left.";

  bottombar.appendChild(actions);
  bottombar.appendChild(counter);

  root.appendChild(modebar);
  root.appendChild(tawrap);
  root.appendChild(bottombar);

  root._pixPp = { ta, counter, copyBtn, replaceBtn, clearBtn, pills };

  return root;
}

// Apply the current state to the DOM.
//   - Textarea value matches state.text (only if it differs - avoid stomping the caret)
//   - Counter updates via updateCounter()
//   - Clear button enabled state reflects whether there is text to clear
//   - Exactly one pill carries the .active class, matched on data-mode
export function applyState(root, state, runState) {
  const els = root._pixPp;
  if (!els) return;
  if (els.ta.value !== state.text) els.ta.value = state.text;
  for (const pill of els.pills || []) {
    pill.classList.toggle("active", pill.dataset.mode === state.mode);
  }
  updateCounter(root, state, runState);
  updateClearButton(root, state);
}

// Update just the counter pill. runState is optional:
//   { running: true, remaining: 3 }    -> "3 left" in orange (counts DOWN
//                                         as workflows finish executing)
//   undefined / null / running:false   -> "N prompts" or "0 prompts"
//
// The count comes from core.mjs's parsePrompts - the SAME function the queue
// loop uses, so the number on the pill is by construction the number of runs
// you will get. This used to be an inline copy of the split "so render.mjs
// doesn't depend on core.mjs at module load time" (there is no cycle: core
// imports only shared/queue_drivers.mjs, which imports nothing). The copy
// knew about paragraph and line only, so the moment a third mode was added
// the pill would have silently counted a --- line file as one prompt.
export function updateCounter(root, state, runState) {
  const els = root._pixPp;
  if (!els || !els.counter) return;
  const total = parsePrompts(state?.text || "", state?.mode).length;

  els.counter.classList.remove("active", "empty");
  if (runState && runState.running) {
    els.counter.classList.add("active");
    els.counter.textContent = `${runState.remaining} left`;
  } else if (total === 0) {
    els.counter.classList.add("empty");
    els.counter.textContent = "0 prompts";
  } else {
    els.counter.textContent = `${total} prompt${total === 1 ? "" : "s"}`;
  }
}

// Enable / disable the Clear prompts button based on whether the textarea
// has any content. Avoids accidental clicks on an empty textarea.
export function updateClearButton(root, state) {
  const els = root._pixPp;
  if (!els || !els.clearBtn) return;
  const hasContent = !!(state?.text && state.text.length > 0);
  els.clearBtn.disabled = !hasContent;
}
