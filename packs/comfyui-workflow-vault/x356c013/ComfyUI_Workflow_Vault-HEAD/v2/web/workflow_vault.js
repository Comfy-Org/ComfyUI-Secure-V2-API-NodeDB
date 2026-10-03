import { comfy } from "/comfy/api/v2.js";
import { MAX_ARCHIVE_BYTES, MAX_MEDIA_BYTES, VaultStore } from "./vault_store.js";

const textEncoder = new TextEncoder();
const textDecoder = new TextDecoder();

function cleanName(value, fallback = "Workflow") {
    const cleaned = String(value ?? "").replace(/[\\/\u0000-\u001f\u007f]/g, " ").replace(/\s+/g, " ").trim();
    return [...(cleaned && cleaned !== "." && cleaned !== ".." ? cleaned : fallback)].slice(0, 128).join("");
}

function el(doc, tag, text, attributes = {}) {
    const node = doc.createElement(tag);
    if (text !== undefined) node.textContent = String(text);
    for (const [name, value] of Object.entries(attributes)) {
        if (name === "className") node.className = value;
        else if (name === "type" || name === "placeholder" || name === "value" || name === "title") node[name] = value;
        else node.setAttribute(name, value);
    }
    return node;
}

function button(doc, label, run, title = label) {
    const result = el(doc, "button", label, { type: "button", title });
    result.addEventListener("click", (event) => {
        event.stopPropagation();
        Promise.resolve(run()).catch((error) => notify("error", error.message || error));
    });
    return result;
}

function field(doc, label, value = "", { multiline = false } = {}) {
    const wrapper = el(doc, "label");
    wrapper.appendChild(el(doc, "span", label));
    const input = el(doc, multiline ? "textarea" : "input", undefined, { value: String(value) });
    input.value = String(value);
    wrapper.appendChild(input);
    return { wrapper, input };
}

function notify(severity, detail) {
    comfy.commands.notify({ severity, summary: "Workflow Vault", detail: String(detail).slice(0, 1000) });
}

function timestamp(value) {
    return new Date(value).toLocaleString();
}

function bytesFromBase64(value) {
    const binary = atob(value); const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
    return bytes;
}

export class WorkflowVault {
    constructor(api = comfy) {
        this.api = api;
        this.store = new VaultStore(api.storage);
        this.sidebar = undefined;
        this.dialog = undefined;
        this.query = "";
        this.showArchived = false;
        this.installed = false;
    }

    async install() {
        if (this.installed) return;
        this.installed = true;
        this.api.ui.addSidebarTab({
            id: "Comfy.WorkflowVault",
            icon: "icon-[lucide--archive]",
            title: "Workflow Vault",
            tooltip: "Browse and save reusable workflows",
            render: (container) => { this.sidebar = container; void this.renderSidebar(); },
            destroy: () => { this.sidebar = undefined; },
        });
        this.api.ui.addActionBarButton({
            id: "Comfy.WorkflowVault.save",
            icon: "icon-[lucide--archive-restore]",
            label: "Save to Vault",
            tooltip: "Save the current workflow to Workflow Vault",
            run: () => this.showSaveDialog(),
        });
        this.api.commands.register({
            id: "Comfy.WorkflowVault.open",
            label: "Workflow Vault: Open vault",
            keybinding: { key: "v", ctrl: true, shift: true },
            scope: "canvas",
            run: () => this.showVaultDialog(),
        });
        this.api.commands.register({
            id: "Comfy.WorkflowVault.save",
            label: "Workflow Vault: Save current workflow",
            keybinding: { key: "s", ctrl: true, alt: true },
            scope: "canvas",
            run: () => this.showSaveDialog(),
        });
        await this.store.load();
    }

