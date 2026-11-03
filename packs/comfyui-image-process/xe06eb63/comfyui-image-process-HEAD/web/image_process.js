import { app } from "/scripts/app.js";

const qualityWidgetsConfig = {
    "disable_metadata": ["png", "jpg", "webp", "tiff"],
    "join_alpha": ["png", "webp", "tiff", "bmp", "tga", "avif"],
    "invert_alpha": ["png", "webp", "tiff", "bmp", "tga", "avif"],
    "quality": ["jpg", "webp", "avif"],
    "compress_level": ["png"],
    "tiff_compression": ["tiff"],
    "tga_rle": ["tga"],
};

const alphaExclusiveConfig = {
    "join_alpha": ["32bit"],
    "invert_alpha": ["32bit"]
};

const colorPatchMergeConfig = {
    "neighborhood": ["Smooth"],
    "min_area": ["Unify"],
    "iterations": ["Unify"],
    "use_lab": ["Unify"]
};

const icoPackerCropConfig = {
    crop_reference_point: [true],
};

class WidgetManager {
    constructor(node, config) {
        this.node = node;
        this.config = config;
        this.widgets = node.widgets.reduce((acc, w) => {
            acc[w.name] = w;
            return acc;
        }, {});
    }

    initWidget(name, prettify = true, customName = "") {
        const widget = this.widgets[name];
        if (widget) {
            if (customName !== "") {
                widget.original_displayName = customName;
            } else {
                if (prettify) {
                    widget.original_displayName = widget.name.replace(/_/g, " ").replace(/\b\w/g, char => char.toUpperCase());
                } else {
                    widget.original_displayName = widget.name;
                }
            }
            widget.label = widget.original_displayName;
        }
        return widget;
    }

    initWidgets(names) {
        names.forEach(name => this.initWidget(name));
    }

    applyStyle(widget, disabled) {
        const dark_grey = "#444";
        const light_grey = "#666";

        const color = disabled ? dark_grey : undefined;
        const textColor = disabled ? light_grey : undefined;

        widget.disabled = !!disabled;
        if (widget.options) {
            widget.options.color = color;
            widget.options.text_color = textColor;
        }

        try { widget.color = color; } catch (e) { }
        try { widget.text_color = textColor; } catch (e) { }

        widget.label = `${widget.original_displayName}${disabled ? " (Disabled)" : ""}`;
    }

    update(triggerValue) {
        for (const name in this.config) {
            const widget = this.widgets[name];
            if (widget) {
                const enabledTypes = this.config[name];
                const isDisabled = !enabledTypes.includes(triggerValue);
                this.applyStyle(widget, isDisabled);
            }
        }
        this.node.setDirtyCanvas(true, true);
    }

    bindTrigger(triggerName) {
        const triggerWidget = this.widgets[triggerName];
        if (!triggerWidget) return;

        const originalCallback = triggerWidget.callback;
        triggerWidget.callback = (...args) => {
            const result = originalCallback ? originalCallback.apply(triggerWidget, args) : undefined;
            this.update(triggerWidget.value);
            return result;
        };

        setTimeout(() => this.update(triggerWidget.value), 0);
    }
}

app.registerExtension({
    name: "Wakaura.SaveImageAdvanced",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name === "SaveImageAdvanced") {
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;

                const manager = new WidgetManager(this, qualityWidgetsConfig);
                manager.initWidgets([
                    "format",
                    "disable_metadata",
                    "join_alpha",
                    "invert_alpha",
                    "quality",
                    "compress_level"
                ]);
                manager.initWidget("tiff_compression", false, "TIFF Compression");
                manager.initWidget("tga_rle", false, "TGA RLE Compression");
                manager.bindTrigger("format");

                return r;
            };
        };
    }
});

app.registerExtension({
    name: "Wakaura.SaveImageAdvancedBMP",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name === "SaveImageAdvancedBMP") {
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;

                const manager = new WidgetManager(this, alphaExclusiveConfig);
                manager.initWidgets(["bit_depth", "join_alpha", "invert_alpha"]);
                manager.bindTrigger("bit_depth");

                return r;
            };
        };
    }
});

