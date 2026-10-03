/**
 * Pure graph comparison and snapshot-diff helpers.
 *
 * This module intentionally has no ComfyUI or DOM dependencies so the capture
 * policy and the UI use the same comparison rules, and the rules can be tested
 * without booting the frontend.
 */

export function quickHash(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        hash = ((hash << 5) - hash + str.charCodeAt(i)) | 0;
    }
    return hash;
}

export function deepEqual(a, b) {
    if (Object.is(a, b)) return true;
    if (typeof a !== typeof b || a == null || b == null) return false;

    if (Array.isArray(a) || Array.isArray(b)) {
        if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length) return false;
        for (let i = 0; i < a.length; i++) {
            if (!deepEqual(a[i], b[i])) return false;
        }
        return true;
    }

    if (typeof a === "object") {
        const aKeys = Object.keys(a).sort();
        const bKeys = Object.keys(b).sort();
        if (!deepEqual(aKeys, bKeys)) return false;
        for (const key of aKeys) {
            if (!deepEqual(a[key], b[key])) return false;
        }
        return true;
    }

    return false;
}

export function validateSnapshotData(graphData) {
    return graphData != null && typeof graphData === "object" && Array.isArray(graphData.nodes);
}

const COSMETIC_NODE_KEYS = ["pos", "size", "flags", "order", "color", "bgcolor", "boxcolor", "shape"];
const PARAM_NODE_KEYS = ["type", "title", "mode", "widgets_values", "properties"];
const CONNECTION_GRAPH_KEYS = ["links", "floatingLinks", "reroutes"];
const OTHER_MEANINGFUL_GRAPH_KEYS = ["definitions", "subgraphs", "config"];

function changedOnAnyKey(a, b, keys) {
    return keys.some((key) => !deepEqual(a?.[key], b?.[key]));
}

function meaningfulGroupState(groups) {
    return (groups || []).filter(Boolean).map((group, index) => ({
        id: group.id ?? index,
        title: group.title ?? group.name ?? "",
    })).sort((a, b) => String(a.id).localeCompare(String(b.id)));
}

/**
 * Classify the user-visible change between two serialized ComfyUI graphs.
 * Composite widget values are compared structurally, never by object identity.
 */
export function detectChangeType(prevGraph, currGraph) {
    if (!prevGraph) return "initial";

    const prevNodes = prevGraph.nodes || [];
    const currNodes = currGraph.nodes || [];
    const prevMap = new Map(prevNodes.filter(Boolean).map((node) => [node.id, node]));
    const currMap = new Map(currNodes.filter(Boolean).map((node) => [node.id, node]));

    let added = false;
    let removed = false;
    for (const id of currMap.keys()) if (!prevMap.has(id)) { added = true; break; }
    for (const id of prevMap.keys()) if (!currMap.has(id)) { removed = true; break; }

    // Node creation/removal is the most useful headline, even though ComfyUI
    // may also add/remove associated links in the same transaction.
    if (added || removed) {
        if (added && removed) return "mixed";
        return added ? "node_add" : "node_remove";
    }

    let connectionChanged = changedOnAnyKey(prevGraph, currGraph, CONNECTION_GRAPH_KEYS);
    let paramChanged = changedOnAnyKey(prevGraph, currGraph, OTHER_MEANINGFUL_GRAPH_KEYS)
        || !deepEqual(
            meaningfulGroupState(prevGraph.groups),
            meaningfulGroupState(currGraph.groups),
        );
    let cosmeticChanged = !deepEqual(prevGraph.groups || [], currGraph.groups || []);

    for (const [id, currNode] of currMap) {
        const prevNode = prevMap.get(id);
        if (!prevNode) continue;
        if (!paramChanged && changedOnAnyKey(prevNode, currNode, PARAM_NODE_KEYS)) paramChanged = true;
        if (!cosmeticChanged && changedOnAnyKey(prevNode, currNode, COSMETIC_NODE_KEYS)) cosmeticChanged = true;
        if (connectionChanged && paramChanged && cosmeticChanged) break;
    }

    if (connectionChanged && paramChanged) return "mixed";
    if (connectionChanged) return "connection";
    if (paramChanged) return "param";
    if (cosmeticChanged) return "cosmetic";

    // Preserve unfamiliar/extension-defined graph changes instead of dropping
    // them as layout noise. Exact duplicates are caught by content hash first.
    return deepEqual(prevGraph, currGraph) ? "unchanged" : "unknown";
}

export function isMeaningfulChangeType(changeType) {
    return changeType !== "unchanged" && changeType !== "cosmetic";
}

