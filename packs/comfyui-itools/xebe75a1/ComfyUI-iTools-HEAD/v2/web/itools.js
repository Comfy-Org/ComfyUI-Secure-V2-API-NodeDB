"use strict";

import { comfy } from "/comfy/api/v2.js";
import { STYLE_NAMES } from "./style_names.js";


/** The frontend census is behavioral: the upstream pack has twenty extension
 * registrations plus one independently registered sidebar. */
export const FRONTEND_INTENTS = Object.freeze([
  "settings-manager",
  "appearance",
  "checkerboard-policy",
  "compare-ui",
  "crop-ui",
  "dev-dom-node",
  "image-adjust-ui",
  "instructor-ui",
  "line-loader-policy",
  "load-images-warning",
  "paint-ui",
  "preview-history-ui",
  "prompt-styler-dynamic-styles",
  "prompt-styler-extra-dynamic-styles",
  "regex-helper",
  "prompt-builder-ui",
  "dev-test-ui",
  "prompt-record-history",
  "text-preview",
  "get-prompt-command",
  "prompt-library-sidebar",
]);

const LIBRARY_FILE = "itools/prompt-library/library.json";
const MAX_IMAGE_BYTES = 16 * 1024 * 1024;
const MAX_LIBRARY_ITEMS = 500;
const MAX_HISTORY_ITEMS = 40;
const nodeState = new Map();

const SETTINGS = /** @type {const} */ ([
  {
    id: "iTools.Nodes.More Styles",
    name: "Load extra styles",
    type: "boolean",
    defaultValue: true,
    tooltip: "Include iTools' additional bundled style catalogs.",
  },
  {
    id: "iTools.Nodes.Compare Mode",
    name: "Image Compare mode",
    type: "combo",
    defaultValue: "makadi",
    options: ["makadi", "rgthree"],
  },
  {
    id: "iTools.Nodes.Auto Resize",
    name: "Auto resize nodes when created",
    type: "boolean",
    defaultValue: false,
  },
  {
    id: "iTools.Nodes.Auto Color",
    name: "Auto color nodes when created",
    type: "boolean",
    defaultValue: true,
  },
  {
    id: "iTools.Nodes.Mask Tool",
    name: "Allow background removal in iTools Paint",
    type: "boolean",
    defaultValue: false,
    tooltip: "Uses the hash-pinned RMBG-2.0 weight declared by this node pack.",
  },
  {
    id: "iTools.Nodes.Dev Mode2",
    name: "Enable dev nodes",
    type: "boolean",
    defaultValue: false,
  },
  {
    id: "iTools.Nodes.Dev Mode",
    name: "Enable beta nodes",
    type: "boolean",
    defaultValue: true,
  },
  {
    id: "iTools.Nodes.Node Display Name Preferences",
    name: "Use simple names for iTools nodes",
    type: "boolean",
    defaultValue: false,
  },
  {
    id: "iTools.Tabs.menuTab",
    name: "Enable the iTools prompt command in the action bar",
    type: "boolean",
    defaultValue: false,
  },
  {
    id: "iTools.Tabs.Side Tab",
    name: "Enable Prompt Library in the sidebar",
    type: "boolean",
    defaultValue: true,
  },
]);

for (const setting of SETTINGS) {
  comfy.settings.declare({
    ...setting,
    category: ["iTools"],
    onChange(value, previous) {
      if (previous !== undefined && previous !== value) {
        comfy.commands.notify({
          severity: "info",
          summary: "iTools setting changed",
          detail: "The change applies to newly opened or newly created controls.",
          life: 2500,
        });
      }
    },
  });
}


function stateKey(node) {
  return `${String(node.graphId ?? "")}:${String(node.id)}`;
}


function element(tag, properties = {}, children = []) {
  const value = document.createElement(tag);
  for (const [name, property] of Object.entries(properties)) {
    if (name === "style" && property && typeof property === "object") {
      Object.assign(value.style, property);
    } else if (name.startsWith("on") && typeof property === "function") {
      value.addEventListener(name.slice(2).toLowerCase(), property);
    } else if (name in value) {
      value[name] = property;
    } else {
      value.setAttribute(name, String(property));
    }
  }
  for (const child of Array.isArray(children) ? children : [children]) {
    if (child === null || child === undefined) continue;
    value.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return value;
}


function panelStyle(container) {
  Object.assign(container.style, {
    boxSizing: "border-box",
    display: "flex",
    flexDirection: "column",
    gap: "6px",
    width: "100%",
    height: "100%",
    padding: "8px",
    overflow: "auto",
    color: "var(--input-text, #ddd)",
    background: "var(--comfy-input-bg, #222)",
    font: "12px system-ui, sans-serif",
  });
}


function row(...children) {
  return element("div", {
    style: { display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap" },
  }, children);
}


function button(label, run, title = "") {
  return element("button", { type: "button", textContent: label, title, onclick: run });
}


function parseObject(value, fallback = {}) {
  if (value && typeof value === "object" && !Array.isArray(value)) return { ...value };
  if (typeof value !== "string") return { ...fallback };
  try {
    const parsed = JSON.parse(value);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? parsed
      : { ...fallback };
  } catch (_error) {
    return { ...fallback };
  }
}


function imageRecordUrl(record) {
  if (!record || typeof record !== "object") return "";
  if (typeof record.url === "string") return record.url;
  if (typeof record.filename !== "string") return "";
  const query = new URLSearchParams({
    filename: record.filename,
    subfolder: typeof record.subfolder === "string" ? record.subfolder : "",
    type: typeof record.type === "string" ? record.type : "output",
  });
  return comfy.backend.url(`/view?${query.toString()}`);
}


function bytesToDataUrl(bytes, mimeType) {
  let binary = "";
  const chunk = 0x8000;
  for (let offset = 0; offset < bytes.length; offset += chunk) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + chunk));
  }
  return `data:${mimeType || "application/octet-stream"};base64,${btoa(binary)}`;
}


