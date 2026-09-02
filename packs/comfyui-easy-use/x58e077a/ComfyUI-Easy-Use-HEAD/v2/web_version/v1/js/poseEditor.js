import { comfy } from '/comfy/api/v2.js';
import { fabric } from "../lib/fabric.js";

fabric.Object.prototype.transparentCorners = false;
fabric.Object.prototype.cornerColor = "#108ce6";
fabric.Object.prototype.borderColor = "#108ce6";
fabric.Object.prototype.cornerSize = 10;

let connect_keypoints = [
  [0, 1],
  [1, 2],
  [2, 3],
  [3, 4],
  [1, 5],
  [5, 6],
  [6, 7],
  [1, 8],
  [8, 9],
  [9, 10],
  [1, 11],
  [11, 12],
  [12, 13],
  [0, 14],
  [14, 16],
  [0, 15],
  [15, 17],
];

let connect_color = [
  [0, 0, 255],
  [255, 0, 0],
  [255, 170, 0],
  [255, 255, 0],
  [255, 85, 0],
  [170, 255, 0],
  [85, 255, 0],
  [0, 255, 0],
  [0, 255, 85],
  [0, 255, 170],
  [0, 255, 255],
  [0, 170, 255],
  [0, 85, 255],
  [85, 0, 255],
  [170, 0, 255],
  [255, 0, 255],
  [255, 0, 170],
  [255, 0, 85],
];

const default_keypoints = [
  [241, 77],
  [241, 120],
  [191, 118],
  [177, 183],
  [163, 252],
  [298, 118],
  [317, 182],
  [332, 245],
  [225, 241],
  [213, 359],
  [215, 454],
  [270, 240],
  [282, 360],
  [286, 456],
  [232, 59],
  [253, 60],
  [225, 70],
  [260, 72],
];

// Handles hold no arbitrary properties, so the pose name the pack wrote to
// node.name, and the editor it hung off the node, live here by node id.
const poseState = new Map();

function poseNameOf(node) {
  return poseState.get(node.id)?.name || "";
}

class OpenPose {
  constructor(node, canvasElement) {
    this.lockMode = false;
    this.visibleEyes = true;
    this.flipped = false;
    this.node = node;
    this.name = poseNameOf(node);
    this.undo_history = LS_Poses[this.name].undo_history || [];
    this.redo_history = LS_Poses[this.name].redo_history || [];
    this.history_change = false;
    this.canvas = this.initCanvas(canvasElement);
    this.image = node.widgets.get("image");
  }

  setPose(keypoints) {
    this.canvas.clear();

    this.canvas.backgroundColor = "#000";

    const res = [];
    for (let i = 0; i < keypoints.length; i += 18) {
      const chunk = keypoints.slice(i, i + 18);
      res.push(chunk);
    }

    for (let item of res) {
      this.addPose(item);
      this.canvas.discardActiveObject();
    }
  }

  addPose(keypoints = undefined) {
    if (keypoints === undefined) {
      keypoints = default_keypoints;
    }

    const group = new fabric.Group();

    const makeCircle = (
      color,
      left,
      top,
      line1,
      line2,
      line3,
      line4,
      line5
    ) => {
      let c = new fabric.Circle({
        left: left,
        top: top,
        strokeWidth: 1,
        radius: 5,
        fill: color,
        stroke: color,
      });

      c.hasControls = c.hasBorders = false;
      c.line1 = line1;
      c.line2 = line2;
      c.line3 = line3;
      c.line4 = line4;
      c.line5 = line5;

      return c;
    };

    const makeLine = (coords, color) => {
      return new fabric.Line(coords, {
        fill: color,
        stroke: color,
        strokeWidth: 10,
        selectable: false,
        evented: false,
      });
    };

    const lines = [];
    const circles = [];

    for (let i = 0; i < connect_keypoints.length; i++) {
      // 接続されるidxを指定　[0, 1]なら0と1つなぐ
      const item = connect_keypoints[i];
      const line = makeLine(
        keypoints[item[0]].concat(keypoints[item[1]]),
        `rgba(${connect_color[i].join(", ")}, 0.7)`
      );
      lines.push(line);
      this.canvas.add(line);
    }

    for (let i = 0; i < keypoints.length; i++) {
      let list = [];

      connect_keypoints.filter((item, idx) => {
        if (item.includes(i)) {
          list.push(lines[idx]);
          return idx;
        }
      });
      const circle = makeCircle(
        `rgb(${connect_color[i].join(", ")})`,
        keypoints[i][0],
        keypoints[i][1],
        ...list
      );
      circle["id"] = i;
      circles.push(circle);
      group.addWithUpdate(circle);
    }

    this.canvas.discardActiveObject();
    this.canvas.setActiveObject(group);
    this.canvas.add(group);
    group.toActiveSelection();
    this.canvas.requestRenderAll();
  }

