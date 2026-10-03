import { comfy } from "/comfy/api/v2.js";

import {
    computeDetailedDiff,
    detectChangeType,
    isMeaningfulChangeType,
    quickHash,
} from "./snapshot_diff.js";
import {
    MAX_IMPORT_RECORDS,
    MAX_SNAPSHOTS,
    SnapshotStore,
    validateGraphData,
    validateProfile,
    validateThumbnail,
} from "./snapshot_store.js";

const INITIAL_CAPTURE_DELAY_MS = 1_500;
const GRAPH_POLL_MS = 500;
const RESTORE_GUARD_MS = 1_000;

function clampInteger(value, minimum, maximum, fallback) {
    const number = Number(value);
    return Number.isInteger(number) ? Math.min(maximum, Math.max(minimum, number)) : fallback;
}

function text(value, maximum = 500) {
    return String(value ?? "").slice(0, maximum);
}

function workflowDisplayName(value) {
    const cleaned = String(value ?? "Snapshot")
        .replace(/[\\/\u0000-\u001f\u007f]/g, " ")
        .replace(/\s+/g, " ")
        .trim();
    const source = !cleaned || cleaned === "." || cleaned === ".." ? "Snapshot" : cleaned;
    const encoder = new TextEncoder();
    let result = "";
    for (const character of source) {
        if ([...result].length >= 128) break;
        const candidate = result + character;
        if (encoder.encode(candidate).byteLength > 256) break;
        result = candidate;
    }
    return result || "Snapshot";
}

function generatedId(prefix = "snap") {
    return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
}

