import { comfy } from "/comfy/api/v2.js";
import { BUILTIN_LAYOUTS } from "./layouts_data.js";

export const CUSTOM_LAYOUT_PREFIX = "__panelcomposer_v2__:";
export const STORAGE_NAME = "panelcomposer/layouts.json";
export const STORAGE_NAMESPACE = "panelcomposer/";
export const MAX_LIBRARY_BYTES = 512 * 1024;
export const MAX_CUSTOM_LAYOUT_BYTES = 128 * 1024;
export const MAX_PANELS = 64;
export const MAX_POINTS_PER_PANEL = 64;

export const ASPECT_RATIO_CHOICES = {
    "1:1 (Square)": 1,
    "9:7": 9 / 7,
    "4:3 (Standard)": 4 / 3,
    "A4": Math.SQRT2,
    "19:13": 19 / 13,
    "3:2 (Classic Photo)": 3 / 2,
    "7:4": 7 / 4,
    "16:9 (Widescreen)": 16 / 9,
    "21:9 (Ultrawide)": 21 / 9,
    "12:5 (Cinemascope)": 12 / 5,
};

const COLOR_PAGE = "#f5f5f5";
const COLOR_PANEL = "#9cc7ff";
const COLOR_BORDER = "#292936";
const COLOR_INK = "#17171f";
const COLOR_MUTED = "#8a8aa0";
const controllerByNode = new Map();

function clone(value) {
    return JSON.parse(JSON.stringify(value));
}

function fail(message) {
    throw new Error(message);
}

function validatePoint(point) {
    return Array.isArray(point)
        && point.length === 2
        && point.every((value) => Number.isFinite(value) && value >= 0 && value <= 1);
}

export function validatePreset(data) {
    if (!data || typeof data !== "object" || Array.isArray(data)) fail("preset must be an object");
    const category = String(data.category ?? "").trim();
    const label = String(data.label ?? "").trim();
    if (!category || category.length > 80) fail("category must contain 1-80 characters");
    if (!label || label.length > 80) fail("label must contain 1-80 characters");
    if (!Array.isArray(data.panels) || data.panels.length < 1 || data.panels.length > MAX_PANELS) {
        fail(`preset must contain 1-${MAX_PANELS} panels`);
    }
    const panels = data.panels.map((polygon) => {
        if (!Array.isArray(polygon) || polygon.length < 3 || polygon.length > MAX_POINTS_PER_PANEL) {
            fail(`every panel needs 3-${MAX_POINTS_PER_PANEL} points`);
        }
        if (!polygon.every(validatePoint)) fail("every point must be finite and inside the page");
        return polygon.map(([x, y]) => [Number(x), Number(y)]);
    });
    validateReadingGroups(data.reading_groups, panels.length);
    return {
        category,
        label,
        panels,
        ...(data.reading_groups == null ? {} : { reading_groups: clone(data.reading_groups) }),
        is_builtin: Boolean(data.is_builtin),
    };
}

function validateReadingGroups(group, panelCount) {
    if (group == null) return;
    const ids = [];
    const visit = (part, depth) => {
        if (depth > 50) fail("reading groups are nested too deeply");
        if (Number.isInteger(part)) {
            if (part < 0 || part >= panelCount) fail("reading group references a missing panel");
            ids.push(part);
            return;
        }
        if (!Array.isArray(part) || part.length === 0) fail("reading groups must contain panel ids");
        part.forEach((child) => visit(child, depth + 1));
    };
    visit(group, 0);
    const expected = Array.from({ length: panelCount }, (_, index) => index);
    if (ids.length !== panelCount || [...ids].sort((a, b) => a - b).some((id, index) => id !== expected[index])) {
        fail("reading groups must reference every panel exactly once");
    }
}

function builtinLibrary() {
    return Object.fromEntries(
        Object.entries(BUILTIN_LAYOUTS).map(([key, value]) => [
            key,
            validatePreset({ ...clone(value), is_builtin: true }),
        ]),
    );
}

function validateLibrary(raw) {
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) fail("layout library must be an object");
    const result = {};
    for (const [key, value] of Object.entries(raw)) {
        if (!/^[a-z0-9_]{1,96}$/.test(key)
            || ["__proto__", "prototype", "constructor"].includes(key)) fail("layout key is invalid");
        result[key] = validatePreset(value);
    }
    return result;
}