  initCanvas() {
    this.canvas = new fabric.Canvas(this.canvas, {
      backgroundColor: "#000",
      preserveObjectStacking: true,
    });

    const updateLines = (target) => {
      if ("_objects" in target) {
        const flipX = target.flipX ? -1 : 1;
        const flipY = target.flipY ? -1 : 1;
        this.flipped = flipX * flipY === -1;
        const showEyes = this.flipped ? !this.visibleEyes : this.visibleEyes;

        if (target.angle === 0) {
          const rtop = target.top;
          const rleft = target.left;
          for (const item of target._objects) {
            let p = item;
            p.scaleX = 1;
            p.scaleY = 1;
            const top =
              rtop +
              p.top * target.scaleY * flipY +
              (target.height * target.scaleY) / 2;
            const left =
              rleft +
              p.left * target.scaleX * flipX +
              (target.width * target.scaleX) / 2;
            p["_top"] = top;
            p["_left"] = left;
            if (p["id"] === 0) {
              p.line1 && p.line1.set({ x1: left, y1: top });
            } else {
              p.line1 && p.line1.set({ x2: left, y2: top });
            }
            if (p["id"] === 14 || p["id"] === 15) {
              p.radius = showEyes ? 5 : 0;
              if (p.line1) p.line1.strokeWidth = showEyes ? 10 : 0;
              if (p.line2) p.line2.strokeWidth = showEyes ? 10 : 0;
            }
            p.line2 && p.line2.set({ x1: left, y1: top });
            p.line3 && p.line3.set({ x1: left, y1: top });
            p.line4 && p.line4.set({ x1: left, y1: top });
            p.line5 && p.line5.set({ x1: left, y1: top });
          }
        } else {
          const aCoords = target.aCoords;
          const center = {
            x: (aCoords.tl.x + aCoords.br.x) / 2,
            y: (aCoords.tl.y + aCoords.br.y) / 2,
          };
          const rad = (target.angle * Math.PI) / 180;
          const sin = Math.sin(rad);
          const cos = Math.cos(rad);

          for (const item of target._objects) {
            let p = item;
            const p_top = p.top * target.scaleY * flipY;
            const p_left = p.left * target.scaleX * flipX;
            const left = center.x + p_left * cos - p_top * sin;
            const top = center.y + p_left * sin + p_top * cos;
            p["_top"] = top;
            p["_left"] = left;
            if (p["id"] === 0) {
              p.line1 && p.line1.set({ x1: left, y1: top });
            } else {
              p.line1 && p.line1.set({ x2: left, y2: top });
            }
            if (p["id"] === 14 || p["id"] === 15) {
              p.radius = showEyes ? 5 : 0.3;
              if (p.line1) p.line1.strokeWidth = showEyes ? 10 : 0;
              if (p.line2) p.line2.strokeWidth = showEyes ? 10 : 0;
            }
            p.line2 && p.line2.set({ x1: left, y1: top });
            p.line3 && p.line3.set({ x1: left, y1: top });
            p.line4 && p.line4.set({ x1: left, y1: top });
            p.line5 && p.line5.set({ x1: left, y1: top });
          }
        }
      } else {
        var p = target;
        if (p["id"] === 0) {
          p.line1 && p.line1.set({ x1: p.left, y1: p.top });
        } else {
          p.line1 && p.line1.set({ x2: p.left, y2: p.top });
        }
        p.line2 && p.line2.set({ x1: p.left, y1: p.top });
        p.line3 && p.line3.set({ x1: p.left, y1: p.top });
        p.line4 && p.line4.set({ x1: p.left, y1: p.top });
        p.line5 && p.line5.set({ x1: p.left, y1: p.top });
      }
      this.canvas.renderAll();
    };

    this.canvas.on("object:moving", (e) => {
      updateLines(e.target);
    });

    this.canvas.on("object:scaling", (e) => {
      updateLines(e.target);
      this.canvas.renderAll();
    });

    this.canvas.on("object:rotating", (e) => {
      updateLines(e.target);
      this.canvas.renderAll();
    });

    this.canvas.on("object:modified", () => {
      if (
        this.lockMode ||
        this.canvas.getActiveObject().type == "activeSelection"
      )
        return;
      this.undo_history.push(this.getJSON());
      this.redo_history.length = 0;
      this.history_change = true;
      this.uploadPoseFile(this.name);
    });

    if (!LS_Poses[this.name].undo_history.length) {
      this.setPose(default_keypoints);
      this.undo_history.push(this.getJSON());
    }
    return this.canvas;
  }

  undo() {
    if (this.undo_history.length > 0) {
      this.lockMode = true;
      if (this.undo_history.length > 1)
        this.redo_history.push(this.undo_history.pop());

      const content = this.undo_history[this.undo_history.length - 1];
      this.loadPreset(content);
      this.canvas.renderAll();
      this.lockMode = false;
      this.history_change = true;
      this.uploadPoseFile(this.name);
    }
  }

