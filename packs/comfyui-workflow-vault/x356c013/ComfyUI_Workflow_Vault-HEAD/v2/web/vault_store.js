export const VAULT_NAMESPACE = "Comfy.WorkflowVault/vault";
export const MAX_ENTRIES = 250;
export const MAX_VERSIONS = 50;
export const MAX_EXAMPLES = 20;
export const MAX_PROFILES = 20;
export const MAX_ARCHIVE_BYTES = 12 * 1024 * 1024;
export const MAX_MEDIA_BYTES = 2 * 1024 * 1024;
const CHUNK_CHARS = 240_000;
const MAX_CHUNKS = 64;
const MANIFEST_KEY = `${VAULT_NAMESPACE}/manifest.json`;
const encoder = new TextEncoder();

function clone(value) {
    return JSON.parse(JSON.stringify(value));
}

function object(value, message) {
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(message);
    return value;
}

function string(value, name, maximum, allowEmpty = false) {
    if (typeof value !== "string" || value.length > maximum || (!allowEmpty && !value.trim())) {
        throw new Error(`Invalid ${name}`);
    }
    return value;
}

function id(value, name = "id") {
    string(value, name, 80);
    if (!/^[A-Za-z0-9_-]+$/.test(value) || value.includes("..")) throw new Error(`Invalid ${name}`);
    return value;
}

function uniqueStrings(value, name, maximum, itemMaximum = 100) {
    if (!Array.isArray(value) || value.length > maximum) throw new Error(`Invalid ${name}`);
    return [...new Set(value.map((item) => string(item, name, itemMaximum).trim()))];
}

function workflow(value) {
    object(value, "Invalid workflow");
    if (!Array.isArray(value.nodes)) throw new Error("Invalid workflow");
    const serialized = JSON.stringify(value);
    if (encodedBytes(serialized) > 8 * 1024 * 1024) throw new Error("Workflow exceeds 8 MiB");
    return clone(value);
}

function generatedId(prefix) {
    return `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 11)}`;
}

function encodedBytes(value) {
    return encoder.encode(value).byteLength;
}

function split(value) {
    const chunks = [];
    for (let start = 0; start < value.length; start += CHUNK_CHARS) {
        let end = Math.min(start + CHUNK_CHARS, value.length);
        if (end < value.length && /[\uD800-\uDBFF]/.test(value[end - 1]) && /[\uDC00-\uDFFF]/.test(value[end])) end -= 1;
        chunks.push(value.slice(start, end));
        start = end - CHUNK_CHARS;
    }
    if (!chunks.length || chunks.length > MAX_CHUNKS) throw new Error("Vault archive has too many chunks");
    return chunks;
}

function emptyVault() {
    const now = Date.now();
    return {
        format: "comfy-workflow-vault/secure-v1",
        activeProfileId: "default",
        profiles: [{ id: "default", name: "Default", createdAt: now }],
        entries: [],
    };
}

function validateExample(value) {
    object(value, "Malformed example");
    id(value.id, "example id");
    const bytes = Number(value.bytes);
    if (!Number.isInteger(bytes) || bytes < 0 || bytes > MAX_MEDIA_BYTES) throw new Error("Invalid example size");
    const data = string(value.data, "example data", Math.ceil(MAX_MEDIA_BYTES * 4 / 3) + 8);
    if (!/^[A-Za-z0-9+/]+={0,2}$/.test(data) || data.length % 4 !== 0) throw new Error("Invalid example data");
    const padding = data.endsWith("==") ? 2 : data.endsWith("=") ? 1 : 0;
    if ((data.length * 3 / 4) - padding !== bytes) throw new Error("Example size does not match data");
    return {
        id: value.id,
        name: string(value.name, "example name", 255),
        type: string(value.type || "application/octet-stream", "example type", 100),
        role: value.role === "input" ? "input" : "output",
        notes: string(value.notes || "", "example notes", 10_000, true),
        bytes,
        data,
    };
}