export async function loadPresets() {
    const saved = await comfy.storage.get(STORAGE_NAME);
    if (saved === undefined) return builtinLibrary();
    try {
        return validateLibrary(JSON.parse(saved));
    } catch (error) {
        comfy.commands.notify({
            severity: "error",
            summary: "PanelComposer layouts could not be loaded",
            detail: error instanceof Error ? error.message : String(error),
        });
        return builtinLibrary();
    }
}

export async function persistLibrary(presets) {
    const normalized = validateLibrary(presets);
    const serialized = JSON.stringify(normalized);
    if (new TextEncoder().encode(serialized).byteLength > MAX_LIBRARY_BYTES) {
        fail("layout library exceeds 512 KiB");
    }
    await comfy.storage.set(STORAGE_NAME, serialized);
    return normalized;
}

function slugify(label) {
    return label.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "") || "layout";
}

export async function savePreset(category, label, panels, readingGroups) {
    const library = await loadPresets();
    const normalizedCategory = String(category ?? "").trim();
    const preservedCategory = Object.values(library).find(
        (preset) => preset.category.toLowerCase() === normalizedCategory.toLowerCase(),
    )?.category ?? normalizedCategory;
    const base = slugify(label);
    let key = base;
    for (let suffix = 2; Object.hasOwn(library, key); suffix += 1) key = `${base}_${suffix}`;
    const preset = validatePreset({
        category: preservedCategory,
        label,
        panels,
        reading_groups: readingGroups,
        is_builtin: false,
    });
    const updated = { ...library, [key]: preset };
    await persistLibrary(updated);
    await refreshControllers(updated);
    return { key, choice: encodePresetChoice(preset), preset };
}

export async function deletePreset(key) {
    const library = await loadPresets();
    if (!Object.hasOwn(library, key)) fail(`no preset named ${key}`);
    const updated = { ...library };
    delete updated[key];
    if (Object.keys(updated).length === 0) fail("at least one layout must remain");
    await persistLibrary(updated);
    await refreshControllers(updated);
    return updated;
}

async function refreshControllers(presets) {
    await Promise.all([...controllerByNode.values()].map((controller) => controller.refresh(presets)));
}

export function encodePresetChoice(preset) {
    const clean = validatePreset({ ...preset, is_builtin: false });
    const payload = JSON.stringify({
        category: clean.category,
        label: clean.label,
        panels: clean.panels,
        ...(clean.reading_groups == null ? {} : { reading_groups: clean.reading_groups }),
    });
    if (new TextEncoder().encode(payload).byteLength > MAX_CUSTOM_LAYOUT_BYTES) {
        fail("custom layout exceeds 128 KiB");
    }
    return CUSTOM_LAYOUT_PREFIX + payload;
}

export function decodePresetChoice(presets, choice) {
    if (typeof choice !== "string") return undefined;
    if (choice.startsWith(CUSTOM_LAYOUT_PREFIX)) {
        const payload = choice.slice(CUSTOM_LAYOUT_PREFIX.length);
        if (new TextEncoder().encode(payload).byteLength > MAX_CUSTOM_LAYOUT_BYTES) return undefined;
        try {
            return validatePreset({ ...JSON.parse(payload), is_builtin: false });
        } catch {
            return undefined;
        }
    }
    for (const preset of Object.values(presets)) {
        if (`${preset.category} / ${preset.label}` === choice) return preset;
    }
    return BUILTIN_LAYOUTS[choice] ? validatePreset({ ...BUILTIN_LAYOUTS[choice], is_builtin: true }) : undefined;
}

export function choiceForPreset(key, preset) {
    return preset.is_builtin ? `${preset.category} / ${preset.label}` : encodePresetChoice(preset);
}

export function parseAspectRatio(choice) {
    return ASPECT_RATIO_CHOICES[choice] ?? 1;
}

export function resolveOrientedAspectRatio(ratio, orientation) {
    return orientation === "portrait" ? Math.min(ratio, 1 / ratio) : Math.max(ratio, 1 / ratio);
}

export function polygonCentroid(points) {
    let twiceArea = 0;
    let cx = 0;
    let cy = 0;
    for (let index = 0; index < points.length; index += 1) {
        const [x1, y1] = points[index];
        const [x2, y2] = points[(index + 1) % points.length];
        const cross = x1 * y2 - x2 * y1;
        twiceArea += cross;
        cx += (x1 + x2) * cross;
        cy += (y1 + y2) * cross;
    }
    if (Math.abs(twiceArea) < 1e-9) {
        return [
            points.reduce((sum, [x]) => sum + x, 0) / points.length,
            points.reduce((sum, [, y]) => sum + y, 0) / points.length,
        ];
    }
    return [cx / (3 * twiceArea), cy / (3 * twiceArea)];
}

