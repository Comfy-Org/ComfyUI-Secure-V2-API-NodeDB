import { comfy } from "/comfy/api/v2.js";


const MAX_IMPORT_BYTES = 16 * 1024 * 1024;
const MAX_IFD_ENTRIES = 512;
const MAX_IFD_DEPTH = 4;
const MAX_IFD_DIRECTORIES = 16;


function bounded(bytes, offset, length, end = bytes.length) {
  if (!Number.isSafeInteger(offset) || !Number.isSafeInteger(length)) return null;
  if (offset < 0 || length < 0 || offset + length > end) return null;
  return bytes.subarray(offset, offset + length);
}


function u16(bytes, offset, little, end) {
  const value = bounded(bytes, offset, 2, end);
  if (!value) return null;
  return little ? value[0] | value[1] << 8 : value[0] << 8 | value[1];
}


function u32(bytes, offset, little, end) {
  const value = bounded(bytes, offset, 4, end);
  if (!value) return null;
  const result = little
    ? value[0] + value[1] * 0x100 + value[2] * 0x10000 + value[3] * 0x1000000
    : value[3] + value[2] * 0x100 + value[1] * 0x10000 + value[0] * 0x1000000;
  return Number.isSafeInteger(result) ? result : null;
}


function decodeUserComment(data) {
  if (!data?.length) return null;
  const header = new TextDecoder("ascii").decode(data.subarray(0, 8));
  let body = data;
  let encoding = "utf-8";
  if (header.startsWith("ASCII")) body = data.subarray(8);
  else if (header.startsWith("UNICODE")) {
    body = data.subarray(8);
    encoding = body[0] === 0xff && body[1] === 0xfe ? "utf-16le" : "utf-16be";
  } else if (header.startsWith("JIS")) return null;
  return new TextDecoder(encoding, { fatal: false })
    .decode(body)
    .replace(/[\u0000\u000b]+/g, "")
    .trim();
}


function tiffUserComment(bytes, tiffStart, tiffEnd) {
  const marker = bounded(bytes, tiffStart, 2, tiffEnd);
  if (!marker) return null;
  const little = marker[0] === 0x49 && marker[1] === 0x49;
  if (!little && !(marker[0] === 0x4d && marker[1] === 0x4d)) return null;
  if (u16(bytes, tiffStart + 2, little, tiffEnd) !== 42) return null;
  const first = u32(bytes, tiffStart + 4, little, tiffEnd);
  if (first === null) return null;
  const pending = [first];
  const visited = new Set();

  for (let depth = 0; depth < MAX_IFD_DEPTH && pending.length; depth += 1) {
    const level = pending.splice(0);
    for (const relative of level) {
      if (visited.has(relative)) continue;
      if (visited.size >= MAX_IFD_DIRECTORIES) return null;
      visited.add(relative);
      const directory = tiffStart + relative;
      const count = u16(bytes, directory, little, tiffEnd);
      if (count === null || count > MAX_IFD_ENTRIES) continue;
      const entriesEnd = directory + 2 + count * 12;
      if (entriesEnd + 4 > tiffEnd) continue;
      for (let index = 0; index < count; index += 1) {
        const entry = directory + 2 + index * 12;
        const tag = u16(bytes, entry, little, tiffEnd);
        const type = u16(bytes, entry + 2, little, tiffEnd);
        const length = u32(bytes, entry + 4, little, tiffEnd);
        const value = u32(bytes, entry + 8, little, tiffEnd);
        if (tag === 0x8769 && type === 4 && length === 1 && value !== null) {
          pending.push(value);
          continue;
        }
        if (tag !== 0x9286 || type !== 7 || length === null || value === null) continue;
        const start = length <= 4 ? entry + 8 : tiffStart + value;
        const data = bounded(bytes, start, length, tiffEnd);
        const comment = decodeUserComment(data);
        if (comment) return comment;
      }
      const next = u32(bytes, entriesEnd, little, tiffEnd);
      if (next) pending.push(next);
    }
  }
  return null;
}


export function parseJpegUserComment(input) {
  const bytes = input instanceof Uint8Array
    ? input
    : input instanceof ArrayBuffer ? new Uint8Array(input) : null;
  if (!bytes || bytes.length < 4 || bytes.length > MAX_IMPORT_BYTES) return null;
  if (bytes[0] !== 0xff || bytes[1] !== 0xd8) return null;
  let offset = 2;
  while (offset + 1 < bytes.length) {
    if (bytes[offset] !== 0xff) return null;
    while (offset < bytes.length && bytes[offset] === 0xff) offset += 1;
    if (offset >= bytes.length) break;
    const marker = bytes[offset++];
    if (marker === 0xd9 || marker === 0xda) break;
    if (marker === 0x01 || marker >= 0xd0 && marker <= 0xd7) continue;
    const length = u16(bytes, offset, false, bytes.length);
    if (length === null || length < 2) return null;
    const start = offset + 2;
    const end = offset + length;
    if (end > bytes.length) return null;
    if (
      marker === 0xe1 && end - start >= 14
      && new TextDecoder("ascii").decode(bytes.subarray(start, start + 6)) === "Exif\0\0"
    ) {
      const comment = tiffUserComment(bytes, start + 6, end);
      if (comment) return comment;
    }
    offset = end;
  }
  return null;
}


