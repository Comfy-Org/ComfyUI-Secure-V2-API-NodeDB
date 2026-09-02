import { comfy } from '/comfy/api/v2.js';
import { computeCanvasSize, getDrawColor, readLinkedNumber, setDefaultProperties, watchLinkedNumbers } from "./common.js";

// Handles hold no arbitrary properties, so the preview surface lives here, keyed
// by node id, and is dropped in onRemoved.
const previews = new Map();
const linkedSubscriptions = new Map();

function showPreviewCanvas(node) {

    const surface = node.widgets.canvas({
        name: "mask-rect-area-canvas",
        height: 220,
        draw: function (ctx, [widgetWidth, widgetHeight], theme) {

            const margin = 12;
            const border = 2;

            // Keep preview in sync when inputs are driven by links.
            syncLinkedInputsToPropertiesAdvanced(node);

            const width = Math.max(1, Math.round(node.getProperty("width")));
            const height = Math.max(1, Math.round(node.getProperty("height")));
            const scale = Math.min(
                    (widgetWidth - margin * 3) / width,
                    (widgetHeight - margin * 3) / height
                    );
            const blurRadius = node.getProperty("blur_radius") || 0;

            let backgroundWidth = width * scale;
            let backgroundHeight = height * scale;

            let xOffset = margin;
            if (backgroundWidth < widgetWidth) {
                xOffset += (widgetWidth - backgroundWidth) / 2 - margin;
            }
            let yOffset = (margin / 2);
            if (backgroundHeight < widgetHeight) {
                yOffset += (widgetHeight - backgroundHeight) / 2 - margin;
            }

            let widgetX = xOffset;
            let widgetY = yOffset;

            // Draw the background border
            ctx.fillStyle = theme.border;
            ctx.fillRect(widgetX - border, widgetY - border, backgroundWidth + border * 2, backgroundHeight + border * 2)

            // Draw the main background area
            ctx.fillStyle = theme.surface;
            ctx.fillRect(widgetX, widgetY, backgroundWidth, backgroundHeight);

            // Draw the conditioning zone
            let [x, y, w, h] = getDrawArea(node, backgroundWidth, backgroundHeight);

            ctx.fillStyle = getDrawColor(0, "80");
            ctx.fillRect(widgetX + x, widgetY + y, w, h);
            ctx.beginPath();
            ctx.lineWidth = 1;

            // Draw grid lines
            for (let x = 0; x <= width / 64; x += 1) {
                ctx.moveTo(widgetX + x * 64 * scale, widgetY);
                ctx.lineTo(widgetX + x * 64 * scale, widgetY + backgroundHeight);
            }

            for (let y = 0; y <= height / 64; y += 1) {
                ctx.moveTo(widgetX, widgetY + y * 64 * scale);
                ctx.lineTo(widgetX + backgroundWidth, widgetY + y * 64 * scale);
            }

            ctx.strokeStyle = theme.textSecondary;
            ctx.stroke();
            ctx.closePath();

            // Draw current zone
            let [sx, sy, sw, sh] = getDrawArea(node, backgroundWidth, backgroundHeight);

            ctx.fillStyle = getDrawColor(0, "80");
            ctx.fillRect(widgetX + sx, widgetY + sy, sw, sh);

            ctx.fillStyle = getDrawColor(0, "40");
            ctx.fillRect(widgetX + sx + border, widgetY + sy + border, sw - border * 2, sh - border * 2);

            // Draw white border around the current zone
            ctx.strokeStyle = theme.text;
            ctx.lineWidth = 2;
            ctx.strokeRect(widgetX + sx, widgetY + sy, sw, sh);

            // Display
            ctx.beginPath();

            ctx.arc(10, 14, 4, 0, Math.PI * 2);
            ctx.fill();

            ctx.lineWidth = 1;
            ctx.strokeStyle = theme.text;
            ctx.stroke();

            ctx.lineWidth = 1;
            ctx.closePath();

            // Draw progress bar canvas
            if (backgroundWidth < widgetWidth) {
                xOffset += (widgetWidth - backgroundWidth) / 2 - margin;
            }

            // Adjust X and Y coordinates
            const barHeight = 8;
            let widgetYBar = widgetY + backgroundHeight + margin;

            // Draw the border around the progress bar
            ctx.fillStyle = theme.border;
            ctx.fillRect(
                    widgetX - border,
                    widgetYBar - border,
                    backgroundWidth + border * 2,
                    barHeight + border * 2
                    );

            // Draw the main bar area (background)
            ctx.fillStyle = theme.surface;
            ctx.fillRect(
                    widgetX,
                    widgetYBar,
                    backgroundWidth,
                    barHeight
                    );

            // Draw progress bar grid
            ctx.beginPath();
            ctx.lineWidth = 1;
            ctx.strokeStyle = theme.textSecondary;

            // Calculate the number of grid lines based on the bar size
            const numLines = Math.floor(backgroundWidth / 64);

            // Draw grid lines
            for (let x = 0; x <= width / 64; x += 1) {
                ctx.moveTo(widgetX + x * 64 * scale, widgetYBar);
                ctx.lineTo(widgetX + x * 64 * scale, widgetYBar + barHeight);
            }
            ctx.stroke();
            ctx.closePath();

            // Draw progress (based on blur_radius)
            const progress = Math.min(blurRadius / 255, 1);
            ctx.fillStyle = "rgba(0, 120, 255, 0.5)";

            ctx.fillRect(
                    widgetX,
                    widgetYBar,
                    backgroundWidth * progress,
                    barHeight
                    );
        }
    });

    previews.set(node.id, surface);

    computeCanvasSize(node, node.getSize(), 220, 240);

    return {minWidth: 200, minHeight: 200, widget: surface.widget};
}