export function groupCentroid(group, centroids) {
    if (Number.isInteger(group)) return centroids[group];
    const points = group.map((part) => groupCentroid(part, centroids));
    return [
        points.reduce((sum, point) => sum + point[0], 0) / points.length,
        points.reduce((sum, point) => sum + point[1], 0) / points.length,
    ];
}

export function orderedIds(group, centroids, readingOrder) {
    if (Number.isInteger(group)) return [group];
    const points = group.map((part) => groupCentroid(part, centroids));
    const xSpread = Math.max(...points.map((point) => point[0])) - Math.min(...points.map((point) => point[0]));
    const ySpread = Math.max(...points.map((point) => point[1])) - Math.min(...points.map((point) => point[1]));
    const indices = group.map((_, index) => index);
    indices.sort((left, right) => {
        if (ySpread >= xSpread) return points[left][1] - points[right][1];
        const delta = points[left][0] - points[right][0];
        return readingOrder === "right_to_left" ? -delta : delta;
    });
    return indices.flatMap((index) => orderedIds(group[index], centroids, readingOrder));
}

export function deriveRowGroups(indices, polygons) {
    const sorted = [...indices].sort((left, right) => polygonCentroid(polygons[left])[1] - polygonCentroid(polygons[right])[1]);
    const groups = [];
    for (const id of sorted) {
        const center = polygonCentroid(polygons[id]);
        const last = groups.at(-1);
        if (!last || Math.abs(center[1] - last.centerY) > 0.08) {
            groups.push({ centerY: center[1], ids: [id] });
        } else {
            last.ids.push(id);
            last.centerY = last.ids.reduce((sum, item) => sum + polygonCentroid(polygons[item])[1], 0) / last.ids.length;
        }
    }
    return groups.map((group) => group.ids.sort((left, right) => polygonCentroid(polygons[left])[0] - polygonCentroid(polygons[right])[0]));
}

export function applyRotation(panels, rotation) {
    const transform = {
        "0": ([x, y]) => [x, y],
        "90": ([x, y]) => [1 - y, x],
        "180": ([x, y]) => [1 - x, 1 - y],
        "270": ([x, y]) => [y, 1 - x],
    }[String(rotation)] ?? ((point) => point);
    return panels.map((polygon) => polygon.map(transform));
}

export function applyReadingOrder(panels, readingOrder, readingGroups) {
    if (readingGroups == null) return panels.map((polygon, order) => ({ order, polygon }));
    const centroids = Object.fromEntries(panels.map((polygon, index) => [index, polygonCentroid(polygon)]));
    const ids = orderedIds(readingGroups, centroids, readingOrder);
    return ids.map((id, order) => ({ order, polygon: panels[id] }));
}

function palette(index, total) {
    const hue = (index * 0.61803398875) % 1;
    const angle = hue * Math.PI * 2;
    const r = Math.round(170 + 55 * Math.sin(angle));
    const g = Math.round(170 + 55 * Math.sin(angle + 2.1));
    const b = Math.round(170 + 55 * Math.sin(angle + 4.2));
    return `rgb(${r}, ${g}, ${b})`;
}

export function drawLayoutPreview(canvas, preset, options = {}) {
    const context = canvas.getContext("2d");
    if (!context) return;
    const width = Math.max(1, Math.floor(canvas.clientWidth || 280));
    const height = Math.max(1, Math.floor(canvas.clientHeight || 180));
    canvas.width = width;
    canvas.height = height;
    context.clearRect(0, 0, width, height);
    const ratio = resolveOrientedAspectRatio(
        parseAspectRatio(options.aspectRatio),
        options.orientation ?? "portrait",
    );
    let pageWidth = width - 16;
    let pageHeight = pageWidth / ratio;
    if (pageHeight > height - 16) {
        pageHeight = height - 16;
        pageWidth = pageHeight * ratio;
    }
    const pageX = (width - pageWidth) / 2;
    const pageY = (height - pageHeight) / 2;
    context.fillStyle = COLOR_PAGE;
    context.fillRect(pageX, pageY, pageWidth, pageHeight);
    const polygons = applyRotation(preset.panels, options.rotation ?? "0");
    const ordered = applyReadingOrder(
        polygons,
        options.readingOrder ?? "left_to_right",
        preset.reading_groups,
    );
    ordered.forEach((panel, index) => {
        context.beginPath();
        panel.polygon.forEach(([x, y], pointIndex) => {
            const px = pageX + x * pageWidth;
            const py = pageY + y * pageHeight;
            if (pointIndex === 0) context.moveTo(px, py);
            else context.lineTo(px, py);
        });
        context.closePath();
        context.fillStyle = palette(index, ordered.length);
        context.fill();
        context.strokeStyle = COLOR_INK;
        context.lineWidth = 1.5;
        context.stroke();
        const [cx, cy] = polygonCentroid(panel.polygon);
        context.fillStyle = COLOR_INK;
        context.font = "bold 12px sans-serif";
        context.textAlign = "center";
        context.textBaseline = "middle";
        context.fillText(String(panel.order + 1), pageX + cx * pageWidth, pageY + cy * pageHeight);
    });
    context.strokeStyle = COLOR_BORDER;
    context.strokeRect(pageX, pageY, pageWidth, pageHeight);
}

