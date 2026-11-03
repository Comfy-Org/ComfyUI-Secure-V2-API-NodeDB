// H3 Timeline Pixaroma - the crop view: what the video keeps of a scene picture.
//
// Only the start picture and a "New look" become the video FRAME, so only they
// are cut: scaled to cover the video's shape, then the window at (x, y), where
// 0 = left / top and 1 = right / bottom of the room there is. The SAME rule as
// _h3_timeline_helpers.cut_box (and CSS background-position percentages), so the
// node's thumbnails, this view and the run agree. "Fit inside" keeps the whole
// picture with black bars instead.

import { passComfyShortcut } from "../shared/text_shortcuts.mjs";
import { pictureUrl } from "./pictures.mjs";

const BOX_MAX_W = 260;
const BOX_MAX_H = 400;

let current = null;

export function closeCrop() {
  const c = current;
  current = null;
  c?.close();
}

/** How a picture of pw x ph fills a video of vw x vh: the kept window in the
 *  picture's own fractions, or null when the shapes (nearly) match: a 720 x 1280
 *  picture in a 480 x 864 video loses 3 pixels a side, which is "nothing cut". */
export function keptWindow(pw, ph, vw, vh, x, y) {
  const a = pw / ph;
  const v = vw / vh;
  if (Math.abs(a - v) / v < 0.025) return null;
  if (a > v) {
    const w = v / a;
    return { x: (1 - w) * x, y: 0, w, h: 1, side: "the sides" };
  }
  const h = a / v;
  return { x: 0, y: (1 - h) * y, w: 1, h, side: "the top and bottom" };
}

