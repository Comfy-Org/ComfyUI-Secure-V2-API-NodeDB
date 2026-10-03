import assert from "node:assert/strict";
import test from "node:test";

import {
    MAX_ARCHIVE_BYTES,
    MAX_MEDIA_BYTES,
    VAULT_NAMESPACE,
    VaultStore,
    validateVault,
} from "../web/vault_store.js";

class MemoryStorage {
    constructor({ quota = Infinity } = {}) { this.values = new Map(); this.quota = quota; }
    async list(namespace) { return [...this.values.keys()].filter((key) => key === namespace || key.startsWith(`${namespace}/`)); }
    async get(key) { return this.values.get(key); }
    async set(key, value) {
        const next = new Map(this.values); next.set(key, value);
        const used = [...next.values()].reduce((sum, item) => sum + new TextEncoder().encode(item).byteLength, 0);
        if (used > this.quota) throw new Error("quota exceeded");
        this.values = next;
    }
    async remove(key) { this.values.delete(key); }
    async usage(namespace) {
        const values = [...this.values.entries()].filter(([key]) => key.startsWith(namespace));
        return { usedBytes: values.reduce((sum, [, item]) => sum + new TextEncoder().encode(item).byteLength, 0), entryCount: values.length, quotaBytes: Number.isFinite(this.quota) ? this.quota : undefined };
    }
}

function graph(name = "Example", payload = "") {
    return { nodes: [{ id: 1, type: "Example", title: name, widgets_values: [payload] }], links: [], groups: [] };
}

test("CRUD, search data, versions, promotion, duplication, archive and reload are preserved", async () => {
    const storage = new MemoryStorage(); const store = new VaultStore(storage);
    const created = await store.createEntry({ name: "Image Cleanup", description: "restore detail", tags: ["image", "cleanup"], workflow: graph("v1") });
    assert.equal((await store.state()).entries.length, 1);
    await store.updateEntry(created.id, { notes: "Uses a local model", status: "ready" });
    const second = await store.addVersion(created.id, graph("v2"), "Better masking");
    await store.promoteVersion(created.id, created.versions[0].id);
    const updated = await store.getEntry(created.id);
    assert.equal(updated.currentVersionId, created.versions[0].id);
    assert.equal(updated.versions.length, 2);
    assert.equal((await store.getVersion(created.id, second.id)).workflow.nodes[0].title, "v2");
    const duplicate = await store.duplicateEntry(created.id, "Image Cleanup Copy");
    assert.notEqual(duplicate.id, created.id);
    assert.equal(duplicate.versions.length, 2);
    await store.updateEntry(created.id, { status: "archived" });
    await store.deleteEntry(duplicate.id);

    const reloaded = new VaultStore(storage);
    const state = await reloaded.state();
    assert.equal(state.entries.length, 1);
    assert.equal(state.entries[0].status, "archived");
    assert.ok((await storage.list(VAULT_NAMESPACE)).some((key) => key.endsWith("manifest.json")));
});

test("profiles isolate entries and reject cross-profile ids", async () => {
    const store = new VaultStore(new MemoryStorage());
    const defaultEntry = await store.createEntry({ name: "Default", workflow: graph() });
    const profile = await store.createProfile("Experiments");
    assert.equal((await store.state()).entries.length, 0);
    await assert.rejects(() => store.getEntry(defaultEntry.id), /active profile/);
    const experiment = await store.createEntry({ name: "Experiment", workflow: graph() });
    await assert.rejects(() => store.deleteProfile(profile.id), /Active profile/);
    await store.activateProfile("default");
    assert.deepEqual((await store.state()).entries.map((item) => item.id), [defaultEntry.id]);
    await assert.rejects(() => store.deleteEntry(experiment.id), /active profile/);
    await store.activateProfile(profile.id);
    assert.deepEqual((await store.state()).entries.map((item) => item.id), [experiment.id]);
});