app.registerExtension({
    name: "Wakaura.ColorPatchMerge",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name === "ColorPatchMerge") {
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;

                const manager = new WidgetManager(this, colorPatchMergeConfig);
                manager.initWidgets([
                    "merge_solution",
                    "neighborhood",
                    "min_area",
                    "iterations",
                    "use_lab",
                ]);
                manager.bindTrigger("merge_solution");

                return r;
            };
        };
    }
});

const ICO_IMAGE_PREFIX = "image_";
const ICO_MASK_PREFIX = "mask_";
const ICO_OPTIONAL_INPUT_SHAPE = 7;
const ICO_VALID_SIZES = new Set([16, 24, 32, 48, 64, 128, 256]);
const ICO_MAX_SIZE_SLOTS = ICO_VALID_SIZES.size;

function parseIcoImageSize(name) {
    if (!name?.startsWith(ICO_IMAGE_PREFIX)) return null;
    const size = parseInt(name.slice(ICO_IMAGE_PREFIX.length), 10);
    return Number.isFinite(size) ? size : null;
}

function getIcoSizes(node) {
    return (node.inputs || [])
        .map((inp) => parseIcoImageSize(inp.name))
        .filter((s) => s !== null)
        .sort((a, b) => a - b);
}

function getOptionalIcoInputExtra(node) {
    const ref = node.inputs?.find((i) => i.name?.startsWith(ICO_IMAGE_PREFIX));
    return { shape: ref?.shape ?? ICO_OPTIONAL_INPUT_SHAPE };
}

function markIcoInputsOptional(node) {
    const { shape } = getOptionalIcoInputExtra(node);
    for (const inp of node.inputs || []) {
        if (inp.name?.startsWith(ICO_IMAGE_PREFIX) || inp.name?.startsWith(ICO_MASK_PREFIX)) {
            inp.shape = shape;
        }
    }
}

function setIcoInputLabels(node, size) {
    const imageInp = node.inputs?.find((i) => i.name === `${ICO_IMAGE_PREFIX}${size}`);
    const maskInp = node.inputs?.find((i) => i.name === `${ICO_MASK_PREFIX}${size}`);
    if (imageInp) imageInp.label = `Image (${size})`;
    if (maskInp) maskInp.label = `Mask (${size})`;
}

function validateIcoSizeValue(raw) {
    const size = parseInt(String(raw).trim(), 10);
    if (!Number.isFinite(size) || !ICO_VALID_SIZES.has(size)) {
        return {
            ok: false,
            error: `Size must be one of: ${[...ICO_VALID_SIZES].sort((a, b) => a - b).join(", ")}.`,
        };
    }
    return { ok: true, size };
}

function addIcoSizePair(node, size) {
    const sizes = getIcoSizes(node);
    if (sizes.includes(size)) {
        return { ok: false, error: `Size ${size} is already added.` };
    }
    if (sizes.length >= ICO_MAX_SIZE_SLOTS) {
        return { ok: false, error: `Maximum of ${ICO_MAX_SIZE_SLOTS} size slots reached.` };
    }
    const extra = getOptionalIcoInputExtra(node);
    node.addInput(`${ICO_IMAGE_PREFIX}${size}`, "IMAGE", extra);
    node.addInput(`${ICO_MASK_PREFIX}${size}`, "MASK", extra);
    setIcoInputLabels(node, size);
    markIcoInputsOptional(node);
    node.setSize?.(node.computeSize?.());
    app.graph?.setDirtyCanvas(true, true);
    return { ok: true };
}

function removeIcoSizePair(node, size) {
    const targetNames = new Set([`${ICO_IMAGE_PREFIX}${size}`, `${ICO_MASK_PREFIX}${size}`]);
    while (true) {
        const idx = node.inputs?.findIndex((i) => targetNames.has(i.name)) ?? -1;
        if (idx < 0) break;
        node.removeInput(idx);
    }
    node.setSize?.(node.computeSize?.());
    app.graph?.setDirtyCanvas(true, true);
}

function removeLastIcoSizePair(node, showDialog = true) {
    const sizes = getIcoSizes(node);
    if (sizes.length === 0) {
        if (showDialog && app.ui?.dialog?.show) {
            app.ui.dialog.show("No size slots to remove.");
        }
        return false;
    }
    removeIcoSizePair(node, sizes[sizes.length - 1]);
    return true;
}

