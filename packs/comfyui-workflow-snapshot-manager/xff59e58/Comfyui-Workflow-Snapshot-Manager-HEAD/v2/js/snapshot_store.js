const SNAPSHOT_NAMESPACE = "ComfyUI.SnapshotManager/snapshots";
const PROFILE_NAMESPACE = "ComfyUI.SnapshotManager/profiles";

export const MAX_SNAPSHOTS = 200;
export const MAX_IMPORT_RECORDS = 200;
export const MAX_RECORD_BYTES = 6 * 1024 * 1024;
export const MAX_LABEL_LENGTH = 500;
export const MAX_NOTES_LENGTH = 50_000;
export const MAX_THUMBNAIL_CHARS = 350_000;
const CHUNK_CHARS = 240_000;
const MAX_CHUNKS = 32;
const encoder = new TextEncoder();

function assertPlainObject(value, message) {
    if (value == null || typeof value !== "object" || Array.isArray(value)) {
        throw new Error(message);
    }
}

function boundedString(value, name, maxLength, { empty = false } = {}) {
    if (typeof value !== "string" || (!empty && !value.trim()) || value.length > maxLength) {
        throw new Error(`Invalid ${name}`);
    }
    return value;
}

function safeId(value, name = "snapshot id") {
    const id = boundedString(value, name, 64);
    if (!/^[A-Za-z0-9._-]+$/.test(id) || id.includes("..")) {
        throw new Error(`Invalid ${name}`);
    }
    return id;
}

function validateMetadata(entry, workflowKey) {
    assertPlainObject(entry, "Snapshot metadata is malformed");
    const id = safeId(entry.id);
    if (entry.workflowKey !== workflowKey) {
        throw new Error("Snapshot metadata crosses workflow boundary");
    }
    if (!Number.isFinite(entry.timestamp) || entry.timestamp < 0) {
        throw new Error("Snapshot metadata has an invalid timestamp");
    }
    const label = boundedString(entry.label, "snapshot label", MAX_LABEL_LENGTH);
    if (!new Set(["auto", "manual", "initial", "node", "restore_guard", "import"]).has(entry.source)) {
        throw new Error("Snapshot metadata has an invalid source");
    }
    if (typeof entry.locked !== "boolean") throw new Error("Snapshot metadata has an invalid lock");
    const notes = boundedString(entry.notes ?? "", "snapshot notes", MAX_NOTES_LENGTH, { empty: true });
    if (!Number.isInteger(entry.nodeCount) || entry.nodeCount < 0) {
        throw new Error("Snapshot metadata has an invalid node count");
    }
    if (!Number.isInteger(entry.chunkCount) || entry.chunkCount < 1 || entry.chunkCount > MAX_CHUNKS) {
        throw new Error("Snapshot metadata has an invalid chunk count");
    }
    if (!Number.isInteger(entry.sizeBytes) || entry.sizeBytes < 1 || entry.sizeBytes > MAX_RECORD_BYTES) {
        throw new Error("Snapshot metadata has an invalid size");
    }
    if (entry.parentId != null) safeId(entry.parentId, "parent id");
    if (typeof entry.hasThumbnail !== "boolean") {
        throw new Error("Snapshot metadata has an invalid thumbnail flag");
    }
    return { ...jsonClone(entry), id, label, notes };
}

function jsonClone(value) {
    return JSON.parse(JSON.stringify(value));
}

function encodedLength(value) {
    return encoder.encode(value).byteLength;
}

function fnv1a(value, seed) {
    let hash = seed >>> 0;
    for (let index = 0; index < value.length; index += 1) {
        hash ^= value.charCodeAt(index);
        hash = Math.imul(hash, 0x01000193) >>> 0;
    }
    return hash.toString(16).padStart(8, "0");
}

export function workflowToken(workflowKey) {
    boundedString(workflowKey, "workflow key", 4096);
    return `${fnv1a(workflowKey, 0x811c9dc5)}${fnv1a(workflowKey, 0x9e3779b9)}`;
}

export function validateGraphData(graphData) {
    assertPlainObject(graphData, "Invalid snapshot graphData");
    if (!Array.isArray(graphData.nodes)) throw new Error("Invalid snapshot graphData");
    const serialized = JSON.stringify(graphData);
    if (serialized === undefined || encodedLength(serialized) > MAX_RECORD_BYTES) {
        throw new Error("Snapshot graph exceeds the 6 MiB pack limit");
    }
    return graphData;
}