    async renderSidebar() {
        if (!this.sidebar) return;
        const container = this.sidebar; const doc = container.ownerDocument;
        container.replaceChildren();
        const header = el(doc, "div");
        header.appendChild(el(doc, "strong", "Workflow Vault"));
        header.appendChild(button(doc, "Open", () => this.showVaultDialog()));
        header.appendChild(button(doc, "Save", () => this.showSaveDialog()));
        container.appendChild(header);
        const state = await this.store.state();
        container.appendChild(el(doc, "p", `${state.entries.length} workflow${state.entries.length === 1 ? "" : "s"} in ${state.profiles.find((item) => item.id === state.activeProfileId)?.name || "vault"}`));
        const recent = state.entries.filter((entry) => entry.status !== "archived").sort((a, b) => b.updatedAt - a.updatedAt).slice(0, 8);
        const list = el(doc, "div");
        for (const entry of recent) {
            const row = button(doc, `${entry.name} · ${entry.versions.length} version${entry.versions.length === 1 ? "" : "s"}`, () => this.showEntryDialog(entry.id));
            row.dataset.entryId = entry.id; list.appendChild(row);
        }
        if (!recent.length) list.appendChild(el(doc, "p", "Save the current workflow to begin."));
        container.appendChild(list);
    }

    async matchingEntries() {
        const state = await this.store.state(); const needle = this.query.trim().toLowerCase();
        return state.entries.filter((entry) => (this.showArchived || entry.status !== "archived") && (!needle || [entry.name, entry.description, entry.notes, ...entry.tags].join(" ").toLowerCase().includes(needle))).sort((a, b) => b.updatedAt - a.updatedAt);
    }

    showVaultDialog() {
        this.dialog?.close();
        this.dialog = this.api.ui.showDialog({
            key: "Comfy.WorkflowVault.browser",
            title: "Workflow Vault",
            render: (container) => { void this.renderVault(container); },
            onKeyDown: (event) => {
                if (event.key === "Escape") this.dialog?.close();
                if (!event.editableTarget && event.key.toLowerCase() === "s") void this.showSaveDialog();
            },
            destroy: () => { this.dialog = undefined; },
        });
    }

    async renderVault(container) {
        const doc = container.ownerDocument; container.replaceChildren();
        const state = await this.store.state();
        const toolbar = el(doc, "div");
        const search = el(doc, "input", undefined, { type: "search", placeholder: "Search workflows, tags, descriptions…", value: this.query });
        search.value = this.query;
        search.addEventListener("input", () => { this.query = search.value; void this.renderVault(container); });
        toolbar.appendChild(search);
        toolbar.appendChild(button(doc, "Save current", () => this.showSaveDialog()));
        toolbar.appendChild(button(doc, "Import", () => this.importArchive()));
        toolbar.appendChild(button(doc, "Export", () => this.exportArchive()));
        toolbar.appendChild(button(doc, this.showArchived ? "Hide archived" : "Show archived", () => { this.showArchived = !this.showArchived; return this.renderVault(container); }));
        container.appendChild(toolbar);

        const profiles = el(doc, "div");
        profiles.appendChild(el(doc, "span", "Vault: "));
        for (const profile of state.profiles) {
            profiles.appendChild(button(doc, profile.id === state.activeProfileId ? `● ${profile.name}` : profile.name, async () => {
                await this.store.activateProfile(profile.id); await this.renderVault(container); await this.renderSidebar();
            }));
        }
        profiles.appendChild(button(doc, "+ Profile", async () => {
            const name = await this.api.ui.prompt({ label: "New vault profile name", value: "" });
            if (name) { await this.store.createProfile(name); await this.renderVault(container); await this.renderSidebar(); }
        }));
        profiles.appendChild(button(doc, "Manage", () => this.showProfilesDialog()));
        container.appendChild(profiles);

        const list = el(doc, "div");
        for (const entry of await this.matchingEntries()) {
            const row = el(doc, "section"); row.dataset.entryId = entry.id;
            row.appendChild(el(doc, "strong", entry.name));
            row.appendChild(el(doc, "span", ` ${entry.status} · ${entry.versions.length} version${entry.versions.length === 1 ? "" : "s"} · ${timestamp(entry.updatedAt)}`));
            if (entry.description) row.appendChild(el(doc, "p", entry.description));
            row.appendChild(button(doc, "Details", () => this.showEntryDialog(entry.id)));
            row.appendChild(button(doc, "Open new", () => this.openEntry(entry.id, "new")));
            row.appendChild(button(doc, "Replace", () => this.openEntry(entry.id, "replace")));
            list.appendChild(row);
        }
        if (!list.children.length) list.appendChild(el(doc, "p", "No workflows match this vault view."));
        container.appendChild(list);
        const footprint = await this.store.footprint();
        container.appendChild(el(doc, "small", `${footprint.entries} entries · ${footprint.usedBytes} stored bytes${footprint.quotaBytes ? ` of ${footprint.quotaBytes}` : ""}`));
    }