/** Open the view for one scene. `onDone({x, y, fit})` when the user keeps it. */
export function openCrop({ title, picture, size, video, scene, onDone }) {
  closeCrop();
  const { w: pw, h: ph } = size;
  const vw = video.w;
  const vh = video.h;
  let x = scene.x;
  let y = scene.y;
  let fit = scene.fit;

  const s = Math.min(BOX_MAX_W / pw, BOX_MAX_H / ph);
  const bw = Math.round(pw * s);
  const bh = Math.round(ph * s);

  const modal = document.createElement("div");
  modal.className = "pix-h3t-modal";
  const dlg = document.createElement("div");
  dlg.className = "pix-h3t-dlg";
  dlg.setAttribute("role", "dialog");
  dlg.setAttribute("aria-label", title);
  dlg.innerHTML = `
    <div class="head"><b></b><span>what the video keeps</span><button class="x" aria-label="Close">×</button></div>
    <div class="body">
      <div class="picbox"><img alt="The whole picture"><div class="dim d1"></div><div class="dim d2"></div>
        <div class="frame"><span>drag to move</span></div></div>
      <div class="side">
        <div class="lbl vid"></div>
        <div class="result" role="img" aria-label="How the first video frame will look"></div>
        <div class="txt"></div>
        <div class="lbl">When the shapes differ</div>
        <div class="pix-h3t-seg"><button data-f="cut">Cut to fill</button><button data-f="fit">Fit inside (adds bars)</button></div>
        <div class="btns"><button class="btn ghost reset">Reset</button><button class="btn primary done">Done</button></div>
      </div>
    </div>`;
  modal.appendChild(dlg);
  dlg.querySelector(".head b").textContent = title;
  const box = dlg.querySelector(".picbox");
  box.style.width = bw + "px";
  box.style.height = bh + "px";
  const img = box.querySelector("img");
  img.src = pictureUrl(picture);
  const d1 = box.querySelector(".d1");
  const d2 = box.querySelector(".d2");
  const frame = box.querySelector(".frame");
  const result = dlg.querySelector(".result");
  const rw = 180;
  const rh = Math.round(rw * vh / vw);
  result.style.width = rw + "px";
  result.style.height = Math.min(320, rh) + "px";
  if (rh > 320) result.style.width = Math.round(320 * vw / vh) + "px";
  result.style.backgroundImage = `url("${pictureUrl(picture)}")`;
  dlg.querySelector(".vid").textContent = `The video frame, ${vw} x ${vh}`;
  const txt = dlg.querySelector(".txt");

  function paint() {
    const k = fit === "cut" ? keptWindow(pw, ph, vw, vh, x, y) : null;
    for (const b of dlg.querySelectorAll(".pix-h3t-seg button")) b.classList.toggle("on", b.dataset.f === fit);
    result.classList.toggle("fit", fit === "fit");
    result.style.backgroundPosition = `${x * 100}% ${y * 100}%`;
    if (!k) {
      frame.style.display = "none";
      d1.style.display = d2.style.display = "none";
      txt.textContent = fit === "fit"
        ? "The whole picture is kept, with black bars where the shapes differ."
        : "The picture has the same shape as the video: nothing is cut.";
      return;
    }
    frame.style.display = d1.style.display = d2.style.display = "";
    const L = k.x * bw, T = k.y * bh, W = k.w * bw, H = k.h * bh;
    Object.assign(frame.style, { left: L + "px", top: T + "px", width: W + "px", height: H + "px" });
    if (k.w < 1) {
      Object.assign(d1.style, { left: "0", top: "0", width: L + "px", height: bh + "px" });
      Object.assign(d2.style, { left: L + W + "px", top: "0", width: bw - L - W + "px", height: bh + "px" });
    } else {
      Object.assign(d1.style, { left: "0", top: "0", width: bw + "px", height: T + "px" });
      Object.assign(d2.style, { left: "0", top: T + H + "px", width: bw + "px", height: bh - T - H + "px" });
    }
    txt.textContent = `The video and the picture have different shapes, so ${k.side} are cut. Move the orange frame `
      + "to choose what stays.";
  }

  // drag the frame (grab point kept; one axis only, the one that has room)
  let drag = null;
  frame.addEventListener("pointerdown", (e) => {
    if (!(e.buttons & 1)) return;
    const k = keptWindow(pw, ph, vw, vh, x, y);
    if (!k) return;
    e.preventDefault();
    frame.setPointerCapture(e.pointerId);
    drag = { sx: e.clientX, sy: e.clientY, x0: x, y0: y, k };
  });
  frame.addEventListener("pointermove", (e) => {
    if (!drag || !(e.buttons & 1)) return;
    const { k } = drag;
    if (k.w < 1) x = Math.min(1, Math.max(0, drag.x0 + (e.clientX - drag.sx) / (bw * (1 - k.w))));
    else y = Math.min(1, Math.max(0, drag.y0 + (e.clientY - drag.sy) / (bh * (1 - k.h))));
    paint();
  });
  const end = () => { drag = null; };
  frame.addEventListener("pointerup", end);
  frame.addEventListener("pointercancel", end);

  for (const b of dlg.querySelectorAll(".pix-h3t-seg button")) b.onclick = () => { fit = b.dataset.f; paint(); };
  dlg.querySelector(".reset").onclick = () => { x = 0.5; y = 0.5; fit = "cut"; paint(); };
  const done = () => { closeCrop(); onDone({ x, y, fit }); };
  dlg.querySelector(".done").onclick = done;
  dlg.querySelector(".x").onclick = () => closeCrop();
  modal.addEventListener("pointerdown", (e) => { if (e.target === modal) closeCrop(); });
  // The dialog is modal: ComfyUI's keys (Ctrl+Z would rebuild the node under it) stay out.
  const onKey = (e) => {
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); closeCrop(); return; }
    if (e.key === "Enter") { e.preventDefault(); e.stopPropagation(); done(); return; }
    if (passComfyShortcut(e, dlg)) return;
    e.stopPropagation();
  };
  window.addEventListener("keydown", onKey, true);
  document.body.appendChild(modal);
  current = {
    close() {
      window.removeEventListener("keydown", onKey, true);
      modal.remove();
    },
  };
  paint();
  dlg.querySelector(".done").focus({ preventScroll: true });
}
