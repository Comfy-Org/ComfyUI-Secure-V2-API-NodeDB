import { comfy } from "/comfy/api/v2.js";
import {
    ASPECT_RATIO_CHOICES,
    decodePresetChoice,
    deriveRowGroups,
    encodePresetChoice,
    loadPresets,
    parseAspectRatio,
    resolveOrientedAspectRatio,
    savePreset,
} from "./panel_layout_preview.js";

const COLOR_INK = "#eeeeF3";
const COLOR_MUTED = "#9292a8";
const COLOR_ACCENT = "#4a90d9";
const COLOR_INVALID = "#dc5555";
const COLOR_OVERLAP = "#d9a13f";
const SNAP_PX = 10;

function clone(value) {
    return JSON.parse(JSON.stringify(value));
}

function clamp01(value) {
    return Math.max(0, Math.min(1, value));
}

export function normalizePanelPoints(points) {
    return points.map(([x, y]) => [clamp01(Number(x)), clamp01(Number(y))]);
}

export function signedArea(points) {
    let area = 0;
    for (let index = 0; index < points.length; index += 1) {
        const [x1, y1] = points[index];
        const [x2, y2] = points[(index + 1) % points.length];
        area += x1 * y2 - x2 * y1;
    }
    return area / 2;
}

export function normalizeWinding(points) {
    const normalized = normalizePanelPoints(points);
    return signedArea(normalized) < 0 ? [...normalized].reverse() : normalized;
}

function orientation(a, b, c) {
    return Math.sign((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]));
}

function segmentsIntersect(a, b, c, d) {
    return orientation(a, b, c) * orientation(a, b, d) < 0
        && orientation(c, d, a) * orientation(c, d, b) < 0;
}

export function hasSelfIntersection(points) {
    for (let left = 0; left < points.length; left += 1) {
        const leftNext = (left + 1) % points.length;
        for (let right = left + 1; right < points.length; right += 1) {
            const rightNext = (right + 1) % points.length;
            if (left === right || leftNext === right || rightNext === left) continue;
            if (segmentsIntersect(points[left], points[leftNext], points[right], points[rightNext])) return true;
        }
    }
    return false;
}

function centroid(points) {
    return [
        points.reduce((sum, point) => sum + point[0], 0) / points.length,
        points.reduce((sum, point) => sum + point[1], 0) / points.length,
    ];
}

export function autoRepairPanel(points) {
    let repaired = normalizePanelPoints(points);
    if (hasSelfIntersection(repaired)) {
        const [cx, cy] = centroid(repaired);
        repaired = [...repaired].sort(
            (left, right) => Math.atan2(left[1] - cy, left[0] - cx) - Math.atan2(right[1] - cy, right[0] - cx),
        );
    }
    return normalizeWinding(repaired);
}

export function validatePanelPoints(points) {
    if (!Array.isArray(points) || points.length < 3) return "needs at least three points";
    if (!points.every((point) => Array.isArray(point)
        && point.length === 2
        && point.every((value) => Number.isFinite(value) && value >= 0 && value <= 1))) {
        return "contains a point outside the page";
    }
    if (Math.abs(signedArea(points)) < 0.00001) return "has no usable area";
    if (hasSelfIntersection(points)) return "crosses itself";
    return null;
}

function pointInPolygon(point, polygon) {
    let inside = false;
    for (let index = 0, previous = polygon.length - 1; index < polygon.length; previous = index++) {
        const [xi, yi] = polygon[index];
        const [xj, yj] = polygon[previous];
        if ((yi > point[1]) !== (yj > point[1])
            && point[0] < ((xj - xi) * (point[1] - yi)) / (yj - yi) + xi) inside = !inside;
    }
    return inside;
}

export function polygonsOverlap(left, right) {
    for (let a = 0; a < left.length; a += 1) {
        for (let b = 0; b < right.length; b += 1) {
            if (segmentsIntersect(left[a], left[(a + 1) % left.length], right[b], right[(b + 1) % right.length])) {
                return true;
            }
        }
    }
    return pointInPolygon(left[0], right) || pointInPolygon(right[0], left);
}