test("host-provided tenant storage handles cannot observe one another", async () => {
    const tenantA = new VaultStore(new MemoryStorage());
    const tenantB = new VaultStore(new MemoryStorage());
    await tenantA.createEntry({ name: "Tenant A only", workflow: graph() });
    assert.equal((await tenantA.state()).entries.length, 1);
    assert.equal((await tenantB.state()).entries.length, 0);
    assert.doesNotMatch(await tenantB.exportArchive(), /Tenant A only/);
});

test("bounded media examples round-trip and reject oversize data", async () => {
    const store = new VaultStore(new MemoryStorage());
    const entry = await store.createEntry({ name: "Media", workflow: graph() });
    const media = await store.addExample(entry.id, { name: "result.png", type: "image/png", bytes: new Uint8Array([1, 2, 3, 4]) }, "output", "result");
    assert.equal(media.data, "AQIDBA==");
    assert.equal((await store.getEntry(entry.id)).examples.length, 1);
    await store.deleteExample(entry.id, media.id);
    assert.equal((await store.getEntry(entry.id)).examples.length, 0);
    await assert.rejects(() => store.addExample(entry.id, { name: "huge.bin", type: "application/octet-stream", bytes: new Uint8Array(MAX_MEDIA_BYTES + 1) }), /2 MiB/);
});

test("archive export/import validates format, ownership, workflow, counts and total size", async () => {
    const source = new VaultStore(new MemoryStorage());
    await source.createEntry({ name: "Portable", workflow: graph("portable") });
    const raw = await source.exportArchive();
    const target = new VaultStore(new MemoryStorage());
    const result = await target.importArchive(raw);
    assert.deepEqual(result, { imported: 1 });
    assert.equal((await target.state()).entries[0].name, "Portable");

    const archive = JSON.parse(raw);
    archive.entries[0].profileId = "another-tenant";
    assert.throws(() => validateVault(archive), /profile boundary/);
    await assert.rejects(() => target.importArchive("not-json"), /Invalid vault import/);
    await assert.rejects(() => target.importArchive("x".repeat(MAX_ARCHIVE_BYTES + 1)), /12 MiB/);
    archive.entries[0].profileId = "default"; archive.entries[0].versions[0].workflow = { nodes: "not an array" };
    await assert.rejects(() => target.importArchive(JSON.stringify(archive)), /Invalid workflow/);
    const mediaArchive = JSON.parse(raw);
    mediaArchive.entries[0].examples = [{ id: "example_safe", name: "x.png", type: "image/png", role: "output", notes: "", bytes: 99, data: "AQIDBA==" }];
    await assert.rejects(() => target.importArchive(JSON.stringify(mediaArchive)), /size does not match/);
});

test("generation commit keeps the previous readable archive when quota interrupts a write", async () => {
    const storage = new MemoryStorage(); const store = new VaultStore(storage);
    const entry = await store.createEntry({ name: "Stable", workflow: graph() });
    const before = await storage.get(`${VAULT_NAMESPACE}/manifest.json`);
    storage.quota = (await storage.usage(VAULT_NAMESPACE)).usedBytes + 100;
    await assert.rejects(() => store.addVersion(entry.id, graph("large", "x".repeat(1000)), "Will fail"), /quota/);
    assert.equal(await storage.get(`${VAULT_NAMESPACE}/manifest.json`), before);
    assert.equal((await storage.list(VAULT_NAMESPACE)).filter((key) => !key.endsWith("manifest.json")).length, 1);
    const reloaded = new VaultStore(storage);
    assert.equal((await reloaded.getEntry(entry.id)).versions.length, 1);
});

test("malformed manifests and incomplete chunks fail closed", async () => {
    const storage = new MemoryStorage();
    await storage.set(`${VAULT_NAMESPACE}/manifest.json`, "{");
    await assert.rejects(() => new VaultStore(storage).load(), /manifest is malformed/);
    await storage.set(`${VAULT_NAMESPACE}/manifest.json`, JSON.stringify({ version: 1, generation: "gen_safe", chunks: 2 }));
    await storage.set(`${VAULT_NAMESPACE}/gen_safe/0`, "{}");
    await assert.rejects(() => new VaultStore(storage).load(), /incomplete/);
});
