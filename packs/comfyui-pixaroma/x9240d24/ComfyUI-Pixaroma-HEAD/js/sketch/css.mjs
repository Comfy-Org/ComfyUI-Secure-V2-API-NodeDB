// Sketch Pixaroma - one stylesheet for the node face AND the big view.
//
// ⚠️ The CSS below is a JS template literal: NO backticks and NO double-slash
// comments inside it (a backtick ends the literal and blanks every Pixaroma
// node; a double-slash line silently eats the next rule - convention #35).
// Use /* */ comments only, and run node --check after editing.

import { pixAsset } from "../shared/api_url.mjs";
import { ACC, ACC_HOVER } from "../shared/node_settings.mjs";

const CSS_ID = "pix-sketch-css";

export function injectCSS() {
  if (document.getElementById(CSS_ID)) return;
  const gear = pixAsset("icons/note/gear.svg");
  const s = document.createElement("style");
  s.id = CSS_ID;
  s.textContent = `
/* the DOM widget root: fills its row, never sizes itself (nodes2-preview-fill #4) */
.pix-sketch-root{position:relative;flex:1 1 0;min-height:0;box-sizing:border-box;}
/* the layout lives on an INNER layer: ComfyUI sets the root's display itself (fill #37) */
.pix-sketch-inner{position:absolute;inset:0;display:flex;flex-direction:column;gap:6px;padding:6px 8px 8px;
  box-sizing:border-box;overflow:hidden;font:12px "Segoe UI",system-ui,sans-serif;color:#ddd;}
.pix-sketch-row1,.pix-sketch-row2{display:flex;align-items:center;gap:4px;flex:0 0 auto;min-width:0;}
.pix-sketch-grow{flex:1 1 auto;min-width:4px;}
.pix-sketch-btn{width:28px;height:26px;padding:0;border-radius:5px;background:#1d1d1d;border:1px solid #444;color:#aaa;
  display:inline-flex;align-items:center;justify-content:center;cursor:pointer;flex:0 0 auto;box-sizing:border-box;}
.pix-sketch-btn:hover{border-color:${ACC};color:#ddd;}
.pix-sketch-btn.on{background:${ACC};border-color:${ACC};color:#fff;}
.pix-sketch-btn:disabled,.pix-sketch-btn:disabled:hover{opacity:.35;cursor:default;border-color:#444;color:#aaa;}
.pix-sketch-btn svg{width:16px;height:16px;display:block;}
.pix-sketch-gear::before{content:"";display:block;width:15px;height:15px;background:currentColor;
  -webkit-mask:url("${gear}") center/contain no-repeat;mask:url("${gear}") center/contain no-repeat;}
.pix-sketch-sep{width:1px;height:18px;background:#444;margin:0 2px;flex:0 0 auto;}
.pix-sketch-hsep{width:22px;height:1px;background:#444;margin:3px 0;flex:0 0 auto;}
.pix-sketch-sw{width:18px;height:18px;padding:0;border-radius:50%;border:2px solid #1d1d1d;box-shadow:0 0 0 1px #555;
  cursor:pointer;flex:0 0 auto;box-sizing:border-box;margin:0 1px;}
.pix-sketch-sw:hover{box-shadow:0 0 0 1px ${ACC};}
.pix-sketch-sw.on{box-shadow:0 0 0 2px ${ACC};}
.pix-sketch-wl{color:#888;font-size:11px;margin-right:2px;flex:0 0 auto;}
.pix-sketch-w{height:22px;min-width:24px;padding:0 4px;border-radius:4px;background:#1d1d1d;border:1px solid #444;color:#aaa;
  font:11px "Segoe UI",sans-serif;cursor:pointer;box-sizing:border-box;flex:0 0 auto;}
.pix-sketch-w:hover{border-color:${ACC};color:#ddd;}
.pix-sketch-w.on{background:${ACC};border-color:${ACC};color:#fff;}
.pix-sketch-stage{position:relative;flex:1 1 0;min-height:140px;border-radius:6px;overflow:hidden;background:#151515;
  border:1px solid #2c2c2c;cursor:crosshair;touch-action:none;user-select:none;}
.pix-sketch-stage.nopic{cursor:default;}
.pix-sketch-empty{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;text-align:center;
  padding:14px;color:#8a8a8a;font-size:12px;line-height:1.5;pointer-events:none;}
.pix-sketch-warn{position:absolute;left:6px;top:6px;right:6px;padding:4px 8px;border-radius:4px;background:rgba(0,0,0,.75);
  color:#ffd27a;font-size:11px;line-height:1.35;pointer-events:none;}
.pix-sketch-txt{position:absolute;z-index:2;width:150px;box-sizing:border-box;background:rgba(0,0,0,.82);color:#fff;
  border:1px solid ${ACC};border-radius:4px;padding:3px 6px;font:13px "Segoe UI",sans-serif;outline:none;}
/* the list may shrink to ONE row and scroll: Classic resizes can bypass the node's
   own floor (Align writes the size clamped only to computeSize), and a list that
   gives way beats the whole body spilling out of the node */
.pix-sketch-list{flex:0 1 auto;display:flex;flex-direction:column;gap:4px;max-height:108px;overflow-y:auto;min-height:24px;}
.pix-sketch-mrow{display:flex;align-items:center;gap:6px;flex:0 0 auto;min-height:24px;}
.pix-sketch-badge{width:20px;height:20px;border-radius:50%;font-size:11px;font-weight:700;display:inline-flex;
  align-items:center;justify-content:center;flex:0 0 auto;}
.pix-sketch-name{width:92px;flex:0 0 auto;color:#bbb;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.pix-sketch-note{flex:1 1 auto;min-width:0;height:24px;box-sizing:border-box;background:#1d1d1d;color:#e0e0e0;
  border:1px solid #333;border-radius:4px;padding:3px 7px;font:12px "Segoe UI",sans-serif;outline:none;}
.pix-sketch-note:focus{border-color:${ACC};}
.pix-sketch-del{background:none;border:none;color:#888;cursor:pointer;font-size:16px;line-height:1;padding:0 3px;flex:0 0 auto;}
.pix-sketch-del:hover{color:${ACC};}
.pix-sketch-hint{color:#8a8a8a;font-size:12px;min-height:24px;display:flex;align-items:center;flex:0 0 auto;line-height:1.3;}
/* the prompt is a READ-ONLY readout: the lighter raised surface, never the dark "type here" field (convention #3) */
.pix-sketch-prompt{flex:0 0 auto;background:#2d2d2d;border:1px solid #3a3a3a;border-radius:4px;padding:4px 8px 6px;
  display:flex;flex-direction:column;gap:2px;}
.pix-sketch-phead{display:flex;align-items:center;gap:8px;min-height:18px;}
.pix-sketch-plabel{color:#999;font-size:10.5px;letter-spacing:.6px;text-transform:uppercase;flex:1 1 auto;}
.pix-sketch-ptext{color:#d8d8d8;font-size:12px;line-height:1.4;height:34px;overflow-y:auto;white-space:pre-wrap;
  word-break:break-word;cursor:text;user-select:text;}
.pix-sketch-ptext.empty{color:#8a8a8a;font-style:italic;}
.pix-sketch-swc{display:flex;align-items:center;gap:6px;color:#bbb;font-size:11px;cursor:pointer;user-select:none;flex:0 0 auto;}
.pix-sketch-tog{width:26px;height:14px;border-radius:7px;background:#555;position:relative;flex:0 0 auto;}
.pix-sketch-tog::after{content:"";position:absolute;top:2px;left:2px;width:10px;height:10px;border-radius:50%;
  background:#ddd;transition:left .12s;}
.pix-sketch-tog.on{background:${ACC};}
.pix-sketch-tog.on::after{left:14px;background:#fff;}

/* ---- the big view ---- */
.pix-sketch-big{position:fixed;inset:0;z-index:10000;background:rgba(8,8,8,.88);display:flex;align-items:stretch;
  justify-content:center;padding:18px;box-sizing:border-box;font:12px "Segoe UI",system-ui,sans-serif;color:#ddd;outline:none;}
.pix-sketch-bpanel{flex:1 1 auto;max-width:1680px;display:flex;flex-direction:column;background:#1a1a1a;
  border:1px solid #3a3a3a;border-radius:10px;overflow:hidden;box-shadow:0 12px 40px rgba(0,0,0,.6);min-width:0;}
.pix-sketch-bhead{height:44px;display:flex;align-items:center;gap:12px;padding:0 12px 0 14px;background:#202020;
  border-bottom:1px solid #2c2c2c;flex:0 0 auto;}
.pix-sketch-btitle{font-weight:600;font-size:13px;}
.pix-sketch-bhint{color:#8a8a8a;font-size:11.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.pix-sketch-done{height:28px;padding:0 18px;border-radius:5px;border:1px solid ${ACC};background:${ACC};color:#fff;
  font:12px "Segoe UI",sans-serif;cursor:pointer;flex:0 0 auto;}
.pix-sketch-done:hover{background:${ACC_HOVER};border-color:${ACC_HOVER};}
.pix-sketch-bmain{flex:1 1 auto;min-height:0;display:grid;grid-template-columns:52px minmax(0,1fr) 330px;}
.pix-sketch-brail{background:#1c1c1c;border-right:1px solid #2a2a2a;display:flex;flex-direction:column;align-items:center;
  gap:6px;padding:10px 0;}
.pix-sketch-brail .pix-sketch-btn{width:34px;height:32px;}
.pix-sketch-bcenter{min-width:0;min-height:0;padding:14px;display:flex;}
.pix-sketch-bcenter .pix-sketch-stage{flex:1 1 auto;min-height:0;}
.pix-sketch-bside{background:#1c1c1c;border-left:1px solid #2a2a2a;padding:12px;display:flex;flex-direction:column;
  gap:10px;min-height:0;overflow-y:auto;}
.pix-sketch-bside h4{margin:2px 0 0;font-size:11px;color:#999;text-transform:uppercase;letter-spacing:.6px;font-weight:600;}
.pix-sketch-bcolors{display:flex;flex-wrap:wrap;gap:6px;align-items:center;}
/* the side panel is too narrow for the swatches AND the widths on one line:
   break on purpose, so the widths get their own labelled row, never a lone XL */
.pix-sketch-bcolors .pix-sketch-grow{flex:0 0 100%;height:0;min-width:0;}
.pix-sketch-bside .pix-sketch-list{max-height:none;flex:0 0 auto;}
.pix-sketch-bside .pix-sketch-ptext{height:auto;min-height:40px;max-height:200px;}
@media (max-width:900px){ .pix-sketch-bmain{grid-template-columns:48px minmax(0,1fr) 250px;} }
`;
  document.head.appendChild(s);
}
