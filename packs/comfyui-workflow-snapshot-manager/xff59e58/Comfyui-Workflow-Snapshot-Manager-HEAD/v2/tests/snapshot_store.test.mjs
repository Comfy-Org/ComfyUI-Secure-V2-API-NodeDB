import assert from "node:assert/strict";
import test from "node:test";

import {
    MAX_IMPORT_RECORDS,
    MAX_RECORD_BYTES,
    SnapshotStore,
    validateProfile,
    validateSnapshotRecord,
} from "../js/snapshot_store.js";

class MemoryStorage {
    constructor({ entryLimit = 1024 * 1024, totalLimit = 8 * 1024 * 1024 } = {}) {
        this.values = new Map();
        this.entryLimit = entryLimit;
        this.totalLimit = totalLimit;
        this.encoder = new TextEncoder();
        this.failAfter = undefined;
        this.setCalls = 0;
    }

    async list(namespace) {
        return [...this.values.keys()].filter((key) => key === namespace || key.startsWith(`${namespace}/`));
    }

    async get(key) {
        return this.values.get(key);
    }

    async set(key, value) {
        this.setCalls += 1;
        if (this.failAfter !== undefined && this.setCalls >= this.failAfter) throw new Error("quota failure");
        if (new TextEncoder().encode(key).byteLength > 128) throw new Error("storage key too long");
        const size = this.encoder.encode(value).byteLength;
        if (size > this.entryLimit) throw new Error("entry quota exceeded");
        const previous = this.values.has(key) ? this.encoder.encode(this.values.get(key)).byteLength : 0;
        const used = [...this.values.values()].reduce((sum, item) => sum + this.encoder.encode(item).byteLength, 0);
        if (used - previous + size > this.totalLimit) throw new Error("total quota exceeded");
        this.values.set(key, value);
    }

    async remove(key) {
        this.values.delete(key);
    }

    async usage(namespace) {
        const entries = [...this.values.entries()].filter(([key]) => key.startsWith(namespace));
        return {
            usedBytes: entries.reduce((sum, [, value]) => sum + this.encoder.encode(value).byteLength, 0),
            entryCount: entries.length,
            quotaBytes: this.totalLimit,
        };
    }
}

function record(id, overrides = {}) {
    return {
        id,
        workflowKey: "path:workflows/example.json",
        timestamp: 100,
        label: "Auto",
        source: "auto",
        locked: false,
        graphData: { nodes: [{ id: 1, type: "Example" }], links: [] },
        ...overrides,
    };
}

test("chunked records round-trip Unicode through the one-MiB entry boundary", async () => {
    const storage = new MemoryStorage();
    const store = new SnapshotStore(storage);
    const large = record("large", {
        graphData: {
            nodes: [{ id: 1, type: "Text", widgets_values: ["🦊".repeat(180_000)] }],
            links: [],
        },
    });
    await store.put(large);
    const metadata = await store.list(large.workflowKey);
    assert.equal(metadata.length, 1);
    assert.ok(metadata[0].chunkCount > 1);
    assert.deepEqual((await store.get(large.workflowKey, large.id)).graphData, large.graphData);
    for (const value of storage.values.values()) {
        assert.ok(new TextEncoder().encode(value).byteLength <= 1024 * 1024);
    }
});

test("malformed and oversized records are rejected before storage mutation", async () => {
    const storage = new MemoryStorage();
    const store = new SnapshotStore(storage);
    assert.throws(() => validateSnapshotRecord(record("../escape")), /Invalid snapshot id/);
    assert.throws(() => validateSnapshotRecord(record("x".repeat(65))), /Invalid snapshot id/);
    assert.throws(() => validateSnapshotRecord(record("bad-graph", { graphData: { links: [] } })), /graphData/);
    assert.throws(() => validateSnapshotRecord(record("bad-source", { source: "remote" })), /source/);
    assert.throws(() => validateSnapshotRecord(record("bad-time", { timestamp: Infinity })), /timestamp/);
    assert.throws(() => validateSnapshotRecord(record("bad-thumbnail", { thumbnail: "not base64!" })), /thumbnail/);
    assert.throws(() => validateSnapshotRecord(record("huge", {
        graphData: { nodes: [{ id: 1, data: "x".repeat(MAX_RECORD_BYTES) }] },
    })), /6 MiB/);
    await assert.rejects(store.import(Array(MAX_IMPORT_RECORDS + 1).fill(record("one"))), /at most 200/);
    assert.equal(storage.values.size, 0);
});

