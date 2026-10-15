import { comfy } from '/comfy/api/v2.js';

// Authored metadata is account state, never a source-adjacent sidecar or a
// worker-global substitute for persistence. The same versioned key/document is
// consumed by the Python pack. Cross-render/JS-to-Python backing-store continuity
// is an integration gate and must be verified against the deployed broker.
export const MODEL_INFO_SCHEMA = 'rgthree-model-info-v1';
const PREFIX = 'rgthree.model-info.v1.';
const LIMIT = 256 * 1024;
const pendingWrites = new Map();
const allowedKind = (kind) => {
    if (!['loras', 'checkpoints'].includes(kind)) throw new Error(`Unsupported model category: ${kind}`);
    return kind;
};

export async function modelInfoKey(kind, file) {
    allowedKind(kind);
    if (typeof file !== 'string' || !file || file.length > 8192) throw new Error('A bounded logical model filename is required.');
    const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(file));
    return PREFIX + kind + '.' + [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, '0')).join('');
}

function decode(text, kind, file) {
    if (text === undefined) return { file };
    if (new TextEncoder().encode(text).length > LIMIT) throw new Error('Stored model info exceeds its size limit.');
    const record = JSON.parse(text);
    if (!record || record.schema !== MODEL_INFO_SCHEMA || record.kind !== kind || record.file !== file ||
        !record.info || typeof record.info !== 'object' || Array.isArray(record.info) || record.info.file !== file) {
        throw new Error('Stored model info has a different schema or model identity.');
    }
    return record.info;
}

export async function readModelInfo(kind, file) {
    const key = await modelInfoKey(kind, file);
    return decode(await comfy.storage.get(key), kind, file);
}

export async function writeModelInfo(kind, file, changes) {
    const key = await modelInfoKey(kind, file);
    if (!changes || typeof changes !== 'object' || Array.isArray(changes)) throw new Error('Model info changes must be an object.');
    for (const field of Object.keys(changes)) {
        if (['__proto__', 'constructor', 'prototype'].includes(field)) throw new Error('Invalid model info field.');
    }
    if ('file' in changes && changes.file !== file) throw new Error('Model info cannot change its logical filename.');
    // Preserve partial edits from two controls in this realm. A failed write
    // rejects its own caller and does not prevent a later explicit retry.
    const before = pendingWrites.get(key) ?? Promise.resolve();
    const writing = before.catch(() => {}).then(async () => {
        const current = decode(await comfy.storage.get(key), kind, file);
        const info = { ...current, ...structuredClone(changes), file };
        const text = JSON.stringify({ schema: MODEL_INFO_SCHEMA, kind, file, info });
        if (new TextEncoder().encode(text).length > LIMIT) throw new Error('Model info exceeds its size limit.');
        await comfy.storage.set(key, text);
        return info;
    });
    pendingWrites.set(key, writing);
    try { return await writing; }
    finally { if (pendingWrites.get(key) === writing) pendingWrites.delete(key); }
}

export async function listModelInfo(kind) {
    allowedKind(kind);
    const keys = await comfy.storage.list(PREFIX + kind);
    const found = [];
    for (const key of keys) {
        if (!key.startsWith(PREFIX + kind + '.')) continue;
        const text = await comfy.storage.get(key);
        if (text === undefined) continue;
        if (new TextEncoder().encode(text).length > LIMIT) throw new Error('Stored model info exceeds its size limit.');
        const record = JSON.parse(text);
        const info = decode(text, kind, record.file);
        if (await modelInfoKey(kind, record.file) !== key) throw new Error('Stored model info key does not match its identity.');
        found.push(info);
    }
    return found;
}

export class ModelMetadataUnavailableError extends Error {
    constructor() {
        super('Model-file metadata and remote Civitai refresh need an admitted metadata provider. Saved user metadata remains available.');
        this.name = 'ModelMetadataUnavailableError';
    }
}
