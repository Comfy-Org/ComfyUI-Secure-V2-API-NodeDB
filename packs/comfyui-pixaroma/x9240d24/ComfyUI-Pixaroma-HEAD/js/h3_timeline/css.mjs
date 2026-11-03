// H3 Timeline Pixaroma - one stylesheet for the node face, the picture list and
// the crop view.
//
// The CSS below is a JS template literal: NO backticks and NO double-slash
// comments inside it (convention #35). Use /* */ comments only, and run
// node --check after editing.

import { ACC, ACC_HOVER } from "../shared/node_settings.mjs";

const CSS_ID = "pix-h3t-css";

export function injectCSS() {
  if (document.getElementById(CSS_ID)) return;
  const s = document.createElement("style");
  s.id = CSS_ID;
  s.textContent = `
/* the DOM widget root fills its row; the layout lives on an INNER absolute layer (nodes2-preview-fill #4, #37) */
.pix-h3t-root{position:relative;flex:1 1 0;min-height:0;box-sizing:border-box;}
.pix-h3t-inner{position:absolute;inset:0;display:flex;flex-direction:column;gap:8px;padding:6px 8px 8px;
  box-sizing:border-box;overflow:hidden;font:11px "Segoe UI",system-ui,sans-serif;color:#ddd;}
.pix-h3t-inner > *{flex-shrink:0;}

/* time bar: one block per scene, as wide as its length, tiled with its picture */
.pix-h3t-bar{display:flex;flex-direction:column;gap:4px;padding:8px;border-radius:6px;background:rgba(0,0,0,.25);}
.pix-h3t-strip{position:relative;height:64px;}
.pix-h3t-block{position:absolute;top:0;bottom:0;box-sizing:border-box;border-radius:4px;overflow:hidden;
  border:1px solid rgba(255,255,255,.18);cursor:pointer;background:rgba(255,255,255,.04);}
.pix-h3t-block.carried{border-style:dashed;border-color:rgba(255,255,255,.3);}
.pix-h3t-block.sel{border:2px solid ${ACC};}
.pix-h3t-tiles{position:absolute;inset:0;display:flex;gap:1px;}
.pix-h3t-tile{flex:0 0 auto;height:100%;background-repeat:no-repeat;background-color:#111;}
.pix-h3t-block.carried .pix-h3t-tiles{opacity:.38;}
/* a scene that starts with a clean cut: a hard white left edge; a kept scene says so in its badge */
.pix-h3t-block.cutin{border-left:3px solid #fff;}
.pix-h3t-block.kept .pix-h3t-badge::after{content:" · Keep";}
.pix-h3t-badge{position:absolute;left:4px;top:4px;padding:1px 6px;border-radius:3px;background:rgba(0,0,0,.72);
  color:#fff;font-size:11px;font-weight:600;white-space:nowrap;}
.pix-h3t-block.sel .pix-h3t-badge{background:${ACC};}
.pix-h3t-tag{position:absolute;left:4px;bottom:4px;padding:1px 5px;border-radius:3px;background:rgba(0,0,0,.72);
  color:#ddd;font-size:10px;white-space:nowrap;}
.pix-h3t-ruler{position:relative;height:13px;color:#9a9a9a;font-size:10px;}
.pix-h3t-ruler span{position:absolute;top:0;transform:translateX(-50%);white-space:nowrap;}
.pix-h3t-ruler span.first{transform:none;}
.pix-h3t-ruler span.last{transform:translateX(-100%);}
.pix-h3t-lane{display:flex;align-items:center;gap:6px;min-height:16px;color:#bbb;font-size:11px;}
.pix-h3t-lane .wave{flex:1 1 auto;height:12px;border-radius:3px;
  background:repeating-linear-gradient(90deg,rgba(79,195,247,.5) 0 2px,rgba(79,195,247,.14) 2px 4px);}
.pix-h3t-lane .wave.off{background:repeating-linear-gradient(90deg,rgba(255,255,255,.14) 0 2px,transparent 2px 4px);}
.pix-h3t-lane .note{flex:0 1 auto;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.pix-h3t-lane .note.ok{color:#9fd9b4;}
.pix-h3t-lane .note.warn{color:#ffd27a;}

/* the scene list: as tall as its rows, never taller (Add scene sits right under the last row), scrolls when the
   node is shorter (convention #39 B) */
.pix-h3t-list{flex:0 1 auto !important;min-height:0;overflow-y:auto;display:flex;flex-direction:column;gap:8px;
  padding-right:2px;}
.pix-h3t-row{display:flex;gap:10px;padding:8px;border-radius:6px;background:rgba(255,255,255,.05);
  border:1px solid rgba(255,255,255,.15);flex-shrink:0;}
.pix-h3t-row.sel{border:2px solid ${ACC};padding:7px;background:color-mix(in srgb, ${ACC} 10%, transparent);}
.pix-h3t-row.drop{outline:2px dashed ${ACC};outline-offset:-2px;}
.pix-h3t-piccol{width:62px;flex:none;display:flex;flex-direction:column;align-items:center;gap:4px;}
.pix-h3t-pic{width:60px;height:106px;padding:0;border-radius:4px;border:1px solid rgba(255,255,255,.18);
  background:#111 center / cover no-repeat;cursor:pointer;box-sizing:border-box;}
.pix-h3t-pic:hover{border-color:${ACC};}
.pix-h3t-pic.fit{background-size:contain;}
.pix-h3t-pic.empty{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;
  background:transparent;border:1px dashed #555;color:#9a9a9a;font:10px "Segoe UI",sans-serif;}
.pix-h3t-pic.empty:hover{border-color:${ACC};color:#ddd;}
.pix-h3t-cap{max-width:62px;padding:0;border:none;background:none;color:#9a9a9a;font:10px "Segoe UI",sans-serif;
  text-align:center;line-height:1.25;cursor:default;white-space:pre-line;}
.pix-h3t-cap.ok{color:#9fd9b4;}
.pix-h3t-cap.cut{color:#ffd27a;cursor:pointer;text-decoration:underline;text-underline-offset:2px;}
.pix-h3t-cap.link{cursor:pointer;text-decoration:underline;text-underline-offset:2px;}
.pix-h3t-main{flex:1 1 auto;min-width:0;display:flex;flex-direction:column;gap:6px;}
.pix-h3t-top{display:flex;align-items:center;gap:6px;flex-wrap:wrap;min-height:24px;}
.pix-h3t-num{width:20px;height:20px;flex:none;display:flex;align-items:center;justify-content:center;border-radius:4px;
  background:#5a5a5a;color:#fff;font-size:11px;font-weight:600;}
.pix-h3t-row.sel .pix-h3t-num{background:${ACC};}
.pix-h3t-len{display:inline-flex;align-items:center;gap:2px;}
.pix-h3t-step{width:24px;height:24px;padding:0;background:#1d1d1d;border:1px solid #444;border-radius:4px;color:#aaa;
  font:13px "Segoe UI",sans-serif;cursor:pointer;user-select:none;}
.pix-h3t-step:hover{border-color:${ACC};color:#ddd;}
.pix-h3t-lenin{width:56px;height:24px;box-sizing:border-box;padding:2px 4px;text-align:center;background:#1d1d1d;
  border:1px solid #444;border-radius:4px;color:#e0e0e0;font:12px monospace;outline:none;}
.pix-h3t-lenin:focus{border-color:${ACC};}
.pix-h3t-seg{display:inline-flex;padding:2px;gap:2px;border-radius:4px;background:rgba(0,0,0,.25);}
.pix-h3t-seg button{height:20px;padding:0 8px;border:none;border-radius:3px;background:transparent;color:#aaa;
  font:10px "Segoe UI",sans-serif;cursor:pointer;user-select:none;}
.pix-h3t-seg button:hover{background:rgba(255,255,255,.18);color:#ddd;}
.pix-h3t-seg button.on{background:${ACC};color:#fff;}
.pix-h3t-keep{height:24px;padding:0 10px;box-sizing:border-box;background:#1d1d1d;border:1px solid #444;
  border-radius:4px;color:#aaa;font:10px "Segoe UI",sans-serif;cursor:pointer;user-select:none;}
.pix-h3t-keep:hover{border-color:${ACC};color:#ddd;}
.pix-h3t-keep.on{background:${ACC};border-color:${ACC};color:#fff;}
.pix-h3t-chip{height:22px;display:inline-flex;align-items:center;padding:0 8px;border-radius:4px;
  background:rgba(255,255,255,.08);color:#ccc;font-size:10px;white-space:nowrap;}
.pix-h3t-tools{display:inline-flex;gap:2px;margin-left:auto;flex:none;}
.pix-h3t-icon{width:24px;height:24px;padding:0;display:flex;align-items:center;justify-content:center;border:none;
  border-radius:4px;background:transparent;color:#9a9a9a;cursor:pointer;}
.pix-h3t-icon:hover{background:rgba(255,255,255,.08);color:#ddd;}
.pix-h3t-icon:disabled{opacity:.35;cursor:default;background:transparent;color:#9a9a9a;}
.pix-h3t-words{width:100%;height:58px;min-height:40px;resize:vertical;box-sizing:border-box;padding:6px 8px;
  background:#1d1d1d;border:1px solid #333;border-radius:4px;color:#e0e0e0;font:12px monospace;line-height:1.35;
  outline:none;}
.pix-h3t-words:focus{border-color:${ACC};}
.pix-h3t-words::placeholder{color:#777;}

/* footer */
.pix-h3t-foot{display:flex;align-items:center;gap:10px;flex-wrap:wrap;}
.pix-h3t-add{height:28px;min-width:120px;padding:0 12px;border-radius:4px;border:1px solid ${ACC};background:${ACC};
  color:#fff;font:11px "Segoe UI",sans-serif;cursor:pointer;user-select:none;}
.pix-h3t-add:hover{background:${ACC_HOVER};border-color:${ACC_HOVER};}
.pix-h3t-add:disabled{opacity:.45;cursor:default;}
.pix-h3t-total{flex:1 1 auto;color:#ccc;font-size:11px;}
.pix-h3t-win{display:inline-flex;align-items:center;gap:6px;flex:none;}
.pix-h3t-winlbl{color:#aaa;font-size:11px;}

/* the picker is Load Image's; its Upload button is the primary action. Only our own class here (one prefix per
   node, convention #38), doubled so it outranks Load Image's button rule whichever stylesheet loads last */
.pix-h3t-upload.pix-h3t-upload{background:${ACC};border-color:${ACC};color:#fff;}
.pix-h3t-upload.pix-h3t-upload:hover{background:${ACC_HOVER};border-color:${ACC_HOVER};color:#fff;}

/* the crop view (D2) */
.pix-h3t-modal{position:fixed;inset:0;z-index:10001;display:flex;align-items:center;justify-content:center;
  background:rgba(0,0,0,.55);font:12px "Segoe UI",system-ui,sans-serif;color:#e0e0e0;}
.pix-h3t-dlg{width:min(640px,calc(100vw - 32px));max-height:calc(100vh - 32px);overflow:auto;box-sizing:border-box;
  padding:16px;display:flex;flex-direction:column;gap:14px;background:#181818;border:1px solid #555;border-radius:6px;
  box-shadow:0 18px 50px rgba(0,0,0,.6);}
.pix-h3t-dlg .head{display:flex;align-items:center;gap:8px;}
.pix-h3t-dlg .head b{font-size:13px;color:#fff;}
.pix-h3t-dlg .head span{color:#aaa;font-size:11px;}
.pix-h3t-dlg .body{display:flex;gap:20px;align-items:flex-start;flex-wrap:wrap;}
.pix-h3t-dlg .picbox{position:relative;flex:none;border-radius:4px;overflow:hidden;touch-action:none;user-select:none;}
.pix-h3t-dlg .picbox img{display:block;width:100%;height:100%;pointer-events:none;}
.pix-h3t-dlg .dim{position:absolute;background:rgba(0,0,0,.62);pointer-events:none;}
.pix-h3t-dlg .frame{position:absolute;box-sizing:border-box;border:2px solid ${ACC};cursor:move;}
.pix-h3t-dlg .frame span{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);padding:3px 8px;
  border-radius:3px;background:rgba(0,0,0,.7);color:#fff;font-size:11px;white-space:nowrap;pointer-events:none;}
.pix-h3t-dlg .side{flex:1 1 200px;min-width:200px;display:flex;flex-direction:column;gap:12px;}
.pix-h3t-dlg .lbl{color:#aaa;font-size:11px;}
.pix-h3t-dlg .result{border-radius:4px;background:#111 center / cover no-repeat;}
.pix-h3t-dlg .result.fit{background-size:contain;}
.pix-h3t-dlg .txt{color:#ccc;font-size:11px;line-height:1.5;}
.pix-h3t-dlg .btns{display:flex;gap:8px;justify-content:flex-end;}
.pix-h3t-dlg .btn{height:28px;min-width:86px;padding:0 10px;border-radius:4px;font:11px "Segoe UI",sans-serif;cursor:pointer;}
.pix-h3t-dlg .btn.ghost{border:none;background:transparent;color:#9a9a9a;}
.pix-h3t-dlg .btn.ghost:hover{color:#ddd;}
.pix-h3t-dlg .btn.primary{border:1px solid ${ACC};background:${ACC};color:#fff;}
.pix-h3t-dlg .btn.primary:hover{background:${ACC_HOVER};border-color:${ACC_HOVER};}
.pix-h3t-dlg .x{margin-left:auto;width:24px;height:24px;border:none;background:none;color:#aaa;font-size:16px;cursor:pointer;}
`;
  document.head.appendChild(s);
}
