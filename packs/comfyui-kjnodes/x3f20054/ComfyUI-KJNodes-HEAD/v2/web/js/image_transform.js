import { comfy } from '/comfy/api/v2.js';
import { addWheelPassthrough, rectHitTest, cursorForBboxMode } from './utility.js';

const BBOX_PALETTE = ["#46b4e6", "#e68246", "#82e646", "#e646b4", "#e6e646", "#46e6c8"];
const MAX_CANVAS_W = 1024, MAX_CANVAS_H = 768;
const BBOX_COLORS = BBOX_PALETTE.map((hex) => {
  const r = parseInt(hex.slice(1, 3), 16), g = parseInt(hex.slice(3, 5), 16), b = parseInt(hex.slice(5, 7), 16);
  return { rgb: `rgb(${r}, ${g}, ${b})`, gridActive: `rgba(${r}, ${g}, ${b}, 0.35)`,
    gridInactive: `rgba(${r}, ${g}, ${b}, 0.3)`, tint: `rgba(${r}, ${g}, ${b}, 0.2)` };
});

function getBboxColor(index, active) {
  const c = BBOX_COLORS[index % BBOX_COLORS.length];
  return { border: c.rgb, fill: c.rgb, handle: c.rgb, gridColor: active ? c.gridActive : c.gridInactive, tint: c.tint };
}

function clampToMaxCanvas(w, h) {
  if (w > MAX_CANVAS_W || h > MAX_CANVAS_H) {
    const s = Math.min(MAX_CANVAS_W / w, MAX_CANVAS_H / h);
    return [Math.round(w * s), Math.round(h * s)];
  }
  return [w, h];
}

function roundDown(val, divBy) {
  return divBy > 1 ? val - (val % divBy) : val;
}

// Per-node editor state. Handles hold no arbitrary properties, so everything the
// original stashed on the node lives here, and the entry is dropped in onRemoved.
const editors = new Map();