comfy.defs.extend("MaskRectAreaAdvanced", (b) => {
    b.onCreated((node) => {
        node.setSerializeWidgets(true);

        // If the node already provides widgets from Python/ComfyUI, do NOT recreate them
        const hasExisting = node.widgets.get("x") !== undefined;

        // Helper: attach callbacks to existing widgets to keep node.properties in sync (canvas preview).
        const hookWidget = (node, widgetName, propName, opts) => {
            const w = node.widgets.get(widgetName);
            if (!w) {
                return;
            }

            const min = (opts && typeof opts.min === "number") ? opts.min : undefined;
            const max = (opts && typeof opts.max === "number") ? opts.max : undefined;
            const step = (opts && typeof opts.step === "number") ? opts.step : undefined;

            if (node.getProperty(propName) !== undefined) {
                w.setValue(node.getProperty(propName));
            } else {
                node.setProperty(propName, w.getValue());
            }

            w.on('change', (v) => {
                let val = v;
                if (typeof val === "number") {
                    if (typeof step === "number" && step > 0) {
                        const s = step / 10;
                        val = Math.round(val / s) * s;
                    } else {
                        val = Math.round(val);
                    }
                    if (typeof min === "number") {
                        val = Math.max(min, val);
                    }
                    if (typeof max === "number") {
                        val = Math.min(max, val);
                    }
                }
                if (val !== v) {
                    w.setValue(val);
                }
                node.setProperty(propName, val);
                previews.get(node.id)?.redraw();
            });
        };

        if (hasExisting) {
            hookWidget(node, "x", "x", {"step": 10});
            hookWidget(node, "y", "y", {"step": 10});
            hookWidget(node, "width", "w", {"step": 10});
            hookWidget(node, "height", "h", {"step": 10});
            hookWidget(node, "image_width", "width", {"step": 10});
            hookWidget(node, "image_height", "height", {"step": 10});
            hookWidget(node, "blur_radius", "blur_radius", {"min": 0, "max": 255, "step": 10});
        } else {
            CUSTOM_INT(node, "x", 0, function (v, w, node) {
                const s = w.getOptions().step / 10;
                w.setValue(Math.round(v / s) * s);
                node.setProperty("x", w.getValue());
            });
            CUSTOM_INT(node, "y", 0, function (v, w, node) {
                const s = w.getOptions().step / 10;
                w.setValue(Math.round(v / s) * s);
                node.setProperty("y", w.getValue());
            });
            CUSTOM_INT(node, "width", 256, function (v, w, node) {
                const s = w.getOptions().step / 10;
                w.setValue(Math.round(v / s) * s);
                node.setProperty("w", w.getValue());
            });
            CUSTOM_INT(node, "height", 256, function (v, w, node) {
                const s = w.getOptions().step / 10;
                w.setValue(Math.round(v / s) * s);
                node.setProperty("h", w.getValue());
            });
            CUSTOM_INT(node, "image_width", 512, function (v, w, node) {
                const s = w.getOptions().step / 10;
                w.setValue(Math.round(v / s) * s);
                node.setProperty("width", w.getValue());
            });
            CUSTOM_INT(node, "image_height", 512, function (v, w, node) {
                const s = w.getOptions().step / 10;
                w.setValue(Math.round(v / s) * s);
                node.setProperty("height", w.getValue());
            });
            CUSTOM_INT(node, "blur_radius", 0, function (v, w, node) {
                w.setValue(Math.round(v) || 0);
                node.setProperty("blur_radius", w.getValue());
            },
                    {"min": 0, "max": 255, "step": 10}
            );
        }

        setDefaultProperties(node, {
            width: 512,
            height: 512,
            x: 0,
            y: 0,
            w: 256,
            h: 256,
            blur_radius: 0
        });

        showPreviewCanvas(node);
        refreshLinkedInputSubscriptions(node);
    });

    b.onConnectionsChanged((node) => {
        refreshLinkedInputSubscriptions(node);
    });

    b.onRemoved((node) => {
        linkedSubscriptions.get(node.id)?.();
        linkedSubscriptions.delete(node.id);
        previews.delete(node.id);
    });
});