export function overlapIndices(panels) {
    const found = new Set();
    for (let left = 0; left < panels.length; left += 1) {
        for (let right = left + 1; right < panels.length; right += 1) {
            if (polygonsOverlap(panels[left], panels[right])) {
                found.add(left);
                found.add(right);
            }
        }
    }
    return found;
}

export function createHistory(initial) {
    let current = clone(initial);
    const undoStack = [];
    const redoStack = [];
    return {
        current: () => clone(current),
        commit(next) {
            undoStack.push(clone(current));
            current = clone(next);
            redoStack.length = 0;
            return clone(current);
        },
        undo() {
            if (!undoStack.length) return clone(current);
            redoStack.push(clone(current));
            current = undoStack.pop();
            return clone(current);
        },
        redo() {
            if (!redoStack.length) return clone(current);
            undoStack.push(clone(current));
            current = redoStack.pop();
            return clone(current);
        },
        canUndo: () => undoStack.length > 0,
        canRedo: () => redoStack.length > 0,
    };
}

function closestPointOnSegment(point, start, end) {
    const dx = end[0] - start[0];
    const dy = end[1] - start[1];
    const lengthSquared = dx * dx + dy * dy;
    const amount = lengthSquared === 0
        ? 0
        : Math.max(0, Math.min(1, ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / lengthSquared));
    return [start[0] + amount * dx, start[1] + amount * dy];
}

export function snapPoint(point, panels, size, enabled) {
    const xTolerance = SNAP_PX / Math.max(1, size.width);
    const yTolerance = SNAP_PX / Math.max(1, size.height);
    const distance = (a, b) => Math.hypot((a[0] - b[0]) / xTolerance, (a[1] - b[1]) / yTolerance);

    if (enabled.vertex) {
        const vertices = panels.flat();
        const best = vertices.reduce((winner, candidate) =>
            (!winner || distance(point, candidate) < distance(point, winner)) ? candidate : winner, null);
        if (best && distance(point, best) <= 1) return [...best];
    }
    if (enabled.edge) {
        let best = null;
        for (const polygon of panels) {
            for (let index = 0; index < polygon.length; index += 1) {
                const candidate = closestPointOnSegment(point, polygon[index], polygon[(index + 1) % polygon.length]);
                if (!best || distance(point, candidate) < distance(point, best)) best = candidate;
            }
        }
        if (best && distance(point, best) <= 1) return best;
    }
    if (enabled.guide) {
        const guides = panels.flat();
        const x = guides.map((candidate) => candidate[0]).find((candidate) => Math.abs(candidate - point[0]) <= xTolerance);
        const y = guides.map((candidate) => candidate[1]).find((candidate) => Math.abs(candidate - point[1]) <= yTolerance);
        if (x !== undefined || y !== undefined) return [x ?? point[0], y ?? point[1]];
    }
    if (enabled.bounds) {
        const x = point[0] <= xTolerance ? 0 : point[0] >= 1 - xTolerance ? 1 : point[0];
        const y = point[1] <= yTolerance ? 0 : point[1] >= 1 - yTolerance ? 1 : point[1];
        if (x !== point[0] || y !== point[1]) return [x, y];
    }
    if (enabled.grid) return [Math.round(point[0] * 20) / 20, Math.round(point[1] * 20) / 20];
    return point;
}

function button(doc, label, title, run) {
    const element = doc.createElement("button");
    element.type = "button";
    element.textContent = label;
    element.title = title;
    element.addEventListener("click", run);
    return element;
}

function checkbox(doc, label, checked, onChange) {
    const wrapper = doc.createElement("label");
    wrapper.style.cssText = "display:flex;gap:4px;align-items:center;font-size:12px;";
    const input = doc.createElement("input");
    input.type = "checkbox";
    input.checked = checked;
    input.addEventListener("change", () => onChange(input.checked));
    wrapper.append(input, doc.createTextNode(label));
    return wrapper;
}

function eventPoint(event, canvas) {
    const bounds = canvas.getBoundingClientRect();
    return [
        clamp01((event.clientX - bounds.left) / Math.max(1, bounds.width)),
        clamp01((event.clientY - bounds.top) / Math.max(1, bounds.height)),
    ];
}