async function pickImage() {
  const picked = await comfy.files.pick({
    mimeTypes: ["image/png", "image/jpeg", "image/webp", "image/gif"],
    extensions: ["png", "jpg", "jpeg", "webp", "gif"],
    maxBytes: MAX_IMAGE_BYTES,
  });
  if (!picked) return undefined;
  return {
    name: picked.name,
    dataUrl: bytesToDataUrl(picked.bytes, picked.type || "image/png"),
  };
}


function readClipboardImage(event, callback) {
  const files = event.clipboardData?.files;
  const file = files && files.length ? files[0] : undefined;
  if (!file || !String(file.type).startsWith("image/") || file.size > MAX_IMAGE_BYTES) return;
  event.preventDefault();
  const reader = new FileReader();
  reader.addEventListener("load", () => callback(String(reader.result || "")), { once: true });
  reader.readAsDataURL(file);
}


function setWidgetJson(widget, value) {
  widget?.setValue(JSON.stringify(value));
}


function valuesForStyle(file) {
  const all = STYLE_NAMES[file] || ["none"];
  return all.length ? all : ["none"];
}


function syncStylePair(node, fileName, styleName) {
  const file = node.widgets.get(fileName);
  const style = node.widgets.get(styleName);
  if (!file || !style) return () => {};
  const update = () => {
    const values = valuesForStyle(String(file.getValue() || ""));
    style.setOption("values", values);
    if (!values.includes(String(style.getValue()))) style.setValue(values[0]);
  };
  const off = file.on("change", update);
  update();
  return off;
}


// Settings-driven appearance is presentation only and stays per node.
const GREEN_TYPES = [
  "iToolsPromptBuilder", "iToolsInstructorNode", "iToolsPromptStyler",
  "iToolsPromptStylerExtra", "iToolsTextReplacer", "iToolsRegexNode",
  "iToolsPromptRecord",
];
const BLUE_TYPES = [
  "iToolsImageAdjust", "iToolsLoadImagePlus", "iToolsCompareImage",
  "iToolsPreviewImage",
];
const RESIZE = {
  iToolsPreviewText: [240, 80],
  iToolsTextReplacer: [200, 80],
  iToolsRegexNode: [280, 130],
  iToolsAddOverlay: [240, 180],
  iToolsLineLoader: [200, 120],
  iToolsGridFiller: [240, 220],
  iToolsLoadImagePlus: [210, 180],
  iToolsCheckerBoard: [270, 260],
};

comfy.defs.extend([...GREEN_TYPES, ...BLUE_TYPES, ...Object.keys(RESIZE)], (builder) => {
  builder.onCreated((node, event) => {
    if (!event.restored && comfy.settings.get("iTools.Nodes.Auto Color") !== false) {
      if (GREEN_TYPES.includes(node.comfyClass)) {
        node.setColor("#232");
        node.setBgColor("#353");
      } else if (BLUE_TYPES.includes(node.comfyClass)) {
        node.setColor("#2a363b");
      }
    }
    const desired = RESIZE[node.comfyClass];
    if (desired && (node.comfyClass === "iToolsPreviewText"
      || comfy.settings.get("iTools.Nodes.Auto Resize") === true)) {
      node.setSize({ width: desired[0], height: desired[1] });
    }
  });
});


for (const [type, policy] of [
  ["iToolsCheckerBoard", "fixed"],
  ["iToolsLineLoader", "increment"],
]) {
  comfy.defs.extend(type, (builder) => {
    builder.onCreated((node) => {
      const control = node.widgets.get("control_after_generate");
      if (control) control.setValue(policy);
    });
  });
}


comfy.defs.extend("iToolsLoadImages", (builder) => {
  builder.onCreated((node) => {
    const mode = node.widgets.get("output_mode");
    mode?.on("change", (value) => {
      if (value === "batch") {
        comfy.commands.notify({
          severity: "warn",
          summary: "iTools batch mode",
          detail: "Every image in a batch must have the same dimensions.",
          life: 3500,
        });
      }
    });
  });
});


comfy.defs.extend("iToolsPromptStyler", (builder) => {
  builder.onCreated((node) => {
    const off = syncStylePair(node, "style_file", "template_name");
    nodeState.set(stateKey(node), { subscriptions: [off] });
  });
  builder.onRemoved((node) => {
    const state = nodeState.get(stateKey(node));
    for (const off of state?.subscriptions || []) off();
    nodeState.delete(stateKey(node));
  });
});


comfy.defs.extend("iToolsPromptStylerExtra", (builder) => {
  builder.onCreated((node) => {
    const subscriptions = [
      syncStylePair(node, "base_file", "base_style"),
      syncStylePair(node, "second_file", "second_style"),
      syncStylePair(node, "third_file", "third_style"),
      syncStylePair(node, "fourth_file", "fourth_style"),
    ];
    const reset = node.widgets.add({
      type: "button", name: "itools_reset_styles", value: null, serialize: false,
    });
    reset.setLabel("Reset all styles");
    subscriptions.push(reset.on("activate", () => {
      const defaults = [
        ["base_file", "basic.yaml", "base_style"],
        ["second_file", "camera.yaml", "second_style"],
        ["third_file", "artist.yaml", "third_style"],
        ["fourth_file", "mood.yaml", "fourth_style"],
      ];
      for (const [fileName, fileValue, styleName] of defaults) {
        node.widgets.get(fileName)?.setValue(fileValue);
        node.widgets.get(styleName)?.setValue("none");
      }
    }));
    nodeState.set(stateKey(node), { subscriptions });
  });
  builder.onRemoved((node) => {
    const state = nodeState.get(stateKey(node));
    for (const off of state?.subscriptions || []) off();
    nodeState.delete(stateKey(node));
  });
});


