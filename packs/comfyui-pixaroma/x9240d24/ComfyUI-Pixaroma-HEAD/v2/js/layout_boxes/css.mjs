// Layout Boxes Pixaroma - one stylesheet for the node face AND the big view.
//
// The CSS below is a JS template literal: NO backticks and NO double-slash
// comments inside it (a backtick ends the literal and blanks every Pixaroma
// node; a double-slash line silently eats the next rule - convention #35).
// Use /* */ comments only, and run node --check after editing.

import { pixAsset } from "../shared/api_url.mjs";
import { ACC, ACC_HOVER } from "../shared/node_settings.mjs";

const CSS_ID = "pix-lyb-css";

export function injectCSS() {
  if (document.getElementById(CSS_ID)) return;
  const gear = pixAsset("icons/note/gear.svg");
  const s = document.createElement("style");
  s.id = CSS_ID;
  s.textContent = `
/* the DOM widget root: fills its row, never sizes itself (nodes2-preview-fill #4) */
.pix-lyb-root{position:relative;flex:1 1 0;min-height:0;box-sizing:border-box;}
/* the layout lives on an INNER layer: ComfyUI sets the root's display itself (fill #37) */
.pix-lyb-inner{position:absolute;inset:0;display:flex;flex-direction:column;gap:6px;padding:6px 8px 8px;
  box-sizing:border-box;overflow:hidden;font:12px "Segoe UI",system-ui,sans-serif;color:#ddd;}
.pix-lyb-bar{display:flex;align-items:center;gap:4px;flex:0 0 auto;min-width:0;}
.pix-lyb-grow{flex:1 1 auto;min-width:4px;}
.pix-lyb-chip{height:22px;line-height:20px;padding:0 8px;border-radius:11px;border:1px solid rgba(255,255,255,.14);
  background:rgba(255,255,255,.05);color:#bbb;font-size:11px;white-space:nowrap;flex:0 0 auto;box-sizing:border-box;
  cursor:default;user-select:none;}
.pix-lyb-chip.warn{color:#ffd27a;border-color:rgba(255,210,122,.4);}
.pix-lyb-btn{width:28px;height:26px;padding:0;border-radius:5px;background:#1d1d1d;border:1px solid #444;color:#aaa;
  display:inline-flex;align-items:center;justify-content:center;cursor:pointer;flex:0 0 auto;box-sizing:border-box;}
.pix-lyb-btn:hover{border-color:${ACC};color:#ddd;}
.pix-lyb-btn:disabled,.pix-lyb-btn:disabled:hover{opacity:.35;cursor:default;border-color:#444;color:#aaa;}
.pix-lyb-btn svg{width:16px;height:16px;display:block;}
.pix-lyb-gear::before{content:"";display:block;width:15px;height:15px;background:currentColor;
  -webkit-mask:url("${gear}") center/contain no-repeat;mask:url("${gear}") center/contain no-repeat;}
.pix-lyb-stage{position:relative;flex:1 1 0;min-height:120px;border-radius:6px;overflow:hidden;background:#151515;
  border:1px solid #2c2c2c;cursor:crosshair;touch-action:none;user-select:none;}
/* the list may shrink to ONE row and scroll (sketch.md #10): a list that gives
   way beats the whole body spilling out of the node */
.pix-lyb-list{flex:0 1 auto;display:flex;flex-direction:column;gap:4px;max-height:108px;overflow-y:auto;min-height:24px;}
.pix-lyb-row{display:flex;align-items:center;gap:5px;flex:0 0 auto;min-height:24px;border-radius:5px;padding:0 2px;}
.pix-lyb-row.sel{background:rgba(255,255,255,.06);}
.pix-lyb-badge{width:20px;height:20px;border-radius:50%;font-size:11px;font-weight:700;display:inline-flex;
  align-items:center;justify-content:center;flex:0 0 auto;user-select:none;}
.pix-lyb-kind{height:22px;width:40px;padding:0;border-radius:4px;background:#1d1d1d;border:1px solid #444;color:#aaa;
  font:11px "Segoe UI",sans-serif;cursor:pointer;flex:0 0 auto;box-sizing:border-box;}
.pix-lyb-kind:hover{border-color:${ACC};color:#ddd;}
.pix-lyb-kind.text{background:${ACC};border-color:${ACC};color:#fff;}
.pix-lyb-kind.text:hover{background:${ACC_HOVER};border-color:${ACC_HOVER};}
.pix-lyb-desc,.pix-lyb-words{min-width:0;height:24px;box-sizing:border-box;background:#1d1d1d;color:#e0e0e0;
  border:1px solid #333;border-radius:4px;padding:3px 7px;font:12px "Segoe UI",sans-serif;outline:none;}
.pix-lyb-desc{flex:1 1 auto;}
.pix-lyb-words{flex:0 1 38%;}
.pix-lyb-desc:focus,.pix-lyb-words:focus{border-color:${ACC};}
.pix-lyb-mini{width:22px;height:22px;padding:0;border-radius:4px;background:none;border:1px solid transparent;color:#999;
  display:inline-flex;align-items:center;justify-content:center;cursor:pointer;flex:0 0 auto;}
.pix-lyb-mini:hover{border-color:${ACC};color:#ddd;}
.pix-lyb-mini:disabled,.pix-lyb-mini:disabled:hover{opacity:.3;cursor:default;border-color:transparent;}
.pix-lyb-mini svg{width:14px;height:14px;display:block;}
.pix-lyb-del{background:none;border:none;color:#888;cursor:pointer;font-size:16px;line-height:1;padding:0 3px;flex:0 0 auto;}
.pix-lyb-del:hover{color:${ACC};}
.pix-lyb-hint{color:#8a8a8a;font-size:12px;min-height:24px;display:flex;align-items:center;flex:0 0 auto;line-height:1.3;}
.pix-lyb-foot{flex:0 0 auto;height:16px;line-height:16px;color:#8a8a8a;font-size:11px;white-space:nowrap;overflow:hidden;
  text-overflow:ellipsis;user-select:none;}
.pix-lyb-foot b{color:#c8c8c8;font-weight:600;}

/* ---- the big view ---- */
.pix-lyb-big{position:fixed;inset:0;z-index:10000;background:rgba(8,8,8,.88);display:flex;align-items:stretch;
  justify-content:center;padding:18px;box-sizing:border-box;font:12px "Segoe UI",system-ui,sans-serif;color:#ddd;outline:none;}
.pix-lyb-bpanel{flex:1 1 auto;max-width:1680px;display:flex;flex-direction:column;background:#1a1a1a;
  border:1px solid #3a3a3a;border-radius:10px;overflow:hidden;box-shadow:0 12px 40px rgba(0,0,0,.6);min-width:0;}
.pix-lyb-bhead{height:44px;display:flex;align-items:center;gap:12px;padding:0 12px 0 14px;background:#202020;
  border-bottom:1px solid #2c2c2c;flex:0 0 auto;}
.pix-lyb-btitle{font-weight:600;font-size:13px;white-space:nowrap;}
.pix-lyb-bhint{color:#8a8a8a;font-size:11.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0;}
.pix-lyb-done{height:28px;padding:0 18px;border-radius:5px;border:1px solid ${ACC};background:${ACC};color:#fff;
  font:12px "Segoe UI",sans-serif;cursor:pointer;flex:0 0 auto;}
.pix-lyb-done:hover{background:${ACC_HOVER};border-color:${ACC_HOVER};}
.pix-lyb-bmain{flex:1 1 auto;min-height:0;display:grid;grid-template-columns:52px minmax(0,1fr) 380px;}
.pix-lyb-brail{background:#1c1c1c;border-right:1px solid #2a2a2a;display:flex;flex-direction:column;align-items:center;
  gap:6px;padding:10px 0;}
.pix-lyb-brail .pix-lyb-btn{width:34px;height:32px;}
.pix-lyb-bcenter{min-width:0;min-height:0;padding:14px;display:flex;flex-direction:column;gap:8px;}
.pix-lyb-bcenter .pix-lyb-stage{flex:1 1 auto;min-height:0;}
.pix-lyb-bside{background:#1c1c1c;border-left:1px solid #2a2a2a;padding:12px;display:flex;flex-direction:column;
  gap:10px;min-height:0;overflow-y:auto;}
.pix-lyb-bside h4{margin:2px 0 0;font-size:11px;color:#999;text-transform:uppercase;letter-spacing:.6px;font-weight:600;}
.pix-lyb-bside .pix-lyb-list{max-height:none;flex:0 0 auto;gap:8px;}
/* a big-view row: the controls on one line, the description box under them */
.pix-lyb-row.big{flex-wrap:wrap;row-gap:6px;padding:6px;border:1px solid #2c2c2c;border-radius:6px;}
.pix-lyb-row.big.sel{border-color:rgba(255,255,255,.18);}
.pix-lyb-row.big .pix-lyb-words{flex:1 1 0;}
.pix-lyb-tag{flex:1 1 auto;min-width:0;color:#8a8a8a;font:11px Consolas,monospace;user-select:all;}
.pix-lyb-area{flex:0 0 100%;width:100%;min-height:44px;resize:none;overflow:hidden;line-height:1.4;padding:5px 7px;}
.pix-lyb-bside .pix-lyb-foot{white-space:normal;height:auto;line-height:1.45;}
@media (max-width:900px){ .pix-lyb-bmain{grid-template-columns:48px minmax(0,1fr) 290px;} }
`;
  document.head.appendChild(s);
}