function renderEditor(canvas, panels, draft, selected, aspectRatio, overlap) {
    const context = canvas.getContext("2d");
    if (!context) return;
    const width = Math.max(1, Math.floor(canvas.clientWidth || 700));
    const height = Math.max(1, Math.floor(canvas.clientHeight || 560));
    canvas.width = width;
    canvas.height = height;
    context.fillStyle = "#f7f7f7";
    context.fillRect(0, 0, width, height);
    context.lineWidth = 2;
    panels.forEach((polygon, index) => {
        context.beginPath();
        polygon.forEach(([x, y], pointIndex) => {
            if (pointIndex === 0) context.moveTo(x * width, y * height);
            else context.lineTo(x * width, y * height);
        });
        context.closePath();
        context.fillStyle = `hsla(${(index * 137.5) % 360},65%,70%,0.55)`;
        context.fill();
        context.strokeStyle = validatePanelPoints(polygon)
            ? COLOR_INVALID
            : overlap.has(index) ? COLOR_OVERLAP : index === selected ? COLOR_ACCENT : "#262632";
        context.setLineDash(overlap.has(index) ? [7, 5] : []);
        context.stroke();
        context.setLineDash([]);
        const [cx, cy] = centroid(polygon);
        context.fillStyle = "#17171f";
        context.font = "bold 14px sans-serif";
        context.textAlign = "center";
        context.fillText(String(index + 1), cx * width, cy * height);
        if (index === selected) {
            for (const [x, y] of polygon) {
                context.beginPath();
                context.arc(x * width, y * height, 4, 0, Math.PI * 2);
                context.fillStyle = COLOR_ACCENT;
                context.fill();
            }
        }
    });
    if (draft.length) {
        context.beginPath();
        draft.forEach(([x, y], index) => {
            if (index === 0) context.moveTo(x * width, y * height);
            else context.lineTo(x * width, y * height);
        });
        context.strokeStyle = COLOR_ACCENT;
        context.stroke();
        for (const [x, y] of draft) {
            context.beginPath();
            context.arc(x * width, y * height, 4, 0, Math.PI * 2);
            context.fillStyle = COLOR_ACCENT;
            context.fill();
        }
    }
    canvas.style.aspectRatio = String(aspectRatio);
}

function notifyError(summary, error) {
    comfy.commands.notify({
        severity: "error",
        summary,
        detail: error instanceof Error ? error.message : String(error),
    });
}