export function validateThumbnail(value) {
    if (value === undefined || value === null) return undefined;
    if (typeof value !== "string" || value.length === 0 || value.length > MAX_THUMBNAIL_CHARS) {
        throw new Error("Invalid snapshot thumbnail");
    }
    if (!/^[A-Za-z0-9+/]+={0,2}$/.test(value) || value.length % 4 !== 0) {
        throw new Error("Invalid snapshot thumbnail");
    }
    return value;
}

export function validateSnapshotRecord(record, expectedWorkflowKey = undefined) {
    assertPlainObject(record, "Snapshot record must be an object");
    safeId(record.id);
    const workflowKey = boundedString(record.workflowKey, "workflow key", 4096);
    if (expectedWorkflowKey !== undefined && workflowKey !== expectedWorkflowKey) {
        throw new Error("Snapshot belongs to another workflow");
    }
    if (!Number.isFinite(record.timestamp) || record.timestamp < 0) {
        throw new Error("Invalid snapshot timestamp");
    }
    boundedString(record.label, "snapshot label", MAX_LABEL_LENGTH);
    if (!new Set(["auto", "manual", "initial", "node", "restore_guard", "import"]).has(record.source)) {
        throw new Error("Invalid snapshot source");
    }
    if (record.locked !== undefined && typeof record.locked !== "boolean") {
        throw new Error("Invalid locked value");
    }
    if (record.notes !== undefined) {
        boundedString(record.notes, "snapshot notes", MAX_NOTES_LENGTH, { empty: true });
    }
    if (record.parentId != null) safeId(record.parentId, "parent id");
    if (record.thumbnail !== undefined) validateThumbnail(record.thumbnail);
    validateGraphData(record.graphData);
    const copy = jsonClone(record);
    const serialized = JSON.stringify(copy);
    if (encodedLength(serialized) > MAX_RECORD_BYTES) {
        throw new Error("Snapshot record exceeds the 6 MiB pack limit");
    }
    return copy;
}

export function validateProfile(profile) {
    assertPlainObject(profile, "Profile must be an object");
    safeId(profile.id, "profile id");
    boundedString(profile.name, "profile name", 200);
    if (!Number.isFinite(profile.timestamp) || profile.timestamp < 0) {
        throw new Error("Invalid profile timestamp");
    }
    if (!Array.isArray(profile.workflows) || profile.workflows.length > 50) {
        throw new Error("Invalid profile workflows");
    }
    const workflows = profile.workflows.map((entry) => {
        assertPlainObject(entry, "Invalid profile workflow");
        const workflowKey = boundedString(entry.workflowKey, "workflow key", 4096);
        const snapshotId = entry.snapshotId == null ? null : safeId(entry.snapshotId);
        return {
            workflowKey,
            displayName: boundedString(entry.displayName ?? workflowKey, "display name", 500),
            snapshotId,
        };
    });
    const activeWorkflowKey = profile.activeWorkflowKey == null
        ? null
        : boundedString(profile.activeWorkflowKey, "active workflow key", 4096);
    return {
        id: profile.id,
        version: 2,
        name: profile.name,
        timestamp: profile.timestamp,
        workflows,
        activeWorkflowKey,
    };
}

function splitRecord(serialized) {
    const chunks = [];
    for (let start = 0; start < serialized.length; start += CHUNK_CHARS) {
        let end = Math.min(serialized.length, start + CHUNK_CHARS);
        if (end < serialized.length) {
            const previous = serialized.charCodeAt(end - 1);
            const next = serialized.charCodeAt(end);
            if (previous >= 0xd800 && previous <= 0xdbff && next >= 0xdc00 && next <= 0xdfff) {
                end -= 1;
            }
        }
        const chunk = serialized.slice(start, end);
        if (encodedLength(chunk) > 1024 * 1024) throw new Error("Snapshot chunk is too large");
        chunks.push(chunk);
        start = end - CHUNK_CHARS;
    }
    if (!chunks.length || chunks.length > MAX_CHUNKS) throw new Error("Snapshot has too many chunks");
    return chunks;
}

function metadata(record, chunkCount, sizeBytes) {
    return {
        id: record.id,
        workflowKey: record.workflowKey,
        timestamp: record.timestamp,
        label: record.label,
        source: record.source,
        locked: record.locked === true,
        notes: record.notes ?? "",
        nodeCount: record.graphData.nodes.length,
        changeType: typeof record.changeType === "string" ? record.changeType.slice(0, 64) : "unknown",
        parentId: record.parentId ?? null,
        hasThumbnail: record.thumbnail !== undefined,
        chunkCount,
        sizeBytes,
    };
}

