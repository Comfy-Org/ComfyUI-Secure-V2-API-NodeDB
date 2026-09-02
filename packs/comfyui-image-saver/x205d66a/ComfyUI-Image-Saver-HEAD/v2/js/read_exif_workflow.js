import { comfy } from "/comfy/api/v2.js";


const SETTING_ID = "ImageSaver.HandleImageWorkflowDrop";
const MAX_IMPORT_BYTES = 16 * 1024 * 1024;
const MAX_IFD_ENTRIES = 512;


function range(bytes, offset, length) {
    if (!Number.isSafeInteger(offset) || !Number.isSafeInteger(length)) return null;
    if (offset < 0 || length < 0 || offset + length > bytes.length) return null;
    return bytes.subarray(offset, offset + length);
}


function read16(bytes, offset, littleEndian) {
    const value = range(bytes, offset, 2);
    if (!value) return null;
    return littleEndian
        ? value[0] | (value[1] << 8)
        : (value[0] << 8) | value[1];
}


function read32(bytes, offset, littleEndian) {
    const value = range(bytes, offset, 4);
    if (!value) return null;
    const result = littleEndian
        ? value[0] + value[1] * 0x100 + value[2] * 0x10000 + value[3] * 0x1000000
        : value[3] + value[2] * 0x100 + value[1] * 0x10000 + value[0] * 0x1000000;
    return Number.isSafeInteger(result) ? result : null;
}


function decodeAscii(bytes) {
    let end = bytes.length;
    while (end > 0 && bytes[end - 1] === 0) end -= 1;
    return new TextDecoder("utf-8", { fatal: false }).decode(bytes.subarray(0, end));
}


function parsePrefixedJson(values) {
    let prompt;
    for (const raw of values) {
        const value = raw.trim();
        const lowered = value.toLowerCase();
        const isWorkflow = lowered.startsWith("workflow:");
        const isPrompt = lowered.startsWith("prompt:");
        if (!isWorkflow && !isPrompt) continue;
        const prefixLength = isWorkflow ? "workflow:".length : "prompt:".length;
        try {
            const parsed = JSON.parse(value.slice(prefixLength));
            if (isWorkflow) return { workflow: parsed };
            if (prompt === undefined) prompt = parsed;
        } catch (error) {
            if (!(error instanceof SyntaxError)) throw error;
        }
    }
    return prompt === undefined ? null : { prompt };
}


function tiffAsciiValues(bytes, tiffStart, tiffEnd) {
    const marker = range(bytes, tiffStart, 2);
    if (!marker) return [];
    const littleEndian = marker[0] === 0x49 && marker[1] === 0x49;
    const bigEndian = marker[0] === 0x4d && marker[1] === 0x4d;
    if (!littleEndian && !bigEndian) return [];
    if (read16(bytes, tiffStart + 2, littleEndian) !== 42) return [];
    const firstOffset = read32(bytes, tiffStart + 4, littleEndian);
    if (firstOffset === null) return [];

    const values = [];
    const visited = new Set();
    let ifdOffset = firstOffset;
    for (let depth = 0; depth < 4 && ifdOffset !== 0; depth += 1) {
        if (visited.has(ifdOffset)) break;
        visited.add(ifdOffset);
        const directory = tiffStart + ifdOffset;
        const count = read16(bytes, directory, littleEndian);
        if (count === null || count > MAX_IFD_ENTRIES) break;
        const entriesEnd = directory + 2 + count * 12;
        if (entriesEnd + 4 > tiffEnd) break;

        for (let index = 0; index < count; index += 1) {
            const entry = directory + 2 + index * 12;
            const type = read16(bytes, entry + 2, littleEndian);
            const length = read32(bytes, entry + 4, littleEndian);
            if (type !== 2 || length === null || length < 1) continue;
            let start;
            if (length <= 4) {
                start = entry + 8;
            } else {
                const valueOffset = read32(bytes, entry + 8, littleEndian);
                if (valueOffset === null) continue;
                start = tiffStart + valueOffset;
            }
            if (start < tiffStart || start + length > tiffEnd) continue;
            const value = range(bytes, start, length);
            if (value) values.push(decodeAscii(value));
        }
        const next = read32(bytes, entriesEnd, littleEndian);
        if (next === null) break;
        ifdOffset = next;
    }
    return values;
}


/** Parse the bounded JPEG EXIF fields emitted by Image Saver and core. */
export function parseJpegMetadata(input) {
    const bytes = input instanceof Uint8Array
        ? input
        : input instanceof ArrayBuffer
            ? new Uint8Array(input)
            : null;
    if (!bytes || bytes.length < 4 || bytes.length > MAX_IMPORT_BYTES) return null;
    if (bytes[0] !== 0xff || bytes[1] !== 0xd8) return null;

    const descriptions = [];
    let offset = 2;
    while (offset + 1 < bytes.length) {
        if (bytes[offset] !== 0xff) return null;
        while (offset < bytes.length && bytes[offset] === 0xff) offset += 1;
        if (offset >= bytes.length) break;
        const marker = bytes[offset++];
        if (marker === 0xd9 || marker === 0xda) break;
        if (marker === 0x01 || (marker >= 0xd0 && marker <= 0xd7)) continue;
        const segmentLength = read16(bytes, offset, false);
        if (segmentLength === null || segmentLength < 2) return null;
        const payloadStart = offset + 2;
        const payloadEnd = offset + segmentLength;
        if (payloadEnd > bytes.length) return null;
        if (
            marker === 0xe1
            && payloadEnd - payloadStart >= 14
            && bytes[payloadStart] === 0x45
            && bytes[payloadStart + 1] === 0x78
            && bytes[payloadStart + 2] === 0x69
            && bytes[payloadStart + 3] === 0x66
            && bytes[payloadStart + 4] === 0
            && bytes[payloadStart + 5] === 0
        ) {
            descriptions.push(...tiffAsciiValues(
                bytes, payloadStart + 6, payloadEnd
            ));
        }
        offset = payloadEnd;
    }
    return parsePrefixedJson(descriptions);
}


comfy.settings.declare({
    id: SETTING_ID,
    name: "Use Image Saver JPEG workflow importer",
    type: "boolean",
    defaultValue: true,
    category: ["Image Saver", "File Handling", "JPEG Workflow Importer"],
    tooltip: "Load workflows or API prompts embedded in Image Saver JPEG EXIF metadata.",
});


comfy.workflow.registerImporter({
    id: "comfyui-image-saver.jpeg-exif",
    mimeTypes: ["image/jpeg"],
    extensions: ["jpg", "jpeg"],
    maxBytes: MAX_IMPORT_BYTES,
    enabled: () => comfy.settings.get(SETTING_ID) !== false,
    parse: (bytes) => parseJpegMetadata(bytes),
});
