import { comfy } from "/comfy/api/v2.js";


const MAX_IMPORT_BYTES = 16 * 1024 * 1024;


/** @param {Uint8Array} bytes */
function view(bytes) {
  return new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
}


/** @param {Uint8Array} bytes @param {number} offset @param {number} length */
function ascii(bytes, offset, length) {
  if (offset < 0 || length < 0 || offset + length > bytes.length) return "";
  return String.fromCharCode(...bytes.subarray(offset, offset + length));
}


/** @param {Uint8Array} bytes @returns {Record<string, unknown> | null} */
function parseTiffUserComment(bytes) {
  if (!(bytes instanceof Uint8Array) || bytes.length < 8) return null;
  const little = bytes[0] === 0x49 && bytes[1] === 0x49;
  if (!little && !(bytes[0] === 0x4d && bytes[1] === 0x4d)) return null;
  const data = view(bytes);
  if (data.getUint16(2, little) !== 42) return null;
  const ifdOffset = data.getUint32(4, little);
  if (ifdOffset + 2 > bytes.length) return null;
  const count = data.getUint16(ifdOffset, little);
  if (count > 4096 || ifdOffset + 2 + count * 12 > bytes.length) return null;
  /** @type {Record<string, unknown>} */
  const metadata = {};
  for (let index = 0; index < count; index += 1) {
    const entry = ifdOffset + 2 + index * 12;
    const tag = data.getUint16(entry, little);
    const type = data.getUint16(entry + 2, little);
    const length = data.getUint32(entry + 4, little);
    if (type !== 2 || length < 2 || length > MAX_IMPORT_BYTES) continue;
    const offset = length <= 4 ? entry + 8 : data.getUint32(entry + 8, little);
    if (offset + length > bytes.length) continue;
    let text = ascii(bytes, offset, length - 1).replace(/^ASCII\0\0\0/, "");
    if (tag === 0x9286) {
      const firstBrace = text.indexOf("{");
      if (firstBrace > 0) text = text.slice(firstBrace);
      try {
        const legacy = JSON.parse(text);
        if (legacy && typeof legacy === "object" && !Array.isArray(legacy)) return legacy;
      } catch {
        continue;
      }
    } else {
      const separator = text.indexOf(":");
      if (separator <= 0) continue;
      try {
        metadata[text.slice(0, separator)] = JSON.parse(text.slice(separator + 1));
      } catch {
        continue;
      }
    }
  }
  return Object.keys(metadata).length ? metadata : null;
}


/** @param {Uint8Array} bytes */
export function parseJpegMetadata(bytes) {
  if (!(bytes instanceof Uint8Array) || bytes.length < 4 || bytes[0] !== 0xff || bytes[1] !== 0xd8) return null;
  const data = view(bytes);
  let offset = 2;
  while (offset + 4 <= bytes.length) {
    if (bytes[offset] !== 0xff) return null;
    const marker = bytes[offset + 1];
    if (marker === 0xd9 || marker === 0xda) break;
    const length = data.getUint16(offset + 2, false);
    if (length < 2 || offset + 2 + length > bytes.length) return null;
    if (marker === 0xe1 && length >= 8 && ascii(bytes, offset + 4, 6) === "Exif\0\0") {
      return parseTiffUserComment(bytes.subarray(offset + 10, offset + 2 + length));
    }
    offset += 2 + length;
  }
  return null;
}


/** @param {Uint8Array} bytes */
export function parseWebpMetadata(bytes) {
  if (!(bytes instanceof Uint8Array) || bytes.length < 12 || ascii(bytes, 0, 4) !== "RIFF" || ascii(bytes, 8, 4) !== "WEBP") return null;
  const data = view(bytes);
  let offset = 12;
  while (offset + 8 <= bytes.length) {
    const length = data.getUint32(offset + 4, true);
    const end = offset + 8 + length;
    if (end > bytes.length) return null;
    if (ascii(bytes, offset, 4) === "EXIF") {
      let payload = bytes.subarray(offset + 8, end);
      if (ascii(payload, 0, 6) === "Exif\0\0") payload = payload.subarray(6);
      return parseTiffUserComment(payload);
    }
    offset = end + (length & 1);
  }
  return null;
}


/** @param {unknown} value @returns {value is Record<string, unknown>} */
function isRecord(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}


/**
 * @param {Record<string, unknown> | null} metadata
 * @returns {import('../comfy-api').WorkflowImportResult | null}
 */
function importResult(metadata) {
  if (!metadata) return null;
  if (isRecord(metadata.workflow)) {
    return { workflow: metadata.workflow };
  }
  if (isRecord(metadata.prompt)) {
    return { prompt: metadata.prompt };
  }
  return null;
}


comfy.workflow.registerImporter({
  id: "SaveImagePlus.Metadata",
  mimeTypes: ["image/jpeg", "image/webp"],
  extensions: ["jpg", "jpeg", "webp"],
  maxBytes: MAX_IMPORT_BYTES,
  parse(bytes, context) {
    const metadata = context.type === "image/webp" || context.name.toLowerCase().endsWith(".webp")
      ? parseWebpMetadata(bytes)
      : parseJpegMetadata(bytes);
    return importResult(metadata);
  },
});


export { importResult, parseTiffUserComment };