function indexKey(workflowKey) {
    return `${SNAPSHOT_NAMESPACE}/${workflowToken(workflowKey)}/index.json`;
}

function chunkKey(workflowKey, snapshotId, index) {
    return `${SNAPSHOT_NAMESPACE}/${workflowToken(workflowKey)}/${safeId(snapshotId)}/${index}`;
}

function profileKey(profileId) {
    return `${PROFILE_NAMESPACE}/${safeId(profileId, "profile id")}.json`;
}

function parseJson(raw, message) {
    try {
        return JSON.parse(raw);
    } catch {
        throw new Error(message);
    }
}

export class SnapshotStore {
    constructor(storage) {
        this.storage = storage;
    }

    async _readIndex(workflowKey) {
        const raw = await this.storage.get(indexKey(workflowKey));
        if (raw === undefined) return { version: 1, workflowKey, records: [] };
        const index = parseJson(raw, "Snapshot index is malformed");
        assertPlainObject(index, "Snapshot index is malformed");
        if (index.version !== 1 || index.workflowKey !== workflowKey || !Array.isArray(index.records)) {
            throw new Error("Snapshot index is malformed or belongs to another workflow");
        }
        const records = index.records.map((entry) => validateMetadata(entry, workflowKey));
        if (records.length > MAX_SNAPSHOTS) throw new Error("Snapshot index exceeds its limit");
        return { version: 1, workflowKey, records };
    }

    async _writeIndex(index) {
        const value = JSON.stringify(index);
        if (encodedLength(value) > 900_000) throw new Error("Snapshot index is too large");
        await this.storage.set(indexKey(index.workflowKey), value);
    }

    async list(workflowKey) {
        const index = await this._readIndex(workflowKey);
        return index.records.slice().sort((a, b) => b.timestamp - a.timestamp);
    }

    async get(workflowKey, snapshotId) {
        const index = await this._readIndex(workflowKey);
        const meta = index.records.find((entry) => entry.id === snapshotId);
        if (!meta) return undefined;
        const chunks = [];
        for (let part = 0; part < meta.chunkCount; part += 1) {
            const chunk = await this.storage.get(chunkKey(workflowKey, snapshotId, part));
            if (chunk === undefined) throw new Error("Snapshot data is incomplete");
            chunks.push(chunk);
        }
        const record = validateSnapshotRecord(
            parseJson(chunks.join(""), "Snapshot data is malformed"),
            workflowKey,
        );
        if (record.id !== snapshotId) throw new Error("Snapshot id does not match its storage key");
        return { ...record, locked: meta.locked, notes: meta.notes, label: meta.label };
    }

    async put(record) {
        const safe = validateSnapshotRecord(record);
        const serialized = JSON.stringify(safe);
        const chunks = splitRecord(serialized);
        const index = await this._readIndex(safe.workflowKey);
        if (index.records.some((entry) => entry.id === safe.id)) {
            throw new Error("Snapshot id already exists");
        }
        if (index.records.length >= MAX_SNAPSHOTS) {
            throw new Error("Snapshot count limit reached; prune before saving");
        }
        const written = [];
        try {
            for (let part = 0; part < chunks.length; part += 1) {
                const key = chunkKey(safe.workflowKey, safe.id, part);
                await this.storage.set(key, chunks[part]);
                written.push(key);
            }
            index.records.push(metadata(safe, chunks.length, encodedLength(serialized)));
            index.records.sort((a, b) => a.timestamp - b.timestamp);
            await this._writeIndex(index);
        } catch (error) {
            await Promise.allSettled(written.map((key) => this.storage.remove(key)));
            throw error;
        }
        return safe.id;
    }

    async delete(workflowKey, snapshotId) {
        const index = await this._readIndex(workflowKey);
        const meta = index.records.find((entry) => entry.id === snapshotId);
        if (!meta) return false;
        const next = { ...index, records: index.records.filter((entry) => entry.id !== snapshotId) };
        await this._writeIndex(next);
        await Promise.allSettled(Array.from(
            { length: meta.chunkCount },
            (_unused, part) => this.storage.remove(chunkKey(workflowKey, snapshotId, part)),
        ));
        return true;
    }