function optionGroups(select, presets, query = "") {
    select.replaceChildren();
    const normalizedQuery = query.trim().toLowerCase();
    const groups = new Map();
    for (const [key, preset] of Object.entries(presets)) {
        if (normalizedQuery && !`${preset.category} ${preset.label}`.toLowerCase().includes(normalizedQuery)) continue;
        if (!groups.has(preset.category)) groups.set(preset.category, []);
        groups.get(preset.category).push([key, preset]);
    }
    for (const [category, entries] of groups) {
        const group = select.ownerDocument.createElement("optgroup");
        group.label = category;
        for (const [key, preset] of entries) {
            const option = select.ownerDocument.createElement("option");
            option.value = key;
            option.textContent = preset.label;
            group.append(option);
        }
        select.append(group);
    }
}

function selectedKey(presets, choice) {
    const selected = decodePresetChoice(presets, choice);
    if (!selected) return Object.keys(presets)[0];
    return Object.entries(presets).find(([, preset]) =>
        preset.category === selected.category
        && preset.label === selected.label
        && JSON.stringify(preset.panels) === JSON.stringify(selected.panels)
    )?.[0] ?? Object.keys(presets)[0];
}

function notifyError(summary, error) {
    comfy.commands.notify({
        severity: "error",
        summary,
        detail: error instanceof Error ? error.message : String(error),
    });
}