function validateVersion(value) {
    object(value, "Malformed version");
    id(value.id, "version id");
    if (!Number.isFinite(value.createdAt) || value.createdAt < 0) throw new Error("Invalid version date");
    return {
        id: value.id,
        label: string(value.label || "Version", "version label", 200),
        notes: string(value.notes || "", "version notes", 50_000, true),
        createdAt: value.createdAt,
        workflow: workflow(value.workflow),
    };
}

function validateEntry(value, profileIds) {
    object(value, "Malformed vault entry");
    id(value.id, "entry id");
    id(value.profileId, "profile id");
    if (!profileIds.has(value.profileId)) throw new Error("Entry crosses profile boundary");
    const versions = Array.isArray(value.versions) ? value.versions.map(validateVersion) : [];
    if (!versions.length || versions.length > MAX_VERSIONS) throw new Error("Invalid entry versions");
    const examples = Array.isArray(value.examples) ? value.examples.map(validateExample) : [];
    if (examples.length > MAX_EXAMPLES) throw new Error("Too many examples");
    const currentVersionId = id(value.currentVersionId, "current version id");
    if (!versions.some((version) => version.id === currentVersionId)) throw new Error("Missing current version");
    return {
        id: value.id,
        profileId: value.profileId,
        name: string(value.name, "entry name", 200),
        description: string(value.description || "", "description", 20_000, true),
        notes: string(value.notes || "", "notes", 100_000, true),
        status: ["draft", "ready", "archived"].includes(value.status) ? value.status : "draft",
        tags: uniqueStrings(value.tags || [], "tags", 30),
        createdAt: Number.isFinite(value.createdAt) ? value.createdAt : Date.now(),
        updatedAt: Number.isFinite(value.updatedAt) ? value.updatedAt : Date.now(),
        currentVersionId,
        versions,
        examples,
    };
}

export function validateVault(value) {
    object(value, "Malformed vault archive");
    if (value.format !== "comfy-workflow-vault/secure-v1") throw new Error("Unsupported vault archive");
    if (!Array.isArray(value.profiles) || !value.profiles.length || value.profiles.length > MAX_PROFILES) throw new Error("Invalid profiles");
    const profiles = value.profiles.map((profile) => {
        object(profile, "Malformed profile");
        return {
            id: id(profile.id, "profile id"),
            name: string(profile.name, "profile name", 200),
            createdAt: Number.isFinite(profile.createdAt) ? profile.createdAt : Date.now(),
        };
    });
    const profileIds = new Set(profiles.map((profile) => profile.id));
    if (profileIds.size !== profiles.length) throw new Error("Duplicate profile id");
    const activeProfileId = id(value.activeProfileId, "active profile id");
    if (!profileIds.has(activeProfileId)) throw new Error("Unknown active profile");
    if (!Array.isArray(value.entries) || value.entries.length > MAX_ENTRIES) throw new Error("Invalid entries");
    const entries = value.entries.map((entry) => validateEntry(entry, profileIds));
    if (new Set(entries.map((entry) => entry.id)).size !== entries.length) throw new Error("Duplicate entry id");
    const result = { format: value.format, activeProfileId, profiles, entries };
    if (encodedBytes(JSON.stringify(result)) > MAX_ARCHIVE_BYTES) throw new Error("Vault exceeds 12 MiB");
    return result;
}

export class VaultStore {
    constructor(storage) {
        this.storage = storage;
        this.vault = undefined;
        this.queue = Promise.resolve();
    }