    async setLocked(workflowKey, snapshotId, locked) {
        if (typeof locked !== "boolean") throw new Error("Invalid locked value");
        const index = await this._readIndex(workflowKey);
        const meta = index.records.find((entry) => entry.id === snapshotId);
        if (!meta) return false;
        meta.locked = locked;
        await this._writeIndex(index);
        return true;
    }

    async prune(workflowKey, maxSnapshots, { source, maxAgeDays = 0 } = {}) {
        if (!Number.isInteger(maxSnapshots) || maxSnapshots < 0 || maxSnapshots > MAX_SNAPSHOTS) {
            throw new Error("Invalid snapshot retention limit");
        }
        if (source !== undefined && source !== "node" && source !== "regular") {
            throw new Error("Invalid snapshot retention source");
        }
        const index = await this._readIndex(workflowKey);
        const now = Date.now();
        const relevant = index.records.filter((entry) =>
            source === "node" ? entry.source === "node" : source === "regular" ? entry.source !== "node" : true
        );
        const unlocked = relevant.filter((entry) => !entry.locked).sort((a, b) => b.timestamp - a.timestamp);
        const keepIds = new Set(unlocked.slice(0, maxSnapshots).map((entry) => entry.id));
        const cutoff = maxAgeDays > 0 ? now - maxAgeDays * 86_400_000 : null;
        const doomed = unlocked.filter((entry) =>
            !keepIds.has(entry.id) || (cutoff !== null && entry.timestamp < cutoff)
        );
        for (const entry of doomed) await this.delete(workflowKey, entry.id);
        return doomed.length;
    }

    async clearUnlocked(workflowKey) {
        const records = await this.list(workflowKey);
        const unlocked = records.filter((entry) => !entry.locked);
        for (const entry of unlocked) await this.delete(workflowKey, entry.id);
        return { deleted: unlocked.length, lockedCount: records.length - unlocked.length };
    }

    async workflowKeys() {
        const keys = await this.storage.list(SNAPSHOT_NAMESPACE);
        const indexKeys = keys.filter((key) => key.startsWith(`${SNAPSHOT_NAMESPACE}/`) && key.endsWith("/index.json"));
        const result = [];
        for (const key of indexKeys) {
            const raw = await this.storage.get(key);
            if (raw === undefined) continue;
            try {
                const index = parseJson(raw, "Snapshot index is malformed");
                if (index?.version === 1 && typeof index.workflowKey === "string" && Array.isArray(index.records)) {
                    result.push({ workflowKey: index.workflowKey, count: index.records.length });
                }
            } catch {
                // A malformed namespace entry is ignored here but never opened.
            }
        }
        return result.sort((a, b) => a.workflowKey.localeCompare(b.workflowKey));
    }

    async export(workflowKey) {
        const metadata = await this.list(workflowKey);
        const records = [];
        for (const entry of metadata.slice().reverse()) {
            const record = await this.get(workflowKey, entry.id);
            if (record) records.push(record);
        }
        return { version: 1, workflowKey, records };
    }

    async import(records) {
        if (!Array.isArray(records) || records.length > MAX_IMPORT_RECORDS) {
            throw new Error("Import must contain at most 200 snapshots");
        }
        const safeRecords = records.map((record) => validateSnapshotRecord({ ...record, source: "import" }));
        for (const record of safeRecords) await this.put(record);
        return safeRecords.length;
    }

    async usage() {
        return this.storage.usage(SNAPSHOT_NAMESPACE);
    }

    async listProfiles() {
        const keys = await this.storage.list(PROFILE_NAMESPACE);
        const profiles = [];
        for (const key of keys.filter((item) => item.startsWith(`${PROFILE_NAMESPACE}/`) && item.endsWith(".json"))) {
            const raw = await this.storage.get(key);
            if (raw === undefined) continue;
            try {
                profiles.push(validateProfile(parseJson(raw, "Profile is malformed")));
            } catch {
                // Ignore malformed profile records without exposing them to the UI.
            }
        }
        return profiles.sort((a, b) => b.timestamp - a.timestamp);
    }

    async putProfile(profile) {
        const safe = validateProfile(profile);
        const serialized = JSON.stringify(safe);
        if (encodedLength(serialized) > 512_000) throw new Error("Profile is too large");
        await this.storage.set(profileKey(safe.id), serialized);
        return safe;
    }

    async deleteProfile(profileId) {
        await this.storage.remove(profileKey(profileId));
    }
}

export const namespaces = Object.freeze({ snapshots: SNAPSHOT_NAMESPACE, profiles: PROFILE_NAMESPACE });