test("failed chunked writes remove partial data and never publish an index", async () => {
    const storage = new MemoryStorage();
    const store = new SnapshotStore(storage);
    storage.failAfter = 2;
    await assert.rejects(store.put(record("partial", {
        graphData: { nodes: [{ id: 1, data: "x".repeat(500_000) }] },
    })), /quota failure/);
    assert.equal(storage.values.size, 0);
});

test("pruning preserves locked records and keeps the newest unlocked records", async () => {
    const store = new SnapshotStore(new MemoryStorage());
    const key = "path:workflows/example.json";
    await store.put(record("old", { timestamp: 1 }));
    await store.put(record("locked", { timestamp: 2, locked: true }));
    await store.put(record("new", { timestamp: 3 }));
    assert.equal(await store.prune(key, 1, { source: "regular" }), 1);
    assert.deepEqual((await store.list(key)).map((entry) => entry.id), ["new", "locked"]);
    assert.deepEqual(await store.clearUnlocked(key), { deleted: 1, lockedCount: 1 });
    assert.deepEqual((await store.list(key)).map((entry) => entry.id), ["locked"]);
});

test("tenant isolation is inherited from separate host storage scopes", async () => {
    const tenantA = new SnapshotStore(new MemoryStorage());
    const tenantB = new SnapshotStore(new MemoryStorage());
    await tenantA.put(record("private-a"));
    assert.equal((await tenantA.list(record("x").workflowKey)).length, 1);
    assert.equal((await tenantB.list(record("x").workflowKey)).length, 0);
    assert.equal(await tenantB.get(record("x").workflowKey, "private-a"), undefined);
});

test("indexes and records fail closed across workflow boundaries", async () => {
    const storage = new MemoryStorage();
    const store = new SnapshotStore(storage);
    await store.put(record("one"));
    const otherKey = "path:workflows/other.json";
    assert.equal(await store.get(otherKey, "one"), undefined);
    const indexKey = [...storage.values.keys()].find((key) => key.endsWith("/index.json"));
    const index = JSON.parse(storage.values.get(indexKey));
    index.workflowKey = otherKey;
    storage.values.set(indexKey, JSON.stringify(index));
    await assert.rejects(store.list(record("x").workflowKey), /another workflow/);
});

test("malformed index metadata is rejected before it reaches the UI", async () => {
    const storage = new MemoryStorage();
    const store = new SnapshotStore(storage);
    await store.put(record("one"));
    const key = [...storage.values.keys()].find((item) => item.endsWith("/index.json"));
    const index = JSON.parse(storage.values.get(key));
    index.records[0].label = "x".repeat(501);
    storage.values.set(key, JSON.stringify(index));
    await assert.rejects(store.list(record("x").workflowKey), /snapshot label/);
});

test("profiles are bounded exact snapshot references", async () => {
    const profile = validateProfile({
        id: "profile-1",
        name: "Editing",
        timestamp: 10,
        activeWorkflowKey: "path:workflows/example.json",
        workflows: [{
            workflowKey: "path:workflows/example.json",
            displayName: "Example",
            snapshotId: "snap-1",
        }],
    });
    assert.equal(profile.workflows[0].snapshotId, "snap-1");
    assert.throws(() => validateProfile({ ...profile, workflows: "wrong" }), /workflows/);
    assert.throws(() => validateProfile({ ...profile, name: "x".repeat(201) }), /profile name/);
});