function mountPreview(node, container, setMountedHeight, initialHeight) {
    const doc = container.ownerDocument;
    container.replaceChildren();
    container.style.cssText = "display:flex;flex-direction:column;gap:4px;height:100%;min-height:180px;";
    const row = doc.createElement("div");
    row.style.cssText = "display:grid;grid-template-columns:auto 1fr auto auto;gap:4px;";
    const previous = doc.createElement("button");
    previous.textContent = "◀";
    previous.title = "Previous layout";
    const search = doc.createElement("input");
    search.placeholder = "Search layouts";
    search.setAttribute("aria-label", "Search layouts");
    const next = doc.createElement("button");
    next.textContent = "▶";
    next.title = "Next layout";
    const remove = doc.createElement("button");
    remove.textContent = "Delete";
    remove.title = "Delete selected layout from your private library";
    row.append(previous, search, next, remove);
    const select = doc.createElement("select");
    select.setAttribute("aria-label", "Panel layout");
    const canvas = doc.createElement("canvas");
    canvas.style.cssText = `width:100%;height:${Math.max(100, initialHeight - 50)}px;border:1px solid #383846;border-radius:4px;background:#14141b;`;
    const resizeHandle = doc.createElement("div");
    resizeHandle.textContent = "⣿";
    resizeHandle.title = "Drag to resize preview";
    resizeHandle.style.cssText = "height:12px;line-height:9px;text-align:center;cursor:ns-resize;color:#77778d;user-select:none;touch-action:none;";
    container.append(row, select, canvas, resizeHandle);

    const layoutWidget = node.widgets.get("layout_preset");
    const aspectWidget = node.widgets.get("aspect_ratio");
    const orientationWidget = node.widgets.get("page_orientation");
    const rotationWidget = node.widgets.get("canvas_rotation");
    const readingWidget = node.widgets.get("reading_order");
    if (!layoutWidget) return () => {};

    let presets = builtinLibrary();
    let key = Object.keys(presets)[0];
    let destroyed = false;
    const redraw = () => {
        const preset = decodePresetChoice(presets, layoutWidget.getValue()) ?? presets[key];
        if (!preset) return;
        drawLayoutPreview(canvas, preset, {
            aspectRatio: aspectWidget?.getValue(),
            orientation: orientationWidget?.getValue(),
            rotation: rotationWidget?.getValue(),
            readingOrder: readingWidget?.getValue(),
        });
        remove.disabled = !key || !Object.hasOwn(presets, key);
    };
    const choose = (nextKey) => {
        const preset = presets[nextKey];
        if (!preset) return;
        key = nextKey;
        select.value = nextKey;
        layoutWidget.setValue(choiceForPreset(nextKey, preset));
        redraw();
    };
    const renderOptions = () => {
        optionGroups(select, presets, search.value);
        key = selectedKey(presets, layoutWidget.getValue());
        if ([...select.options].some((option) => option.value === key)) select.value = key;
        redraw();
    };
    const refresh = async (provided) => {
        presets = provided ?? await loadPresets();
        if (destroyed) return;
        renderOptions();
    };

    const onSearch = () => renderOptions();
    const onSelect = () => choose(select.value);
    const step = (delta) => {
        const keys = Object.keys(presets);
        if (!keys.length) return;
        const index = Math.max(0, keys.indexOf(key));
        choose(keys[(index + delta + keys.length) % keys.length]);
    };
    const onDelete = async () => {
        try {
            const keys = Object.keys(presets);
            const oldIndex = Math.max(0, keys.indexOf(key));
            await deletePreset(key);
            presets = await loadPresets();
            const nextKeys = Object.keys(presets);
            choose(nextKeys[Math.min(oldIndex, nextKeys.length - 1)]);
        } catch (error) {
            notifyError("PanelComposer layout was not deleted", error);
        }
    };
    search.addEventListener("input", onSearch);
    select.addEventListener("change", onSelect);
    previous.addEventListener("click", () => step(-1));
    next.addEventListener("click", () => step(1));
    remove.addEventListener("click", onDelete);
    resizeHandle.addEventListener("pointerdown", (event) => {
        const startY = event.clientY;
        const startHeight = Math.max(180, container.getBoundingClientRect().height);
        resizeHandle.setPointerCapture?.(event.pointerId);
        const onMove = (moveEvent) => {
            const height = Math.max(180, Math.min(640, startHeight + moveEvent.clientY - startY));
            setMountedHeight(height);
            canvas.style.height = `${Math.max(100, height - 50)}px`;
            redraw();
        };
        const onUp = (upEvent) => {
            resizeHandle.releasePointerCapture?.(upEvent.pointerId);
            resizeHandle.removeEventListener("pointermove", onMove);
            resizeHandle.removeEventListener("pointerup", onUp);
            resizeHandle.removeEventListener("pointercancel", onUp);
        };
        resizeHandle.addEventListener("pointermove", onMove);
        resizeHandle.addEventListener("pointerup", onUp);
        resizeHandle.addEventListener("pointercancel", onUp);
    });
    const subscriptions = [layoutWidget, aspectWidget, orientationWidget, rotationWidget, readingWidget]
        .filter(Boolean)
        .map((widget) => widget.on("change", redraw));

    const controller = { refresh };
    controllerByNode.set(node.id, controller);
    void refresh().catch((error) => notifyError("PanelComposer layouts could not be loaded", error));

    return () => {
        destroyed = true;
        controllerByNode.delete(node.id);
        subscriptions.forEach((unsubscribe) => unsubscribe());
    };
}

comfy.defs.extend("PanelLayoutProvider", (builder) => {
    builder.hideWidget("layout_preset");
    builder.onCreated((node) => {
        node.setSizeConstraints({ minWidth: 300, minHeight: 360 });
        let previewHeight = Number(node.getProperty("previewHeight") ?? 230);
        if (!Number.isFinite(previewHeight)) previewHeight = 230;
        previewHeight = Math.max(180, Math.min(640, previewHeight));
        let teardown = () => {};
        let mounted;
        mounted = node.widgets.mount({
            name: "layout_preview",
            height: previewHeight,
            serialize: false,
            sendToPrompt: false,
            render(container) {
                teardown = mountPreview(node, container, (height) => {
                    previewHeight = height;
                    node.setProperty("previewHeight", height);
                    mounted?.setHeight(height);
                }, previewHeight);
            },
            destroy() {
                teardown();
            },
        });
        mounted.setHeight(previewHeight);
    });
});