  redo() {
    if (this.redo_history.length > 0) {
      this.lockMode = true;
      const content = this.redo_history.pop();
      this.undo_history.push(content);
      this.loadPreset(content);
      this.canvas.renderAll();
      this.lockMode = false;
      this.history_change = true;
      this.uploadPoseFile(this.name);
    }
  }

  resetCanvas() {
    this.canvas.clear();
    this.canvas.backgroundColor = "#000";
    this.addPose();
  }

  updateHistoryData() {
    if (this.history_change) {
      LS_Poses[this.name].undo_history = this.undo_history;
      LS_Poses[this.name].redo_history = this.redo_history;
      LS_Save();
      this.history_change = false;
    }
  }

  uploadPoseFile(fileName) {
    // Upload pose to temp folder ComfyUI

    const uploadFile = async (blobFile) => {
      try {
        const resp = await fetch("/upload/image", {
          method: "POST",
          body: blobFile,
        });

        if (resp.status === 200) {
          const data = await resp.json();

          const values = this.image.getOptions()?.values;
          if (Array.isArray(values) && !values.includes(data.name)) {
            this.image.setOption("values", [...values, data.name]);
          }

          this.image.setValue(data.name);
          this.updateHistoryData();
        } else {
          alert(resp.status + " - " + resp.statusText);
        }
      } catch (error) {
        console.error(error);
      }
    };

    this.canvas.lowerCanvasEl.toBlob(function (blob) {
      let formData = new FormData();
      formData.append("image", blob, fileName);
      formData.append("overwrite", "true");
      formData.append("type", "temp");
      uploadFile(formData);
    }, "image/png");
    // - end

    // DROPPED: the pack reassigned the image widget's callback to a function
    // whose body read `this.image` off the widget, which is undefined - it
    // threw on every change and the user's selection stuck anyway. Reproducing
    // it as an on("change") listener would newly force the combo back to the
    // pose file, which is a behaviour change, so the dead callback is gone.
  }

  getJSON() {
    const json = {
      keypoints: this.canvas
        .getObjects()
        .filter((item) => {
          if (item.type === "circle") return item;
        })
        .map((item) => {
          return [Math.round(item.left), Math.round(item.top)];
        }),
    };

    return json;
  }

  loadPreset(json) {
    try {
      if (json["keypoints"].length % 18 === 0) {
        this.setPose(json["keypoints"]);
      } else {
        throw new Error("keypoints is invalid");
      }
    } catch (e) {
      console.error(e);
    }
  }
}

// Create OpenPose widget
function createOpenPose(node, inputName, inputData) {
  poseState.set(node.id, { name: inputName, openPose: null });

  // Fabric canvas
  let canvasOpenPose = document.createElement("canvas");
  const openPose = new OpenPose(node, canvasOpenPose);
  poseState.get(node.id).openPose = openPose;

  openPose.canvas.setWidth(512);
  openPose.canvas.setHeight(512);

  let widgetCombo = node.widgets.all().filter((w) => w.widgetType === "combo");
  widgetCombo[0].setValue(inputName);

  // Create elements undo, redo, clear history
  let panelButtons = document.createElement("div"),
    undoButton = document.createElement("button"),
    redoButton = document.createElement("button"),
    historyClearButton = document.createElement("button");

  panelButtons.className = "panelButtons comfy-menu-btns";
  undoButton.textContent = "⟲";
  redoButton.textContent = "⟳";
  historyClearButton.textContent = "✖";
  undoButton.title = "Undo";
  redoButton.title = "Redo";
  historyClearButton.title = "Clear History";

  undoButton.addEventListener("click", () => openPose.undo());
  redoButton.addEventListener("click", () => openPose.redo());
  historyClearButton.addEventListener("click", () => {
    if (confirm(`Delete all pose history of a node "${inputName}"?`)) {
      openPose.undo_history = [];
      openPose.redo_history = [];
      openPose.setPose(default_keypoints);
      openPose.undo_history.push(openPose.getJSON());
      openPose.history_change = true;
      openPose.updateHistoryData();
    }
  });

  panelButtons.appendChild(undoButton);
  panelButtons.appendChild(redoButton);
  panelButtons.appendChild(historyClearButton);
  openPose.canvas.wrapperEl.appendChild(panelButtons);

  // Add buttons add, reset, undo, redo poses
  const addPoseButton = node.widgets.add({
    type: "button",
    name: "Add pose",
    value: "add_pose",
  });
  addPoseButton.on("activate", () => openPose.addPose());

  const resetPoseButton = node.widgets.add({
    type: "button",
    name: "Reset pose",
    value: "reset_pose",
  });
  resetPoseButton.on("activate", () => openPose.resetCanvas());

  // Replaces addCustomWidget plus the widget's own draw(), which existed only
  // to reposition a document.body-parented fabric canvas over the node every
  // frame from the canvas transform. Mounted, the widget layer places it.
  //
  // The legacy custom widget carried neither a serialize flag nor options, so
  // it occupied a widgets_values slot and was sent as a prompt input;
  // serialize/sendToPrompt keep both. Its cell was `null` before and is `""`
  // now — the pack never reads it, and keeping the slot is what matters for
  // positional restore.
  // Was `visible = app.canvas.ds.scale > 0.5` inside that same per-frame draw.
  // The zoom is derived from the node rather than read off the renderer, which
  // is how the published API answers it: getScreenRect() is the node's rectangle
  // in screen pixels and getBounds() the same rectangle in graph units, so the
  // ratio is the scale. onViewportChanged fires on pan, zoom and resize — every
  // moment the old draw was re-deciding this.
  const applyZoomVisibility = () => {
    const screen = node.getScreenRect();
    const bounds = node.getBounds();
    if (!screen || !bounds.width) return;
    panelButtons.hidden = screen.width / bounds.width <= 0.5;
  };
  const stopWatchingZoom = comfy.onViewportChanged(applyZoomVisibility);

  node.widgets.mount({
    name: `w${inputName}`,
    defaultValue: "",
    serialize: true,
    sendToPrompt: true,
    render: (container) => {
      container.append(openPose.canvas.wrapperEl);
      applyZoomVisibility();
    },
    destroy: () => {
      stopWatchingZoom();
      openPose.canvas.wrapperEl.remove();
    },
  });

  // COSMETIC: the undo / redo / clear buttons no longer have their width, height
  // and font size recomputed from the canvas transform on every frame. A mounted
  // widget is scaled by the layer that places it, so they follow the node's zoom
  // without the pack doing the arithmetic; what is lost is that the pack picked
  // 28x22px at 10px text and now the host picks.
}