function dismissComfyContextMenu() {
    document.querySelectorAll(".litecontextmenu").forEach((el) => el.remove());
    const target = document.body;
    const opts = { bubbles: true, cancelable: true, composed: true, view: window };
    target.dispatchEvent(new PointerEvent("pointerdown", opts));
    target.dispatchEvent(new PointerEvent("pointerup", opts));
}

function afterContextMenuAction(fn) {
    requestAnimationFrame(() => {
        fn();
        requestAnimationFrame(dismissComfyContextMenu);
    });
}

function ensureIcoPackerModalStyles() {
    if (document.getElementById("ico-packer-modal-styles")) return;
    const styleElement = document.createElement("style");
    styleElement.id = "ico-packer-modal-styles";
    styleElement.textContent = `
        .ico-packer-modal {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 10000;
            font-family: Arial, sans-serif;
        }
        .ico-packer-dialog {
            background: var(--comfy-menu-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 20px;
            min-width: 400px;
            max-width: 500px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.7);
            color: var(--fg-color);
        }
        .ico-packer-title {
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 15px;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 10px;
        }
        .ico-packer-info {
            background: var(--comfy-input-bg);
            padding: 10px;
            border-radius: 4px;
            margin-bottom: 15px;
            font-size: 13px;
            color: var(--descrip-text);
        }
        .ico-packer-label {
            display: block;
            font-size: 12px;
            font-weight: 600;
            margin-bottom: 8px;
            color: var(--descrip-text);
            text-transform: uppercase;
        }
        .ico-packer-input {
            width: 100%;
            padding: 8px 10px;
            background: var(--comfy-input-bg);
            border: 1px solid var(--border-color);
            color: var(--input-text);
            border-radius: 4px;
            font-size: 13px;
            box-sizing: border-box;
        }
        .ico-packer-input:focus {
            outline: none;
            border-color: #007acc;
            background: var(--bg-color);
        }
        .ico-packer-error {
            background: color-mix(in srgb, var(--error-text) 15%, transparent);
            border: 1px solid var(--error-text);
            color: var(--error-text);
            padding: 10px;
            border-radius: 4px;
            margin-bottom: 15px;
            font-size: 12px;
        }
        .ico-packer-size-list {
            list-style: none;
            margin: 0 0 15px 0;
            padding: 0;
            max-height: 200px;
            overflow-y: auto;
            border: 1px solid var(--border-color);
            border-radius: 4px;
        }
        .ico-packer-size-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 8px 10px;
            border-bottom: 1px solid var(--border-color);
            font-size: 13px;
        }
        .ico-packer-size-row:last-child {
            border-bottom: none;
        }
        .ico-packer-size-row:nth-child(odd) {
            background: var(--tr-odd-bg-color);
        }
        .ico-packer-size-row:nth-child(even) {
            background: var(--tr-even-bg-color);
        }
        .ico-packer-row-remove {
            padding: 4px 10px;
            background: var(--comfy-input-bg);
            border: 1px solid var(--border-color);
            color: var(--fg-color);
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
        }
        .ico-packer-row-remove:hover {
            background: var(--content-hover-bg);
        }
        .ico-packer-row-actions {
            display: flex;
            gap: 8px;
            margin-bottom: 15px;
        }
        .ico-packer-row-actions .ico-packer-input {
            flex: 1;
        }
        .ico-packer-buttons {
            display: flex;
            gap: 10px;
            justify-content: flex-end;
            padding-top: 15px;
            border-top: 1px solid var(--border-color);
        }
        .ico-packer-btn {
            padding: 8px 16px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 13px;
            font-weight: 500;
        }
        .ico-packer-btn-primary {
            background: #007acc;
            color: white;
        }
        .ico-packer-btn-primary:hover {
            background: #0098ff;
        }
        .ico-packer-btn-primary:disabled {
            background: var(--border-color);
            cursor: not-allowed;
            opacity: 0.5;
        }
        .ico-packer-btn-secondary {
            background: var(--comfy-input-bg);
            color: var(--fg-color);
            border: 1px solid var(--border-color);
        }
        .ico-packer-btn-secondary:hover {
            background: var(--bg-color);
        }
    `;
    document.head.appendChild(styleElement);
}

