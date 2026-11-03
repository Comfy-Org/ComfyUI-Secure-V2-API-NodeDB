// Spell check in the Pixaroma text boxes follows ComfyUI's own setting, the way ComfyUI's boxes do (a Discord ask,
// 2026-10-23: "I have it turned on in ComfyUI but it doesn't work in the Pixaroma nodes").
//
// The setting: Settings > Comfy > Node Widget > "Textarea widget spellcheck" (Comfy.TextareaWidget.Spellcheck,
// default off). Core reads it when it builds a box and, on a change, sets it on every textarea.comfy-multiline-input;
// ours are not that class, so they hard-coded off (or kept the browser's on) and never followed it.
// Only boxes people WRITE in follow it (prompts, ideas, captions, descriptions); names, paths, numbers, colours and
// formulas stay off.
import { app } from "../../../scripts/app.js";

export const SPELLCHECK_SETTING = "Comfy.TextareaWidget.Spellcheck";
const MARK = "data-pix-spellcheck";
let listening = false;

export function spellcheckOn() {
  try { return !!app.ui.settings.getSettingValue(SPELLCHECK_SETTING); } catch { return false; }
}

// el follows the setting from now on. A change reaches every box in the page at once; a box that was out of the page
// then (another tab, a closed subgraph) catches up when it gets the focus, which is when spell check matters.
export function followSpellcheck(el) {
  el.setAttribute(MARK, "");
  el.spellcheck = spellcheckOn();
  if (!listening && app.ui?.settings?.addEventListener) {
    listening = true;
    app.ui.settings.addEventListener(`${SPELLCHECK_SETTING}.change`, (e) => {
      const on = !!e.detail?.value;
      for (const box of document.querySelectorAll(`[${MARK}]`)) box.spellcheck = on;
    });
    document.addEventListener("focusin", (e) => {
      const box = e.target;
      if (box?.hasAttribute?.(MARK)) box.spellcheck = spellcheckOn();
    }, true);
  }
  return el;
}