export async function openDrawingDialog(node) {
    const layoutWidget = node.widgets.get("layout_preset");
    const aspectWidget = node.widgets.get("aspect_ratio");
    const orientationWidget = node.widgets.get("page_orientation");
    if (!layoutWidget) return;

    const presets = await loadPresets();
    const selectedPreset = decodePresetChoice(presets, layoutWidget.getValue())
        ?? Object.values(presets)[0];
    const history = createHistory(selectedPreset.panels);
    let panels = history.current();
    let draft = [];
    let selected = null;
    let selectedVertex = null;
    let mode = "select";
    let drag = null;
    let manualOrder = false;
    const snaps = { vertex: true, edge: true, guide: true, bounds: true, grid: false };
    let canvas;
    let list;
    let status;
    let undoButton;
    let redoButton;
    let aspectSelect;
    let orientationSelect;
    let dialog;

    const pageRatio = () => resolveOrientedAspectRatio(
        parseAspectRatio(aspectSelect?.value ?? aspectWidget?.getValue()),
        orientationSelect?.value ?? orientationWidget?.getValue() ?? "portrait",
    );
    const refresh = () => {
        if (!canvas) return;
        const overlap = overlapIndices(panels);
        renderEditor(canvas, panels, draft, selected, pageRatio(), overlap);
        list.replaceChildren();
        panels.forEach((polygon, index) => {
            const row = list.ownerDocument.createElement("div");
            row.style.cssText = "display:grid;grid-template-columns:1fr auto auto;gap:4px;align-items:center;";
            const pick = button(list.ownerDocument, `Panel ${index + 1}`, "Select panel", () => {
                selected = index;
                selectedVertex = null;
                mode = "select";
                refresh();
            });
            if (validatePanelPoints(polygon)) pick.style.color = COLOR_INVALID;
            else if (overlap.has(index)) pick.style.color = COLOR_OVERLAP;
            const up = button(list.ownerDocument, "↑", "Move earlier", () => reorder(index, -1));
            const down = button(list.ownerDocument, "↓", "Move later", () => reorder(index, 1));
            row.append(pick, up, down);
            list.append(row);
        });
        undoButton.disabled = !history.canUndo();
        redoButton.disabled = !history.canRedo();
        status.textContent = overlap.size
            ? "Amber dashed panels overlap. Overlap is allowed and later panels paint on top."
            : mode === "draw" ? "Click points; click the first point again to close." : "";
    };
    const commit = (next) => {
        panels = history.commit(next);
        refresh();
    };
    const reorder = (index, delta) => {
        const target = index + delta;
        if (target < 0 || target >= panels.length) return;
        const next = clone(panels);
        [next[index], next[target]] = [next[target], next[index]];
        selected = target;
        manualOrder = true;
        commit(next);
    };
    const undo = () => {
        panels = history.undo();
        selected = null;
        selectedVertex = null;
        draft = [];
        mode = "select";
        refresh();
    };
    const redo = () => {
        panels = history.redo();
        selected = null;
        selectedVertex = null;
        draft = [];
        mode = "select";
        refresh();
    };
    const removeSelected = () => {
        if (selected == null) return;
        if (selectedVertex != null && panels[selected].length > 3) {
            const next = clone(panels);
            next[selected].splice(selectedVertex, 1);
            selectedVertex = null;
            commit(next);
            return;
        }
        commit(panels.filter((_, index) => index !== selected));
        selected = null;
        selectedVertex = null;
    };
    const closeDraft = () => {
        if (draft.length < 3) {
            status.textContent = "A panel needs at least three points.";
            return;
        }
        const repaired = autoRepairPanel(draft);
        const problem = validatePanelPoints(repaired);
        if (problem) {
            status.textContent = `Panel ${problem}.`;
            return;
        }
        commit([...panels, repaired]);
        draft = [];
        selected = panels.length - 1;
        mode = "select";
    };
    const onKey = (event) => {
        if (event.editableTarget) return;
        const modifier = event.ctrlKey || event.metaKey;
        if (modifier && event.key.toLowerCase() === "z") {
            if (event.shiftKey) redo();
            else undo();
        } else if (modifier && event.key.toLowerCase() === "y") {
            redo();
        } else if (event.key === "Delete" || event.key === "Backspace") {
            removeSelected();
        } else if (event.key === "Escape") {
            if (draft.length) {
                draft = [];
                mode = "select";
                refresh();
            } else {
                dialog.close();
            }
        }
    };

    dialog = comfy.ui.showDialog({
        key: "PanelComposer.DrawingDialog",
        title: "Draw Panels",
        onKeyDown: onKey,
        render(container) {
            const doc = container.ownerDocument;
            container.replaceChildren();
            container.style.cssText = "width:min(92vw,1100px);height:min(82vh,760px);display:flex;flex-direction:column;gap:8px;color:#eee;";
            const toolbar = doc.createElement("div");
            toolbar.style.cssText = "display:flex;gap:5px;flex-wrap:wrap;align-items:center;";
            const newPanel = button(doc, "New Panel", "Draw a polygon", () => {
                mode = "draw";
                draft = [];
                selected = null;
                selectedVertex = null;
                refresh();
            });
            const selectMode = button(doc, "Select", "Select and move panels", () => {
                mode = "select";
                draft = [];
                refresh();
            });
            const remove = button(doc, "Delete", "Delete selected panel", removeSelected);
            const clear = button(doc, "Clear", "Remove all panels", () => {
                selected = null;
                selectedVertex = null;
                draft = [];
                commit([]);
            });
            const normalize = button(doc, "Normalize", "Clamp and repair all polygons", () => {
                commit(panels.map(autoRepairPanel));
            });
            undoButton = button(doc, "Undo", "Undo local panel edit", undo);
            redoButton = button(doc, "Redo", "Redo local panel edit", redo);
            const autoOrder = button(doc, "Auto Order", "Restore geometry-derived reading order", () => {
                const groups = deriveRowGroups(panels.map((_, index) => index), panels);
                const ordered = groups.flat().map((index) => panels[index]);
                manualOrder = false;
                selected = null;
                selectedVertex = null;
                commit(ordered);
            });
            toolbar.append(newPanel, selectMode, remove, clear, normalize, undoButton, redoButton, autoOrder);

            const presetSelect = doc.createElement("select");
            for (const [key, preset] of Object.entries(presets)) {
                const option = doc.createElement("option");
                option.value = key;
                option.textContent = `${preset.category} / ${preset.label}`;
                presetSelect.append(option);
            }
            const loadPreset = button(doc, "Load Preset", "Load a preset as an editable starting point", () => {
                const preset = presets[presetSelect.value];
                if (!preset) return;
                selected = null;
                selectedVertex = null;
                draft = [];
                manualOrder = false;
                commit(clone(preset.panels));
            });
            toolbar.append(presetSelect, loadPreset);

            for (const [name, label] of [
                ["vertex", "Vertices"],
                ["edge", "Edges"],
                ["guide", "Guides"],
                ["bounds", "Bounds"],
                ["grid", "Grid"],
            ]) {
                toolbar.append(checkbox(doc, label, snaps[name], (checked) => { snaps[name] = checked; }));
            }
            aspectSelect = doc.createElement("select");
            for (const value of Object.keys(ASPECT_RATIO_CHOICES)) {
                const option = doc.createElement("option");
                option.value = value;
                option.textContent = value;
                aspectSelect.append(option);
            }
            aspectSelect.value = String(aspectWidget?.getValue() ?? "1:1 (Square)");
            orientationSelect = doc.createElement("select");
            for (const value of ["portrait", "landscape"]) {
                const option = doc.createElement("option");
                option.value = value;
                option.textContent = value;
                orientationSelect.append(option);
            }
            orientationSelect.value = String(orientationWidget?.getValue() ?? "portrait");
            aspectSelect.addEventListener("change", refresh);
            orientationSelect.addEventListener("change", refresh);
            toolbar.append(aspectSelect, orientationSelect);

            const body = doc.createElement("div");
            body.style.cssText = "display:grid;grid-template-columns:minmax(0,1fr) 220px;gap:8px;min-height:0;flex:1;";
            const canvasWrap = doc.createElement("div");
            canvasWrap.style.cssText = "min-height:0;display:flex;align-items:center;justify-content:center;background:#111118;padding:8px;";
            canvas = doc.createElement("canvas");
            canvas.tabIndex = 0;
            canvas.style.cssText = "display:block;max-width:100%;max-height:100%;width:100%;touch-action:none;cursor:crosshair;";
            canvasWrap.append(canvas);
            const side = doc.createElement("div");
            side.style.cssText = "display:flex;flex-direction:column;gap:6px;min-height:0;";
            list = doc.createElement("div");
            list.style.cssText = "display:flex;flex-direction:column;gap:4px;overflow:auto;flex:1;";
            status = doc.createElement("div");
            status.style.cssText = `min-height:36px;color:${COLOR_MUTED};font-size:12px;`;
            const category = doc.createElement("input");
            category.placeholder = "Category";
            category.value = selectedPreset.category;
            const label = doc.createElement("input");
            label.placeholder = "Layout name";
            label.value = selectedPreset.is_builtin ? `${selectedPreset.label} Copy` : selectedPreset.label;
            const save = button(doc, "Save Layout", "Save to your private PanelComposer library", async () => {
                const repaired = panels.map((polygon) => normalizeWinding(autoRepairPanel(polygon)));
                const invalid = repaired.findIndex((polygon) => validatePanelPoints(polygon));
                if (invalid >= 0) {
                    selected = invalid;
                    panels = repaired;
                    status.textContent = `Panel ${invalid + 1} ${validatePanelPoints(repaired[invalid])}.`;
                    refresh();
                    return;
                }
                if (!repaired.length) {
                    status.textContent = "Draw at least one panel before saving.";
                    return;
                }
                save.disabled = true;
                try {
                    const groups = manualOrder
                        ? null
                        : deriveRowGroups(repaired.map((_, index) => index), repaired);
                    const result = await savePreset(category.value, label.value, repaired, groups);
                    layoutWidget.setValue(encodePresetChoice(result.preset));
                    aspectWidget?.setValue(aspectSelect.value);
                    orientationWidget?.setValue(orientationSelect.value);
                    dialog.close();
                } catch (error) {
                    notifyError("PanelComposer layout was not saved", error);
                    status.textContent = error instanceof Error ? error.message : String(error);
                } finally {
                    save.disabled = false;
                }
            });
            side.append(list, status, category, label, save);
            body.append(canvasWrap, side);
            container.append(toolbar, body);

            canvas.addEventListener("pointerdown", (event) => {
                const point = eventPoint(event, canvas);
                canvas.setPointerCapture?.(event.pointerId);
                if (mode === "draw") {
                    const snapped = snapPoint(point, [...panels, draft], {
                        width: canvas.clientWidth,
                        height: canvas.clientHeight,
                    }, snaps);
                    if (draft.length >= 3 && Math.hypot(
                        (snapped[0] - draft[0][0]) * canvas.clientWidth,
                        (snapped[1] - draft[0][1]) * canvas.clientHeight,
                    ) <= SNAP_PX) {
                        closeDraft();
                    } else {
                        draft.push(snapped);
                        refresh();
                    }
                    return;
                }
                const width = Math.max(1, canvas.clientWidth);
                const height = Math.max(1, canvas.clientHeight);
                let vertexHit = null;
                for (let panelIndex = panels.length - 1; panelIndex >= 0 && !vertexHit; panelIndex -= 1) {
                    for (let vertexIndex = 0; vertexIndex < panels[panelIndex].length; vertexIndex += 1) {
                        const vertex = panels[panelIndex][vertexIndex];
                        if (Math.hypot((vertex[0] - point[0]) * width, (vertex[1] - point[1]) * height) <= SNAP_PX) {
                            vertexHit = { panelIndex, vertexIndex };
                            break;
                        }
                    }
                }
                if (vertexHit) {
                    selected = vertexHit.panelIndex;
                    selectedVertex = vertexHit.vertexIndex;
                    drag = { kind: "vertex", start: point, original: clone(panels) };
                    refresh();
                    return;
                }
                selected = [...panels].reverse().findIndex((polygon) => pointInPolygon(point, polygon));
                if (selected >= 0) selected = panels.length - 1 - selected;
                else selected = null;
                selectedVertex = null;
                if (selected != null) drag = { kind: "panel", start: point, original: clone(panels) };
                refresh();
            });
            canvas.addEventListener("pointermove", (event) => {
                if (!drag || selected == null) return;
                const point = eventPoint(event, canvas);
                const dx = point[0] - drag.start[0];
                const dy = point[1] - drag.start[1];
                panels = clone(drag.original);
                const polygon = panels[selected];
                if (drag.kind === "vertex") {
                    const others = panels.map((candidate, panelIndex) =>
                        panelIndex === selected
                            ? candidate.filter((_, vertexIndex) => vertexIndex !== selectedVertex)
                            : candidate);
                    polygon[selectedVertex] = snapPoint(point, others, {
                        width: canvas.clientWidth,
                        height: canvas.clientHeight,
                    }, snaps);
                    refresh();
                    return;
                }
                const minX = Math.min(...polygon.map(([x]) => x));
                const maxX = Math.max(...polygon.map(([x]) => x));
                const minY = Math.min(...polygon.map(([, y]) => y));
                const maxY = Math.max(...polygon.map(([, y]) => y));
                const safeDx = Math.max(-minX, Math.min(1 - maxX, dx));
                const safeDy = Math.max(-minY, Math.min(1 - maxY, dy));
                panels[selected] = polygon.map(([x, y]) => [x + safeDx, y + safeDy]);
                refresh();
            });
            canvas.addEventListener("pointerup", (event) => {
                if (drag) {
                    const next = clone(panels);
                    panels = drag.original;
                    drag = null;
                    commit(next);
                }
                canvas.releasePointerCapture?.(event.pointerId);
            });
            canvas.addEventListener("dblclick", () => {
                if (mode === "draw") closeDraft();
            });
            refresh();
        },
    });
}

comfy.defs.extend("PanelLayoutProvider", (builder) => {
    builder.onCreated((node) => {
        const drawButton = node.widgets.add({
            type: "button",
            name: "draw_panels",
            value: null,
            serialize: true,
        });
        drawButton.setLabel("Draw Panels");
        drawButton.on("activate", () => {
            void openDrawingDialog(node).catch((error) =>
                notifyError("PanelComposer editor could not open", error));
        });
    });
});