const REGEX_PATTERNS = Object.freeze({
  custom: "",
  any_character: String.raw`.`, digit: String.raw`\d`, non_digit: String.raw`\D`,
  whitespace: String.raw`\s`, non_whitespace: String.raw`\S`,
  word_character: String.raw`\w`, non_word_character: String.raw`\W`,
  all_caps: String.raw`\b[A-Z]+\b`, all_lower: String.raw`\b[a-z]+\b`,
  integer: String.raw`\b-?\d+\b`, floating_point: String.raw`-?\d+(\.\d+)?`,
  no_numbers: String.raw`\b[^0-9]+\b`,
  email: String.raw`\b[a-zA-Z0-9._%+-]+@(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b`,
  phone_number: String.raw`^\d{3}-?\d{3}-?\d{4}$`,
  double_quoted: String.raw`"([^"]*)"`, single_quoted: String.raw`'([^']*)'`,
  in_parentheses: String.raw`\((.*?)\)`, angle_brackets: String.raw`<([^>]*)>`,
  starts_with_abc: String.raw`\babc\w*`, ends_with_xyz: String.raw`\b\w*xyz\b`,
  contains_hello: "hello", cat_or_dog: "cat|dog",
});

comfy.defs.extend("iToolsRegexNode", (builder) => {
  builder.onCreated((node) => {
    const pattern = node.widgets.get("regex_pattern");
    const picker = node.widgets.get("pattern_picker");
    const matched = node.widgets.get("replace_match");
    const unmatched = node.widgets.get("replace_non_match");
    if (!pattern || !picker) return;
    picker.setOption("values", Object.keys(REGEX_PATTERNS));
    const subscriptions = [];
    subscriptions.push(pattern.on("change", () => picker.setValue("custom")));
    subscriptions.push(picker.on("change", (value) => {
      const name = String(value);
      if (name !== "custom" && Object.hasOwn(REGEX_PATTERNS, name)) {
        pattern.setValue(REGEX_PATTERNS[name]);
      }
    }));
    const relabel = () => {
      const hasMatch = Boolean(matched?.getValue());
      const hasNonMatch = Boolean(unmatched?.getValue());
      const label = hasMatch && hasNonMatch ? "replace"
        : hasMatch ? "replace_match" : hasNonMatch ? "replace_non_match" : "match";
      node.outputs.at(0)?.modify({ label });
    };
    if (matched) subscriptions.push(matched.on("change", relabel));
    if (unmatched) subscriptions.push(unmatched.on("change", relabel));
    relabel();
    nodeState.set(stateKey(node), { subscriptions });
  });
  builder.onRemoved((node) => {
    const state = nodeState.get(stateKey(node));
    for (const off of state?.subscriptions || []) off();
    nodeState.delete(stateKey(node));
  });
});


function mountDomCounter(node) {
  node.setSize({ width: 220, height: 260 });
  node.widgets.mount({
    name: "CounterWidget",
    height: 180,
    defaultValue: { count: 0, text: "Notes here..." },
    render(container, mounted) {
      panelStyle(container);
      let state = parseObject(mounted.get(), { count: 0, text: "Notes here..." });
      const count = element("strong", { textContent: String(Number(state.count) || 0) });
      const notes = element("textarea", {
        value: String(state.text || ""), rows: 5, style: { width: "100%" },
      });
      const commit = () => {
        state = { count: Number(count.textContent) || 0, text: notes.value };
        mounted.set(state);
      };
      notes.addEventListener("input", commit);
      container.append(
        element("strong", { textContent: "Counter" }),
        row(button("−", () => { count.textContent = String((Number(count.textContent) || 0) - 1); commit(); }),
          count,
          button("+", () => { count.textContent = String((Number(count.textContent) || 0) + 1); commit(); })),
        notes,
      );
      mounted.onChange((value) => {
        state = parseObject(value, state);
        count.textContent = String(Number(state.count) || 0);
        notes.value = String(state.text || "");
      });
    },
  });
}

comfy.defs.extend("iToolsDomNode", (builder) => {
  builder.onCreated(mountDomCounter);
});


comfy.defs.extend("iToolsTestNode", (builder) => {
  builder.onCreated((node) => {
    node.setSize({ width: 200, height: 140 });
    node.widgets.mount({
      name: "Click",
      height: 70,
      defaultValue: 0,
      render(container, mounted) {
        panelStyle(container);
        const value = element("strong", { textContent: String(Number(mounted.get()) || 0) });
        container.append(row(value, button("Add click", () => {
          const next = (Number(value.textContent) || 0) + 1;
          value.textContent = String(next);
          mounted.set(next);
        }), button("Set…", async () => {
          const entered = await comfy.ui.prompt({ label: "Click count", value: value.textContent });
          if (entered === undefined) return;
          const next = Number.parseInt(entered, 10) || 0;
          value.textContent = String(next);
          mounted.set(next);
        })));
        mounted.onChange((next) => { value.textContent = String(Number(next) || 0); });
      },
    });
  });
});


const INSTRUCTION_TEMPLATES = Object.freeze({
  "Background swap": "Replace the background with {value} while preserving the subject and edges.",
  "Environment mood": "Change the environment mood to {value}.",
  "Style transfer": "Render the image in {value} style while preserving composition.",
  "Material change": "Change the primary material to {value}.",
  "Pose modification": "Modify the subject pose to {value}.",
  "Expression edit": "Change the facial expression to {value}.",
  "Outfit change": "Change the outfit to {value}.",
  "Color grade": "Apply a {value} color grade.",
  "Add prop": "Add {value} naturally to the scene.",
  "Remove object": "Remove {value} and reconstruct the background.",
  "High-end retouch": "Retouch the image with {value}, keeping realistic texture.",
  "Lighting fix": "Adjust the lighting to {value}.",
  "Background blur": "Apply {value} background blur while keeping the subject sharp.",
  "Weather effect": "Add {value} weather while retaining scene consistency.",
  "Camera angle": "Recompose the scene from {value} camera angle.",
  "Motion blur": "Apply {value} motion blur to the moving subject only.",
});