    async load() {
        if (this.vault) return clone(this.vault);
        const raw = await this.storage.get(MANIFEST_KEY);
        if (raw === undefined) {
            this.vault = emptyVault();
            return clone(this.vault);
        }
        let manifest;
        try { manifest = JSON.parse(raw); } catch { throw new Error("Vault manifest is malformed"); }
        object(manifest, "Vault manifest is malformed");
        id(manifest.generation, "generation");
        if (!Number.isInteger(manifest.chunks) || manifest.chunks < 1 || manifest.chunks > MAX_CHUNKS) throw new Error("Vault manifest is malformed");
        const values = await Promise.all(Array.from({ length: manifest.chunks }, (_, index) => this.storage.get(`${VAULT_NAMESPACE}/${manifest.generation}/${index}`)));
        if (values.some((value) => value === undefined)) throw new Error("Vault archive is incomplete");
        try { this.vault = validateVault(JSON.parse(values.join(""))); } catch (error) {
            throw new Error(`Vault archive is malformed: ${error.message}`);
        }
        return clone(this.vault);
    }

    async _save(value) {
        const validated = validateVault(value);
        const serialized = JSON.stringify(validated);
        const chunks = split(serialized);
        const generation = generatedId("gen");
        let written = 0;
        const previousRaw = await this.storage.get(MANIFEST_KEY);
        try {
            for (; written < chunks.length; written += 1) await this.storage.set(`${VAULT_NAMESPACE}/${generation}/${written}`, chunks[written]);
            await this.storage.set(MANIFEST_KEY, JSON.stringify({ version: 1, generation, chunks: chunks.length, bytes: encodedBytes(serialized) }));
        } catch (error) {
            await Promise.all(Array.from({ length: written }, (_, index) => this.storage.remove(`${VAULT_NAMESPACE}/${generation}/${index}`)));
            throw error;
        }
        this.vault = validated;
        if (previousRaw) {
            try {
                const previous = JSON.parse(previousRaw);
                if (previous.generation !== generation && Number.isInteger(previous.chunks)) {
                    await Promise.all(Array.from({ length: Math.min(previous.chunks, MAX_CHUNKS) }, (_, index) => this.storage.remove(`${VAULT_NAMESPACE}/${previous.generation}/${index}`))).catch(() => undefined);
                }
            } catch { /* the new valid generation is authoritative */ }
        }
        return clone(validated);
    }

    _mutate(update) {
        const run = this.queue.then(async () => {
            const current = await this.load();
            const result = await update(current);
            await this._save(current);
            return clone(result);
        });
        this.queue = run.catch(() => undefined);
        return run;
    }

    async state() {
        const vault = await this.load();
        return { ...vault, entries: vault.entries.filter((entry) => entry.profileId === vault.activeProfileId) };
    }

    async createProfile(name) {
        return this._mutate((vault) => {
            if (vault.profiles.length >= MAX_PROFILES) throw new Error("Profile limit reached");
            const profile = { id: generatedId("profile"), name: string(name, "profile name", 200).trim(), createdAt: Date.now() };
            vault.profiles.push(profile); vault.activeProfileId = profile.id; return profile;
        });
    }

    async activateProfile(profileId) {
        return this._mutate((vault) => {
            id(profileId, "profile id");
            if (!vault.profiles.some((profile) => profile.id === profileId)) throw new Error("Unknown profile");
            vault.activeProfileId = profileId; return profileId;
        });
    }

    async renameProfile(profileId, name) {
        return this._mutate((vault) => {
            const profile = vault.profiles.find((item) => item.id === id(profileId, "profile id"));
            if (!profile) throw new Error("Unknown profile");
            profile.name = string(name, "profile name", 200).trim(); return profile;
        });
    }

    async deleteProfile(profileId) {
        return this._mutate((vault) => {
            id(profileId, "profile id");
            if (profileId === "default") throw new Error("Default profile cannot be deleted");
            if (vault.activeProfileId === profileId) throw new Error("Active profile cannot be deleted");
            const before = vault.profiles.length;
            vault.profiles = vault.profiles.filter((profile) => profile.id !== profileId);
            if (vault.profiles.length === before) throw new Error("Unknown profile");
            vault.entries = vault.entries.filter((entry) => entry.profileId !== profileId);
            return true;
        });
    }

