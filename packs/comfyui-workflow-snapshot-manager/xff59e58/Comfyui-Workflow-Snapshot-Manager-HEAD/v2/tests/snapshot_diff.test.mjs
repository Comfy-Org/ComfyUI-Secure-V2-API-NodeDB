import test from "node:test";
import assert from "node:assert/strict";

import {
    computeDetailedDiff,
    deepEqual,
    detectChangeType,
    isMeaningfulChangeType,
} from "../js/snapshot_diff.js";

function graph(overrides = {}) {
    return {
        nodes: [{
            id: 1,
            type: "Example",
            pos: [10, 20],
            size: [200, 100],
            flags: {},
            mode: 0,
            widgets_values: [{ enabled: true, values: [1, 2] }],
            properties: { precision: { value: 16 } },
        }],
        links: [[1, 1, 0, 2, 0, "IMAGE"]],
        ...overrides,
    };
}

test("deepEqual compares composite widget values structurally", () => {
    assert.equal(deepEqual({ a: [1, { b: true }] }, { a: [1, { b: true }] }), true);
    assert.equal(deepEqual({ a: [1, { b: true }] }, { a: [1, { b: false }] }), false);
});

test("equal composite widget content is not a parameter change", () => {
    const before = graph();
    const after = structuredClone(before);
    after.nodes[0].pos = [40, 60];
    assert.equal(detectChangeType(before, after), "cosmetic");
    assert.equal(isMeaningfulChangeType(detectChangeType(before, after)), false);
});

test("nested widget content changes are parameter changes", () => {
    const before = graph();
    const after = structuredClone(before);
    after.nodes[0].widgets_values[0].values[1] = 3;
    assert.equal(detectChangeType(before, after), "param");
});

test("properties changed during a move remain meaningful", () => {
    const before = graph();
    const after = structuredClone(before);
    after.nodes[0].pos = [100, 200];
    after.nodes[0].properties.precision.value = 32;
    assert.equal(detectChangeType(before, after), "param");
});

test("a rewired link with the same id is represented as remove plus add", () => {
    const before = graph();
    const after = structuredClone(before);
    after.links[0][3] = 3;
    assert.equal(detectChangeType(before, after), "connection");
    const diff = computeDetailedDiff(before, after);
    assert.equal(diff.removedLinks.length, 1);
    assert.equal(diff.addedLinks.length, 1);
    assert.equal(diff.removedLinks[0].destNodeId, 2);
    assert.equal(diff.addedLinks[0].destNodeId, 3);
});

test("node additions take precedence over their associated links", () => {
    const before = graph({ nodes: [], links: [] });
    const after = graph();
    assert.equal(detectChangeType(before, after), "node_add");
});

test("group movement is cosmetic but group naming is meaningful", () => {
    const before = graph({
        groups: [{ id: 1, title: "Inputs", bounding: [0, 0, 200, 200], color: "#333" }],
    });
    const moved = structuredClone(before);
    moved.groups[0].bounding = [50, 50, 200, 200];
    assert.equal(detectChangeType(before, moved), "cosmetic");

    const renamed = structuredClone(before);
    renamed.groups[0].title = "Sources";
    assert.equal(detectChangeType(before, renamed), "param");
    const diff = computeDetailedDiff(before, renamed);
    assert.equal(diff.summary.groupsChanged, 1);
    assert.match(diff.groupChanges[0].detail, /Inputs.*Sources/);
});