comfy.defs.extend("iToolsInstructorNode", (builder) => {
  builder.onCreated((node) => {
    node.setSize({ width: 320, height: 300 });
    node.widgets.mount({
      name: "InstructorWidget",
      height: 220,
      defaultValue: { template: "Background swap", value: "", finalText: "" },
      render(container, mounted) {
        panelStyle(container);
        let state = parseObject(mounted.get());
        const select = element("select");
        for (const name of Object.keys(INSTRUCTION_TEMPLATES)) {
          select.append(element("option", { value: name, textContent: name }));
        }
        select.value = state.template || Object.keys(INSTRUCTION_TEMPLATES)[0];
        const value = element("textarea", {
          rows: 4, value: String(state.value || ""), placeholder: "Describe the requested change",
          style: { width: "100%" },
        });
        const preview = element("textarea", {
          rows: 5, readOnly: true, style: { width: "100%" },
        });
        const commit = () => {
          const template = INSTRUCTION_TEMPLATES[select.value] || "{value}";
          const finalText = template.replace("{value}", value.value.trim() || "the requested result");
          preview.value = finalText;
          state = { template: select.value, value: value.value, finalText };
          mounted.set(state);
        };
        select.addEventListener("change", commit);
        value.addEventListener("input", commit);
        container.append(select, value, element("label", { textContent: "Instruction sent to the node" }), preview);
        commit();
      },
    });
  });
});


comfy.defs.extend("iToolsPromptBuilder", (builder) => {
  builder.onCreated((node) => {
    node.setSize({ width: 340, height: 390 });
    node.widgets.mount({
      name: "PromptBuilderWidget",
      height: 310,
      defaultValue: { prompt: "", negative: "", category: "basic.yaml", style: "none" },
      render(container, mounted) {
        panelStyle(container);
        let state = parseObject(mounted.get());
        const prompt = element("textarea", {
          rows: 7, value: String(state.prompt || ""), placeholder: "Positive prompt",
          style: { width: "100%" },
        });
        const negative = element("textarea", {
          rows: 4, value: String(state.negative || ""), placeholder: "Negative prompt",
          style: { width: "100%" },
        });
        const category = element("select");
        const allowedFiles = Object.keys(STYLE_NAMES).filter((name) => (
          comfy.settings.get("iTools.Nodes.More Styles") !== false
          || ["artist.yaml", "basic.yaml", "camera.yaml", "mood.yaml", "nexus.yaml", "original.yaml"].includes(name)
        ));
        for (const name of allowedFiles) category.append(element("option", { value: name, textContent: name }));
        category.value = allowedFiles.includes(state.category) ? state.category : "basic.yaml";
        const style = element("select");
        const refill = () => {
          const previous = style.value || String(state.style || "none");
          style.replaceChildren();
          for (const name of valuesForStyle(category.value)) {
            style.append(element("option", { value: name, textContent: name }));
          }
          style.value = valuesForStyle(category.value).includes(previous) ? previous : "none";
        };
        const commit = () => mounted.set({
          prompt: prompt.value, negative: negative.value,
          category: category.value, style: style.value,
        });
        prompt.addEventListener("input", commit);
        negative.addEventListener("input", commit);
        category.addEventListener("change", () => { refill(); commit(); });
        style.addEventListener("change", commit);
        refill();
        container.append(element("label", { textContent: "Positive" }), prompt,
          element("label", { textContent: "Negative" }), negative,
          row(category, style),
          button("Clear", () => { prompt.value = ""; negative.value = ""; style.value = "none"; commit(); }));
        commit();
      },
    });
  });
});


function installAdjustPanel(node) {
  const serialized = node.widgets.get("widget_state");
  if (!serialized) return;
  serialized.setHidden(true);
  node.setSize({ width: 360, height: 440 });
  node.widgets.mount({
    name: "itools_adjust_panel",
    height: 350,
    serialize: false,
    sendToPrompt: false,
    render(container) {
      panelStyle(container);
      let state = parseObject(serialized.getValue(), {
        brightness: 0, contrast: 100, saturation: 100, temperature: 0,
        gamma: 100, sharpness: 100, hue: 0, imagePath: "",
      });
      const preview = element("img", {
        alt: "iTools adjustment preview", tabindex: 0,
        style: { width: "100%", maxHeight: "210px", objectFit: "contain", background: "#111" },
      });
      const controls = element("div", { style: { display: "grid", gridTemplateColumns: "90px 1fr 42px", gap: "4px" } });
      const definitions = [
        ["brightness", -100, 100, 0], ["contrast", 0, 200, 100],
        ["saturation", 0, 200, 100], ["temperature", -100, 100, 0],
        ["gamma", 10, 300, 100], ["sharpness", 0, 300, 100],
        ["hue", -180, 180, 0],
      ];
      const sliders = {};
      const redraw = () => {
        preview.src = state.imageData || state.processedImageData || "";
        preview.style.filter = `brightness(${Math.max(0, 100 + Number(state.brightness || 0))}%) `
          + `contrast(${Number(state.contrast || 100)}%) saturate(${Number(state.saturation || 100)}%) `
          + `hue-rotate(${Number(state.hue || 0)}deg)`;
      };
      const commit = () => {
        for (const [name] of definitions) state[name] = Number(sliders[name].value);
        setWidgetJson(serialized, state);
        redraw();
      };
      for (const [name, min, max, initial] of definitions) {
        const slider = element("input", {
          type: "range", min, max, value: Number(state[name] ?? initial),
        });
        const output = element("output", { textContent: String(slider.value) });
        slider.addEventListener("input", () => { output.textContent = slider.value; commit(); });
        sliders[name] = slider;
        controls.append(element("label", { textContent: name }), slider, output);
      }
      const load = async () => {
        const picked = await pickImage();
        if (!picked) return;
        state.imageData = picked.dataUrl;
        state.imagePath = "";
        commit();
      };
      preview.addEventListener("paste", (event) => readClipboardImage(event, (dataUrl) => {
        state.imageData = dataUrl;
        state.imagePath = "";
        commit();
      }));
      container.append(preview, row(button("Choose image…", load),
        button("Reset controls", () => {
          for (const [name, _min, _max, initial] of definitions) sliders[name].value = String(initial);
          commit();
        })), controls,
        element("small", { textContent: "Tip: focus the preview and paste an image, or connect an IMAGE input." }));
      redraw();
    },
  });
}