function showIcoPackerSingleAddDialog(node) {
    ensureIcoPackerModalStyles();
    const existing = getIcoSizes(node);
    const modal = document.createElement("div");
    modal.className = "ico-packer-modal";
    const dialog = document.createElement("div");
    dialog.className = "ico-packer-dialog";

    const title = document.createElement("div");
    title.className = "ico-packer-title";
    title.textContent = "Add ICO Size";

    const info = document.createElement("div");
    info.className = "ico-packer-info";
    info.innerHTML = `Current slots: <strong>${existing.length}</strong> / <strong>${ICO_MAX_SIZE_SLOTS}</strong>`;

    const label = document.createElement("label");
    label.className = "ico-packer-label";
    label.textContent = "Icon size (px)";

    const sizeInput = document.createElement("input");
    sizeInput.type = "number";
    sizeInput.className = "ico-packer-input";
    sizeInput.placeholder = "e.g. 32";
    sizeInput.min = "1";

    const messageArea = document.createElement("div");

    const buttons = document.createElement("div");
    buttons.className = "ico-packer-buttons";

    const okBtn = document.createElement("button");
    okBtn.className = "ico-packer-btn ico-packer-btn-primary";
    okBtn.textContent = "OK";

    const cancelBtn = document.createElement("button");
    cancelBtn.className = "ico-packer-btn ico-packer-btn-secondary";
    cancelBtn.textContent = "Cancel";

    const closeModal = () => {
        modal.remove();
        document.removeEventListener("keydown", handleKeyDown);
    };

    const showError = (msg) => {
        messageArea.innerHTML = `<div class="ico-packer-error">${msg}</div>`;
    };

    const applySize = () => {
        messageArea.innerHTML = "";
        const validated = validateIcoSizeValue(sizeInput.value);
        if (!validated.ok) {
            showError(validated.error);
            return;
        }
        if (existing.includes(validated.size)) {
            showError(`Size ${validated.size} is already on this node.`);
            return;
        }
        if (existing.length >= ICO_MAX_SIZE_SLOTS) {
            showError(`Maximum of ${ICO_MAX_SIZE_SLOTS} size slots reached.`);
            return;
        }
        const result = addIcoSizePair(node, validated.size);
        if (!result.ok) {
            showError(result.error);
            return;
        }
        closeModal();
    };

    okBtn.onclick = applySize;
    cancelBtn.onclick = closeModal;
    sizeInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") applySize();
    });

    const handleKeyDown = (e) => {
        if (e.key === "Escape") closeModal();
    };
    document.addEventListener("keydown", handleKeyDown);
    modal.onclick = (e) => {
        if (e.target === modal) closeModal();
    };

    buttons.appendChild(okBtn);
    buttons.appendChild(cancelBtn);
    dialog.appendChild(title);
    dialog.appendChild(info);
    dialog.appendChild(label);
    dialog.appendChild(sizeInput);
    dialog.appendChild(messageArea);
    dialog.appendChild(buttons);
    modal.appendChild(dialog);
    document.body.appendChild(modal);
    sizeInput.focus();
}