    async showSaveDialog() {
        const current = this.api.workflow.current();
        const graph = await this.api.workflow.snapshot();
        let handle;
        handle = this.api.ui.showDialog({
            key: "Comfy.WorkflowVault.saveDialog",
            title: "Save workflow to Vault",
            render: (container) => {
                const doc = container.ownerDocument; container.replaceChildren();
                const name = field(doc, "Name", cleanName(current?.name || "Workflow"));
                const description = field(doc, "Description", "", { multiline: true });
                const tags = field(doc, "Tags (comma separated)", "");
                container.append(name.wrapper, description.wrapper, tags.wrapper);
                container.appendChild(button(doc, "Save new entry", async () => {
                    await this.store.createEntry({ name: name.input.value, description: description.input.value, tags: tags.input.value.split(",").map((item) => item.trim()).filter(Boolean), workflow: graph });
                    handle.close(); await this.renderSidebar(); notify("success", "Workflow saved to the vault");
                }));
            },
            onKeyDown: (event) => { if (event.key === "Escape") handle.close(); },
        });
    }

    async showEntryDialog(entryId) {
        const entry = await this.store.getEntry(entryId); let handle;
        handle = this.api.ui.showDialog({
            key: `Comfy.WorkflowVault.entry.${entry.id}`,
            title: entry.name,
            render: (container) => {
                const doc = container.ownerDocument; container.replaceChildren();
                container.appendChild(el(doc, "p", entry.description || "No description"));
                container.appendChild(el(doc, "p", entry.notes || "No notes"));
                container.appendChild(el(doc, "p", `Tags: ${entry.tags.join(", ") || "none"}`));
                const actions = el(doc, "div");
                actions.appendChild(button(doc, "Open new tab", () => this.openEntry(entry.id, "new")));
                actions.appendChild(button(doc, "Replace current", () => this.openEntry(entry.id, "replace")));
                actions.appendChild(button(doc, "Save current as version", async () => { await this.store.addVersion(entry.id, await this.api.workflow.snapshot(), "Saved version"); handle.close(); await this.showEntryDialog(entry.id); }));
                actions.appendChild(button(doc, "Edit details", () => { handle.close(); return this.showEditDialog(entry.id); }));
                actions.appendChild(button(doc, entry.status === "archived" ? "Unarchive" : "Archive", async () => { await this.store.updateEntry(entry.id, { status: entry.status === "archived" ? "ready" : "archived" }); handle.close(); await this.renderSidebar(); }));
                actions.appendChild(button(doc, "Duplicate", async () => { await this.store.duplicateEntry(entry.id); handle.close(); await this.renderSidebar(); }));
                actions.appendChild(button(doc, "Delete", async () => { await this.store.deleteEntry(entry.id); handle.close(); await this.renderSidebar(); }));
                container.appendChild(actions);
                const versions = el(doc, "div");
                for (const version of [...entry.versions].reverse()) {
                    const row = el(doc, "div");
                    row.appendChild(el(doc, "span", `${version.label} · ${timestamp(version.createdAt)}${version.id === entry.currentVersionId ? " · current" : ""}`));
                    row.appendChild(button(doc, "Open new", () => this.openEntry(entry.id, "new", version.id)));
                    row.appendChild(button(doc, "Replace", () => this.openEntry(entry.id, "replace", version.id)));
                    if (version.id !== entry.currentVersionId) row.appendChild(button(doc, "Promote", () => this.store.promoteVersion(entry.id, version.id)));
                    versions.appendChild(row);
                }
                container.appendChild(versions);
                const examples = el(doc, "div"); examples.appendChild(el(doc, "h3", "Examples"));
                for (const example of entry.examples) {
                    const row = el(doc, "div"); row.appendChild(el(doc, "span", `${example.role}: ${example.name} (${example.bytes} bytes)`));
                    row.appendChild(button(doc, "Download", () => this.api.files.download({ name: cleanName(example.name, "example.bin"), mimeType: example.type, bytes: bytesFromBase64(example.data) })));
                    row.appendChild(button(doc, "Remove", () => this.store.deleteExample(entry.id, example.id))); examples.appendChild(row);
                }
                examples.appendChild(button(doc, "Add media", () => this.addExamples(entry.id)));
                container.appendChild(examples);
            },
            onKeyDown: (event) => {
                if (event.key === "Escape") handle.close();
                if (!event.editableTarget && event.key.toLowerCase() === "o") void this.openEntry(entry.id, "new");
            },
        });
    }