comfy.defs.extend("iToolsImageAdjust", (builder) => {
  builder.onCreated(installAdjustPanel);
});


function installPaintPanel(node) {
  node.setSize({ width: 570, height: 690 });
  node.widgets.mount({
    name: "PaintWidget",
    height: 600,
    defaultValue: { dataUrl: "", removeBackground: false },
    render(container, mounted) {
      panelStyle(container);
      const canvas = element("canvas", {
        width: 512, height: 512, tabindex: 0,
        style: { width: "100%", aspectRatio: "1", touchAction: "none", background: "white", cursor: "crosshair" },
      });
      const context = canvas.getContext("2d", { willReadFrequently: false });
      const color = element("input", { type: "color", value: "#111111" });
      const size = element("input", { type: "range", min: 1, max: 80, value: 12 });
      const erase = element("input", { type: "checkbox" });
      const removeBackground = element("input", {
        type: "checkbox", checked: Boolean(parseObject(mounted.get()).removeBackground),
      });
      const history = [];
      let future = [];
      let drawing = false;
      let previous = null;

      const snapshot = () => {
        const value = canvas.toDataURL("image/png");
        history.push(value);
        if (history.length > 16) history.shift();
        future = [];
        mounted.set({ dataUrl: value, removeBackground: removeBackground.checked });
      };
      const drawData = (dataUrl, save = false) => {
        const image = document.createElement("img");
        image.addEventListener("load", () => {
          context.save();
          context.globalCompositeOperation = "source-over";
          context.fillStyle = "white";
          context.fillRect(0, 0, canvas.width, canvas.height);
          context.drawImage(image, 0, 0, canvas.width, canvas.height);
          context.restore();
          if (save) snapshot();
        }, { once: true });
        image.src = dataUrl;
      };
      const coordinates = (event) => {
        const bounds = canvas.getBoundingClientRect();
        return {
          x: (event.clientX - bounds.left) * canvas.width / bounds.width,
          y: (event.clientY - bounds.top) * canvas.height / bounds.height,
        };
      };
      canvas.addEventListener("pointerdown", (event) => {
        if (event.button !== 0) return;
        drawing = true;
        previous = coordinates(event);
        canvas.setPointerCapture(event.pointerId);
      });
      canvas.addEventListener("pointermove", (event) => {
        if (!drawing || !previous) return;
        const next = coordinates(event);
        context.save();
        context.globalCompositeOperation = erase.checked ? "destination-out" : "source-over";
        context.strokeStyle = color.value;
        context.lineWidth = Number(size.value);
        context.lineCap = "round";
        context.lineJoin = "round";
        context.beginPath();
        context.moveTo(previous.x, previous.y);
        context.lineTo(next.x, next.y);
        context.stroke();
        context.restore();
        previous = next;
      });
      const finish = () => {
        if (!drawing) return;
        drawing = false;
        previous = null;
        snapshot();
      };
      canvas.addEventListener("pointerup", finish);
      canvas.addEventListener("pointercancel", finish);
      canvas.addEventListener("paste", (event) => readClipboardImage(event, (dataUrl) => drawData(dataUrl, true)));
      removeBackground.addEventListener("change", () => {
        if (removeBackground.checked && comfy.settings.get("iTools.Nodes.Mask Tool") !== true) {
          removeBackground.checked = false;
          comfy.commands.notify({
            severity: "warn", summary: "Background removal is disabled",
            detail: "Enable it in iTools settings first.", life: 3000,
          });
        }
        mounted.set({ dataUrl: canvas.toDataURL("image/png"), removeBackground: removeBackground.checked });
      });
      const choose = async () => {
        const picked = await pickImage();
        if (picked) drawData(picked.dataUrl, true);
      };
      const undo = () => {
        if (history.length < 2) return;
        future.push(history.pop());
        drawData(history[history.length - 1], false);
        mounted.set({ dataUrl: history[history.length - 1], removeBackground: removeBackground.checked });
      };
      const redo = () => {
        const next = future.pop();
        if (!next) return;
        history.push(next);
        drawData(next, false);
        mounted.set({ dataUrl: next, removeBackground: removeBackground.checked });
      };
      const addText = async () => {
        const text = await comfy.ui.prompt({ label: "Text to paint", value: "" });
        if (!text) return;
        context.save();
        context.globalCompositeOperation = "source-over";
        context.fillStyle = color.value;
        context.font = `${Math.max(12, Number(size.value) * 2)}px sans-serif`;
        context.fillText(text, 24, canvas.height / 2);
        context.restore();
        snapshot();
      };
      const clear = () => {
        context.save();
        context.globalCompositeOperation = "source-over";
        context.fillStyle = "white";
        context.fillRect(0, 0, canvas.width, canvas.height);
        context.restore();
        snapshot();
      };

      container.append(row(button("Open…", choose), button("Undo", undo), button("Redo", redo),
        button("Text…", addText), button("Clear", clear)),
        row(element("label", { textContent: "Color" }), color,
          element("label", { textContent: "Brush" }), size,
          element("label", { textContent: "Eraser" }), erase),
        canvas,
        row(element("label", { textContent: "Remove background on run" }), removeBackground),
        element("small", { textContent: "Tip: focus the canvas and paste an image." }));
      const restored = parseObject(mounted.get());
      if (restored.dataUrl) {
        drawData(String(restored.dataUrl), false);
        history.push(String(restored.dataUrl));
      } else {
        clear();
      }
      mounted.onChange((value) => {
        const next = parseObject(value);
        removeBackground.checked = Boolean(next.removeBackground);
        if (next.dataUrl && next.dataUrl !== history[history.length - 1]) drawData(String(next.dataUrl), false);
      });
    },
  });
}