function showIcoPackerBatchAddDialog(node) {
    ensureIcoPackerModalStyles();
    const pendingSizes = [];
    const existing = new Set(getIcoSizes(node));

    const modal = document.createElement("div");
    modal.className = "ico-packer-modal";
    const dialog = document.createElement("div");
    dialog.className = "ico-packer-dialog";

    const title = document.createElement("div");
    title.className = "ico-packer-title";
    title.textContent = "Batch Add ICO Sizes";

    const info = document.createElement("div");

    const refreshInfo = () => {
        info.className = "ico-packer-info";
        info.innerHTML =
            `On node: <strong>${existing.size}</strong> / <strong>${ICO_MAX_SIZE_SLOTS}</strong>` +
            ` &nbsp;|&nbsp; Pending: <strong>${pendingSizes.length}</strong>`;
    };
    refreshInfo();

    const listLabel = document.createElement("label");
    listLabel.className = "ico-packer-label";
    listLabel.textContent = "Sizes to add";

    const listEl = document.createElement("ul");
    listEl.className = "ico-packer-size-list";

    const renderList = () => {
        listEl.innerHTML = "";
        if (pendingSizes.length === 0) {
            const empty = document.createElement("li");
            empty.className = "ico-packer-size-row";
            empty.style.justifyContent = "center";
            empty.style.color = "var(--descrip-text)";
            empty.textContent = "No pending sizes";
            listEl.appendChild(empty);
            return;
        }
        pendingSizes.forEach((size, index) => {
            const row = document.createElement("li");
            row.className = "ico-packer-size-row";
            const text = document.createElement("span");
            text.textContent = `${size}px (image_${size}, mask_${size})`;
            const removeBtn = document.createElement("button");
            removeBtn.type = "button";
            removeBtn.className = "ico-packer-row-remove";
            removeBtn.textContent = "Remove";
            removeBtn.onclick = () => {
                pendingSizes.splice(index, 1);
                renderList();
                refreshInfo();
                refreshAddBtn();
            };
            row.appendChild(text);
            row.appendChild(removeBtn);
            listEl.appendChild(row);
        });
    };

    const addRowLabel = document.createElement("label");
    addRowLabel.className = "ico-packer-label";
    addRowLabel.textContent = "Add size to list";

    const rowActions = document.createElement("div");
    rowActions.className = "ico-packer-row-actions";

    const sizeInput = document.createElement("input");
    sizeInput.type = "number";
    sizeInput.className = "ico-packer-input";
    sizeInput.placeholder = "e.g. 64";

    const listOkBtn = document.createElement("button");
    listOkBtn.className = "ico-packer-btn ico-packer-btn-secondary";
    listOkBtn.textContent = "OK";

    const messageArea = document.createElement("div");

    const buttons = document.createElement("div");
    buttons.className = "ico-packer-buttons";

    const addBtn = document.createElement("button");
    addBtn.className = "ico-packer-btn ico-packer-btn-primary";
    addBtn.textContent = "Add";

    const cancelBtn = document.createElement("button");
    cancelBtn.className = "ico-packer-btn ico-packer-btn-secondary";
    cancelBtn.textContent = "Cancel";

    const showError = (msg) => {
        messageArea.innerHTML = `<div class="ico-packer-error">${msg}</div>`;
    };

    const refreshAddBtn = () => {
        const total = existing.size + pendingSizes.length;
        addBtn.disabled = pendingSizes.length === 0 || total > ICO_MAX_SIZE_SLOTS;
    };

    const addToPendingList = () => {
        messageArea.innerHTML = "";
        const validated = validateIcoSizeValue(sizeInput.value);
        if (!validated.ok) {
            showError(validated.error);
            return;
        }
        const { size } = validated;
        if (existing.has(size) || pendingSizes.includes(size)) {
            showError(`Size ${size} is already listed or on the node.`);
            return;
        }
        if (existing.size + pendingSizes.length >= ICO_MAX_SIZE_SLOTS) {
            showError(`Cannot queue more sizes (max ${ICO_MAX_SIZE_SLOTS} total).`);
            return;
        }
        pendingSizes.push(size);
        pendingSizes.sort((a, b) => a - b);
        sizeInput.value = "";
        renderList();
        refreshInfo();
        refreshAddBtn();
    };

    listOkBtn.onclick = addToPendingList;
    sizeInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") addToPendingList();
    });

    const closeModal = () => {
        modal.remove();
        document.removeEventListener("keydown", handleKeyDown);
    };

    addBtn.onclick = () => {
        messageArea.innerHTML = "";
        for (const size of pendingSizes) {
            const result = addIcoSizePair(node, size);
            if (!result.ok) {
                showError(result.error);
                return;
            }
            existing.add(size);
        }
        closeModal();
    };
    cancelBtn.onclick = closeModal;

    const handleKeyDown = (e) => {
        if (e.key === "Escape") closeModal();
    };
    document.addEventListener("keydown", handleKeyDown);
    modal.onclick = (e) => {
        if (e.target === modal) closeModal();
    };

    rowActions.appendChild(sizeInput);
    rowActions.appendChild(listOkBtn);
    buttons.appendChild(addBtn);
    buttons.appendChild(cancelBtn);

    dialog.appendChild(title);
    dialog.appendChild(info);
    dialog.appendChild(listLabel);
    dialog.appendChild(listEl);
    dialog.appendChild(addRowLabel);
    dialog.appendChild(rowActions);
    dialog.appendChild(messageArea);
    dialog.appendChild(buttons);
    modal.appendChild(dialog);
    document.body.appendChild(modal);

    renderList();
    refreshAddBtn();
    sizeInput.focus();
}