function formatBytes(bytes) {
    if (!Number.isFinite(bytes) || bytes < 0) return "unknown";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KiB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MiB`;
}

function style(element, values) {
    Object.assign(element.style, values);
    return element;
}

function makeElement(doc, tag, { textContent, title, type, value, placeholder } = {}, styles = {}) {
    const element = doc.createElement(tag);
    if (textContent !== undefined) element.textContent = textContent;
    if (title !== undefined) element.title = title;
    if (type !== undefined) element.type = type;
    if (value !== undefined) element.value = value;
    if (placeholder !== undefined) element.placeholder = placeholder;
    return style(element, styles);
}

function button(doc, label, run, title = label) {
    const element = makeElement(doc, "button", { textContent: label, title, type: "button" }, {
        border: "1px solid var(--border-color, #555)",
        borderRadius: "5px",
        background: "var(--comfy-input-bg, #252525)",
        color: "inherit",
        padding: "5px 8px",
        cursor: "pointer",
    });
    element.addEventListener("click", (event) => {
        event.stopPropagation();
        Promise.resolve(run()).catch((error) => {
            comfy.commands.notify({
                severity: "error",
                summary: "Snapshot Manager",
                detail: text(error?.message || error, 1_000),
            });
        });
    });
    return element;
}

function currentWorkflowKey(api = comfy) {
    const current = api.workflow.current();
    if (!current) return "session:unloaded";
    return current.path ? `path:${current.path}` : `session:${current.id}`;
}

function currentWorkflowName(api = comfy) {
    const current = api.workflow.current();
    return current?.name || current?.path || "Unsaved workflow";
}

function notify(severity, summary, detail) {
    comfy.commands.notify({ severity, summary, detail: detail ? text(detail, 1_000) : undefined });
}

function confirmDialog(message) {
    return new Promise((resolve) => {
        let settled = false;
        let handle;
        const finish = (answer) => {
            if (settled) return;
            settled = true;
            handle?.close();
            resolve(answer);
        };
        handle = comfy.ui.showDialog({
            key: `SnapshotManager.confirm.${generatedId("dialog")}`,
            title: "Snapshot Manager",
            render(container) {
                const doc = container.ownerDocument;
                container.replaceChildren();
                container.appendChild(makeElement(doc, "p", { textContent: message }));
                const actions = style(doc.createElement("div"), {
                    display: "flex", gap: "8px", justifyContent: "flex-end",
                });
                actions.appendChild(button(doc, "Cancel", () => finish(false)));
                actions.appendChild(button(doc, "Continue", () => finish(true)));
                container.appendChild(actions);
            },
            onKeyDown(event) {
                if (event.key === "Escape") finish(false);
                if (event.key === "Enter" && !event.editableTarget) finish(true);
            },
            destroy() {
                if (!settled) finish(false);
            },
        });
    });
}

export class SnapshotManager {
    constructor(api = comfy) {
        this.api = api;
        this.store = new SnapshotStore(api.storage);
        this.lastHashes = new Map();
        this.lastGraphs = new Map();
        this.lastAutoAt = new Map();
        this.sessionWorkflows = new Map();
        this.captureQueue = Promise.resolve();
        this.captureTimer = undefined;
        this.pollTimer = undefined;
        this.initialTimer = undefined;
        this.lastGraphVersion = api.graph.version;
        this.suppressUntil = 0;
        this.restoring = false;
        this.sidebarContainer = undefined;
        this.sidebarRevision = 0;
        this.viewingWorkflowKey = undefined;
        this.installed = false;

        this.config = {
            autoCapture: true,
            debounceSeconds: 3,
            minAutoIntervalSeconds: 60,
            maxSnapshots: 50,
            maxNodeSnapshots: 5,
            maxAgeDays: 0,
            captureOnLoad: true,
        };
    }

    workflowKey() {
        return currentWorkflowKey(this.api);
    }

    async install() {
        if (this.installed) return;
        this.installed = true;
        this.installSettings();
        this.installCommands();
        this.installNodeHook();
        this.api.ui.addSidebarTab({
            id: "ComfyUI.SnapshotManager",
            icon: "icon-[lucide--history]",
            title: "Snapshots",
            tooltip: "Browse and restore workflow snapshots",
            render: (container) => {
                this.sidebarContainer = container;
                void this.refreshSidebar();
            },
            destroy: () => {
                this.sidebarContainer = undefined;
                this.sidebarRevision += 1;
            },
        });
        this.api.onWorkflowLoaded(() => this.handleWorkflowLoaded());
        this.api.onDocumentActivated((documentHandle) => {
            this.sessionWorkflows.set(this.workflowKey(), {
                displayName: documentHandle.name || documentHandle.path || "Unsaved workflow",
                lastSeen: Date.now(),
            });
            this.viewingWorkflowKey = undefined;
            void this.handleWorkflowLoaded();
        });
        this.pollTimer = setInterval(() => this.pollGraph(), GRAPH_POLL_MS);
        await this.handleWorkflowLoaded();
    }

    installSettings() {
        const declarations = [
            ["autoCapture", "Auto-capture on edit", "boolean", true, undefined],
            ["debounceSeconds", "Capture delay (seconds)", "slider", 3, { min: 1, max: 30, step: 1 }],
            ["minAutoIntervalSeconds", "Minimum auto interval (seconds)", "slider", 60, { min: 0, max: 300, step: 15 }],
            ["maxSnapshots", "Maximum snapshots per workflow", "slider", 50, { min: 5, max: 200, step: 5 }],
            ["maxNodeSnapshots", "Maximum node-triggered snapshots", "slider", 5, { min: 1, max: 50, step: 1 }],
            ["maxAgeDays", "Delete unlocked snapshots older than (days)", "slider", 0, { min: 0, max: 365, step: 1 }],
            ["captureOnLoad", "Initial snapshot for empty histories", "boolean", true, undefined],
        ];
        for (const [name, label, type, defaultValue, attrs] of declarations) {
            const id = `SnapshotManager.${name}`;
            const current = this.api.settings.get(id);
            if (current !== undefined) this.config[name] = current;
            this.api.settings.declare({
                id,
                name: label,
                type,
                defaultValue,
                attrs,
                category: ["Snapshot Manager", "Capture", label],
                onChange: (value) => {
                    this.config[name] = value;
                    if (name === "autoCapture" && value === false && this.captureTimer) {
                        clearTimeout(this.captureTimer);
                        this.captureTimer = undefined;
                    }
                },
            });
        }
    }

    installCommands() {
        const capture = () => this.capture("Manual", {
            source: "manual", dedupe: false, skipCosmetic: false,
        }).then((saved) => {
            if (saved) notify("success", "Snapshot saved");
        });
        this.api.commands.register({
            id: "SnapshotManager.capture",
            label: "Snapshot Manager: Capture now",
            run: capture,
            keybinding: { key: "s", ctrl: true },
            scope: "canvas",
        });
        this.api.commands.register({
            id: "SnapshotManager.captureMac",
            label: "Snapshot Manager: Capture now (macOS)",
            run: capture,
            keybinding: { key: "s", meta: true },
            scope: "canvas",
        });
        this.api.ui.addActionBarButton({
            id: "SnapshotManager.capture.button",
            icon: "icon-[lucide--camera]",
            label: "Snapshot",
            tooltip: "Capture the current workflow",
            run: capture,
        });
    }

    installNodeHook() {
        this.api.defs.extend("SaveSnapshot", (builder) => {
            builder.onExecuted((_node, result) => {
                const request = result.raw?.snapshot_manager_capture?.[0];
                if (request && typeof request.label === "string") {
                    void this.capture(request.label, {
                        source: "node", dedupe: false, skipCosmetic: false,
                        thumbnail: validateThumbnail(request.thumbnail),
                    });
                }
            });
        });
    }

    async handleWorkflowLoaded() {
        const workflowKey = this.workflowKey();
        this.sessionWorkflows.set(workflowKey, {
            displayName: currentWorkflowName(this.api),
            lastSeen: Date.now(),
        });
        this.lastGraphVersion = this.api.graph.version;
        try {
            const graph = validateGraphData(await this.api.workflow.snapshot());
            this.lastHashes.set(workflowKey, quickHash(JSON.stringify(graph)));
            this.lastGraphs.set(workflowKey, graph);
            const records = await this.store.list(workflowKey);
            if (records.length === 0 && this.config.captureOnLoad && graph.nodes.length > 0) {
                if (this.initialTimer) clearTimeout(this.initialTimer);
                this.initialTimer = setTimeout(() => {
                    this.initialTimer = undefined;
                    void this.capture("Initial", {
                        source: "initial", dedupe: true, skipCosmetic: false,
                    });
                }, INITIAL_CAPTURE_DELAY_MS);
            }
        } catch (error) {
            notify("error", "Snapshot history unavailable", error?.message || error);
        }
        void this.refreshSidebar();
    }

    pollGraph() {
        const version = this.api.graph.version;
        if (version === this.lastGraphVersion) return;
        this.lastGraphVersion = version;
        this.scheduleAutoCapture();
    }

    scheduleAutoCapture() {
        if (!this.config.autoCapture || this.restoring) return;
        if (this.captureTimer) clearTimeout(this.captureTimer);
        const workflowKey = this.workflowKey();
        const now = Date.now();
        const debounce = clampInteger(this.config.debounceSeconds, 1, 30, 3) * 1_000;
        const minimum = clampInteger(this.config.minAutoIntervalSeconds, 0, 300, 60) * 1_000;
        const remaining = Math.max(0, minimum - (now - (this.lastAutoAt.get(workflowKey) || 0)));
        const suppression = Math.max(0, this.suppressUntil - now);
        this.captureTimer = setTimeout(() => {
            this.captureTimer = undefined;
            if (this.restoring || Date.now() < this.suppressUntil) {
                this.scheduleAutoCapture();
                return;
            }
            void this.capture("Auto", { source: "auto", dedupe: true, skipCosmetic: true });
        }, Math.max(debounce, remaining, suppression));
    }

    capture(label, options = {}) {
        const task = this.captureQueue.catch(() => undefined).then(() => this._capture(label, options));
        this.captureQueue = task.catch(() => undefined);
        return task;
    }

    async _capture(label, {
        source = "auto", dedupe = source === "auto", skipCosmetic = source === "auto",
        thumbnail = undefined,
    } = {}) {
        if (this.restoring && source !== "restore_guard") return false;
        if (source === "auto" && !this.config.autoCapture) return false;
        const workflowKey = this.workflowKey();
        const graphData = validateGraphData(await this.api.workflow.snapshot());
        if (graphData.nodes.length === 0) return false;
        const serialized = JSON.stringify(graphData);
        const hash = quickHash(serialized);
        if (dedupe && hash === this.lastHashes.get(workflowKey)) return false;
        const previous = this.lastGraphs.get(workflowKey);
        const changeType = detectChangeType(previous, graphData);
        if (skipCosmetic && !isMeaningfulChangeType(changeType)) return false;

        const record = {
            id: generatedId(),
            workflowKey,
            timestamp: Date.now(),
            label: text(label || "Snapshot", 500) || "Snapshot",
            source,
            locked: false,
            graphData,
            changeType,
            ...(thumbnail === undefined ? {} : { thumbnail: validateThumbnail(thumbnail) }),
        };
        const max = source === "node"
            ? clampInteger(this.config.maxNodeSnapshots, 1, 50, 5)
            : clampInteger(this.config.maxSnapshots, 5, MAX_SNAPSHOTS, 50);
        const group = source === "node" ? "node" : "regular";
        await this.store.prune(workflowKey, Math.max(0, max - 1), {
            source: group,
            maxAgeDays: clampInteger(this.config.maxAgeDays, 0, 365, 0),
        });
        await this.store.put(record);
        this.lastHashes.set(workflowKey, hash);
        this.lastGraphs.set(workflowKey, graphData);
        if (source === "auto") this.lastAutoAt.set(workflowKey, record.timestamp);
        await this.refreshSidebar();
        return record.id;
    }

    async protectCurrent() {
        try {
            await this.capture("Return point", {
                source: "restore_guard", dedupe: true, skipCosmetic: false,
            });
            return true;
        } catch (error) {
            notify("error", "Restore cancelled", `Current workflow could not be protected: ${error?.message || error}`);
            return false;
        }
    }

    async restore(workflowKey, snapshotId) {
        const record = await this.store.get(workflowKey, snapshotId);
        if (!record) throw new Error("Snapshot not found");
        validateGraphData(record.graphData);
        if (!await this.protectCurrent()) return;
        this.restoring = true;
        this.suppressUntil = Date.now() + RESTORE_GUARD_MS;
        try {
            await this.api.workflow.open(record.graphData, { mode: "replace" });
            notify("success", "Snapshot restored", record.label);
        } finally {
            this.restoring = false;
        }
    }

    showDiff(workflowKey, snapshotId) {
        return Promise.all([
            this.store.get(workflowKey, snapshotId),
            this.api.workflow.snapshot(),
        ]).then(([record, current]) => {
            if (!record) throw new Error("Snapshot not found");
            const diff = computeDetailedDiff(record.graphData, validateGraphData(current));
            comfy.ui.showDialog({
                key: `SnapshotManager.diff.${snapshotId}`,
                title: `Snapshot diff — ${record.label}`,
                render(container) {
                    const doc = container.ownerDocument;
                    container.replaceChildren();
                    const summary = diff.summary;
                    container.appendChild(makeElement(doc, "p", {
                        textContent: [
                            `Nodes +${summary.nodesAdded} / -${summary.nodesRemoved} / ${summary.nodesModified} changed`,
                            `Links +${summary.linksAdded} / -${summary.linksRemoved}`,
                            `Groups ${summary.groupsChanged} changed`,
                        ].join(" · "),
                    }));
                    const pre = makeElement(doc, "pre", {
                        textContent: JSON.stringify(diff, null, 2),
                    }, { maxHeight: "55vh", overflow: "auto", whiteSpace: "pre-wrap" });
                    container.appendChild(pre);
                },
            });
        });
    }

    async showThumbnail(workflowKey, snapshotId) {
        const record = await this.store.get(workflowKey, snapshotId);
        if (!record?.thumbnail) throw new Error("Snapshot has no thumbnail");
        const thumbnail = validateThumbnail(record.thumbnail);
        comfy.ui.showDialog({
            key: `SnapshotManager.thumbnail.${snapshotId}`,
            title: `Snapshot preview — ${record.label}`,
            render(container) {
                const image = makeElement(container.ownerDocument, "img", {
                    title: record.label,
                }, { maxWidth: "100%", maxHeight: "70vh", objectFit: "contain" });
                image.src = `data:image/jpeg;base64,${thumbnail}`;
                container.replaceChildren(image);
            },
        });
    }

    async exportWorkflow(workflowKey) {
        const payload = await this.store.export(workflowKey);
        const safe = workflowKey.replace(/[^A-Za-z0-9._-]+/g, "-").slice(0, 80) || "workflow";
        await this.api.files.download({
            name: `${safe}-snapshots.json`,
            mimeType: "application/json",
            bytes: new TextEncoder().encode(JSON.stringify(payload, null, 2)),
        });
    }

    async importWorkflow() {
        const picked = await this.api.files.pick({
            extensions: ["json"],
            mimeTypes: ["application/json"],
            maxBytes: 8 * 1024 * 1024,
        });
        if (!picked) return;
        let payload;
        try {
            payload = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(picked.bytes));
        } catch {
            throw new Error("Import file is not valid UTF-8 JSON");
        }
        if (!payload || payload.version !== 1 || !Array.isArray(payload.records)) {
            throw new Error("Import file is not a Snapshot Manager export");
        }
        if (payload.records.length > MAX_IMPORT_RECORDS) throw new Error("Import contains too many snapshots");
        const imported = await this.store.import(payload.records);
        notify("success", "Snapshots imported", `${imported} snapshot${imported === 1 ? "" : "s"}`);
        await this.refreshSidebar();
    }

    async saveProfile() {
        const name = await this.api.ui.prompt({ label: "Profile name", value: "My Profile" });
        if (name === undefined) return;
        const known = await this.store.workflowKeys();
        const workflows = [];
        for (const item of known.slice(0, 50)) {
            const records = await this.store.list(item.workflowKey);
            const latest = records[0];
            if (!latest) continue;
            workflows.push({
                workflowKey: item.workflowKey,
                displayName: this.sessionWorkflows.get(item.workflowKey)?.displayName || item.workflowKey,
                snapshotId: latest.id,
            });
        }
        const profile = validateProfile({
            id: generatedId("profile"),
            version: 2,
            name: text(name.trim() || "My Profile", 200),
            timestamp: Date.now(),
            activeWorkflowKey: this.workflowKey(),
            workflows,
        });
        await this.store.putProfile(profile);
        notify("success", "Profile saved", `${profile.name} (${profile.workflows.length} workflows)`);
        await this.refreshSidebar();
    }

    async loadProfile(profile) {
        const ordered = profile.workflows.slice().sort((left, right) =>
            Number(left.workflowKey === profile.activeWorkflowKey)
            - Number(right.workflowKey === profile.activeWorkflowKey)
        );
        if (!await this.protectCurrent()) return;
        this.restoring = true;
        this.suppressUntil = Date.now() + RESTORE_GUARD_MS;
        let opened = 0;
        try {
            for (const item of ordered) {
                if (!item.snapshotId) continue;
                const record = await this.store.get(item.workflowKey, item.snapshotId);
                if (!record) continue;
                validateGraphData(record.graphData);
                await this.api.workflow.open(record.graphData, {
                    mode: "new",
                    name: workflowDisplayName(item.displayName),
                });
                opened += 1;
            }
        } finally {
            this.restoring = false;
        }
        notify("success", "Profile restored", `${opened} workflow${opened === 1 ? "" : "s"}`);
    }

    async refreshSidebar() {
        const container = this.sidebarContainer;
        if (!container) return;
        const revision = ++this.sidebarRevision;
        const workflowKey = this.viewingWorkflowKey || this.workflowKey();
        let records;
        let workflows;
        let profiles;
        let usage;
        try {
            [records, workflows, profiles, usage] = await Promise.all([
                this.store.list(workflowKey),
                this.store.workflowKeys(),
                this.store.listProfiles(),
                this.store.usage(),
            ]);
        } catch (error) {
            if (container === this.sidebarContainer && revision === this.sidebarRevision) {
                container.replaceChildren();
                container.appendChild(makeElement(container.ownerDocument, "p", {
                    textContent: `Snapshot history unavailable: ${text(error?.message || error, 1_000)}`,
                }));
            }
            return;
        }
        if (container !== this.sidebarContainer || revision !== this.sidebarRevision) return;
        this.renderSidebar(container, { workflowKey, records, workflows, profiles, usage });
    }

    renderSidebar(container, { workflowKey, records, workflows, profiles, usage }) {
        const doc = container.ownerDocument;
        container.replaceChildren();
        style(container, {
            display: "flex", flexDirection: "column", gap: "8px", padding: "8px",
            overflow: "auto", color: "inherit", height: "100%", boxSizing: "border-box",
        });

        const header = style(doc.createElement("div"), { display: "flex", gap: "6px", flexWrap: "wrap" });
        header.appendChild(button(doc, "Capture", () => this.capture("Manual", {
            source: "manual", dedupe: false, skipCosmetic: false,
        })));
        header.appendChild(button(doc, "Import", () => this.importWorkflow()));
        header.appendChild(button(doc, "Export", () => this.exportWorkflow(workflowKey)));
        header.appendChild(button(doc, "Refresh", () => this.refreshSidebar()));
        container.appendChild(header);

        const selector = makeElement(doc, "select", { title: "Workflow history" }, {
            width: "100%", padding: "5px", background: "var(--comfy-input-bg, #252525)", color: "inherit",
        });
        const available = workflows.some((item) => item.workflowKey === this.workflowKey())
            ? workflows
            : [{ workflowKey: this.workflowKey(), count: 0 }, ...workflows];
        for (const item of available) {
            const option = makeElement(doc, "option", {
                textContent: `${item.workflowKey} (${item.count})`,
                value: item.workflowKey,
            });
            option.selected = item.workflowKey === workflowKey;
            selector.appendChild(option);
        }
        selector.addEventListener("change", () => {
            this.viewingWorkflowKey = selector.value === this.workflowKey() ? undefined : selector.value;
            void this.refreshSidebar();
        });
        container.appendChild(selector);

        container.appendChild(makeElement(doc, "div", {
            textContent: `${records.length} snapshot${records.length === 1 ? "" : "s"} · ${formatBytes(usage.usedBytes)} used${usage.quotaBytes ? ` of ${formatBytes(usage.quotaBytes)}` : ""}`,
        }, { opacity: "0.75", fontSize: "12px" }));

        if (records.length === 0) {
            container.appendChild(makeElement(doc, "p", { textContent: "No snapshots for this workflow." }));
        }
        for (const record of records) {
            const row = style(doc.createElement("article"), {
                border: "1px solid var(--border-color, #555)", borderRadius: "7px", padding: "7px",
                display: "flex", flexDirection: "column", gap: "5px",
            });
            const title = style(doc.createElement("div"), {
                display: "flex", justifyContent: "space-between", gap: "8px",
            });
            title.appendChild(makeElement(doc, "strong", { textContent: record.label }));
            title.appendChild(makeElement(doc, "span", {
                textContent: new Date(record.timestamp).toLocaleString(),
            }, { opacity: "0.7", fontSize: "11px" }));
            row.appendChild(title);
            row.appendChild(makeElement(doc, "div", {
                textContent: `${record.source} · ${record.nodeCount} nodes · ${record.changeType}`,
            }, { opacity: "0.75", fontSize: "12px" }));
            const actions = style(doc.createElement("div"), { display: "flex", gap: "5px", flexWrap: "wrap" });
            actions.appendChild(button(doc, "Restore", () => this.restore(workflowKey, record.id)));
            actions.appendChild(button(doc, "Diff", () => this.showDiff(workflowKey, record.id)));
            if (record.hasThumbnail) {
                actions.appendChild(button(doc, "Preview", () => this.showThumbnail(workflowKey, record.id)));
            }
            actions.appendChild(button(doc, record.locked ? "Unlock" : "Lock", async () => {
                await this.store.setLocked(workflowKey, record.id, !record.locked);
                await this.refreshSidebar();
            }));
            actions.appendChild(button(doc, "Delete", async () => {
                if (!await confirmDialog(`Delete snapshot “${record.label}”?`)) return;
                await this.store.delete(workflowKey, record.id);
                await this.refreshSidebar();
            }));
            row.appendChild(actions);
            container.appendChild(row);
        }

        const clear = button(doc, "Clear unlocked", async () => {
            if (!await confirmDialog("Delete every unlocked snapshot in this workflow?")) return;
            await this.store.clearUnlocked(workflowKey);
            await this.refreshSidebar();
        });
        container.appendChild(clear);

        const profileHeading = style(doc.createElement("div"), {
            display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "8px",
        });
        profileHeading.appendChild(makeElement(doc, "strong", { textContent: "Profiles" }));
        profileHeading.appendChild(button(doc, "Save profile", () => this.saveProfile()));
        container.appendChild(profileHeading);
        if (profiles.length === 0) {
            container.appendChild(makeElement(doc, "div", { textContent: "No profiles saved." }, { opacity: "0.7" }));
        }
        for (const profile of profiles) {
            const row = style(doc.createElement("div"), {
                display: "flex", gap: "5px", alignItems: "center",
            });
            const label = makeElement(doc, "span", {
                textContent: `${profile.name} (${profile.workflows.length})`,
                title: profile.name,
            }, { flex: "1", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" });
            row.appendChild(label);
            row.appendChild(button(doc, "Load", () => this.loadProfile(profile)));
            row.appendChild(button(doc, "×", async () => {
                if (!await confirmDialog(`Delete profile “${profile.name}”?`)) return;
                await this.store.deleteProfile(profile.id);
                await this.refreshSidebar();
            }, "Delete profile"));
            container.appendChild(row);
        }
    }
}

export const snapshotManager = new SnapshotManager(comfy);
await snapshotManager.install();