comfy.defs.extend("iToolsPaintNode", (builder) => {
  builder.onCreated(installPaintPanel);
});


function installCropPanel(node) {
  node.setSize({ width: 520, height: 620 });
  const imageWidget = node.widgets.get("image");
  imageWidget?.setHidden(true);
  node.widgets.mount({
    name: "crop",
    height: 520,
    defaultValue: { data: "", box: null, source: "" },
    render(container, mounted) {
      panelStyle(container);
      const canvas = element("canvas", {
        width: 512, height: 512,
        style: { width: "100%", aspectRatio: "1", touchAction: "none", background: "#111", cursor: "crosshair" },
      });
      const context = canvas.getContext("2d");
      let source = null;
      let start = null;
      let box = null;
      const toCanvas = (event) => {
        const bounds = canvas.getBoundingClientRect();
        return {
          x: Math.max(0, Math.min(canvas.width, (event.clientX - bounds.left) * canvas.width / bounds.width)),
          y: Math.max(0, Math.min(canvas.height, (event.clientY - bounds.top) * canvas.height / bounds.height)),
        };
      };
      const redraw = () => {
        context.clearRect(0, 0, canvas.width, canvas.height);
        if (source) context.drawImage(source, 0, 0, canvas.width, canvas.height);
        if (box) {
          context.save();
          context.strokeStyle = "#49d6ff";
          context.lineWidth = 3;
          context.setLineDash([8, 5]);
          context.strokeRect(box.left, box.top, box.right - box.left, box.bottom - box.top);
          context.restore();
        }
      };
      const loadData = (dataUrl) => {
        const image = document.createElement("img");
        image.addEventListener("load", () => { source = image; box = null; redraw(); }, { once: true });
        image.src = dataUrl;
      };
      canvas.addEventListener("pointerdown", (event) => {
        if (!source || event.button !== 0) return;
        start = toCanvas(event);
        box = { left: start.x, top: start.y, right: start.x, bottom: start.y };
        canvas.setPointerCapture(event.pointerId);
      });
      canvas.addEventListener("pointermove", (event) => {
        if (!start) return;
        const point = toCanvas(event);
        let width = point.x - start.x;
        let height = point.y - start.y;
        const rule = String(node.widgets.get("resize_rule")?.getValue() || "free");
        if (!["free", "grid"].includes(rule) && rule.includes(":")) {
          const [x, y] = rule.split(":").map(Number);
          if (x > 0 && y > 0) height = Math.sign(height || 1) * Math.abs(width) * y / x;
        }
        box = {
          left: Math.min(start.x, start.x + width), top: Math.min(start.y, start.y + height),
          right: Math.max(start.x, start.x + width), bottom: Math.max(start.y, start.y + height),
        };
        redraw();
      });
      canvas.addEventListener("pointerup", () => { start = null; });
      const choose = async () => {
        const picked = await pickImage();
        if (picked) loadData(picked.dataUrl);
      };
      const commit = () => {
        if (!source) return;
        const chosen = box && box.right - box.left >= 1 && box.bottom - box.top >= 1
          ? box : { left: 0, top: 0, right: canvas.width, bottom: canvas.height };
        let width = Math.max(1, Math.round(chosen.right - chosen.left));
        let height = Math.max(1, Math.round(chosen.bottom - chosen.top));
        if (String(node.widgets.get("resize_rule")?.getValue()) === "grid") {
          const step = Math.max(1, Number(node.widgets.get("grid_step")?.getValue()) || 64);
          width = Math.max(step, Math.round(width / step) * step);
          height = Math.max(step, Math.round(height / step) * step);
        }
        const output = document.createElement("canvas");
        output.width = width;
        output.height = height;
        output.getContext("2d").drawImage(canvas,
          chosen.left, chosen.top, chosen.right - chosen.left, chosen.bottom - chosen.top,
          0, 0, width, height);
        mounted.set({ data: output.toDataURL("image/png"), box: null, source: "frontend-picker" });
        comfy.commands.notify({ severity: "success", summary: "iTools crop captured", detail: `${width} × ${height}`, life: 2200 });
      };
      container.append(row(button("Choose image…", choose), button("Use selection", commit),
        button("Select all", () => { box = null; redraw(); })), canvas,
        element("small", { textContent: "Drag a crop region. Aspect and grid settings above are applied when captured." }));
      const restored = parseObject(mounted.get());
      if (restored.data) loadData(String(restored.data));
    },
  });
}

comfy.defs.extend("iToolsCropImage", (builder) => {
  builder.onCreated(installCropPanel);
});


function installImageViewer(node, kind) {
  const key = stateKey(node);
  const state = { images: [], history: [], container: null, mode: kind };
  nodeState.set(key, state);
  node.setSize(kind === "compare"
    ? { width: 520, height: 420 }
    : { width: 420, height: 420 });
  node.widgets.mount({
    name: `itools_${kind}_viewer`,
    height: 330,
    serialize: false,
    sendToPrompt: false,
    render(container) {
      state.container = container;
      renderImageViewer(state);
    },
    destroy() { state.container = null; },
  });
}