app.registerExtension({
    name: "Wakaura.ICOPacker",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "ICOPacker") return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const r = onNodeCreated?.apply(this, arguments);
            const manager = new WidgetManager(this, icoPackerCropConfig);
            manager.initWidget("crop_images", false, "Crop Images");
            manager.initWidget("crop_reference_point", false, "Reference Point");
            manager.bindTrigger("crop_images");
            requestAnimationFrame(() => {
                for (const size of getIcoSizes(this)) {
                    setIcoInputLabels(this, size);
                }
                markIcoInputsOptional(this);
            });
            return r;
        };

        const origGetExtraMenuOptions = nodeType.prototype.getExtraMenuOptions;
        nodeType.prototype.getExtraMenuOptions = function (_, options) {
            const r = origGetExtraMenuOptions?.apply?.(this, arguments);
            const node = this;
            const count = getIcoSizes(node).length;
            const atLimit = count >= ICO_MAX_SIZE_SLOTS;

            options.unshift({
                content: "Batch Add Input",
                disabled: atLimit,
                callback: () => showIcoPackerBatchAddDialog(node),
            });
            options.unshift({
                content: atLimit ? `Add Input (max ${ICO_MAX_SIZE_SLOTS})` : "Add Input",
                disabled: atLimit,
                callback: () => showIcoPackerSingleAddDialog(node),
            });
            options.unshift({
                content: "Remove Input",
                disabled: count === 0,
                callback: () => afterContextMenuAction(() => removeLastIcoSizePair(node)),
            });
            return r;
        };
    },
});

app.registerExtension({
    name: "Wakaura.FilenameTokenMenu",
    async beforeRegisterNodeDef(nodeType) {
        const origGetExtraMenuOptions = nodeType.prototype.getExtraMenuOptions;
        nodeType.prototype.getExtraMenuOptions = function (_, options) {
            const r = origGetExtraMenuOptions?.apply(this, arguments);

            const widget = this.widgets?.find(w => w.name === "filename_prefix");
            if (!widget) return r;

            const node = this;
            const append = (token) => {
                widget.value = (widget.value ?? "") + token;
                node.setDirtyCanvas(true, true);
            };

            options.push({
                content: "Insert Filename Token",
                has_submenu: true,
                submenu: {
                    options: [
                        {
                            content: "date",
                            has_submenu: true,
                            submenu: {
                                options: [
                                    {
                                        content: "Full date: %date:yyyy-MM-dd%",
                                        callback: () => append("%date:yyyy-MM-dd%"),
                                    },
                                    {
                                        content: "Full datetime: %date:yyyy-MM-dd_HH-mm-ss%",
                                        callback: () => append("%date:yyyy-MM-dd_HH-mm-ss%"),
                                    },
                                    null,
                                    {
                                        content: "Year: %year%",
                                        callback: () => append("%year%"),
                                    },
                                    {
                                        content: "Month: %month%",
                                        callback: () => append("%month%"),
                                    },
                                    {
                                        content: "Day: %day%",
                                        callback: () => append("%day%"),
                                    },
                                ],
                            },
                        },
                        {
                            content: "time",
                            has_submenu: true,
                            submenu: {
                                options: [
                                    {
                                        content: "Hour: %hour%",
                                        callback: () => append("%hour%"),
                                    },
                                    {
                                        content: "Minute: %minute%",
                                        callback: () => append("%minute%"),
                                    },
                                    {
                                        content: "Second: %second%",
                                        callback: () => append("%second%"),
                                    },
                                ],
                            },
                        },
                        {
                            content: "image",
                            has_submenu: true,
                            submenu: {
                                options: [
                                    {
                                        content: "Width: %width%",
                                        callback: () => append("%width%"),
                                    },
                                    {
                                        content: "Height: %height%",
                                        callback: () => append("%height%"),
                                    },
                                ],
                            },
                        },
                    ],
                },
            });

            return r;
        };
    },
});