function refreshLinkedInputSubscriptions(node) {
    linkedSubscriptions.get(node.id)?.();
    const refresh = () => {
        syncLinkedInputsToPropertiesAdvanced(node);
        previews.get(node.id)?.redraw();
    };
    linkedSubscriptions.set(node.id, watchLinkedNumbers(
        node,
        ["x", "y", "width", "height", "image_width", "image_height", "blur_radius"],
        refresh
    ));
    refresh();
}

// Calculate the drawing area using individual properties.
function getDrawArea(node, backgroundWidth, backgroundHeight) {
    let x = node.getProperty("x") * backgroundWidth / node.getProperty("width");
    let y = node.getProperty("y") * backgroundHeight / node.getProperty("height");
    let w = node.getProperty("w") * backgroundWidth / node.getProperty("width");
    let h = node.getProperty("h") * backgroundHeight / node.getProperty("height");

    if (x > backgroundWidth) {
        x = backgroundWidth;
    }
    if (y > backgroundHeight) {
        y = backgroundHeight;
    }

    if (x + w > backgroundWidth) {
        w = Math.max(0, backgroundWidth - x);
    }

    if (y + h > backgroundHeight) {
        h = Math.max(0, backgroundHeight - y);
    }

    return [x, y, w, h];
}

function CUSTOM_INT(node, inputName, val, func, config = {}) {
    const widget = node.widgets.add({
        type: "number",
        name: inputName,
        value: val,
        options: Object.assign({}, {min: 0, max: 4096, step: 640, precision: 0}, config)
    });
    widget.on('change', (v) => func(v, widget, node));
    return { widget };
}

function syncLinkedInputsToPropertiesAdvanced(node) {
    let changed = false;

    const vx = readLinkedNumber(node, "x");
    if (vx != null) {
        const nv = Math.max(0, Math.round(vx));
        if (node.getProperty("x") !== nv) {
            node.setProperty("x", nv);
            changed = true;
        }
    }

    const vy = readLinkedNumber(node, "y");
    if (vy != null) {
        const nv = Math.max(0, Math.round(vy));
        if (node.getProperty("y") !== nv) {
            node.setProperty("y", nv);
            changed = true;
        }
    }

    // Input "width" is the rectangle width in px -> property "w"
    const vw = readLinkedNumber(node, "width");
    if (vw != null) {
        const nv = Math.max(0, Math.round(vw));
        if (node.getProperty("w") !== nv) {
            node.setProperty("w", nv);
            changed = true;
        }
    }

    // Input "height" is the rectangle height in px -> property "h"
    const vh = readLinkedNumber(node, "height");
    if (vh != null) {
        const nv = Math.max(0, Math.round(vh));
        if (node.getProperty("h") !== nv) {
            node.setProperty("h", nv);
            changed = true;
        }
    }

    // Image size (must be >=1 to avoid division by zero in getDrawArea)
    const viw = readLinkedNumber(node, "image_width");
    if (viw != null) {
        const nv = Math.max(1, Math.round(viw));
        if (node.getProperty("width") !== nv) {
            node.setProperty("width", nv);
            changed = true;
        }
    }

    const vih = readLinkedNumber(node, "image_height");
    if (vih != null) {
        const nv = Math.max(1, Math.round(vih));
        if (node.getProperty("height") !== nv) {
            node.setProperty("height", nv);
            changed = true;
        }
    }

    const vbr = readLinkedNumber(node, "blur_radius");
    if (vbr != null) {
        const nv = Math.max(0, Math.min(255, Math.round(vbr)));
        if (node.getProperty("blur_radius") !== nv) {
            node.setProperty("blur_radius", nv);
            changed = true;
        }
    }

    return changed;
}