function renderImageViewer(state) {
  const container = state.container;
  if (!container) return;
  container.replaceChildren();
  panelStyle(container);
  const images = state.images;
  if (!images.length) {
    container.append(element("em", { textContent: "Run the node to populate the preview." }));
    return;
  }
  if (state.mode === "compare" && images.length >= 2) {
    const holder = element("div", { style: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: "4px", minHeight: "250px" } });
    holder.append(element("img", { src: images[0], alt: "A", style: { width: "100%", height: "100%", objectFit: "contain" } }),
      element("img", { src: images[1], alt: "B", style: { width: "100%", height: "100%", objectFit: "contain" } }));
    container.append(holder, element("small", { textContent: `Compare mode: ${comfy.settings.get("iTools.Nodes.Compare Mode") || "makadi"}` }));
    return;
  }
  let index = images.length - 1;
  const preview = element("img", {
    src: images[index], alt: "iTools preview",
    style: { width: "100%", maxHeight: "270px", objectFit: "contain" },
  });
  const label = element("span", { textContent: `${index + 1}/${images.length}` });
  container.append(preview, row(button("◀", () => {
    index = (index - 1 + images.length) % images.length;
    preview.src = images[index]; label.textContent = `${index + 1}/${images.length}`;
  }), label, button("▶", () => {
    index = (index + 1) % images.length;
    preview.src = images[index]; label.textContent = `${index + 1}/${images.length}`;
  })));
}


for (const [type, mode] of [["iToolsCompareImage", "compare"], ["iToolsPreviewImage", "preview"]]) {
  comfy.defs.extend(type, (builder) => {
    builder.onCreated((node) => installImageViewer(node, mode));
    builder.onExecuted((node, result) => {
      const state = nodeState.get(stateKey(node));
      if (!state) return;
      const urls = (result.images || []).map(imageRecordUrl).filter(Boolean);
      if (urls.length) {
        state.images = mode === "compare" ? urls.slice(-2) : [...state.history, ...urls].slice(-MAX_HISTORY_ITEMS);
        state.history = state.images;
      }
      renderImageViewer(state);
    });
    builder.onRemoved((node) => nodeState.delete(stateKey(node)));
  });
}


comfy.defs.extend("iToolsPreviewText", (builder) => {
  builder.onCreated((node) => {
    const display = node.widgets.add({
      type: "text", name: "itools_text_preview", value: "", disabled: true, serialize: false,
      options: { multiline: true, read_only: true },
    });
    display.setHeight(70);
  });
  builder.onExecuted((node, result) => {
    node.widgets.get("itools_text_preview")?.setValue((result.text || []).join("\n"));
  });
});


async function loadLibrary() {
  try {
    const raw = await comfy.storage.get(LIBRARY_FILE);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.slice(0, MAX_LIBRARY_ITEMS).filter((item) => (
      item && typeof item === "object" && typeof item.text === "string"
    )).map((item) => ({ title: String(item.title || "Prompt"), text: item.text }));
  } catch (_error) {
    return [];
  }
}


async function saveLibrary(items) {
  const bounded = items.slice(0, MAX_LIBRARY_ITEMS).map((item) => ({
    title: String(item.title || "Prompt").slice(0, 200),
    text: String(item.text || "").slice(0, 1_048_576),
  }));
  await comfy.storage.set(LIBRARY_FILE, JSON.stringify(bounded));
}


function installPromptRecord(node) {
  const timeline = node.widgets.get("timeline_data");
  timeline?.setHidden(true);
  const key = stateKey(node);
  let history = [];
  try {
    const restored = JSON.parse(String(timeline?.getValue() || "[]"));
    if (Array.isArray(restored)) history = restored.filter((value) => typeof value === "string").slice(-MAX_HISTORY_ITEMS);
  } catch (_error) {}
  const state = { history, container: null };
  nodeState.set(key, state);
  node.setSize({ width: 340, height: 330 });
  node.widgets.mount({
    name: "itools_prompt_history",
    height: 210,
    serialize: false,
    sendToPrompt: false,
    render(container) { state.container = container; renderPromptHistory(node, state); },
    destroy() { state.container = null; },
  });
}


function renderPromptHistory(node, state) {
  const container = state.container;
  if (!container) return;
  container.replaceChildren();
  panelStyle(container);
  const textWidget = node.widgets.get("text");
  const list = element("div", { style: { display: "flex", flexDirection: "column", gap: "4px" } });
  for (const [index, text] of [...state.history].reverse().entries()) {
    const actual = state.history.length - 1 - index;
    const excerpt = text.length > 100 ? `${text.slice(0, 100)}…` : text;
    list.append(row(button(excerpt || "(empty)", () => textWidget?.setValue(text)),
      button("★", async () => {
        const library = await loadLibrary();
        library.unshift({ title: excerpt || "Prompt", text });
        await saveLibrary(library);
      }, "Add to Prompt Library"),
      button("×", () => {
        state.history.splice(actual, 1);
        timelineValue(node, state);
        renderPromptHistory(node, state);
      })));
  }
  container.append(row(button("Clear history", () => {
    state.history = [];
    timelineValue(node, state);
    renderPromptHistory(node, state);
  })), list);
}


function timelineValue(node, state) {
  node.widgets.get("timeline_data")?.setValue(JSON.stringify(state.history.slice(-MAX_HISTORY_ITEMS)));
}

comfy.defs.extend("iToolsPromptRecord", (builder) => {
  builder.onCreated(installPromptRecord);
  builder.onExecuted((node, result) => {
    const state = nodeState.get(stateKey(node));
    const value = (result.text || [])[0];
    if (!state || typeof value !== "string" || !value || state.history.at(-1) === value) return;
    state.history.push(value);
    state.history = state.history.slice(-MAX_HISTORY_ITEMS);
    timelineValue(node, state);
    renderPromptHistory(node, state);
  });
  builder.onRemoved((node) => nodeState.delete(stateKey(node)));
});