    async createEntry({ name, description = "", notes = "", status = "draft", tags = [], workflow: graph }) {
        return this._mutate((vault) => {
            if (vault.entries.length >= MAX_ENTRIES) throw new Error("Entry limit reached");
            const now = Date.now(); const versionId = generatedId("version");
            const entry = validateEntry({
                id: generatedId("entry"), profileId: vault.activeProfileId,
                name, description, notes, status, tags, createdAt: now, updatedAt: now,
                currentVersionId: versionId,
                versions: [{ id: versionId, label: "Initial", notes: "", createdAt: now, workflow: graph }], examples: [],
            }, new Set(vault.profiles.map((profile) => profile.id)));
            vault.entries.push(entry); return entry;
        });
    }

    async getEntry(entryId) {
        const vault = await this.load();
        const entry = vault.entries.find((item) => item.id === id(entryId, "entry id") && item.profileId === vault.activeProfileId);
        if (!entry) throw new Error("Entry not found in active profile");
        return clone(entry);
    }

    async updateEntry(entryId, patch) {
        return this._mutate((vault) => {
            const entry = vault.entries.find((item) => item.id === id(entryId, "entry id") && item.profileId === vault.activeProfileId);
            if (!entry) throw new Error("Entry not found in active profile");
            if (patch.name !== undefined) entry.name = string(patch.name, "entry name", 200).trim();
            if (patch.description !== undefined) entry.description = string(patch.description, "description", 20_000, true);
            if (patch.notes !== undefined) entry.notes = string(patch.notes, "notes", 100_000, true);
            if (patch.status !== undefined) {
                if (!["draft", "ready", "archived"].includes(patch.status)) throw new Error("Invalid status");
                entry.status = patch.status;
            }
            if (patch.tags !== undefined) entry.tags = uniqueStrings(patch.tags, "tags", 30);
            entry.updatedAt = Date.now(); return entry;
        });
    }

    async addVersion(entryId, graph, label = "Version") {
        return this._mutate((vault) => {
            const entry = vault.entries.find((item) => item.id === id(entryId, "entry id") && item.profileId === vault.activeProfileId);
            if (!entry) throw new Error("Entry not found in active profile");
            const version = validateVersion({ id: generatedId("version"), label, notes: "", createdAt: Date.now(), workflow: graph });
            entry.versions.push(version); entry.currentVersionId = version.id; entry.updatedAt = Date.now();
            if (entry.versions.length > MAX_VERSIONS) entry.versions.splice(0, entry.versions.length - MAX_VERSIONS);
            return version;
        });
    }

    async getVersion(entryId, versionId) {
        const entry = await this.getEntry(entryId);
        const version = entry.versions.find((item) => item.id === id(versionId, "version id"));
        if (!version) throw new Error("Version not found"); return clone(version);
    }

    async promoteVersion(entryId, versionId) {
        return this._mutate((vault) => {
            const entry = vault.entries.find((item) => item.id === id(entryId, "entry id") && item.profileId === vault.activeProfileId);
            if (!entry || !entry.versions.some((item) => item.id === id(versionId, "version id"))) throw new Error("Version not found");
            entry.currentVersionId = versionId; entry.updatedAt = Date.now(); return entry;
        });
    }

    async deleteEntry(entryId) {
        return this._mutate((vault) => {
            const before = vault.entries.length;
            vault.entries = vault.entries.filter((item) => item.id !== id(entryId, "entry id") || item.profileId !== vault.activeProfileId);
            if (vault.entries.length === before) throw new Error("Entry not found in active profile"); return true;
        });
    }