export function buildNodeLookup(...graphs) {
    const map = new Map();
    for (const graph of graphs) {
        if (!graph || !Array.isArray(graph.nodes)) continue;
        for (const node of graph.nodes) {
            if (!node || map.has(node.id)) continue;
            map.set(node.id, {
                type: node.type || "?",
                title: node.title || node.type || `#${node.id}`,
            });
        }
    }
    return map;
}

function widgetNameFor(widgetNames, node, index) {
    if (!widgetNames || !node) return null;
    const names = widgetNames.get(node.id);
    return (names && names[index]) || null;
}

function displayValue(value) {
    if (value == null) return "";
    if (typeof value === "object") {
        try { return JSON.stringify(value); } catch { return String(value); }
    }
    return String(value);
}

export function computeDetailedDiff(baseGraph, targetGraph, widgetMaps = null) {
    const empty = {
        addedNodes: [], removedNodes: [], modifiedNodes: [],
        addedLinks: [], removedLinks: [], groupChanges: [],
        summary: {
            nodesAdded: 0, nodesRemoved: 0, nodesModified: 0,
            linksAdded: 0, linksRemoved: 0, groupsChanged: 0,
        },
    };
    if (!baseGraph && !targetGraph) return empty;

    const baseNodes = baseGraph?.nodes || [];
    const targetNodes = targetGraph?.nodes || [];
    const baseMap = new Map(baseNodes.filter(Boolean).map((node) => [node.id, node]));
    const targetMap = new Map(targetNodes.filter(Boolean).map((node) => [node.id, node]));
    const addedNodes = [];
    const removedNodes = [];
    const modifiedNodes = [];

    for (const [id, node] of baseMap) {
        if (!targetMap.has(id)) {
            removedNodes.push({ id, type: node.type || "?", title: node.title || node.type || `#${id}` });
        }
    }

    for (const [id, targetNode] of targetMap) {
        const baseNode = baseMap.get(id);
        if (!baseNode) {
            addedNodes.push({ id, type: targetNode.type || "?", title: targetNode.title || targetNode.type || `#${id}` });
            continue;
        }

        const changes = {};
        if (!deepEqual(baseNode.pos, targetNode.pos)) changes.position = { from: baseNode.pos, to: targetNode.pos };
        if (!deepEqual(baseNode.size, targetNode.size)) changes.size = { from: baseNode.size, to: targetNode.size };
        if ((baseNode.title || "") !== (targetNode.title || "")) {
            changes.title = { from: baseNode.title || "", to: targetNode.title || "" };
        }
        if ((baseNode.mode || 0) !== (targetNode.mode || 0)) {
            changes.mode = { from: baseNode.mode, to: targetNode.mode };
        }

        const baseWidgets = Array.isArray(baseNode.widgets_values) ? baseNode.widgets_values : [];
        const targetWidgets = Array.isArray(targetNode.widgets_values) ? targetNode.widgets_values : [];
        if (!deepEqual(baseNode.widgets_values, targetNode.widgets_values)) {
            const widgetDiffs = [];
            const length = Math.max(baseWidgets.length, targetWidgets.length);
            for (let index = 0; index < length; index++) {
                const from = baseWidgets[index];
                const to = targetWidgets[index];
                if (!deepEqual(from, to)) {
                    widgetDiffs.push({
                        index,
                        name: widgetNameFor(widgetMaps, targetNode, index),
                        from: displayValue(from),
                        to: displayValue(to),
                    });
                }
            }
            if (widgetDiffs.length) changes.widgetValues = widgetDiffs;
        }

        const baseProps = baseNode.properties || {};
        const targetProps = targetNode.properties || {};
        const propDiffs = [];
        for (const key of new Set([...Object.keys(baseProps), ...Object.keys(targetProps)])) {
            if (!deepEqual(baseProps[key], targetProps[key])) {
                propDiffs.push({ key, from: displayValue(baseProps[key]), to: displayValue(targetProps[key]) });
            }
        }
        if (propDiffs.length) changes.properties = propDiffs;

        if (Object.keys(changes).length) {
            modifiedNodes.push({
                id,
                type: targetNode.type || "?",
                title: targetNode.title || targetNode.type || `#${id}`,
                changes,
            });
        }
    }

    const baseLinks = (baseGraph?.links || []).filter(Boolean);
    const targetLinks = (targetGraph?.links || []).filter(Boolean);
    const baseLinkMap = new Map(baseLinks.map((link) => [link[0], link]));
    const targetLinkMap = new Map(targetLinks.map((link) => [link[0], link]));
    const addedLinks = [];
    const removedLinks = [];
    const toLink = (link) => ({
        linkId: link[0], srcNodeId: link[1], srcSlot: link[2],
        destNodeId: link[3], destSlot: link[4], type: link[5],
    });

    for (const [linkId, link] of baseLinkMap) {
        const targetLink = targetLinkMap.get(linkId);
        if (!targetLink || !deepEqual(link, targetLink)) removedLinks.push(toLink(link));
    }
    for (const [linkId, link] of targetLinkMap) {
        const baseLink = baseLinkMap.get(linkId);
        if (!baseLink || !deepEqual(link, baseLink)) addedLinks.push(toLink(link));
    }

    const baseGroups = new Map((baseGraph?.groups || []).filter(Boolean).map(
        (group, index) => [group.id ?? `index:${index}`, group],
    ));
    const targetGroups = new Map((targetGraph?.groups || []).filter(Boolean).map(
        (group, index) => [group.id ?? `index:${index}`, group],
    ));
    const groupChanges = [];
    for (const [id, group] of baseGroups) {
        const targetGroup = targetGroups.get(id);
        if (!targetGroup) {
            groupChanges.push({ id, kind: "removed", title: group.title || group.name || `Group ${id}` });
        } else if (!deepEqual(group, targetGroup)) {
            const oldTitle = group.title || group.name || `Group ${id}`;
            const newTitle = targetGroup.title || targetGroup.name || `Group ${id}`;
            groupChanges.push({
                id,
                kind: "modified",
                title: newTitle,
                detail: oldTitle !== newTitle
                    ? `Title: ${oldTitle} → ${newTitle}`
                    : "Layout or group settings changed",
            });
        }
    }
    for (const [id, group] of targetGroups) {
        if (!baseGroups.has(id)) {
            groupChanges.push({ id, kind: "added", title: group.title || group.name || `Group ${id}` });
        }
    }

    return {
        addedNodes, removedNodes, modifiedNodes, addedLinks, removedLinks, groupChanges,
        summary: {
            nodesAdded: addedNodes.length,
            nodesRemoved: removedNodes.length,
            nodesModified: modifiedNodes.length,
            linksAdded: addedLinks.length,
            linksRemoved: removedLinks.length,
            groupsChanged: groupChanges.length,
        },
    };
}