comfy.defs.extend("ImageTransformKJ", (b) => {

    b.onCreated((node) => {
      const state = {};
      const _unsubs = [];
      editors.set(node.id, state);

      const findW = (n) => node.widgets.get(n);
      const bboxWidget = findW("bboxes"), twWidget = findW("target_width"), thWidget = findW("target_height");
      const kpWidget = findW("keep_proportion"), divWidget = findW("divisible_by");
      const epWidget = findW("extra_padding"), icWidget = findW("invert_crop");
      bboxWidget.setHidden(true);

      function _getSubWidget(name) {
        return node.widgets.get(name) || null;
      }

      const _tmpCanvas = document.createElement("canvas"), _tmpCtx = _tmpCanvas.getContext("2d");
      const _mirrorCanvas = document.createElement("canvas"), _mirrorCtx = _mirrorCanvas.getContext("2d");
      const _rotCanvas = document.createElement("canvas"), _rotCtx = _rotCanvas.getContext("2d");
      let _rotCacheKey = "";
      function getRotatedPreview() {
        if (!state._previewImg) return null;
        const nw = state._previewImg.naturalWidth;
        const nh = state._previewImg.naturalHeight;
        const { w: effW, h: effH } = getEffectiveImageDims(true);
        // Scale to reasonable preview size
        let [rw, rh] = clampToMaxCanvas(effW, effH);
        const key = `${state._previewImg.src}|${state._rotation}|${rw}|${rh}`;
        if (_rotCacheKey === key) return _rotCanvas;
        _rotCanvas.width = rw;
        _rotCanvas.height = rh;
        _rotCtx.clearRect(0, 0, rw, rh);
        if (state._rotation === 0) {
          _rotCtx.drawImage(state._previewImg, 0, 0, rw, rh);
        } else {
          const rad = Math.abs(rotRad());
          const rotW = Math.abs(nw * Math.cos(rad)) + Math.abs(nh * Math.sin(rad));
          const rotH = Math.abs(nw * Math.sin(rad)) + Math.abs(nh * Math.cos(rad));
          const fitScale = Math.min(rw / rotW, rh / rotH);
          _rotCtx.translate(rw / 2, rh / 2);
          _rotCtx.rotate(rotRad());
          _rotCtx.drawImage(state._previewImg, -(nw * fitScale) / 2, -(nh * fitScale) / 2, nw * fitScale, nh * fitScale);
          _rotCtx.setTransform(1, 0, 0, 1, 0, 0);
        }
        _rotCacheKey = key;
        return _rotCanvas;
      }

      let _frameEp = { top: 0, bottom: 0, left: 0, right: 0, mode: "disabled", color: null, edgeMode: "clamp" };
      let _framePadXY = { x: 0.5, y: 0.5 };

      const wrapper = document.createElement("div");
      wrapper.style.cssText = "display:flex;flex-direction:column;overflow:hidden;position:relative;pointer-events:auto;";
      const canvasEl = document.createElement("canvas");
      const canvasCtx = canvasEl.getContext("2d");
      canvasEl.style.cssText = "cursor:crosshair;display:block;width:100%;height:auto;";
      addWheelPassthrough(wrapper);

      // Inject slider thumb styles once
      if (!document.getElementById("kjcrop-slider-style")) {
        const style = document.createElement("style");
        style.id = "kjcrop-slider-style";
        style.textContent = `
          .kjcrop-slider { -webkit-appearance: none; appearance: none; background: #444; border-radius: 4px; outline: none; }
          .kjcrop-slider::-webkit-slider-thumb { -webkit-appearance: none; width: 8px; height: 18px; background: #46b4e6; border-radius: 4px; cursor: pointer; border: none; }
          .kjcrop-slider::-moz-range-thumb { width: 8px; height: 18px; background: #46b4e6; border-radius: 4px; cursor: pointer; border: none; }
          .kjcrop-btn { background: #333; border: 1px solid #555; border-radius: 4px; color: #bbb; font: 11px sans-serif; cursor: pointer; padding: 2px 8px; line-height: 16px; white-space: nowrap; flex-shrink: 0; transition: border-color 0.15s, color 0.15s, background 0.15s; text-align: center; }
          .kjcrop-btn:hover { border-color: #46b4e6; color: #fff; background: #3a3a3a; }
          .kjcrop-btn.active { border-color: #46b4e6; color: #46b4e6; background: #2a3a42; }
        `;
        document.head.appendChild(style);
      }
      // Grid size slider overlay (purely visual aid, not serialized)
      const gridBar = document.createElement("div");
      gridBar.style.cssText = "display:flex;align-items:center;gap:6px;padding:3px 6px;margin-bottom:4px;font:11px sans-serif;color:#aaa;user-select:none;box-sizing:border-box;width:100%;flex:0 0 auto;";
      const gridLabel = document.createElement("span");
      gridLabel.textContent = "Grid: off";
      gridLabel.style.cssText = "min-width:62px;text-align:right;";
      const gridSlider = document.createElement("input");
      gridSlider.type = "range";
      gridSlider.min = "0";
      gridSlider.max = "256";
      gridSlider.step = "1";
      gridSlider.value = node.getProperty("gridSize") ?? "0";
      gridSlider.className = "kjcrop-slider";
      gridSlider.style.cssText = "flex:1;height:8px;cursor:pointer;";
      function updateGridLabel() {
        const v = parseInt(gridSlider.value);
        gridLabel.textContent = v > 0 ? `Grid: ${v}px` : "Grid: off";
      }
      updateGridLabel();
      let _gridStops = null;
      function getGridStops() {
        if (!state._previewImg) return null;
        const tw = state._previewImg.naturalWidth;
        const th = state._previewImg.naturalHeight;
        const max = parseInt(gridSlider.max);
        const set = new Set([0]);
        for (let n = 1; n <= Math.max(tw, th); n++) {
          const gw = tw / n, gh = th / n;
          if (gw >= 2 && gw <= max) set.add(Math.round(gw * 10) / 10);
          if (gh >= 2 && gh <= max) set.add(Math.round(gh * 10) / 10);
          if (gw < 2 && gh < 2) break;
        }
        return [...set].sort((a, b) => a - b);
      }
      function invalidateGridStops() { _gridStops = null; }
      gridSlider.addEventListener("input", () => {
        let v = parseInt(gridSlider.value);
        // Snap to divisors of the longer dimension for whole-cell grid
        if (v > 0 && state._previewImg) {
          if (!_gridStops) _gridStops = getGridStops();
          if (_gridStops) {
            let best = 0, bestDist = Infinity;
            for (const s of _gridStops) {
              const d = Math.abs(s - v);
              if (d < bestDist) { bestDist = d; best = s; }
            }
            v = best;
          }
        }
        gridSlider.value = Math.round(v);
        node.setProperty("gridSize", Math.round(v));
        updateGridLabel();
        drawCanvas();
      });
      // Prevent drag events from propagating to the LiteGraph canvas,
      // but only when not actively dragging a bbox handle
      for (const evt of ["mousedown", "mousemove", "mouseup"]) {
        gridSlider.addEventListener(evt, (e) => {
          if (!state._drawing) e.stopPropagation();
        });
      }
      // Toggle button to disable image preview (draw bboxes on blank canvas)
      const previewBtn = document.createElement("button");
      previewBtn.title = "Auto: canvas sized to input image. Manual: canvas sized to target dimensions.";
      previewBtn.className = "kjcrop-btn";
      previewBtn.style.width = "56px";
      if (node.getProperty("previewEnabled") === undefined) node.setProperty("previewEnabled", true);
      state._previewEnabled = node.getProperty("previewEnabled");

      function updatePreviewBtn() {
        previewBtn.textContent = state._previewEnabled ? "Auto" : "Manual";
        previewBtn.classList.toggle("active", !state._previewEnabled);
      }
      updatePreviewBtn();

      previewBtn.addEventListener("click", () => {
        state._previewEnabled = !state._previewEnabled;
        node.setProperty("previewEnabled", state._previewEnabled);
        updatePreviewBtn();
        if (!state._previewEnabled) {
          updateCanvasFromTargetDims();
        } else if (state._previewImg) {
          // Restore canvas to image dimensions
          const [cw, ch] = clampToMaxCanvas(state._previewImg.naturalWidth, state._previewImg.naturalHeight);
          setCanvasSize(cw, ch);
        }
        drawCanvas();
      });
      previewBtn.addEventListener("mousedown", (e) => e.stopPropagation());

      const colorSwatch = document.createElement("div");
      const colorInput = document.createElement("input");
      colorInput.type = "color";
      colorInput.value = node.getProperty("fillColor") || "#000000";
      colorInput.style.cssText = "position:absolute;opacity:0;width:0;height:0;pointer-events:none;";
      colorSwatch.style.cssText = "width:18px;height:18px;border:1px solid #666;border-radius:3px;cursor:pointer;flex-shrink:0;background:" + (node.getProperty("fillColor") || "#000000") + ";";
      colorSwatch.title = "Fill color (used by pad, invert crop, rotation)";
      colorSwatch.appendChild(colorInput);
      colorSwatch.addEventListener("click", () => colorInput.click());
      colorSwatch.addEventListener("mousedown", (e) => e.stopPropagation());
      colorInput.addEventListener("input", () => {
        node.setProperty("fillColor", colorInput.value); colorSwatch.style.background = colorInput.value;
        updateBboxWidgets(); drawCanvas();
      });

      function getEffectiveImageDims(expand = true) {
        const w = state._previewImg.naturalWidth, h = state._previewImg.naturalHeight;
        if (state._rotation === 0 || !expand) return { w, h };
        const rad = Math.abs(rotRad());
        const cosR = Math.cos(rad), sinR = Math.sin(rad);
        return { w: Math.round(Math.abs(w * cosR) + Math.abs(h * sinR)),
          h: Math.round(Math.abs(w * sinR) + Math.abs(h * cosR)) };
      }

      function renderReplicateRotated(destW, destH) {
        const img = state._previewImg, nw = img.naturalWidth, nh = img.naturalHeight;
        const pad = Math.max(nw, nh), pw = nw + pad * 2, ph = nh + pad * 2;
        // Build replicate-padded image on _mirrorCanvas
        _mirrorCanvas.width = pw; _mirrorCanvas.height = ph;
        _mirrorCtx.drawImage(img, pad, pad, nw, nh);
        // Edges (top, bottom, left, right)
        _mirrorCtx.drawImage(img, 0, 0, nw, 1, pad, 0, nw, pad);
        _mirrorCtx.drawImage(img, 0, nh - 1, nw, 1, pad, pad + nh, nw, pad);
        _mirrorCtx.drawImage(img, 0, 0, 1, nh, 0, pad, pad, nh);
        _mirrorCtx.drawImage(img, nw - 1, 0, 1, nh, pad + nw, pad, pad, nh);
        // Corners (TL, TR, BL, BR)
        _mirrorCtx.drawImage(img, 0, 0, 1, 1, 0, 0, pad, pad);
        _mirrorCtx.drawImage(img, nw - 1, 0, 1, 1, pad + nw, 0, pad, pad);
        _mirrorCtx.drawImage(img, 0, nh - 1, 1, 1, 0, pad + nh, pad, pad);
        _mirrorCtx.drawImage(img, nw - 1, nh - 1, 1, 1, pad + nw, pad + nh, pad, pad);
        // Rotate padded image, crop to original size, scale to dest
        _tmpCanvas.width = destW; _tmpCanvas.height = destH;
        _tmpCtx.save();
        _tmpCtx.scale(destW / nw, destH / nh);
        _tmpCtx.translate(nw / 2, nh / 2);
        _tmpCtx.rotate(rotRad());
        _tmpCtx.drawImage(_mirrorCanvas, -(pw / 2), -(ph / 2));
        _tmpCtx.restore();
      }

      // Resize node to fit the current canvas/image. If onlyGrow is true,
      // the node will only get larger, never shrink (preserves user resize).
      // If false, the node is set to the exact size needed.
      function fitNodeToImage(onlyGrow) {
        if (!state._previewEnabled) {
          // Manual mode: only grow to fit current canvas, never change width
          if (onlyGrow && canvasEl.width > 0 && canvasEl.height > 0) {
            _resizing = true;
            const displayedH = Math.round(canvasEl.height * ((node.getSize().width - 30) / canvasEl.width));
            cropWidget.setHeight(displayedH + GRID_BAR_HEIGHT);
            _resizing = false;
          }
          return;
        }
        if (!state._previewImg) return;
        _resizing = true;
        const { w: effW, h: effH } = getEffectiveImageDims(true);
        const ar = effH / effW;
        const nodeW = onlyGrow ? node.getSize().width : canvasEl.width + 30;
        const canvasDisplayH = Math.round((nodeW - 30) * ar);
        cropWidget.setHeight(canvasDisplayH + GRID_BAR_HEIGHT);
        const newW = onlyGrow ? Math.max(node.getSize().width, nodeW) : nodeW;
        if (newW !== node.getSize().width) {
          node.setSize({ width: newW, height: node.getSize().height });
        }
        _resizing = false;
        // Force reflow and redraw so the layout updates immediately
        void canvasEl.offsetHeight;
        requestAnimationFrame(() => {
          drawCanvas();
        });
      }

      function resetRotation() {
        if (state._rotation === 0) return;
        state._rotation = 0;
        node.setProperty("rotation", 0);
        restoreCanvasToImage();
        fitNodeToImage(false);
        updateBboxWidgets();
        drawCanvas();
      }

      const rotateBtn = document.createElement("button");
      rotateBtn.title = "Toggle rotation cross (drag to rotate image)";
      rotateBtn.className = "kjcrop-btn";
      if (node.getProperty("showRotationCross") === undefined) node.setProperty("showRotationCross", false);
      state._showRotationCross = node.getProperty("showRotationCross");

      function updateRotateBtn() {
        rotateBtn.textContent = "Rotate";
        rotateBtn.classList.toggle("active", state._showRotationCross);
      }
      updateRotateBtn();

      rotateBtn.addEventListener("click", () => {
        state._showRotationCross = !state._showRotationCross;
        node.setProperty("showRotationCross", state._showRotationCross);
        updateRotateBtn();
        drawCanvas();
      });
      rotateBtn.addEventListener("mousedown", (e) => e.stopPropagation());
      rotateBtn.addEventListener("contextmenu", (e) => {
        e.preventDefault();
        resetRotation();
      });

      const gridColorInput = document.createElement("input");
      gridColorInput.type = "color";
      gridColorInput.value = node.getProperty("gridColor") || "#ffffff";
      gridColorInput.style.cssText = "position:absolute;opacity:0;width:0;height:0;pointer-events:none;";
      const gridColorSwatch = document.createElement("div");
      gridColorSwatch.style.cssText = "width:18px;height:18px;border:1px solid #666;border-radius:3px;cursor:pointer;flex-shrink:0;background:" + (node.getProperty("gridColor") || "#ffffff") + ";";
      gridColorSwatch.title = "Grid color";
      gridColorSwatch.appendChild(gridColorInput);
      gridColorSwatch.addEventListener("click", () => gridColorInput.click());
      gridColorSwatch.addEventListener("mousedown", (e) => e.stopPropagation());
      let _gridColorRGB = null;
      function getGridColorRGB() {
        const gc = node.getProperty("gridColor") || "#ffffff";
        if (!_gridColorRGB || _gridColorRGB.hex !== gc) {
          _gridColorRGB = { hex: gc, r: parseInt(gc.slice(1, 3), 16), g: parseInt(gc.slice(3, 5), 16), b: parseInt(gc.slice(5, 7), 16) };
        }
        return _gridColorRGB;
      }
      gridColorInput.addEventListener("input", () => {
        node.setProperty("gridColor", gridColorInput.value); gridColorSwatch.style.background = gridColorInput.value;
        _gridColorRGB = null;
        drawCanvas();
      });

      for (const el of [previewBtn, rotateBtn, colorSwatch, gridLabel, gridColorSwatch, gridSlider]) gridBar.appendChild(el);
      wrapper.appendChild(gridBar); wrapper.appendChild(canvasEl);

      const GRID_BAR_HEIGHT = 46;

      const cropWidget = node.widgets.mount({
        name: "crop_preview",
        render: (container) => container.appendChild(wrapper),
        destroy: () => { for (const off of _unsubs) off(); _unsubs.length = 0; },
      });

      // The old code sized the node by hand: node height = the widget's measured y
      // offset (cropEditor.last_y) + the height it wanted + a 20px margin. That
      // offset is the renderer's layout, and reading it is what setHeight removes
      // the need for — state the row's height and let the node fit around it, which
      // is correct under both renderers and needs no margin constant.
      //
      // LIMITATION: node height is now derived rather than user-set, so the
      // "onlyGrow, never shrink" arm no longer preserves a height the user dragged
      // taller than the content. Width still does.
      node.setSizeConstraints({ autoHeight: true });
      cropWidget.setHeight(300 + GRID_BAR_HEIGHT);

      // Set default width wider than the renderer's default — deferred so onConfigured can set the flag first
      setTimeout(() => {
        if (!state._cropConfigured) node.setSize({ width: 450, height: node.getSize().height });
      }, 0);

      Object.assign(state, { _previewImg: null, _bboxes: [], _activeIdx: -1,
        _drawing: false, _dragMode: null, _dragStart: null, _bboxAtDragStart: null,
        _rotation: node.getProperty("rotation") || 0 });

      for (const w of [twWidget, thWidget, kpWidget, divWidget, epWidget, icWidget]) {
        if (!w) continue;
        _unsubs.push(w.on("change", () => {
          updateCanvasFromTargetDims();
          drawCanvas();
          fitNodeToCanvas();
          fitNodeToImage(true);
          if (w === kpWidget || w === icWidget || w === epWidget) {
            // Restore values with increasing delays to catch ComfyUI's own default-setting
            const restoreSaved = () => {
              hookSubWidgets();
              // setValue notifies listeners where the old direct `.value` write did not.
              _suppressSubCallbacks = true;
              if (w === epWidget && state._savedEpValues && epWidget.getValue() !== "disabled") {
                for (const [n, v] of Object.entries(state._savedEpValues)) {
                  const sw = _getSubWidget(`extra_padding.${n}`);
                  if (sw) sw.setValue(v);
                }
              } else if (w === kpWidget && state._savedKpValues) {
                for (const [n, v] of Object.entries(state._savedKpValues)) {
                  const sw = _getSubWidget(`keep_proportion.${n}`);
                  if (sw) sw.setValue(v);
                }
              }
              _suppressSubCallbacks = false;
              drawCanvas();
              fitNodeToCanvas();
              fitNodeToImage(true);
            };
            for (const delay of [50, 100, 200, 300, 500, 1000]) {
              setTimeout(restoreSaved, delay);
            }
          }
        }));
      }

      // epWidget is already hooked with the other top-level widgets above.
      const _hookedSubs = new Set(["extra_padding"]);
      const hookSubWidgets = () => {
        for (const subName of ["keep_proportion.edge_mode", "keep_proportion.pad_x", "keep_proportion.pad_y", "keep_proportion.width_mult", "keep_proportion.height_mult", "extra_padding.pad_top", "extra_padding.pad_bottom", "extra_padding.pad_left", "extra_padding.pad_right", "extra_padding.edge_mode", ]) {
          const sw = _getSubWidget(subName);
          if (sw && !_hookedSubs.has(subName)) {
            _hookedSubs.add(subName);
            // Restore saved values from mode switch
            const shortName = subName.split(".")[1];
            if (subName.startsWith("extra_padding.") && state._savedEpValues && shortName in state._savedEpValues) {
              sw.setValue(state._savedEpValues[shortName]);
            } else if (subName.startsWith("keep_proportion.") && state._savedKpValues && shortName in state._savedKpValues) {
              sw.setValue(state._savedKpValues[shortName]);
            }
            // Listen — save values on change so they persist across mode switches.
            // Listeners are additive, so no callback is captured or chained.
            _unsubs.push(sw.on("change", () => {
              if (_suppressSubCallbacks) return;
              if (subName.startsWith("extra_padding.")) state._savedEpValues[shortName] = sw.getValue();
              else if (subName.startsWith("keep_proportion.")) state._savedKpValues[shortName] = sw.getValue();
              drawCanvas();
            }));
          }
        }
        // The removed draw callback polled these every repaint to notice a
        // change; a change listener reports it directly.
        for (const name of _snapshotNames) {
          if (_hookedSubs.has(name)) continue;
          const w = _getSubWidget(name);
          if (!w) continue;
          _hookedSubs.add(name);
          _unsubs.push(w.on("change", drawCanvas));
        }
      };
      for (const delay of [50, 150, 300, 500]) {
        setTimeout(hookSubWidgets, delay);
      }

      const _snapshotNames = [
        "extra_padding", "extra_padding.pad_top", "extra_padding.pad_bottom",
        "extra_padding.pad_left", "extra_padding.pad_right",
        "extra_padding.edge_mode",
        "keep_proportion.pad_x", "keep_proportion.pad_y", "keep_proportion.color",
        "keep_proportion.edge_mode", "keep_proportion.width_mult", "keep_proportion.height_mult",
      ];
      state._savedEpValues = state._savedEpValues || {};
      state._savedKpValues = state._savedKpValues || {};

      // Restore bboxes from widget
      restoreBboxesFromWidget();

      // Boxes are serialized in the canvas frame they were authored in (previewWidth/Height).
      // Bring them into the current canvas frame so the in-memory coords stay canvas-relative.
      function normalizeLoadedBboxes(boxes) {
        const cw = canvasEl.width, ch = canvasEl.height;
        if (!cw || !ch) return boxes;
        return boxes.map((b) => {
          const pw = b.previewWidth, ph = b.previewHeight;
          if (!pw || !ph || (pw === cw && ph === ch)) {
            const { previewWidth, previewHeight, ...rest } = b;
            return rest;
          }
          const sx = cw / pw, sy = ch / ph;
          return { startX: b.startX * sx, startY: b.startY * sy, endX: b.endX * sx, endY: b.endY * sy };
        });
      }

      function restoreBboxesFromWidget() {
        if (bboxWidget.getValue()) {
          try {
            const parsed = JSON.parse(bboxWidget.getValue());
            // New format: { bboxes: [...], rotation: N }
            if (parsed && !Array.isArray(parsed) && typeof parsed === "object") {
              if (parsed.bboxes && Array.isArray(parsed.bboxes)) {
                state._bboxes = normalizeLoadedBboxes(parsed.bboxes.filter((b) => b?.startX != null));
                state._activeIdx = state._bboxes.length > 0 ? 0 : -1;
              }
              if (parsed.rotation !== undefined) {
                state._rotation = parsed.rotation;
                node.setProperty("rotation", parsed.rotation);
              }
              if (parsed.fillColor) {
                node.setProperty("fillColor", parsed.fillColor);
                colorInput.value = parsed.fillColor;
                colorSwatch.style.background = parsed.fillColor;
              }
            }
            // Legacy format: [bbox, bbox, ...]
            else if (Array.isArray(parsed) && parsed.length > 0) {
              state._bboxes = normalizeLoadedBboxes(parsed.filter((b) => b?.startX != null));
              state._activeIdx = state._bboxes.length > 0 ? 0 : -1;
            }
          } catch (e) {}
        }
      }

      function normBbox(bbox) {
        return { x1: Math.min(bbox.startX, bbox.endX), y1: Math.min(bbox.startY, bbox.endY),
          x2: Math.max(bbox.startX, bbox.endX), y2: Math.max(bbox.startY, bbox.endY) };
      }

      function getCanvasMouse(e) {
        const rect = canvasEl.getBoundingClientRect();
        return { x: (e.clientX - rect.left) * (canvasEl.width / rect.width),
          y: (e.clientY - rect.top) * (canvasEl.height / rect.height) };
      }

      function rotRad() { return state._rotation * Math.PI / 180; }
      function getDivBy() { return divWidget ? divWidget.getValue() : 0; }
      function getGridSize() { return parseInt(gridSlider.value) || 0; }
      // Subtract extra padding from target dims for non-pad keep_proportion modes
      function adjustTargetForPadding(rw, rh, tgtW, tgtH) {
        const ep = getExtraPadding();
        if (hasExtraPad(ep) && !ep.isFirst) {
          if (tgtW > 0) rw = Math.max(1, rw - ep.left - ep.right);
          if (tgtH > 0) rh = Math.max(1, rh - ep.top - ep.bottom);
        }
        return { rw, rh };
      }
      function getEffectiveTargetDims(fallbackW, fallbackH) {
        const divBy = getDivBy();
        const { w: tgtW, h: tgtH } = getTgt();
        let { rw, rh } = adjustTargetForPadding(tgtW > 0 ? tgtW : fallbackW, tgtH > 0 ? tgtH : fallbackH, tgtW, tgtH);
        return { rw: roundDown(rw, divBy), rh: roundDown(rh, divBy) };
      }

      function getFillColor() { return node.getProperty("fillColor") || "#000000"; }
      function getTgt() { return { w: twWidget ? twWidget.getValue() : 0, h: thWidget ? thWidget.getValue() : 0 }; }
      function getKp() { return kpWidget ? kpWidget.getValue() : "stretch"; }
      function isPadMode(kp) { return kp === "pad_color" || kp === "pad_edge"; }
      function hasExtraPad(ep) { return ep.top + ep.bottom + ep.left + ep.right > 0; }

      function hitTestRotationCross(mx, my) {
        if (!state._showRotationCross) return false;
        const cx = canvasEl.width / 2;
        const cy = canvasEl.height / 2;
        const dx = mx - cx;
        const dy = my - cy;
        const rad = rotRad();
        const cosR = Math.cos(rad);
        const sinR = Math.sin(rad);
        const perpH = -dx * sinR + dy * cosR;
        const perpV = dx * cosR + dy * sinR;
        const dist = Math.sqrt(dx * dx + dy * dy);
        return dist < 15 || Math.abs(perpH) < 8 || Math.abs(perpV) < 8;
      }

      function restoreCanvasToImage() {
        if (!state._previewImg || !state._previewEnabled) return;
        setCanvasSize(...clampToMaxCanvas(...Object.values(getEffectiveImageDims(true))));
      }

      function drawPreviewRegion(ctx, rx, ry, rw, rh, dx, dy, dw, dh) {
        const rp = getRotatedPreview();
        const sx = _rotCanvas.width / canvasEl.width, sy = _rotCanvas.height / canvasEl.height;
        ctx.drawImage(rp, rx * sx, ry * sy, rw * sx, rh * sy, dx, dy, dw, dh);
      }

      function drawStretchOverlay(ctx, ar, rx, ry, rw, rh) {
        const { pW, pH, pX, pY } = fitAspect(ar, rw, rh, rx, ry);
        ctx.fillStyle = "rgba(0, 0, 0, 0.5)";
        ctx.fillRect(rx, ry, rw, rh);
        if (state._previewEnabled && state._previewImg) drawPreviewRegion(ctx, rx, ry, rw, rh, pX, pY, pW, pH);
        drawDashedBorder(ctx, pX, pY, pW, pH);
      }

      // Compute content dimensions after keep_proportion resize, before extra padding
      function computeContentDims(cropW, cropH) {
        if (cropW <= 0 || cropH <= 0) return null;
        const { w: tgtW, h: tgtH } = getTgt();
        let outW = cropW, outH = cropH;
        const kp = getKp();
        // For pad-first non-pad modes, the source is padded before keep_proportion
        const ep = getExtraPadding();
        if (ep.isFirst && hasExtraPad(ep) && !isPadMode(kp)) {
          cropW += ep.left + ep.right;
          cropH += ep.top + ep.bottom;
        }
        if (tgtW > 0 || tgtH > 0) {
          let { rw, rh } = adjustTargetForPadding(tgtW > 0 ? tgtW : cropW, tgtH > 0 ? tgtH : cropH, tgtW, tgtH);
          if (kp === "keep_long_edge") {
            const ratio = Math.min(rw / cropW, rh / cropH);
            rw = Math.round(cropW * ratio);
            rh = Math.round(cropH * ratio);
          } else if (kp === "keep_short_edge") {
            const ratio = Math.max(rw / cropW, rh / cropH);
            rw = Math.round(cropW * ratio);
            rh = Math.round(cropH * ratio);
          } else if (kp === "total_pixels") {
            const totalPx = rw * rh;
            const ar = cropW / cropH;
            rh = Math.round(Math.sqrt(totalPx / ar));
            rw = Math.round(Math.sqrt(totalPx * ar));
          }
          outW = rw;
          outH = rh;
        }
        if (kp === "multiplier") {
          const wm = _getSubWidget("keep_proportion.width_mult")?.getValue() || 1.0;
          const hm = _getSubWidget("keep_proportion.height_mult")?.getValue() || 1.0;
          outW = Math.round(cropW * wm);
          outH = Math.round(cropH * hm);
        }
        return { w: outW, h: outH };
      }

      function computeOutputDims(cropW, cropH) {
        const content = computeContentDims(cropW, cropH);
        if (!content) return null;
        let outW = content.w, outH = content.h;
        // Add extra padding (skip for pad-first — handled on the source image)
        const ep = getExtraPadding();
        if (!ep.isFirst) {
          outW += ep.left + ep.right;
          outH += ep.top + ep.bottom;
        }
        const divBy = getDivBy();
        outW = roundDown(outW, divBy);
        outH = roundDown(outH, divBy);
        return { w: outW, h: outH };
      }

      function getPadXY() { return _framePadXY; }
      function getExtraPadding() { return _frameEp; }

      function _readPadXY() {
        const px = _getSubWidget("keep_proportion.pad_x"), py = _getSubWidget("keep_proportion.pad_y");
        return { x: px ? px.getValue() : 0.5, y: py ? py.getValue() : 0.5 };
      }

      let _suppressSubCallbacks = false;
      function setPadXY(x, y, defer) {
        x = Math.max(0, Math.min(1, x));
        y = Math.max(0, Math.min(1, y));
        _framePadXY = { x, y };
        if (!defer) {
          const px = _getSubWidget("keep_proportion.pad_x"), py = _getSubWidget("keep_proportion.pad_y");
          _suppressSubCallbacks = true;
          if (px) px.setValue(x);
          if (py) py.setValue(y);
          _suppressSubCallbacks = false;
        }
      }

      function _readExtraPadding() {
        const get = (name) => _getSubWidget(`extra_padding.${name}`)?.getValue() || 0;
        const mode = epWidget?.getValue() || "disabled";
        // pad_color/pad_edge = pad first (before crop), pad_crop_color/pad_crop_edge = pad after crop
        const isCrop = mode.startsWith("pad_crop_");
        const baseMode = isCrop ? mode.replace("pad_crop_", "pad_") : mode;
        return {
          top: get("pad_top"), bottom: get("pad_bottom"),
          left: get("pad_left"), right: get("pad_right"),
          mode: baseMode,
          isFirst: !isCrop && mode !== "disabled",
          edgeMode: _getSubWidget("extra_padding.edge_mode")?.getValue() || "clamp",
        };
      }

      // Draw extra padding fill around content area (cX,cY,cW,cH) within pad area (pX,pY,pW,pH)
      // srcImg is the source image, srcX/Y/W/H define the source region
      // Draw edge/color fill around content area. srcImg must be pre-rendered at its full dimensions.
      function drawExtraPadFill(ctx, ep, pX, pY, pW, pH, cX, cY, cW, cH, srcImg) {
        if (ep.mode === "pad_color") {
          ctx.fillStyle = getFillColor();
          ctx.fillRect(pX, pY, pW, pH);
        } else if (ep.mode === "pad_edge") {
          const em = ep.edgeMode;
          const sw = srcImg.width, sh = srcImg.height;
          if (em === "clamp") {
            const l = cX - pX, r = (pX + pW) - (cX + cW), t = cY - pY, b = (pY + pH) - (cY + cH);
            if (t > 0) ctx.drawImage(srcImg, 0, 0, sw, 1, cX, pY, cW, t);
            if (b > 0) ctx.drawImage(srcImg, 0, sh - 1, sw, 1, cX, cY + cH, cW, b);
            if (l > 0) ctx.drawImage(srcImg, 0, 0, 1, sh, pX, cY, l, cH);
            if (r > 0) ctx.drawImage(srcImg, sw - 1, 0, 1, sh, cX + cW, cY, r, cH);
            if (l > 0 && t > 0) ctx.drawImage(srcImg, 0, 0, 1, 1, pX, pY, l, t);
            if (r > 0 && t > 0) ctx.drawImage(srcImg, sw - 1, 0, 1, 1, cX + cW, pY, r, t);
            if (l > 0 && b > 0) ctx.drawImage(srcImg, 0, sh - 1, 1, 1, pX, cY + cH, l, b);
            if (r > 0 && b > 0) ctx.drawImage(srcImg, sw - 1, sh - 1, 1, 1, cX + cW, cY + cH, r, b);
          } else if (em === "repeat" || em === "mirror") {
            // Copy srcImg to _mirrorCanvas first — srcImg may be _tmpCanvas
            const tileW = Math.max(1, Math.round(cW));
            const tileH = Math.max(1, Math.round(cH));
            _mirrorCanvas.width = tileW;
            _mirrorCanvas.height = tileH;
            _mirrorCtx.drawImage(srcImg, 0, 0, tileW, tileH);
            let tileCanvas;
            if (em === "mirror") {
              _tmpCanvas.width = tileW * 2; _tmpCanvas.height = tileH * 2;
              _tmpCtx.drawImage(_mirrorCanvas, 0, 0);
              _tmpCtx.save(); _tmpCtx.translate(_tmpCanvas.width, 0); _tmpCtx.scale(-1, 1); _tmpCtx.drawImage(_mirrorCanvas, 0, 0); _tmpCtx.restore();
              _tmpCtx.save(); _tmpCtx.translate(0, _tmpCanvas.height); _tmpCtx.scale(1, -1); _tmpCtx.drawImage(_mirrorCanvas, 0, 0); _tmpCtx.restore();
              _tmpCtx.save(); _tmpCtx.translate(_tmpCanvas.width, _tmpCanvas.height); _tmpCtx.scale(-1, -1); _tmpCtx.drawImage(_mirrorCanvas, 0, 0); _tmpCtx.restore();
              tileCanvas = _tmpCanvas;
            } else {
              tileCanvas = _mirrorCanvas;
            }
            const pattern = ctx.createPattern(tileCanvas, "repeat");
            ctx.save();
            ctx.beginPath(); ctx.rect(pX, pY, pW, pH); ctx.clip();
            ctx.translate(cX, cY);
            ctx.fillStyle = pattern;
            ctx.fillRect(pX - cX, pY - cY, pW, pH);
            ctx.restore();
          }
        }
      }

      function fitAspect(targetAR, cw, ch, cx = 0, cy = 0) {
        if (targetAR > cw / ch) { const pH = cw / targetAR; return { pW: cw, pH, pX: cx, pY: cy + (ch - pH) / 2 }; }
        const pW = ch * targetAR; return { pW, pH: ch, pX: cx + (cw - pW) / 2, pY: cy };
      }

      function drawDashedBorder(ctx, x, y, w, h, color = "rgba(255, 180, 60, 0.8)") {
        ctx.setLineDash([4, 4]); ctx.strokeStyle = color; ctx.lineWidth = 1;
        ctx.strokeRect(x, y, w, h); ctx.setLineDash([]);
      }

      // Dim four sides around an inner rect within an outer rect
      function dimSides(ctx, ox, oy, ow, oh, ix, iy, iw, ih, color = "rgba(255, 80, 80, 0.3)") {
        ctx.fillStyle = color;
        ctx.fillRect(ox, oy, ow, iy - oy);                        // top
        ctx.fillRect(ox, iy + ih, ow, (oy + oh) - (iy + ih));     // bottom
        ctx.fillRect(ox, iy, ix - ox, ih);                         // left
        ctx.fillRect(ix + iw, iy, (ox + ow) - (ix + iw), ih);     // right
      }

      // Compute pad mode layout: fit target AR, compute content rect inside
      function computePadLayout(rw, rh, cropW, cropH, fitW, fitH, fitX, fitY) {
        const { pW, pH, pX, pY } = fitAspect(rw / rh, fitW, fitH, fitX, fitY);
        const imgRatio = Math.min(rw / cropW, rh / cropH);
        const cW = pW * (cropW * imgRatio / rw), cH = pH * (cropH * imgRatio / rh);
        const { cX, cY } = computePadContentPos(pX, pY, pW, pH, cW, cH);
        return { pW, pH, pX, pY, cW, cH, cX, cY };
      }

      // Render source to _tmpCanvas at given size. If srcImg + source rect provided, draws that region.
      // Otherwise draws the rotated preview (with replicate rotation for pad_edge mode).
      // replicate: force replicate-pad rotation (for keep_proportion pad_edge mode)
      function renderToTmp(w, h, srcImg, sx, sy, sw, sh, replicate) {
        const ep = getExtraPadding();
        if (!srcImg && state._rotation !== 0 && (replicate || (ep.mode === "pad_edge" && ep.isFirst))) {
          renderReplicateRotated(w, h); return;
        }
        _tmpCanvas.width = w; _tmpCanvas.height = h;
        if (srcImg) _tmpCtx.drawImage(srcImg, sx, sy, sw, sh, 0, 0, w, h);
        else _tmpCtx.drawImage(getRotatedPreview(), 0, 0, _rotCanvas.width, _rotCanvas.height, 0, 0, w, h);
      }

      function getEdgeEp() {
        return { mode: "pad_edge", edgeMode: _getSubWidget("keep_proportion.edge_mode")?.getValue() || "clamp" };
      }

      function computePadContentPos(pX, pY, pW, pH, cW, cH) {
        const { x, y } = getPadXY();
        return { cX: pX + (pW - cW) * x, cY: pY + (pH - cH) * y };
      }

      function getOtherBboxEdges(axis) {
        const edges = [];
        for (let i = 0; i < state._bboxes.length; i++) {
          if (i === state._activeIdx) continue;
          const { x1, y1, x2, y2 } = normBbox(state._bboxes[i]);
          edges.push(axis === "x" ? x1 : y1, axis === "x" ? x2 : y2);
        }
        return edges;
      }

      function getEffectiveSnap() {
        const g = getGridParams();
        if (g) return { x: g.effGridW, y: g.effGridH };
        const d = getDivBy();
        return d > 1 ? { x: d, y: d } : { x: 0, y: 0 };
      }

      function snapCoord(val, snapSize, scale, canvasDim, otherEdges) {
        let best = val, bestDist = Infinity;
        const consider = (c) => { const d = Math.abs(val - c); if (d < bestDist) { bestDist = d; best = c; } };
        consider(0);
        consider(canvasDim);
        if (snapSize > 1) consider(Math.round(val * scale / snapSize) * snapSize / scale);
        if (otherEdges) for (const edge of otherEdges) consider(edge);
        return best;
      }

      // Snap the moving corner(s) of a bbox to grid / edges / other bboxes.
      function snapBbox(bbox) {
        if (!bbox) return bbox;
        const snap = getEffectiveSnap(), scale = getCanvasScale();
        const xEdges = getOtherBboxEdges("x"), yEdges = getOtherBboxEdges("y");
        return { startX: snapCoord(bbox.startX, snap.x, scale.x, canvasEl.width, xEdges),
          startY: snapCoord(bbox.startY, snap.y, scale.y, canvasEl.height, yEdges),
          endX: snapCoord(bbox.endX, snap.x, scale.x, canvasEl.width, xEdges),
          endY: snapCoord(bbox.endY, snap.y, scale.y, canvasEl.height, yEdges) };
      }

      function snapBboxPosition(bbox) {
        if (!bbox) return bbox;
        const snap = getEffectiveSnap();
        const scale = getCanvasScale();
        const xEdges = getOtherBboxEdges("x");
        const yEdges = getOtherBboxEdges("y");
        const { x1, y1 } = normBbox(bbox);
        const w = Math.abs(bbox.endX - bbox.startX);
        const h = Math.abs(bbox.endY - bbox.startY);
        // Snap both the left/top and right/bottom edges, pick whichever is closer
        const snappedX1 = snapCoord(x1, snap.x, scale.x, canvasEl.width, xEdges);
        const snappedX2 = snapCoord(x1 + w, snap.x, scale.x, canvasEl.width, xEdges) - w;
        const snappedX = Math.abs(snappedX1 - x1) <= Math.abs(snappedX2 - x1) ? snappedX1 : snappedX2;
        const snappedY1 = snapCoord(y1, snap.y, scale.y, canvasEl.height, yEdges);
        const snappedY2 = snapCoord(y1 + h, snap.y, scale.y, canvasEl.height, yEdges) - h;
        const snappedY = Math.abs(snappedY1 - y1) <= Math.abs(snappedY2 - y1) ? snappedY1 : snappedY2;
        return { startX: snappedX, startY: snappedY, endX: snappedX + w, endY: snappedY + h };
      }

      function constrainAspect(bbox, dragMode) {
        if (!bbox) return bbox;
        const { w: tw, h: th } = getTgt();
        // Target aspect in source-image pixels
        const srcAR = (tw > 0 && th > 0) ? tw / th : 1;
        // Convert to preview-pixel aspect by accounting for non-uniform scaling
        const scale = getCanvasScale();
        const ar = srcAR * scale.y / scale.x;

        const { x1, y1, x2, y2 } = normBbox(bbox);
        let bw = x2 - x1;
        let bh = y2 - y1;
        if (bw <= 0 || bh <= 0) return bbox;

        // Adjust height to match aspect, keep width
        const hFromW = bw / ar;
        const wFromH = bh * ar;
        // Pick the smaller fit so we don't exceed the drawn extent
        if (hFromW <= bh) {
          bh = hFromW;
        } else {
          bw = wFromH;
        }

        // Anchor based on drag mode
        if (dragMode === "resize-tl") {
          return { startX: x2 - bw, startY: y2 - bh, endX: x2, endY: y2 };
        } else if (dragMode === "resize-tr") {
          return { startX: x1, startY: y2 - bh, endX: x1 + bw, endY: y2 };
        } else if (dragMode === "resize-bl") {
          return { startX: x2 - bw, startY: y1, endX: x2, endY: y1 + bh };
        } else {
          // resize-br or draw (anchor top-left)
          return { startX: x1, startY: y1, endX: x1 + bw, endY: y1 + bh };
        }
      }

      function removeBbox(index) {
        state._bboxes.splice(index, 1);
        if (state._bboxes.length === 0) state._activeIdx = -1;
        else if (index <= state._activeIdx) state._activeIdx = Math.min(state._activeIdx - (index < state._activeIdx ? 1 : 0), state._bboxes.length - 1);
      }

      function hitTestBboxes(mx, my) {
        const order = state._activeIdx >= 0 ? [state._activeIdx] : [];
        for (let i = 0; i < state._bboxes.length; i++) { if (i !== state._activeIdx) order.push(i); }
        for (const idx of order) {
          const { x1, y1, x2, y2 } = normBbox(state._bboxes[idx]);
          const mode = rectHitTest(mx, my, x1, y1, x2, y2, 10);
          if (mode) return { index: idx, mode };
        }
        return null;
      }

      canvasEl.addEventListener("mousedown", (e) => {
        canvasEl.focus();
        if (e.button === 2) {
          e.preventDefault();
          const m = getCanvasMouse(e);
          // Right-click on rotation cross: reset rotation
          if (state._rotation !== 0 && hitTestRotationCross(m.x, m.y)) {
            resetRotation();
            return;
          }
          // Right-click: delete the bbox under cursor, or active bbox
          const hit = hitTestBboxes(m.x, m.y);
          if (hit) {
            removeBbox(hit.index);
          } else if (state._activeIdx >= 0) {
            removeBbox(state._activeIdx);
          }
          updateBboxWidgets();
          drawCanvas();
          return;
        }
        if (e.button !== 0) return;
        const m = getCanvasMouse(e);

        // Check for rotation cross drag (click near the center or any arm)
        if (hitTestRotationCross(m.x, m.y)) {
            state._dragMode = "rotate";
            state._rotateStart = state._rotation;
            const rect0 = canvasEl.getBoundingClientRect();
            // Capture screen center once — immune to canvas resize
            state._rotateCenterX = rect0.left + rect0.width / 2;
            state._rotateCenterY = rect0.top + rect0.height / 2;
            state._rotateScreenStartAngle = Math.atan2(
              e.clientY - state._rotateCenterY,
              e.clientX - state._rotateCenterX
            ) * 180 / Math.PI;
            state._drawing = true;
            state._dragStart = m;
            document.addEventListener("mousemove", onDragMove);
            document.addEventListener("mouseup", onDragEnd);
            e.preventDefault();
            e.stopPropagation();
            return;
        }

        // Shift+drag: drag content position within padded area
        if (e.shiftKey) {
          const kpVal = getKp();
          const { w: tW2, h: tH2 } = getTgt();
          const ep = getExtraPadding();
          const startDrag = (mode, extra) => {
            state._dragMode = mode; Object.assign(state, extra);
            state._drawing = true; state._dragStart = m;
            document.addEventListener("mousemove", onDragMove);
            document.addEventListener("mouseup", onDragEnd);
            e.preventDefault(); e.stopPropagation();
          };
          if ((tW2 > 0 || tH2 > 0) && isPadMode(kpVal)) {
            startDrag("pad_drag", { _padDragStart: getPadXY(), _bboxAtDragStart: null }); return;
          } else if (hasExtraPad(ep)) {
            startDrag("extra_pad_drag", { _extraPadStart: { ...ep }, _bboxAtDragStart: null }); return;
          }
        }

        const hit = hitTestBboxes(m.x, m.y);
        if (hit) {
          // Select and interact with existing bbox
          state._activeIdx = hit.index;
          state._dragMode = hit.mode;
          const bbox = state._bboxes[hit.index];
          const { x1, y1, x2, y2 } = normBbox(bbox);
          state._bboxAtDragStart = { startX: x1, startY: y1, endX: x2, endY: y2 };
        } else {
          // Draw new bbox
          state._dragMode = "draw";
          const newBbox = { startX: m.x, startY: m.y, endX: m.x, endY: m.y };
          state._bboxes.push(newBbox);
          state._activeIdx = state._bboxes.length - 1;
          state._bboxAtDragStart = null;
        }
        state._drawing = true;
        state._dragStart = m;

        document.addEventListener("mousemove", onDragMove);
        document.addEventListener("mouseup", onDragEnd);
        e.preventDefault();
        e.stopPropagation();
      });

      // Hover cursor updates
      canvasEl.addEventListener("mousemove", (e) => {
        if (state._drawing) return;
        const m = getCanvasMouse(e);
        const hit = hitTestBboxes(m.x, m.y);
        if (!hit) {
          if (!state._showRotationCross) {
            canvasEl.style.cursor = e.shiftKey ? "grab" : "crosshair";
          } else if (hitTestRotationCross(m.x, m.y)) {
            canvasEl.style.cursor = "alias";
          } else if (e.shiftKey) {
            const kpVal = getKp();
            const { w: tW, h: tH } = getTgt();
            const epHover = getExtraPadding();
            if (((tW > 0 || tH > 0) && isPadMode(kpVal)) || hasExtraPad(epHover)) {
              canvasEl.style.cursor = "grab";
            } else {
              canvasEl.style.cursor = "crosshair";
            }
          } else {
            canvasEl.style.cursor = "crosshair";
          }
        } else {
          canvasEl.style.cursor = cursorForBboxMode(hit.mode) || "crosshair";
        }
      });

      function onDragMove(e) {
        if (!state._drawing) return;
        if (state._dragMode === "rotate") {
          // Screen-space atan2 with fixed center (captured at drag start)
          const sdx = e.clientX - state._rotateCenterX;
          const sdy = e.clientY - state._rotateCenterY;
          const screenDist = Math.sqrt(sdx * sdx + sdy * sdy);
          if (screenDist < 15) {
            state._rotateStart = state._rotation;
            state._rotateScreenStartAngle = Math.atan2(sdy, sdx) * 180 / Math.PI;
            return;
          }
          const angleCur = Math.atan2(sdy, sdx) * 180 / Math.PI;
          let angleDelta = angleCur - state._rotateScreenStartAngle;
          // Normalize delta to -180..180 to handle atan2 wrap-around
          while (angleDelta > 180) angleDelta -= 360;
          while (angleDelta < -180) angleDelta += 360;
          let newRot = state._rotateStart + angleDelta;
          if (e.ctrlKey) {
            newRot = Math.round(newRot / 15) * 15;
          } else {
            for (const snap of [0, 90, 180, 270, -90, -180, -270, 360]) {
              if (Math.abs(newRot - snap) < 3) { newRot = snap; break; }
            }
          }
          while (newRot > 180) newRot -= 360;
          while (newRot < -180) newRot += 360;
          state._rotation = newRot;
          node.setProperty("rotation", newRot);
          // Resize canvas to match rotated image dimensions
          if (state._previewImg && state._previewEnabled) {
            const { w: ew, h: eh } = getEffectiveImageDims(true);
            const [rw, rh] = clampToMaxCanvas(ew, eh);
            if (Math.abs(rw - canvasEl.width) > 3 || Math.abs(rh - canvasEl.height) > 3) {
              setCanvasSize(rw, rh);
            }
          }
          drawCanvas();
          return;
        }
        if (state._dragMode === "pad_drag") {
          const m = getCanvasMouse(e);
          const dx = m.x - state._dragStart.x;
          const dy = m.y - state._dragStart.y;
          // Compute the pad preview layout to find how many canvas pixels = full 0-1 range
          const ep = getExtraPadding();
          const { w: imgW, h: imgH } = state._previewImg
            ? getEffectiveImageDims(getKp() !== "pad_edge")
            : { w: canvasEl.width, h: canvasEl.height };
          const { rw: baseTw, rh: baseTh } = getEffectiveTargetDims(imgW, imgH);
          const totalW = baseTw + ep.left + ep.right;
          const totalH = baseTh + ep.top + ep.bottom;
          const { pW, pH } = fitAspect(totalW / totalH, canvasEl.width, canvasEl.height);
          const imgRatio = Math.min(baseTw / imgW, baseTh / imgH);
          const cW = pW * (imgW * imgRatio / totalW), cH = pH * (imgH * imgRatio / totalH);
          const rangeX = pW - cW, rangeY = pH - cH;
          const newX = rangeX > 0 ? state._padDragStart.x + dx / rangeX : 0.5;
          const newY = rangeY > 0 ? state._padDragStart.y + dy / rangeY : 0.5;
          setPadXY(newX, newY, true);
          drawCanvas();
          return;
        }
        if (state._dragMode === "extra_pad_drag") {
          const m = getCanvasMouse(e);
          const dx = m.x - state._dragStart.x;
          const dy = m.y - state._dragStart.y;
          const s = state._extraPadStart;
          const totalH = s.top + s.bottom, totalW = s.left + s.right;
          const fullW = (state._previewImg ? state._previewImg.naturalWidth : canvasEl.width) + totalW;
          const fullH = (state._previewImg ? state._previewImg.naturalHeight : canvasEl.height) + totalH;
          const scale = (fullW / fullH > canvasEl.width / canvasEl.height)
            ? fullW / canvasEl.width : fullH / canvasEl.height;
          const pixDx = Math.round(dx * scale);
          const pixDy = Math.round(dy * scale);
          const newLeft = Math.max(0, Math.min(totalW, s.left + pixDx));
          const newTop = Math.max(0, Math.min(totalH, s.top + pixDy));
          _suppressSubCallbacks = true;
          for (const [name, val] of [["pad_left", newLeft], ["pad_right", totalW - newLeft],
              ["pad_top", newTop], ["pad_bottom", totalH - newTop]]) {
            const w = _getSubWidget(`extra_padding.${name}`);
            if (w) w.setValue(val);
          }
          _suppressSubCallbacks = false;
          drawCanvas();
          return;
        }
        if (state._activeIdx < 0) return;
        const m = getCanvasMouse(e);
        const cw = canvasEl.width;
        const ch = canvasEl.height;
        let bbox = state._bboxes[state._activeIdx];

        if (state._dragMode === "draw") {
          bbox.endX = Math.max(0, Math.min(cw, m.x));
          bbox.endY = Math.max(0, Math.min(ch, m.y));
        } else if (state._dragMode === "move" && state._bboxAtDragStart) {
          const dx = m.x - state._dragStart.x;
          const dy = m.y - state._dragStart.y;
          const bs = state._bboxAtDragStart;
          const w = bs.endX - bs.startX;
          const h = bs.endY - bs.startY;
          const nx = Math.max(0, Math.min(cw - w, bs.startX + dx));
          const ny = Math.max(0, Math.min(ch - h, bs.startY + dy));
          bbox = { startX: nx, startY: ny, endX: nx + w, endY: ny + h };
        } else if (state._dragMode?.startsWith("resize") && state._bboxAtDragStart) {
          const bs = state._bboxAtDragStart;
          const dm = state._dragMode;
          // Edge resize: only one axis moves
          if (dm === "resize-t" || dm === "resize-b" || dm === "resize-l" || dm === "resize-r") {
            const edgeCoord = dm === "resize-t" ? bs.startY : dm === "resize-b" ? bs.endY : dm === "resize-l" ? bs.startX : bs.endX;
            const isVert = dm === "resize-t" || dm === "resize-b";
            const off = (isVert ? state._dragStart.y : state._dragStart.x) - edgeCoord;
            const val = Math.max(0, Math.min(isVert ? ch : cw, (isVert ? m.y : m.x) - off));
            if (dm === "resize-t") bbox = { startX: bs.startX, startY: val, endX: bs.endX, endY: bs.endY };
            else if (dm === "resize-b") bbox = { startX: bs.startX, startY: bs.startY, endX: bs.endX, endY: val };
            else if (dm === "resize-l") bbox = { startX: val, startY: bs.startY, endX: bs.endX, endY: bs.endY };
            else bbox = { startX: bs.startX, startY: bs.startY, endX: val, endY: bs.endY };
          } else {
            // Corner resize
            let cornerX, cornerY;
            if (dm === "resize-tl") { cornerX = bs.startX; cornerY = bs.startY; }
            else if (dm === "resize-tr") { cornerX = bs.endX; cornerY = bs.startY; }
            else if (dm === "resize-bl") { cornerX = bs.startX; cornerY = bs.endY; }
            else { cornerX = bs.endX; cornerY = bs.endY; }
            const offX = state._dragStart.x - cornerX;
            const offY = state._dragStart.y - cornerY;
            const cx = Math.max(0, Math.min(cw, m.x - offX));
            const cy = Math.max(0, Math.min(ch, m.y - offY));
            if (dm === "resize-tl") bbox = { startX: bs.endX, startY: bs.endY, endX: cx, endY: cy };
            else if (dm === "resize-tr") bbox = { startX: bs.startX, startY: bs.endY, endX: cx, endY: cy };
            else if (dm === "resize-bl") bbox = { startX: bs.endX, startY: bs.startY, endX: cx, endY: cy };
            else if (dm === "resize-br") bbox = { startX: bs.startX, startY: bs.startY, endX: cx, endY: cy };
          }
        }

        // Alt: resize symmetrically — for draw, the click point is center;
        // for resize, the center of the original bbox is the pivot
        if (e.altKey && state._dragMode !== "move") {
          let cx, cy;
          if (state._dragMode === "draw") {
            cx = state._dragStart.x;
            cy = state._dragStart.y;
          } else if (state._bboxAtDragStart) {
            const bs = state._bboxAtDragStart;
            cx = (bs.startX + bs.endX) / 2;
            cy = (bs.startY + bs.endY) / 2;
          } else {
            cx = (bbox.startX + bbox.endX) / 2;
            cy = (bbox.startY + bbox.endY) / 2;
          }
          const dx = Math.abs(bbox.endX - cx);
          const dy = Math.abs(bbox.endY - cy);
          bbox = {
            startX: Math.max(0, cx - dx),
            startY: Math.max(0, cy - dy),
            endX: Math.min(cw, cx + dx),
            endY: Math.min(ch, cy + dy),
          };
        }

        // Shift: constrain to target aspect ratio (not applicable to edge resize)
        const isEdgeResize = /^resize-[tblr]$/.test(state._dragMode);
        if (e.shiftKey && state._dragMode !== "move" && !isEdgeResize) {
          bbox = constrainAspect(bbox, state._dragMode);
        }

        // Ctrl: snap to grid in source image space
        if (e.ctrlKey) {
          if (state._dragMode === "move") {
            bbox = snapBboxPosition(bbox);
          } else if (e.altKey) {
            // Snap both edges, keep centered
            const snap = getEffectiveSnap();
            const scale = getCanvasScale();
            const xEdges = getOtherBboxEdges("x");
            const yEdges = getOtherBboxEdges("y");
            const sx1 = snapCoord(bbox.startX, snap.x, scale.x, cw, xEdges);
            const sx2 = snapCoord(bbox.endX, snap.x, scale.x, cw, xEdges);
            const sy1 = snapCoord(bbox.startY, snap.y, scale.y, ch, yEdges);
            const sy2 = snapCoord(bbox.endY, snap.y, scale.y, ch, yEdges);
            bbox = { startX: sx1, startY: sy1, endX: sx2, endY: sy2 };
          } else if (isEdgeResize) {
            // Only snap the edge being dragged
            const snap = getEffectiveSnap();
            const scale = getCanvasScale();
            const xEdges = getOtherBboxEdges("x"), yEdges = getOtherBboxEdges("y");
            const dm = state._dragMode;
            bbox = { ...bbox,
              ...(dm === "resize-t" && { startY: snapCoord(bbox.startY, snap.y, scale.y, ch, yEdges) }),
              ...(dm === "resize-b" && { endY: snapCoord(bbox.endY, snap.y, scale.y, ch, yEdges) }),
              ...(dm === "resize-l" && { startX: snapCoord(bbox.startX, snap.x, scale.x, cw, xEdges) }),
              ...(dm === "resize-r" && { endX: snapCoord(bbox.endX, snap.x, scale.x, cw, xEdges) }),
            };
          } else {
            bbox = snapBbox(bbox);
          }
        }

        state._bboxes[state._activeIdx] = bbox;
        drawCanvas();
        e.preventDefault();
      }

      function onDragEnd(e) {
        if (!state._drawing) return;
        const wasRotate = state._dragMode === "rotate";
        const wasPadDrag = state._dragMode === "pad_drag";
        Object.assign(state, { _drawing: false, _dragMode: null, _dragStart: null,
          _bboxAtDragStart: null, _padDragStart: null, _extraPadStart: null });
        // Flush deferred pad_x/pad_y widget values
        if (wasPadDrag) setPadXY(_framePadXY.x, _framePadXY.y);
        document.removeEventListener("mousemove", onDragMove);
        document.removeEventListener("mouseup", onDragEnd);

        // Snap canvas to exact rotated dimensions on release (during drag we use a threshold to avoid jitter)
        if (wasRotate) {
          restoreCanvasToImage();
          fitNodeToImage(false);
        }

        if (state._activeIdx >= 0) {
          const bbox = state._bboxes[state._activeIdx];
          const { x1, y1, x2, y2 } = normBbox(bbox);
          if (x2 - x1 < 3 && y2 - y1 < 3) {
            // Too small — remove it
            removeBbox(state._activeIdx);
          } else {
            state._bboxes[state._activeIdx] = { startX: x1, startY: y1, endX: x2, endY: y2 };
          }
        }
        updateBboxWidgets();
        drawCanvas();
      }

      canvasEl.addEventListener("contextmenu", (e) => { e.preventDefault(); e.stopPropagation(); });

      canvasEl.tabIndex = 0;
      canvasEl.style.outline = "none";
      canvasEl.addEventListener("keydown", (e) => {
        if (state._activeIdx < 0) return;
        const arrows = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
        const dir = arrows[e.key];
        if (!dir) {
          // Delete key removes active bbox
          if (e.key === "Delete" || e.key === "Backspace") {
            e.preventDefault();
            e.stopPropagation();
            removeBbox(state._activeIdx);
            updateBboxWidgets();
            drawCanvas();
          }
          // Tab cycles through bboxes
          if (e.key === "Tab" && state._bboxes.length > 1) {
            e.preventDefault();
            e.stopPropagation();
            state._activeIdx = (state._activeIdx + (e.shiftKey ? -1 : 1) + state._bboxes.length) % state._bboxes.length;
            drawCanvas();
          }
          return;
        }
        e.preventDefault();
        e.stopPropagation();

        const snap = getEffectiveSnap();
        const step = e.ctrlKey ? (snap.x > 1 ? snap.x / getCanvasScale().x : 10) : 1;
        const stepY = e.ctrlKey ? (snap.y > 1 ? snap.y / getCanvasScale().y : 10) : 1;
        const dx = dir[0] * step;
        const dy = dir[1] * stepY;
        const bbox = state._bboxes[state._activeIdx];
        const { x1, y1, x2, y2 } = normBbox(bbox);
        const w = x2 - x1, h = y2 - y1;
        const nx = Math.max(0, Math.min(canvasEl.width - w, x1 + dx));
        const ny = Math.max(0, Math.min(canvasEl.height - h, y1 + dy));
        state._bboxes[state._activeIdx] = { startX: nx, startY: ny, endX: nx + w, endY: ny + h };
        updateBboxWidgets();
        drawCanvas();
      });

      function updateBboxWidgets() {
        const data = {};
        if (state._rotation !== 0) data.rotation = state._rotation;
        data.fillColor = getFillColor();
        if (state._bboxes.length > 0) {
          data.bboxes = state._bboxes.map((bbox) => {
            const b = Object.assign({}, bbox);
            if (state._previewImg) {
              b.previewWidth = canvasEl.width;
              b.previewHeight = canvasEl.height;
            }
            return b;
          });
        }
        bboxWidget.setValue(Object.keys(data).length > 0 ? JSON.stringify(data) : "");
      }

      let _resizing = false;
      function fitNodeToCanvas() {
        if (canvasEl.width <= 0 || canvasEl.height <= 0) return;
        // If in a no-bbox mode with target dims, resize canvas to output AR
        const kp = getKp();
        const { w: tgtW, h: tgtH } = getTgt();
        const hasBboxes = state._bboxes.length > 0;
        if (!hasBboxes && state._previewImg && state._previewEnabled && state._rotation === 0 && (tgtW > 0 || tgtH > 0) &&
            (kp === "stretch" || isPadMode(kp))) {
          const { w: imgW, h: imgH } = getEffectiveImageDims(kp !== "pad_edge");
          let rw = tgtW > 0 ? tgtW : imgW;
          let rh = tgtH > 0 ? tgtH : imgH;
          const outAR = rw / rh;
          const newH = Math.round(canvasEl.width / outAR);
          if (Math.abs(newH - canvasEl.height) > 2) {
            canvasEl.height = newH;
            canvasEl.style.aspectRatio = `${canvasEl.width} / ${newH}`;
            _rotCacheKey = "";
          }
        } else if (state._previewImg && state._previewEnabled) {
          // Restore to image AR (including pad-first extra padding if active)
          let { w: iw, h: ih } = getEffectiveImageDims(true);
          const ep = getExtraPadding();
          if (ep.isFirst && (ep.top + ep.bottom + ep.left + ep.right) > 0) {
            iw += ep.left + ep.right;
            ih += ep.top + ep.bottom;
          }
          const imgAR = iw / ih;
          const newH = Math.round(canvasEl.width / imgAR);
          if (Math.abs(newH - canvasEl.height) > 2) {
            rescaleBboxesTo(canvasEl.width, newH);
            canvasEl.height = newH;
            canvasEl.style.aspectRatio = `${canvasEl.width} / ${newH}`;
            _rotCacheKey = "";
          }
        }
        // Update widget height but don't force node size — only grow if needed
        const nodeW = node.getSize().width;
        const displayedW = nodeW - 30;
        const displayedH = Math.round(canvasEl.height * (displayedW / canvasEl.width));
        cropWidget.setHeight(displayedH + GRID_BAR_HEIGHT);
      }

      // Bbox coords are stored in current canvas-pixel space. Whenever the canvas
      // buffer is resized (preview load, node resize, AR change) the boxes must be
      // rescaled by the same ratio so they stay locked to the image content.
      function rescaleBboxesTo(newW, newH) {
        const oldW = canvasEl.width, oldH = canvasEl.height;
        if (!oldW || !oldH || !newW || !newH || !state._bboxes.length) return;
        if (oldW === newW && oldH === newH) return;
        const sx = newW / oldW, sy = newH / oldH;
        state._bboxes = state._bboxes.map((b) => ({
          startX: b.startX * sx, startY: b.startY * sy,
          endX: b.endX * sx, endY: b.endY * sy,
        }));
      }

      function setCanvasSize(cw, ch) {
        rescaleBboxesTo(cw, ch);
        canvasEl.width = cw;
        canvasEl.height = ch;
        canvasEl.style.aspectRatio = `${cw} / ${ch}`;
        node.setProperty("canvasSize", [cw, ch]);
        cropWidget.setHeight(ch + GRID_BAR_HEIGHT);
        fitNodeToCanvas();
      }

      function updateCanvasFromTargetDims() {
        if (state._previewImg && state._previewEnabled) return;
        const divBy = getDivBy();
        const { w: twV, h: thV } = getTgt();
        let tw = roundDown(twV, divBy);
        let th = roundDown(thV, divBy);
        const [cw, ch] = clampToMaxCanvas(tw > 0 ? Math.max(tw, 200) : 400, th > 0 ? Math.max(th, 150) : 300);
        if (cw !== canvasEl.width || ch !== canvasEl.height) {
          setCanvasSize(cw, ch);
        }
      }

      function getCanvasScale() {
        if (state._previewImg && state._previewEnabled) {
          if (state._rotation !== 0) {
            // When rotated, canvas is sized to rotated bounds — uniform scale
            const { w: rotW } = getEffectiveImageDims(true);
            const s = rotW / canvasEl.width;  // same as rotH / canvasEl.height
            return { x: s, y: s };
          }
          let nw = state._previewImg.naturalWidth;
          let nh = state._previewImg.naturalHeight;
          // For "pad first" modes, bbox coords map to padded image dimensions
          const ep = getExtraPadding();
          if (ep.isFirst && hasExtraPad(ep)) {
            nw += ep.left + ep.right;
            nh += ep.top + ep.bottom;
          }
          return { x: nw / canvasEl.width, y: nh / canvasEl.height };
        }
        const { w: tw, h: th } = getTgt();
        return { x: tw > 0 ? tw / canvasEl.width : 1, y: th > 0 ? th / canvasEl.height : 1 };
      }

      function getOutputDims(bbox) {
        if (!bbox) return null;
        const { x: sX, y: sY } = getCanvasScale();
        const { x1, y1, x2, y2 } = normBbox(bbox);
        const cropW = Math.round((x2 - x1) * sX);
        const cropH = Math.round((y2 - y1) * sY);
        const dims = computeOutputDims(cropW, cropH);
        return dims ? { w: Math.max(1, dims.w), h: Math.max(1, dims.h) } : null;
      }

      function getGridParams() {
        const gridSize = getGridSize();
        if (gridSize <= 1) return null;

        let tw, th;
        if (state._previewImg && state._previewEnabled) {
          const dims = getEffectiveImageDims(true);
          tw = dims.w;
          th = dims.h;
        } else {
          tw = twWidget ? twWidget.getValue() : canvasEl.width;
          th = thWidget ? thWidget.getValue() : canvasEl.height;
        }
        const scaleX = canvasEl.width / tw;
        const scaleY = canvasEl.height / th;
        if (gridSize * scaleX < 4 && gridSize * scaleY < 4) return null;
        // Per-dimension effective grid: no partial cells, cells are near-square
        const cellsX = Math.max(1, Math.round(tw / gridSize));
        const cellsY = Math.max(1, Math.round(th / gridSize));
        const effGridW = tw / cellsX;
        const effGridH = th / cellsY;
        return { gridSize, tw, th, scaleX, scaleY, effGridW, effGridH };
      }

      function drawGrid(ctx, alpha, clipBbox, color) {
        const g = getGridParams();
        if (!g) return;
        const { tw, th, scaleX, scaleY, effGridW, effGridH } = g;

        ctx.save();
        if (clipBbox) {
          const { x1, y1, x2, y2 } = normBbox(clipBbox);
          ctx.beginPath();
          ctx.rect(x1, y1, x2 - x1, y2 - y1);
          ctx.clip();
        }

        const showPreview = state._previewImg && state._previewEnabled;
        const defaultAlpha = showPreview ? 0.25 : 0.1;
        if (color) {
          ctx.strokeStyle = color;
        } else {
          const { r, g, b } = getGridColorRGB();
          ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, ${alpha ?? defaultAlpha})`;
        }
        ctx.lineWidth = 1;
        ctx.beginPath();
        for (let rx = effGridW; rx < tw - 0.5; rx += effGridW) {
          const px = Math.round(rx * scaleX) + 0.5;
          ctx.moveTo(px, 0);
          ctx.lineTo(px, canvasEl.height);
        }
        for (let ry = effGridH; ry < th - 0.5; ry += effGridH) {
          const py = Math.round(ry * scaleY) + 0.5;
          ctx.moveTo(0, py);
          ctx.lineTo(canvasEl.width, py);
        }
        ctx.stroke();
        ctx.restore();
      }

      function drawRotationCross(ctx) {
        if (!state._showRotationCross) return;
        const { width: cw, height: ch } = canvasEl;
        const armLen = Math.sqrt(cw * cw + ch * ch) / 2;
        const rad = rotRad();
        const isActive = state._rotation !== 0;
        ctx.save();
        ctx.translate(cw / 2, ch / 2);
        ctx.rotate(rad);
        ctx.beginPath();
        ctx.moveTo(-armLen, 0); ctx.lineTo(armLen, 0);
        ctx.moveTo(0, -armLen); ctx.lineTo(0, armLen);
        // Black outline
        Object.assign(ctx, { strokeStyle: "rgba(0, 0, 0, 0.6)", lineWidth: isActive ? 5 : 4 });
        ctx.stroke();
        // Orange fill
        Object.assign(ctx, { strokeStyle: "rgba(255, 160, 30, 0.8)", lineWidth: isActive ? 3 : 2 });
        ctx.stroke();
        if (isActive) {
          ctx.rotate(-rad);
          const label = `${state._rotation.toFixed(1)}°`;
          Object.assign(ctx, { font: "12px sans-serif", textAlign: "center" });
          const lw = ctx.measureText(label).width + 8;
          ctx.fillStyle = "rgba(0, 0, 0, 0.6)";
          ctx.beginPath(); ctx.roundRect(-lw / 2, -34, lw, 16, 3); ctx.fill();
          ctx.fillStyle = "rgba(255, 160, 30, 1)";
          ctx.fillText(label, 0, -20);
        }
        ctx.restore();
      }

      function drawBbox(ctx, bbox, index, isActive) {
        const { x1, y1, x2, y2 } = normBbox(bbox);
        const w = x2 - x1, h = y2 - y1;
        const color = getBboxColor(index, isActive);
        const invertEnabled = icWidget ? icWidget.getValue() === "enabled" : false;
        if (isActive) {
          if (invertEnabled) {
            ctx.fillStyle = getFillColor(); ctx.fillRect(x1, y1, w, h);
          } else {
            ctx.fillStyle = "rgba(0, 0, 0, 0.5)"; ctx.beginPath();
            ctx.rect(0, 0, canvasEl.width, canvasEl.height); ctx.rect(x1, y1, w, h); ctx.fill("evenodd");
          }
        }
        drawGrid(ctx, null, bbox, color.gridColor);
        if (!isActive) { ctx.fillStyle = color.tint; ctx.fillRect(x1, y1, w, h); }

        if (isActive && !invertEnabled) {
          const { x: sX, y: sY } = getCanvasScale();
          const cropW = Math.round(w * sX);
          const cropH = Math.round(h * sY);
          const { w: tgtW, h: tgtH } = getTgt();
          const kp = getKp();

          if (kp === "multiplier") {
            const wmv = _getSubWidget("keep_proportion.width_mult")?.getValue() || 1.0;
            const hmv = _getSubWidget("keep_proportion.height_mult")?.getValue() || 1.0;
            if (wmv !== 1.0 || hmv !== 1.0) {
              drawStretchOverlay(ctx, (cropW * wmv) / (cropH * hmv), x1, y1, w, h);
            }
          }

          if ((tgtW > 0 || tgtH > 0) && kp === "stretch") {
            const { rw, rh } = getEffectiveTargetDims(cropW, cropH);
            drawStretchOverlay(ctx, rw / rh, x1, y1, w, h);
          }

          if ((tgtW > 0 || tgtH > 0) && (kp === "crop" || isPadMode(kp))) {
            const { rw, rh } = getEffectiveTargetDims(cropW, cropH);

            if (kp === "crop") {
              const ratio = Math.max(rw / cropW, rh / cropH);
              const visW = rw / ratio, visH = rh / ratio;
              const offX = (cropW - visW) / 2, offY = (cropH - visH) / 2;
              const vx1 = x1 + offX / sX, vy1 = y1 + offY / sY;
              const vx2 = x1 + (offX + visW) / sX, vy2 = y1 + (offY + visH) / sY;
              dimSides(ctx, x1, y1, w, h, vx1, vy1, vx2 - vx1, vy2 - vy1);
              drawDashedBorder(ctx, vx1, vy1, vx2 - vx1, vy2 - vy1, "rgba(255, 255, 100, 0.8)");
            } else if (isPadMode(kp)) {
              const { pW, pH, pX, pY, cW, cH, cX, cY } = computePadLayout(rw, rh, cropW, cropH, w, h, x1, y1);
              ctx.fillStyle = "rgba(0, 0, 0, 0.7)";
              ctx.fillRect(x1, y1, w, h);
              if (kp === "pad_edge" && state._previewEnabled && state._previewImg) {
                renderToTmp(Math.max(1, Math.round(cW)), Math.max(1, Math.round(cH)),
                  state._previewImg, x1 * sX, y1 * sY, w * sX, h * sY);
                drawExtraPadFill(ctx, getEdgeEp(), pX, pY, pW, pH, cX, cY, cW, cH, _tmpCanvas);
              } else if (kp === "pad_color") {
                ctx.fillStyle = getFillColor();
                ctx.fillRect(pX, pY, pW, pH);
              }
              if (state._previewEnabled) {
                drawPreviewRegion(ctx, x1, y1, w, h, cX, cY, cW, cH);
              }
              drawDashedBorder(ctx, cX, cY, cW, cH, "rgba(100, 200, 255, 0.8)");
            }
          }

          const epBbox = getExtraPadding();
          const padModeHandledBbox = isPadMode(kp) && (tgtW > 0 || tgtH > 0);
          if (hasExtraPad(epBbox) && !padModeHandledBbox && !invertEnabled && !epBbox.isFirst && state._previewImg) {
            const epContent = computeContentDims(cropW, cropH);
            const epCW = epContent ? epContent.w : cropW, epCH = epContent ? epContent.h : cropH;
            const totalW2 = epCW + epBbox.left + epBbox.right, totalH2 = epCH + epBbox.top + epBbox.bottom;
            const { pW: pW2, pH: pH2, pX: pX2, pY: pY2 } = fitAspect(totalW2 / totalH2, w, h, x1, y1);
            ctx.fillStyle = "rgba(0, 0, 0, 0.7)"; ctx.fillRect(x1, y1, w, h);
            const cW2 = pW2 * (epCW / totalW2), cH2 = pH2 * (epCH / totalH2);
            const cX2 = pX2 + pW2 * (epBbox.left / totalW2), cY2 = pY2 + pH2 * (epBbox.top / totalH2);
            // Draw crop fitted within content area (letterbox, don't stretch)
            const cropAR = cropW / cropH;
            const { pW: iW2, pH: iH2, pX: iX2, pY: iY2 } = fitAspect(cropAR, cW2, cH2, cX2, cY2);
            const riW2 = Math.max(1, Math.round(iW2)), riH2 = Math.max(1, Math.round(iH2));
            renderToTmp(riW2, riH2, state._previewImg, x1 * sX, y1 * sY, w * sX, h * sY);
            drawExtraPadFill(ctx, epBbox, pX2, pY2, pW2, pH2, cX2, cY2, cW2, cH2, _tmpCanvas);
            drawPreviewRegion(ctx, x1, y1, w, h, iX2, iY2, iW2, iH2);
            drawDashedBorder(ctx, cX2, cY2, cW2, cH2, "rgba(100, 200, 255, 0.8)");
          }

          const { w: outW, h: outH } = getOutputDims(bbox) || { w: cropW, h: cropH };
          const boxLabel = state._bboxes.length > 1 ? `[${index + 1}] ` : "";
          const label = (tgtW > 0 || tgtH > 0)
            ? `${boxLabel}${cropW}×${cropH} → ${outW}×${outH}`
            : `${boxLabel}${cropW} × ${cropH}`;
          ctx.font = "12px sans-serif";
          const lw = ctx.measureText(label).width + 12;
          const lh = 20;
          const ly = y1 > lh + 4 ? y1 - lh - 2 : y1 + 4;
          ctx.fillStyle = "rgba(0, 0, 0, 0.7)";
          ctx.fillRect(x1, ly, lw, lh);
          ctx.fillStyle = "#fff";
          ctx.textAlign = "left";
          ctx.fillText(label, x1 + 6, ly + 14);
        } else if (!isActive) {
          // Inactive: show index label centered in bbox
          const boxLabel = `${index + 1}`;
          ctx.font = "bold 20px sans-serif";
          ctx.fillStyle = color.border;
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillText(boxLabel, x1 + w / 2, y1 + h / 2);
          ctx.textBaseline = "alphabetic";
        }

        if (isActive) {
          const cx = (x1 + x2) / 2, cy = (y1 + y2) / 2;
          Object.assign(ctx, { strokeStyle: color.border, lineWidth: 1 });
          ctx.beginPath();
          ctx.moveTo(cx - 5, cy); ctx.lineTo(cx + 5, cy);
          ctx.moveTo(cx, cy - 5); ctx.lineTo(cx, cy + 5);
          ctx.stroke();
        }
        if (!isActive) { ctx.strokeStyle = "rgba(0, 0, 0, 0.6)"; ctx.lineWidth = 4; ctx.strokeRect(x1, y1, w, h); }
        ctx.strokeStyle = color.border; ctx.lineWidth = 2; ctx.strokeRect(x1, y1, w, h);

        ctx.fillStyle = color.handle;
        const hs = isActive ? 5 : 4, s2 = hs * 2;
        const cx1 = Math.max(hs, Math.min(canvasEl.width - hs, x1));
        const cx2 = Math.max(hs, Math.min(canvasEl.width - hs, x2));
        const cy1 = Math.max(hs, Math.min(canvasEl.height - hs, y1));
        const cy2 = Math.max(hs, Math.min(canvasEl.height - hs, y2));
        for (const [hx, hy] of [[cx1, cy1], [cx2, cy1], [cx1, cy2], [cx2, cy2]])
          ctx.fillRect(hx - hs, hy - hs, s2, s2);
      }

      function drawCanvas() {
        const ctx = canvasCtx;
        ctx.clearRect(0, 0, canvasEl.width, canvasEl.height);
        _frameEp = _readExtraPadding();
        if (state._dragMode !== "pad_drag") _framePadXY = _readPadXY();
        const _kpVal = getKp(), { w: _tgtW, h: _tgtH } = getTgt();
        const hasBboxes = state._bboxes.length > 0;
        const showPreview = state._previewImg && state._previewEnabled;
        const _skipFullImage = !hasBboxes && showPreview && isPadMode(_kpVal) && (_tgtW > 0 || _tgtH > 0);

        const _epBase = getExtraPadding();
        const _isFirst = _epBase.isFirst, _hasFirstPad = _isFirst && hasExtraPad(_epBase);
        const maybeResize = (cw, ch) => {
          if (cw !== canvasEl.width || ch !== canvasEl.height) { setCanvasSize(cw, ch); ctx.clearRect(0, 0, cw, ch); }
        };
        if (showPreview) {
          if (_hasFirstPad) {
            const { w: eiw, h: eih } = getEffectiveImageDims(_epBase.mode !== "pad_edge");
            maybeResize(...clampToMaxCanvas(eiw + _epBase.left + _epBase.right, eih + _epBase.top + _epBase.bottom));
          } else if (state._previewImg) {
            maybeResize(...clampToMaxCanvas(...Object.values(getEffectiveImageDims(true))));
          }
        }

        if (showPreview && !_skipFullImage) {
          if (_hasFirstPad) {
            const { w: epImgW, h: epImgH } = getEffectiveImageDims(_epBase.mode !== "pad_edge");
            const totalW = epImgW + _epBase.left + _epBase.right, totalH = epImgH + _epBase.top + _epBase.bottom;
            const cX = canvasEl.width * (_epBase.left / totalW), cY = canvasEl.height * (_epBase.top / totalH);
            const cW = canvasEl.width * (epImgW / totalW), cH = canvasEl.height * (epImgH / totalH);
            const rcW = Math.max(1, Math.round(cW)), rcH = Math.max(1, Math.round(cH));
            // Render content (with replicate-rotate for pad_edge + rotation)
            renderToTmp(rcW, rcH);
            drawExtraPadFill(ctx, _epBase, 0, 0, canvasEl.width, canvasEl.height, cX, cY, cW, cH, _tmpCanvas);
            drawPreviewRegion(ctx, 0, 0, canvasEl.width, canvasEl.height, cX, cY, cW, cH);
          } else {
            if (state._rotation !== 0) { ctx.fillStyle = getFillColor(); ctx.fillRect(0, 0, canvasEl.width, canvasEl.height); }
            const { pW, pH, pX, pY } = fitAspect(_rotCanvas.width / _rotCanvas.height, canvasEl.width, canvasEl.height);
            ctx.drawImage(getRotatedPreview(), 0, 0, _rotCanvas.width, _rotCanvas.height, pX, pY, pW, pH);
          }
        } else if (!showPreview) {
          ctx.fillStyle = "#383838"; ctx.fillRect(0, 0, canvasEl.width, canvasEl.height);
          const divBy = getDivBy(), { w: lw0, h: lh0 } = getTgt();
          Object.assign(ctx, { fillStyle: "#888", font: "14px sans-serif", textAlign: "center" });
          ctx.fillText(`${roundDown(lw0, divBy) || canvasEl.width} × ${roundDown(lh0, divBy) || canvasEl.height}`,
            canvasEl.width / 2, canvasEl.height / 2);
        }

        // Manual mode: visualize extra padding on the placeholder
        if (!hasBboxes && !showPreview) {
          const _ep = getExtraPadding();
          if (hasExtraPad(_ep)) {
            const cW0 = canvasEl.width, cH0 = canvasEl.height;
            const { w: tw0, h: th0 } = getTgt();
            const rawW = tw0 > 0 ? tw0 : cW0;
            const rawH = th0 > 0 ? th0 : cH0;
            const content = computeContentDims(rawW, rawH);
            const contentW = content ? content.w : rawW;
            const contentH = content ? content.h : rawH;
            const totalW = contentW + _ep.left + _ep.right;
            const totalH = contentH + _ep.top + _ep.bottom;
            const { pW, pH, pX, pY } = fitAspect(totalW / totalH, cW0, cH0);
            const cW = pW * (contentW / totalW), cH = pH * (contentH / totalH);
            const cX = pX + pW * (_ep.left / totalW), cY = pY + pH * (_ep.top / totalH);
            ctx.fillStyle = "rgba(0, 0, 0, 0.5)";
            ctx.fillRect(0, 0, cW0, cH0);
            if (_ep.mode === "pad_color" || _ep.mode === "pad_crop_color") {
              ctx.fillStyle = getFillColor();
            } else {
              ctx.fillStyle = "#555";
            }
            ctx.fillRect(pX, pY, pW, pH);
            ctx.fillStyle = "#383838";
            ctx.fillRect(cX, cY, cW, cH);
            drawDashedBorder(ctx, cX, cY, cW, cH, "rgba(100, 200, 255, 0.8)");
            // Redraw dimension text on top
            const divBy = getDivBy(), { w: lw0, h: lh0 } = getTgt();
            Object.assign(ctx, { fillStyle: "#888", font: "14px sans-serif", textAlign: "center" });
            ctx.fillText(`${roundDown(lw0, divBy) || cW0} × ${roundDown(lh0, divBy) || cH0}`, cX + cW / 2, cY + cH / 2);
          }
        }

        // When no bboxes are drawn, show pad/crop preview for the full image (auto mode only)
        if (!hasBboxes && state._previewEnabled) {
          const cW0 = canvasEl.width, cH0 = canvasEl.height;
          if (state._previewImg) {
            const { w: tgtW, h: tgtH } = getTgt();
            const kp = getKp();
            // Multiplier mode: compute effective target from crop dims × multiplier
            if (kp === "multiplier") {
              const wmv = _getSubWidget("keep_proportion.width_mult")?.getValue() || 1.0;
              const hmv = _getSubWidget("keep_proportion.height_mult")?.getValue() || 1.0;
              if (wmv !== 1.0 || hmv !== 1.0) {
                const nw = state._previewImg.naturalWidth;
                const nh = state._previewImg.naturalHeight;
                drawStretchOverlay(ctx, (nw * wmv) / (nh * hmv), 0, 0, cW0, cH0);
              }
            }
            if ((tgtW > 0 || tgtH > 0) && (kp === "stretch" || isPadMode(kp) || kp === "crop")) {
              const { w: imgW, h: imgH } = getEffectiveImageDims(kp !== "pad_edge");
              const { rw, rh } = getEffectiveTargetDims(imgW, imgH);

              if (kp === "stretch") {
                drawStretchOverlay(ctx, rw / rh, 0, 0, cW0, cH0);
              } else if (isPadMode(kp)) {
                const epPad = getExtraPadding();
                const hasEp = hasExtraPad(epPad);
                // Full output = target. Content = target - extra padding.
                const fullTgtW = tgtW > 0 ? tgtW : imgW;
                const fullTgtH = tgtH > 0 ? tgtH : imgH;
                const contentTgtW = hasEp ? Math.max(1, fullTgtW - epPad.left - epPad.right) : fullTgtW;
                const contentTgtH = hasEp ? Math.max(1, fullTgtH - epPad.top - epPad.bottom) : fullTgtH;
                // Fit the full output to the canvas
                const { pW: outerW, pH: outerH, pX: outerX, pY: outerY } = fitAspect(fullTgtW / fullTgtH, cW0, cH0);
                // Content area within the output (offset by padding)
                const contentW = outerW * (contentTgtW / fullTgtW);
                const contentH = outerH * (contentTgtH / fullTgtH);
                const contentX = outerX + outerW * (epPad.left / fullTgtW);
                const contentY = outerY + outerH * (epPad.top / fullTgtH);
                // Image is sized to fit the content area, but positioned across the full output via pad_x/pad_y
                const imgRatio = Math.min(contentTgtW / imgW, contentTgtH / imgH);
                const scaledW = imgW * imgRatio, scaledH = imgH * imgRatio;
                const pW = outerW, pH = outerH, pX = outerX, pY = outerY;
                const cW = outerW * (scaledW / fullTgtW), cH = outerH * (scaledH / fullTgtH);
                const { cX, cY } = computePadContentPos(outerX, outerY, outerW, outerH, cW, cH);
                ctx.clearRect(0, 0, cW0, cH0);
                // Fill outer area (extra padding region)
                if (hasEp) {
                  ctx.fillStyle = getFillColor();
                  ctx.fillRect(outerX, outerY, outerW, outerH);
                }
                if (kp === "pad_edge") {
                  renderToTmp(Math.max(1, Math.round(cW)), Math.max(1, Math.round(cH)),
                    null, 0, 0, 0, 0, true);
                  ctx.drawImage(_tmpCanvas, 0, 0, _tmpCanvas.width, _tmpCanvas.height, cX, cY, cW, cH);
                  drawExtraPadFill(ctx, getEdgeEp(), pX, pY, pW, pH, cX, cY, cW, cH, _tmpCanvas);
                } else {
                  ctx.fillStyle = getFillColor();
                  ctx.fillRect(pX, pY, pW, pH);
                  drawPreviewRegion(ctx, 0, 0, cW0, cH0, cX, cY, cW, cH);
                }
                drawDashedBorder(ctx, cX, cY, cW, cH, "rgba(100, 200, 255, 0.8)");
                if (hasEp) drawDashedBorder(ctx, contentX, contentY, contentW, contentH, "rgba(255, 200, 100, 0.6)");
              } else if (kp === "crop") {
                const ratio = Math.max(rw / imgW, rh / imgH);
                const visW = rw / ratio, visH = rh / ratio;
                const offX = (imgW - visW) / 2, offY = (imgH - visH) / 2;
                const sc = Math.min(cW0 / imgW, cH0 / imgH);
                const ox = (cW0 - imgW * sc) / 2, oy = (cH0 - imgH * sc) / 2;
                const vx1 = ox + offX * sc, vy1 = oy + offY * sc;
                const vw = visW * sc, vh = visH * sc;
                dimSides(ctx, 0, 0, cW0, cH0, vx1, vy1, vw, vh);
                drawDashedBorder(ctx, vx1, vy1, vw, vh, "rgba(255, 255, 100, 0.8)");
              }
            }
          }
          const _ep = getExtraPadding();
          if (hasExtraPad(_ep) && state._previewImg && !_isFirst && !(isPadMode(_kpVal) && (_tgtW > 0 || _tgtH > 0))) {
            const { w: rawImgW, h: rawImgH } = getEffectiveImageDims(_ep.mode !== "pad_edge");
            const content = computeContentDims(rawImgW, rawImgH);
            const epImgW = content ? content.w : rawImgW;
            const epImgH = content ? content.h : rawImgH;
            const totalW = epImgW + _ep.left + _ep.right, totalH = epImgH + _ep.top + _ep.bottom;
            const { pW, pH, pX, pY } = fitAspect(totalW / totalH, cW0, cH0);
            ctx.clearRect(0, 0, cW0, cH0);
            const cW = pW * (epImgW / totalW), cH = pH * (epImgH / totalH);
            const cX = pX + pW * (_ep.left / totalW), cY = pY + pH * (_ep.top / totalH);
            // Draw padding fill, then image in content area (same approach as keep_proportion pad mode)
            if (_ep.mode === "pad_color") {
              ctx.fillStyle = getFillColor();
              ctx.fillRect(pX, pY, pW, pH);
              drawPreviewRegion(ctx, 0, 0, cW0, cH0, cX, cY, cW, cH);
            } else {
              // pad_edge: render content for edge fill source
              const rcW2 = Math.max(1, Math.round(cW)), rcH2 = Math.max(1, Math.round(cH));
              renderToTmp(rcW2, rcH2, null, 0, 0, 0, 0, _ep.isFirst);
              drawExtraPadFill(ctx, _ep, pX, pY, pW, pH, cX, cY, cW, cH, _tmpCanvas);
              drawPreviewRegion(ctx, 0, 0, cW0, cH0, cX, cY, cW, cH);
            }
            drawDashedBorder(ctx, cX, cY, cW, cH, "rgba(100, 200, 255, 0.8)");
          }

          drawGrid(ctx);
          drawRotationCross(ctx);
          if (!state._drawing) updateOutputSlotLabels();
          return;
        }

        if (state._activeIdx >= 0 && state._activeIdx < state._bboxes.length) {
          drawBbox(ctx, state._bboxes[state._activeIdx], state._activeIdx, true);
        }
        for (let i = 0; i < state._bboxes.length; i++) {
          if (i === state._activeIdx) continue;
          drawBbox(ctx, state._bboxes[i], i, false);
        }

        drawGrid(ctx);
        drawRotationCross(ctx);
        if (!state._drawing) updateOutputSlotLabels();
      }

      let _lastSlotLabelKey = "";
      const _origNames = new Map();
      function updateOutputSlotLabels() {
        const activeBbox = (state._activeIdx >= 0 && state._activeIdx < state._bboxes.length)
          ? state._bboxes[state._activeIdx] : null;
        let dims = activeBbox ? getOutputDims(activeBbox) : null;
        if (!dims) {
          const { w: tW, h: tH } = getTgt();
          const imgW = state._previewImg ? state._previewImg.naturalWidth
            : (tW > 0 ? tW : canvasEl.width);
          const imgH = state._previewImg ? state._previewImg.naturalHeight
            : (tH > 0 ? tH : canvasEl.height);
          const computed = computeOutputDims(imgW, imgH);
          if (computed && computed.w > 0 && computed.h > 0) {
            dims = computed;
          }
        }
        // Skip expensive DOM/canvas updates if nothing changed
        const key = `${dims?.w || 0},${dims?.h || 0},${state._bboxes.length}`;
        if (key === _lastSlotLabelKey) return;
        _lastSlotLabelKey = key;
        const hasBboxes = state._bboxes.length > 0;
        for (let i = 0; i < node.outputs.length; i++) {
          const out = node.outputs.at(i);
          let origName = _origNames.get(out.id);
          if (!origName) {
            if (out.name?.includes("width") || out.label?.includes("width")) origName = "width";
            else if (out.name?.includes("height") || out.label?.includes("height")) origName = "height";
            else if (out.name === "bbox") origName = "bbox";
            else if (out.name === "bbox_mask") origName = "bbox_mask";
            // Identify output/output_mask slots
            else if (out.name === "cropped" || out.name === "output") origName = "output";
            else if (out.name === "cropped_mask" || out.name === "output_mask") origName = "output_mask";
            if (origName) _origNames.set(out.id, origName);
          }
          if (origName === "width") {
            out.modify({ label: dims ? `${dims.w} width` : "width" });
          } else if (origName === "height") {
            out.modify({ label: dims ? `${dims.h} height` : "height" });
          }
          // The list icon is the named 'list' shape — the old `shape = 6` was
          // litegraph's RenderShape.GRID. `dir` was only ever reset to undefined
          // here, never set, so nothing follows it. The Vue-mode DOM fallback goes
          // too: it existed because shape and colour were canvas-only properties,
          // and modify() reaches both renderers.
          const listShape = state._bboxes.length > 1 ? "list" : "default";
          if (origName === "output" || origName === "output_mask") {
            out.modify({ shape: hasBboxes ? listShape : "default" });
          }
          if (origName === "bbox" || origName === "bbox_mask") {
            out.modify(hasBboxes
              ? { label: origName, color: null, colorWhenUnconnected: null, shape: listShape }
              : { label: " ", color: "transparent", colorWhenUnconnected: "transparent", shape: "list" });
          }
        }
      }

      function loadPreviewImage(src, preserveBbox) {
        const img = new Image();
        img.crossOrigin = "anonymous";
        img.onload = () => {
          state._previewImg = img;
          _rotCacheKey = "";
          invalidateGridStops();
          restoreCanvasToImage();
          if (state._previewEnabled && !preserveBbox) {
            state._bboxes = [];
            state._activeIdx = -1;
          }
          updateBboxWidgets();
          drawCanvas();
          fitNodeToImage(preserveBbox);
        };
        img.onerror = () => {
          console.warn("ImageTransformKJ: failed to load preview:", src);
        };
        img.src = src;
      }

      function loadPreviewFromTempFile(filename) {
        if (!filename) return;
        loadPreviewImage(comfy.backend.url(`/view?filename=${encodeURIComponent(filename)}&type=temp`), true);
      }

      function handleSourceChange(sources, preserveBbox) {
        if (sources.length === 0) {
          // Disconnected
          state._previewImg = null;
          node.setProperty("previewFile", undefined);
          if (state._previewEnabled) {
            state._bboxes = [];
            state._activeIdx = -1;
            updateBboxWidgets();
          }
          updateCanvasFromTargetDims();
          drawCanvas();
          return;
        }
        const src = sources[0];
        if (src.url) {
          loadPreviewImage(src.url, preserveBbox);
        }
      }

      let _configuring = false, _sourceResolved = false;
      // watchImageInputs() takes a raw node — it reads node.inputs[i].link and
      // walks node.graph — so its two jobs, resolving the connected source and
      // re-resolving when it changes, are done here through the published API.
      let _watchedSources = [];
      function sourceNodes() {
        const found = [];
        for (const input of node.inputs) {
          if (input.name !== "image") continue;
          const source = input.source();
          if (!source) continue;
          const srcNode = comfy.graph.node(source.nodeId);
          if (!srcNode) continue;
          // The first source the old code tried was another pack's DOM: the live
          // <video> element off VideoHelperSuite's "videopreview" widget.
          //
          // REFUSED, not a pending gap: reaching into another pack's widget object for
          // the element it mounted. Same refusal as utility.js resolveSourcePreview —
          // a mounted element's lifetime, readiness and name belong to whoever mounted
          // it, and none of the three is promised to this pack.
          //
          // DROPPED: a connected video is no longer previewed from that element, so
          // the crop preview shows a video source only once it resolves through a
          // "video" widget value or through the node's executed images.
          found.push({ srcNode, w: srcNode.widgets.get("image") || srcNode.widgets.get("video") });
        }
        return found;
      }
      function resolveSources() {
        const sources = [];
        for (const { srcNode, w } of sourceNodes()) {
          let fname = w?.getValue();
          if (!fname) {
            const [executed] = srcNode.getOutputImages();
            if (executed) sources.push({ url: executed, isVideo: false });
            continue;
          }
          let subfolder = "";
          const lastSlash = fname.lastIndexOf("/");
          if (lastSlash >= 0) { subfolder = fname.substring(0, lastSlash); fname = fname.substring(lastSlash + 1); }
          const url = comfy.backend.url(`/view?filename=${encodeURIComponent(fname)}&type=input&subfolder=${encodeURIComponent(subfolder)}`);
          sources.push({ url, isVideo: w.name === "video" });
        }
        return sources;
      }
      function onSources() {
        _sourceResolved = true;
        handleSourceChange(resolveSources(), _configuring);
      }
      function watchSources() {
        for (const off of _watchedSources) off();
        _watchedSources = sourceNodes()
          .filter(({ w }) => w)
          .map(({ w }) => w.on("change", () => setTimeout(onSources, 100)));
      }
      _unsubs.push(() => { for (const off of _watchedSources) off(); _watchedSources = []; });
      state.onConnectionsChanged = () => setTimeout(() => { watchSources(); onSources(); }, 100);

      // The node's own resize callback is not published; the mounted element's
      // box changes with the node, so observing it reports the same thing.
      let _lastResizeW = 0;
      const _resizeObserver = new ResizeObserver(() => {
        if (_resizing) return;
        const nodeW = node.getSize().width;
        if (nodeW === _lastResizeW) return;
        _lastResizeW = nodeW;
        const availW = Math.max(100, nodeW - 30);
        _resizing = true;
        if (state._previewEnabled) {
          // Auto mode: resize canvas pixel buffer to match node width
          const ar = canvasEl.height / canvasEl.width;
          const newW = Math.round(availW);
          const newH = Math.round(availW * ar);
          if (newW !== canvasEl.width || newH !== canvasEl.height) {
            rescaleBboxesTo(newW, newH);
            canvasEl.width = newW;
            canvasEl.height = newH;
            canvasEl.style.aspectRatio = `${newW} / ${newH}`;
            node.setProperty("canvasSize", [newW, newH]);
          }
          cropWidget.setHeight(newH + GRID_BAR_HEIGHT);
        } else {
          // Manual mode: keep pixel buffer fixed, CSS handles display scaling
          const displayedH = Math.round(canvasEl.height * (availW / canvasEl.width));
          cropWidget.setHeight(displayedH + GRID_BAR_HEIGHT);
        }
        drawCanvas();
        _resizing = false;
      });
      _resizeObserver.observe(wrapper);
      _unsubs.push(() => _resizeObserver.disconnect());

      state.onConfigure = () => {
        state._cropConfigured = true;
        if (node.getProperty("gridSize") !== undefined) {
          gridSlider.value = node.getProperty("gridSize");
          updateGridLabel();
        }
        if (node.getProperty("previewEnabled") !== undefined) {
          state._previewEnabled = node.getProperty("previewEnabled");
          updatePreviewBtn();
        }
        restoreBboxesFromWidget();
        if (node.getProperty("rotation") !== undefined) state._rotation = node.getProperty("rotation");
        if (node.getProperty("fillColor")) {
          colorInput.value = node.getProperty("fillColor");
          colorSwatch.style.background = node.getProperty("fillColor");
        }
        if (node.getProperty("gridColor")) {
          gridColorInput.value = node.getProperty("gridColor");
          gridColorSwatch.style.background = node.getProperty("gridColor");
        }

        if (node.getProperty("canvasSize")) {
          setCanvasSize(node.getProperty("canvasSize")[0], node.getProperty("canvasSize")[1]);
        }

        _configuring = true;
        _sourceResolved = false;
        setTimeout(() => {
          if (node.getProperty("gridSize") !== undefined) {
            gridSlider.value = node.getProperty("gridSize");
            updateGridLabel();
          }
          _configuring = false;
          if (!_sourceResolved) {
            if (node.getProperty("previewFile")) {
              loadPreviewFromTempFile(node.getProperty("previewFile"));
            } else {
              updateCanvasFromTargetDims();
              drawCanvas();
            }
          }
        }, 200);
      };

      state.onExecuted = (result) => {
        const filename = result.raw?.preview_filename?.[0];
        if (filename) {
          node.setProperty("previewFile", filename);
          loadPreviewFromTempFile(filename);
        }
      };

      // Initial draw
      setCanvasSize(400, 300);
      drawCanvas();
    });

    b.onConnectionsChanged((node, event) => {
      if (event.side !== "input") return;
      editors.get(node.id)?.onConnectionsChanged?.();
    });

    b.onConfigured((node) => editors.get(node.id)?.onConfigure?.());

    b.onExecuted((node, result) => editors.get(node.id)?.onExecuted?.(result));

    b.onRemoved((node) => editors.delete(node.id));
});