function splitParameters(value) {
  const result = [];
  let start = 0;
  let quote = null;
  let escaped = false;
  let depth = 0;
  for (let index = 0; index < value.length; index += 1) {
    const char = value[index];
    if (escaped) escaped = false;
    else if (char === "\\") escaped = true;
    else if (quote) {
      if (char === quote) quote = null;
    } else if (char === '"' || char === "'") quote = char;
    else if ("[{(".includes(char)) depth += 1;
    else if ("]})".includes(char)) depth = Math.max(0, depth - 1);
    else if (char === "," && value[index + 1] === " " && depth === 0) {
      result.push(value.slice(start, index));
      start = index + 2;
      index += 1;
    }
  }
  result.push(value.slice(start));
  return result;
}


export function parseA1111Parameters(parameters) {
  const clean = String(parameters).replace(/[\u0000\u000b]+/g, "");
  const marker = clean.lastIndexOf("\nSteps:");
  if (marker < 0) return null;
  const negativeMarker = clean.lastIndexOf("\nNegative prompt:", marker);
  const positive = clean.slice(0, negativeMarker < 0 ? marker : negativeMarker).trim();
  const negative = negativeMarker < 0
    ? ""
    : clean.slice(negativeMarker + "\nNegative prompt:".length, marker).trim();
  const options = {};
  for (const part of splitParameters(clean.slice(marker + 1))) {
    const separator = part.indexOf(": ");
    if (separator < 0) continue;
    options[part.slice(0, separator).trim().toLowerCase()] =
      part.slice(separator + 2).trim();
  }
  return { positive, negative, options };
}


function number(value, fallback) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}


function sampler(value) {
  let name = String(value || "euler").toLowerCase()
    .replace("cfg++", "cfg_pp").replace("++", "pp")
    .replace("dpm2", "dpm_2").replaceAll(" ", "_")
    .replace("_heun", "").replace("_sde", "_sde_gpu");
  let scheduler = "normal";
  if (name.includes("karras")) {
    scheduler = "karras";
    name = name.replace("karras", "");
  } else if (name.includes("exponential")) {
    scheduler = "exponential";
    name = name.replace("exponential", "");
  }
  name = name.replace(/_+$/, "").replace(/_a$/, "_ancestral");
  return { name, scheduler };
}


function scheduleType(value, fallback) {
  const map = {
    "Automatic": "normal",
    "Align Your Steps": "ays",
    "DDIM": "ddim_uniform",
    "Align Your Steps GITS": "gits",
    "Align Your Steps 11": "ays_30",
    "Align Your Steps 32": "ays_30+",
  };
  if (!value) return fallback;
  return map[value] || String(value).toLowerCase().replaceAll(" ", "_");
}


function extractLoras(text) {
  const loras = [];
  const clean = String(text).replace(
    /<(?:lora|lyco|lycoris):([^:>]+):([^>]+)>/gi,
    (match, name, rawWeight) => {
      const weight = Number(rawWeight);
      if (!Number.isFinite(weight)) {
        throw new Error(`invalid LoRA weight in ${match}`);
      }
      loras.push({ name, weight });
      return "";
    },
  );
  return { text: clean, loras };
}


function encodeInputs(text, clip, meanNormalization) {
  return {
    text,
    clip,
    parser: "A1111",
    mean_normalization: meanNormalization,
    multi_conditioning: true,
    use_old_emphasis_implementation: false,
    with_SDXL: false,
    ascore: 6,
    width: 1024,
    height: 1024,
    crop_w: 0,
    crop_h: 0,
    target_width: 1024,
    target_height: 1024,
    text_g: "",
    text_l: "",
    smZ_steps: 1,
  };
}