window.LS_Poses = {};
function LS_Save() {
  ///console.log("Save:", LS_Poses);
  localStorage.setItem("ComfyUI_Poses", JSON.stringify(LS_Poses));
}

let poseEditorStyle = document.createElement("style");
poseEditorStyle.innerText = `.panelButtons{
      position: absolute;
      padding: 4px;
      display: flex;
      gap: 4px;
      flex-direction: column;
      width: fit-content;
    }
    .panelButtons button:last-child{
      border-color: var(--error-text);
      color: var(--error-text) !important;
    }

    `;
document.head.appendChild(poseEditorStyle);

comfy.defs.extend("easy poseEditor", (b) => {
  b.onCreated((node) => {
    let openPoseNode = comfy.graph.nodes().filter(
        (wi) => {wi.type == "easy poseEditor"}
      ),
      nodeName = `Pose_${openPoseNode.length}`,
      nodeNamePNG = `${nodeName}.png`;

    console.log(`Create PoseNode: ${nodeName}`);

    LS_Poses =
      localStorage.getItem("ComfyUI_Poses") &&
      JSON.parse(localStorage.getItem("ComfyUI_Poses"));
    if (!LS_Poses) {
      localStorage.setItem("ComfyUI_Poses", JSON.stringify({}));
      LS_Poses = JSON.parse(localStorage.getItem("ComfyUI_Poses"));
    }

    if (!Object.hasOwn(LS_Poses, nodeNamePNG)) {
      LS_Poses[nodeNamePNG] = {
        undo_history: [],
        redo_history: [],
      };
      LS_Save();
    }

    createOpenPose(node, nodeNamePNG, {});
    setTimeout(() => {
      poseState.get(node.id)?.openPose.uploadPoseFile(nodeNamePNG);
    }, 1);

    node.setSize({ width: 530, height: 620 });
  });

  // The pack's setup() walked every node once the page had loaded to restore
  // each editor's last pose. comfy.onReady would reproduce that literally, but
  // it would miss every workflow opened afterwards; per node, on configure, is
  // where the restore belongs.
  b.onConfigured((node) => {
    const openPose = poseState.get(node.id)?.openPose;
    const name = poseNameOf(node);
    if (!openPose || !node.widgets.get("image") || !Object.hasOwn(LS_Poses, name)) return;
    console.log(`Setup PoseNode: ${name}`);
    let pose_ls = LS_Poses[name].undo_history;
    openPose.loadPreset(
      pose_ls.length > 0
        ? pose_ls[pose_ls.length - 1]
        : { keypoints: default_keypoints }
    );
  });

  b.onRemoved((node) => {
    const name = poseNameOf(node);
    if (Object.hasOwn(LS_Poses, name)) {
      delete LS_Poses[name];
      LS_Save();
    }
    poseState.delete(node.id);
  });
});