function parsePngText(bytes) {
  if (!(bytes instanceof Uint8Array) || bytes.length < 12) return {};
  const signature = [137, 80, 78, 71, 13, 10, 26, 10];
  if (!signature.every((value, index) => bytes[index] === value)) return {};
  const decoder = new TextDecoder("utf-8", { fatal: false });
  const values = {};
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  let offset = 8;
  let chunks = 0;
  while (offset + 12 <= bytes.length && chunks < 4096) {
    const length = view.getUint32(offset, false);
    if (length > bytes.length - offset - 12) break;
    const type = decoder.decode(bytes.subarray(offset + 4, offset + 8));
    if (type === "tEXt") {
      const payload = bytes.subarray(offset + 8, offset + 8 + length);
      const separator = payload.indexOf(0);
      if (separator > 0) {
        const key = decoder.decode(payload.subarray(0, separator));
        values[key] = decoder.decode(payload.subarray(separator + 1));
      }
    }
    offset += length + 12;
    chunks += 1;
    if (type === "IEND") break;
  }
  return values;
}


function longestPrompt(prompt) {
  const keys = new Set(["text", "text_positive", "positive", "text_g", "text_l", "t5xxl"]);
  if (!prompt || typeof prompt !== "object") return "";
  const candidates = [];
  for (const node of Object.values(prompt)) {
    const inputs = node && typeof node === "object" ? node.inputs : undefined;
    if (!inputs || typeof inputs !== "object") continue;
    for (const [name, value] of Object.entries(inputs)) {
      if (keys.has(name) && typeof value === "string") candidates.push(value);
    }
  }
  return candidates.sort((a, b) => b.length - a.length)[0] || "";
}


async function getPromptFromImage() {
  const picked = await comfy.files.pick({
    extensions: ["png"], mimeTypes: ["image/png"], maxBytes: MAX_IMAGE_BYTES,
  });
  if (!picked) return;
  try {
    const metadata = parsePngText(picked.bytes);
    const prompt = longestPrompt(JSON.parse(metadata.prompt || "{}"));
    if (!prompt) throw new Error("No prompt strings were found");
    comfy.ui.showDialog({
      key: "itools.extractedPrompt",
      title: "Prompt from image",
      render(container) {
        const textarea = element("textarea", {
          value: prompt, readOnly: true, rows: 14,
          style: { width: "min(720px, 80vw)" },
        });
        container.append(element("p", { textContent: "Select and copy the extracted prompt:" }), textarea);
        textarea.focus();
        textarea.select();
      },
    });
  } catch (_error) {
    comfy.commands.notify({
      severity: "warn", summary: "No ComfyUI prompt metadata found",
      detail: "Choose a PNG containing an uncompressed ComfyUI prompt tEXt chunk.", life: 4000,
    });
  }
}

comfy.commands.register({
  id: "iTools.getPromptFromImage",
  label: "iTools: Get prompt from image",
  run: getPromptFromImage,
});

let actionBarHandle = null;
function updateActionBar(enabled) {
  actionBarHandle?.remove();
  actionBarHandle = null;
  if (!enabled) return;
  actionBarHandle = comfy.ui.addActionBarButton({
    id: "iTools.getPromptFromImage.button",
    icon: "icon-[lucide--file-image]",
    label: "Get prompt",
    tooltip: "Extract the longest prompt from ComfyUI PNG metadata",
    run: getPromptFromImage,
  });
}
updateActionBar(comfy.settings.get("iTools.Tabs.menuTab") === true);
comfy.settings.onChange("iTools.Tabs.menuTab", (value) => updateActionBar(value === true));


let sidebarRemove = null;
function updateSidebar(enabled) {
  sidebarRemove?.();
  sidebarRemove = null;
  if (!enabled) return;
  sidebarRemove = comfy.ui.addSidebarTab({
    id: "iTools.promptLibrary",
    title: "Prompt Library",
    icon: "icon-[lucide--library]",
    tooltip: "Reusable iTools prompts",
    render(container) { renderPromptLibrary(container); },
  });
}


function renderPromptLibrary(container) {
  panelStyle(container);
  let disposed = false;
  const heading = element("h3", { textContent: "iTools Prompt Library" });
  const editor = element("textarea", {
    rows: 6, placeholder: "Write or paste a reusable prompt", style: { width: "100%" },
  });
  const list = element("div", { style: { display: "flex", flexDirection: "column", gap: "5px" } });
  const refresh = async () => {
    const items = await loadLibrary();
    if (disposed) return;
    list.replaceChildren();
    for (const [index, item] of items.entries()) {
      list.append(row(button(item.title, () => { editor.value = item.text; }),
        button("×", async () => { items.splice(index, 1); await saveLibrary(items); await refresh(); })));
    }
  };
  const add = async () => {
    const text = editor.value.trim();
    if (!text) return;
    const title = await comfy.ui.prompt({ label: "Prompt title", value: text.slice(0, 60) });
    if (title === undefined) return;
    const items = await loadLibrary();
    items.unshift({ title: title || "Prompt", text });
    await saveLibrary(items);
    await refresh();
  };
  const exportItems = async () => {
    const items = await loadLibrary();
    await comfy.files.download({
      name: "itools-prompt-library.json", mimeType: "application/json",
      bytes: new TextEncoder().encode(JSON.stringify(items, null, 2)),
    });
  };
  const importItems = async () => {
    const picked = await comfy.files.pick({
      extensions: ["json"], mimeTypes: ["application/json"], maxBytes: 2 * 1024 * 1024,
    });
    if (!picked) return;
    try {
      const parsed = JSON.parse(new TextDecoder().decode(picked.bytes));
      if (!Array.isArray(parsed)) throw new Error("not an array");
      const current = await loadLibrary();
      await saveLibrary([...parsed, ...current]);
      await refresh();
    } catch (_error) {
      comfy.commands.notify({ severity: "error", summary: "Invalid prompt library file" });
    }
  };
  container.append(heading, editor, row(button("Add", add), button("Import…", importItems), button("Export", exportItems)), list);
  void refresh();
  return () => { disposed = true; };
}

updateSidebar(comfy.settings.get("iTools.Tabs.Side Tab") !== false);
comfy.settings.onChange("iTools.Tabs.Side Tab", (value) => updateSidebar(value !== false));