export function a1111ToPrompt(parameters) {
  const parsed = parseA1111Parameters(parameters);
  if (!parsed) return null;
  const { positive, negative, options } = parsed;
  if (options["hires upscale"] || options["hires resize"] || options["hires upscaler"]) {
    throw new Error(
      "smZ secure importer does not silently flatten A1111 hires workflows",
    );
  }
  const unsupported = Object.keys(options).filter((name) => [
    "civitai resources", "civitai metadata", "freeu", "sag", "pag",
    "multidiffusion", "tiled diffusion", "ultimate sd upscale",
    "latent_modifier", "noise schedule", "advanced sampling",
    "rescale_cfg", "token merging ratio", "sd upscale upscaler",
    "module 1", "module 2", "module 3",
  ].some((prefix) => name === prefix || name.startsWith(`${prefix} `)));
  if (unsupported.length) {
    throw new Error(
      `smZ secure importer cannot yet reproduce: ${unsupported.join(", ")}`,
    );
  }
  const [rawWidth, rawHeight] = String(options.size || "512x512").split("x");
  const width = Math.ceil(number(rawWidth, 512) / 8) * 8;
  const height = Math.ceil(number(rawHeight, 512) / 8) * 8;
  const sample = sampler(options.sampler);
  sample.scheduler = scheduleType(options["schedule type"], sample.scheduler);
  const clipSkip = number(options["clip skip"], 0);
  let clipSource = clipSkip ? ["2", 0] : ["1", 1];
  let modelSource = ["1", 0];
  const positiveLoras = extractLoras(positive);
  const negativeLoras = extractLoras(negative);
  const meanNormalization = String(options.emphasis || "").toLowerCase() !== "no norm";
  const settings = { "*": null };
  const settingMap = {
    "eta": ["eta", Number],
    "s_churn": ["s_churn", Number],
    "s_tmin": ["s_tmin", Number],
    "s_tmax": ["s_tmax", Number],
    "s_noise": ["s_noise", Number],
    "ensd": ["ENSD", Number],
    "rng": ["RNG", String],
    "skip early cfg": ["skip_early_cond", Number],
    "ngms": ["NGMS", Number],
    "sgm noise multiplier": [
      "sgm_noise_multiplier",
      (value) => String(value).toLowerCase() === "true",
    ],
  };
  for (const [source, [target, convert]] of Object.entries(settingMap)) {
    if (options[source] !== undefined) settings[target] = convert(options[source]);
  }
  const prompt = {
    "1": { class_type: "CheckpointLoaderSimple", inputs: { ckpt_name: options.model || "" } },
    "3": { class_type: "smZ CLIPTextEncode", inputs: {} },
    "4": { class_type: "smZ CLIPTextEncode", inputs: {} },
    "5": { class_type: "smZ Settings", inputs: settings },
    "6": { class_type: "EmptyLatentImage", inputs: { width, height, batch_size: 1 } },
    "7": {
      class_type: "KSampler",
      inputs: {
        model: ["5", 0], positive: ["3", 0], negative: ["4", 0],
        latent_image: ["6", 0], seed: number(options["global seed"] ?? options.seed, 0),
        steps: number(options.steps, 20), cfg: number(options["cfg scale"], 7),
        sampler_name: sample.name, scheduler: sample.scheduler,
        denoise: number(options["denoising strength"], 1),
      },
    },
    "8": { class_type: "VAEDecode", inputs: { samples: ["7", 0], vae: ["1", 2] } },
    "9": { class_type: "SaveImage", inputs: { images: ["8", 0], filename_prefix: "ComfyUI" } },
  };
  if (clipSkip) {
    prompt["2"] = {
      class_type: "CLIPSetLastLayer",
      inputs: { clip: ["1", 1], stop_at_clip_layer: -Math.abs(clipSkip) },
    };
  }
  let nextId = 10;
  for (const lora of [...positiveLoras.loras, ...negativeLoras.loras]) {
    const id = String(nextId++);
    prompt[id] = {
      class_type: "LoraLoader",
      inputs: {
        model: modelSource,
        clip: clipSource,
        lora_name: lora.name,
        strength_model: lora.weight,
        strength_clip: lora.weight,
      },
    };
    modelSource = [id, 0];
    clipSource = [id, 1];
  }
  prompt["3"].inputs = encodeInputs(
    positiveLoras.text, clipSource, meanNormalization,
  );
  prompt["4"].inputs = encodeInputs(
    negativeLoras.text, clipSource, meanNormalization,
  );
  settings["*"] = modelSource;
  if (options.vae && !["automatic", "none"].includes(options.vae.toLowerCase())) {
    const id = String(nextId++);
    prompt[id] = { class_type: "VAELoader", inputs: { vae_name: options.vae } };
    prompt["8"].inputs.vae = [id, 0];
  }
  return prompt;
}


export function parseWorkflowImage(bytes) {
  const comment = parseJpegUserComment(bytes);
  if (!comment) return null;
  try {
    const value = JSON.parse(comment);
    if (value && typeof value === "object" && !Array.isArray(value)) {
      const { extra: _extra, extraMetadata: _extraMetadata, ...prompt } = value;
      return { prompt };
    }
  } catch (error) {
    if (!(error instanceof SyntaxError)) throw error;
  }
  const prompt = a1111ToPrompt(comment);
  return prompt ? { prompt } : null;
}


// One pinned frontend registration replacing ``Comfy.smZ.WorkflowImage``.
// The host selects the file and projects bounded bytes into the worker. There
// is no app.handleFile override, script injection, ambient file API, or network I/O.
comfy.workflow.registerImporter({
  id: "Comfy.smZ.WorkflowImage",
  mimeTypes: ["image/jpeg"],
  extensions: ["jpg", "jpeg"],
  maxBytes: MAX_IMPORT_BYTES,
  parse: (bytes) => parseWorkflowImage(bytes),
});