export function computeCaptureMetaDiff(prevGraph, currGraph, widgetMaps = null) {
    if (!prevGraph || !currGraph) return null;
    const diff = computeDetailedDiff(prevGraph, currGraph, widgetMaps);
    const result = {};
    if (diff.addedNodes.length) result.added = diff.addedNodes.map((node) => node.title);
    if (diff.removedNodes.length) result.removed = diff.removedNodes.map((node) => node.title);

    const paramChanged = diff.modifiedNodes.filter((node) =>
        node.changes.widgetValues || node.changes.properties || node.changes.title || node.changes.mode
    );
    if (paramChanged.length) {
        result.params = paramChanged.map((node) => {
            const names = [];
            if (Array.isArray(node.changes.widgetValues)) {
                for (const value of node.changes.widgetValues) if (value.name) names.push(value.name);
            }
            if (Array.isArray(node.changes.properties)) {
                for (const value of node.changes.properties) if (value.key) names.push(value.key);
            }
            if (node.changes.title) names.push("title");
            if (node.changes.mode) names.push("mode");
            const uniqueNames = [...new Set(names)];
            if (uniqueNames.length) return `${node.title} (${uniqueNames.join(", ")})`;
            const widgetCount = Array.isArray(node.changes.widgetValues) ? node.changes.widgetValues.length : 0;
            const count = widgetCount + (node.changes.properties?.length ?? 0);
            return count ? `${node.title} (${count} value${count === 1 ? "" : "s"})` : node.title;
        });
    }
    if (diff.addedLinks.length || diff.removedLinks.length) {
        result.links = { added: diff.addedLinks.length, removed: diff.removedLinks.length };
    }
    if (diff.groupChanges.length) {
        result.groups = diff.groupChanges.map((group) => `${group.kind}: ${group.title}`);
    }
    return Object.keys(result).length ? result : null;
}

export function formatCaptureDiffLines(captureDiff) {
    if (!captureDiff) return [];
    const lines = [];
    if (captureDiff.added?.length) lines.push(`+ ${captureDiff.added.join(", ")}`);
    if (captureDiff.removed?.length) lines.push(`− ${captureDiff.removed.join(", ")}`);
    if (captureDiff.params?.length) lines.push(`~ ${captureDiff.params.join(", ")}`);
    if (captureDiff.links) {
        const parts = [];
        if (captureDiff.links.added) parts.push(`+${captureDiff.links.added} link${captureDiff.links.added === 1 ? "" : "s"}`);
        if (captureDiff.links.removed) parts.push(`−${captureDiff.links.removed} link${captureDiff.links.removed === 1 ? "" : "s"}`);
        if (parts.length) lines.push(parts.join(", "));
    }
    if (captureDiff.groups?.length) lines.push(`▣ ${captureDiff.groups.join(", ")}`);
    return lines;
}