    async openEntry(entryId, mode, versionId = undefined) {
        const entry = await this.store.getEntry(entryId);
        const version = versionId ? await this.store.getVersion(entryId, versionId) : entry.versions.find((item) => item.id === entry.currentVersionId);
        await this.api.workflow.open(version.workflow, mode === "new" ? { mode: "new", name: cleanName(entry.name) } : { mode: "replace" });
        notify("success", mode === "new" ? "Opened workflow in a new tab" : "Replaced current workflow");
    }

    async showEditDialog(entryId) {
        const entry = await this.store.getEntry(entryId); let handle;
        handle = this.api.ui.showDialog({
            key: `Comfy.WorkflowVault.edit.${entry.id}`,
            title: `Edit ${entry.name}`,
            render: (container) => {
                const doc = container.ownerDocument; container.replaceChildren();
                const name = field(doc, "Name", entry.name);
                const description = field(doc, "Description", entry.description, { multiline: true });
                const notes = field(doc, "Documentation", entry.notes, { multiline: true });
                const tags = field(doc, "Tags", entry.tags.join(", "));
                container.append(name.wrapper, description.wrapper, notes.wrapper, tags.wrapper);
                container.appendChild(button(doc, "Save", async () => {
                    await this.store.updateEntry(entry.id, { name: name.input.value, description: description.input.value, notes: notes.input.value, tags: tags.input.value.split(",").map((item) => item.trim()).filter(Boolean) });
                    handle.close(); await this.renderSidebar(); await this.showEntryDialog(entry.id);
                }));
            },
            onKeyDown: (event) => { if (event.key === "Escape") handle.close(); },
        });
    }

    async showProfilesDialog() {
        const state = await this.store.state(); let handle;
        handle = this.api.ui.showDialog({
            key: "Comfy.WorkflowVault.profiles",
            title: "Vault profiles",
            render: (container) => {
                const doc = container.ownerDocument; container.replaceChildren();
                for (const profile of state.profiles) {
                    const row = el(doc, "div"); row.appendChild(el(doc, "span", `${profile.name}${profile.id === state.activeProfileId ? " · active" : ""}`));
                    row.appendChild(button(doc, "Rename", async () => {
                        const name = await this.api.ui.prompt({ label: "Rename vault profile", value: profile.name });
                        if (name) { await this.store.renameProfile(profile.id, name); handle.close(); await this.showProfilesDialog(); }
                    }));
                    if (profile.id !== "default" && profile.id !== state.activeProfileId) row.appendChild(button(doc, "Delete", async () => { await this.store.deleteProfile(profile.id); handle.close(); await this.showProfilesDialog(); }));
                    container.appendChild(row);
                }
            },
            onKeyDown: (event) => { if (event.key === "Escape") handle.close(); },
        });
    }

    async addExamples(entryId) {
        const files = await this.api.files.pickMany({ maxFiles: 10, maxBytes: MAX_MEDIA_BYTES, maxTotalBytes: 10 * MAX_MEDIA_BYTES, mimeTypes: ["image/png", "image/jpeg", "image/webp", "video/mp4", "audio/mpeg", "audio/wav"] });
        for (const file of files) await this.store.addExample(entryId, file);
        notify("success", `${files.length} example file${files.length === 1 ? "" : "s"} added`);
    }

    async exportArchive() {
        const raw = await this.store.exportArchive();
        await this.api.files.download({ name: "workflow-vault-secure.json", mimeType: "application/json", bytes: textEncoder.encode(raw) });
        notify("success", "Vault archive downloaded");
    }

    async importArchive() {
        const file = await this.api.files.pick({ extensions: [".json"], mimeTypes: ["application/json"], maxBytes: MAX_ARCHIVE_BYTES });
        if (!file) return;
        await this.store.importArchive(textDecoder.decode(file.bytes));
        await this.renderSidebar();
        notify("success", "Vault archive imported into isolated storage");
    }
}

export const workflowVault = new WorkflowVault();
await workflowVault.install();