    async duplicateEntry(entryId, name) {
        return this._mutate((vault) => {
            const source = vault.entries.find((item) => item.id === id(entryId, "entry id") && item.profileId === vault.activeProfileId);
            if (!source) throw new Error("Entry not found in active profile");
            if (vault.entries.length >= MAX_ENTRIES) throw new Error("Entry limit reached");
            const copy = clone(source); copy.id = generatedId("entry"); copy.name = string(name || `${source.name} Copy`, "entry name", 200); copy.createdAt = copy.updatedAt = Date.now();
            const versionMap = new Map(); copy.versions = copy.versions.map((version) => { const next = generatedId("version"); versionMap.set(version.id, next); return { ...version, id: next }; }); copy.currentVersionId = versionMap.get(source.currentVersionId);
            copy.examples = copy.examples.map((example) => ({ ...example, id: generatedId("example") })); vault.entries.push(copy); return copy;
        });
    }

    async addExample(entryId, file, role = "output", notes = "") {
        return this._mutate((vault) => {
            const entry = vault.entries.find((item) => item.id === id(entryId, "entry id") && item.profileId === vault.activeProfileId);
            if (!entry) throw new Error("Entry not found in active profile");
            if (entry.examples.length >= MAX_EXAMPLES) throw new Error("Example limit reached");
            const bytes = file.bytes instanceof Uint8Array ? file.bytes : new Uint8Array(file.bytes || []);
            if (!bytes.length || bytes.length > MAX_MEDIA_BYTES) throw new Error("Example exceeds 2 MiB");
            let binary = ""; for (const byte of bytes) binary += String.fromCharCode(byte);
            const example = validateExample({ id: generatedId("example"), name: file.name, type: file.type, role, notes, bytes: bytes.length, data: btoa(binary) });
            entry.examples.push(example); entry.updatedAt = Date.now(); return example;
        });
    }

    async deleteExample(entryId, exampleId) {
        return this._mutate((vault) => {
            const entry = vault.entries.find((item) => item.id === id(entryId, "entry id") && item.profileId === vault.activeProfileId);
            if (!entry) throw new Error("Entry not found in active profile");
            const before = entry.examples.length; entry.examples = entry.examples.filter((item) => item.id !== id(exampleId, "example id"));
            if (before === entry.examples.length) throw new Error("Example not found"); return true;
        });
    }

    async exportArchive() { return JSON.stringify(await this.load(), null, 2); }

    async importArchive(raw, { replace = false } = {}) {
        if (typeof raw !== "string" || encodedBytes(raw) > MAX_ARCHIVE_BYTES) throw new Error("Import exceeds 12 MiB");
        let imported; try { imported = validateVault(JSON.parse(raw)); } catch (error) { throw new Error(`Invalid vault import: ${error.message}`); }
        if (replace) return this._mutate((vault) => { Object.assign(vault, imported); return vault; });
        return this._mutate((vault) => {
            const profileMap = new Map();
            for (const profile of imported.profiles) {
                const next = profile.id === "default" ? vault.profiles.find((item) => item.id === "default") : undefined;
                if (next) profileMap.set(profile.id, next.id);
                else {
                    if (vault.profiles.length >= MAX_PROFILES) throw new Error("Profile limit reached");
                    const created = { ...profile, id: generatedId("profile") }; vault.profiles.push(created); profileMap.set(profile.id, created.id);
                }
            }
            for (const source of imported.entries) {
                if (vault.entries.length >= MAX_ENTRIES) throw new Error("Entry limit reached");
                const entry = clone(source); entry.id = generatedId("entry"); entry.profileId = profileMap.get(source.profileId);
                const versionMap = new Map(); entry.versions = entry.versions.map((version) => { const next = generatedId("version"); versionMap.set(version.id, next); return { ...version, id: next }; }); entry.currentVersionId = versionMap.get(source.currentVersionId);
                entry.examples = entry.examples.map((example) => ({ ...example, id: generatedId("example") })); vault.entries.push(entry);
            }
            return { imported: imported.entries.length };
        });
    }

    async footprint() {
        const usage = await this.storage.usage(VAULT_NAMESPACE);
        const vault = await this.load();
        return { ...usage, entries: vault.entries.length, profiles: vault.profiles.length };
    }
}
