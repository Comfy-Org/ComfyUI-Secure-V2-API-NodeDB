import { comfy } from '/comfy/api/v2.js';
import { computeCanvasSize, getDrawColor, readLinkedNumber, setDefaultProperties, watchLinkedNumbers } from "./common.js";

// Handles hold no arbitrary properties, so the preview surface lives here, keyed
// by node id, and is dropped in onRemoved.
const previews = new Map();
const linkedSubscriptions = new Map();

function showPreviewCanvas(node) {

    const surface = node.widgets.canvas({
        name: "mask-rect-area-canvas",
        height: 200,
        draw: function (ctx, [widgetWidth, widgetHeight], theme) {

            const margin = 12;
            const border = 2;
            const width = 512;
            const height = 512;
            const scale = Math.min((widgetWidth - margin * 3) / width, (widgetHeight - margin * 3) / height);

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
            ctx.fillRect(widgetX - border, widgetY - border, backgroundWidth + border * 2, backgroundHeight + border * 2);

            // Draw the main background area
            ctx.fillStyle = theme.surface;
            ctx.fillRect(widgetX, widgetY, backgroundWidth, backgroundHeight);

            // Keep preview in sync when inputs are driven by links.
            syncLinkedInputsToProperties(node);
            const blurRadius = node.getProperty("blur_radius") || 0;

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

            const barHeight = 8;
            let widgetYBar = widgetY + backgroundHeight + margin;

            // Draw progress bar border
            ctx.fillStyle = theme.border;
            ctx.fillRect(
                    widgetX - border,
                    widgetYBar - border,
                    backgroundWidth + border * 2,
                    barHeight + border * 2
                    );

            // Draw progress bar area
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

            // Determine max lines
            const numLines = Math.floor(backgroundWidth / 64);

            // Draw progress bar grid
            for (let x = 0; x <= width / 64; x += 1) {
                ctx.moveTo(widgetX + x * 64 * scale, widgetYBar);
                ctx.lineTo(widgetX + x * 64 * scale, widgetYBar + barHeight);
            }
            ctx.stroke();
            ctx.closePath();

            // Draw progress bar
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

    computeCanvasSize(node, node.getSize(), 200, 200);

    return {minWidth: 200, minHeight: 200, widget: surface.widget};
}

comfy.defs.extend("MaskRectArea", (b) => {
    b.onCreated((node) => {
        node.setSerializeWidgets(true);

        // If Python/ComfyUI already created typed widgets, do not recreate them (avoid duplicates).
        const hasExisting = node.widgets.get("x") !== undefined;

        // Hook existing widgets to keep node.properties in sync (canvas uses properties).
        const hookWidget = (node, widgetName, propName, opts) => {
            const w = node.widgets.get(widgetName);
            if (!w) {
                return;
            }

            const min = (opts && typeof opts.min === "number") ? opts.min : undefined;
            const max = (opts && typeof opts.max === "number") ? opts.max : undefined;

            if (node.getProperty(propName) !== undefined) {
                w.setValue(node.getProperty(propName));
            } else {
                node.setProperty(propName, w.getValue());
            }

            w.on('change', (v) => {
                let val = v;

                if (typeof val === "number") {
                    val = Math.round(val);

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
            // Note: "width"/"height" widgets map to "w"/"h" properties (percent-based).
            hookWidget(node, "x", "x", {"min": 0, "max": 100});
            hookWidget(node, "y", "y", {"min": 0, "max": 100});
            hookWidget(node, "width", "w", {"min": 0, "max": 100});
            hookWidget(node, "height", "h", {"min": 0, "max": 100});
            hookWidget(node, "blur_radius", "blur_radius", {"min": 0, "max": 255});
        } else {
            CUSTOM_INT(node, "x", 0, function (v, w, node) {
                w.setValue(Math.max(0, Math.min(100, Math.round(v))));
                node.setProperty("x", w.getValue());
            });
            CUSTOM_INT(node, "y", 0, function (v, w, node) {
                w.setValue(Math.max(0, Math.min(100, Math.round(v))));
                node.setProperty("y", w.getValue());
            });
            CUSTOM_INT(node, "w", 50, function (v, w, node) {
                w.setValue(Math.max(0, Math.min(100, Math.round(v))));
                node.setProperty("w", w.getValue());
            });
            CUSTOM_INT(node, "h", 50, function (v, w, node) {
                w.setValue(Math.max(0, Math.min(100, Math.round(v))));
                node.setProperty("h", w.getValue());
            });
            CUSTOM_INT(node, "blur_radius", 0, function (v, w, node) {
                w.setValue(Math.round(v) || 0);
                node.setProperty("blur_radius", w.getValue());
            }, {"min": 0, "max": 255, "step": 10});

            // If Python widgets exist, they will be used instead; this is back-compat only.
        }

        setDefaultProperties(node, {
            width: 512,
            height: 512,
            x: 0,
            y: 0,
            w: 50,
            h: 50,
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
        syncLinkedInputsToProperties(node);
        previews.get(node.id)?.redraw();
    };
    linkedSubscriptions.set(node.id, watchLinkedNumbers(
        node,
        ["x", "y", "width", "height", "blur_radius"],
        refresh
    ));
    refresh();
}


// Calculate the drawing area using percentage-based properties.
function getDrawArea(node, backgroundWidth, backgroundHeight) {
    // Convert percentages to actual pixel values based on the background dimensions
    let x = (node.getProperty("x") / 100) * backgroundWidth;
    let y = (node.getProperty("y") / 100) * backgroundHeight;
    let w = (node.getProperty("w") / 100) * backgroundWidth;
    let h = (node.getProperty("h") / 100) * backgroundHeight;

    // Ensure the values do not exceed the background boundaries
    if (x > backgroundWidth) {
        x = backgroundWidth;
    }
    if (y > backgroundHeight) {
        y = backgroundHeight;
    }

    // Adjust width and height to fit within the background dimensions
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
        options: Object.assign({}, {min: 0, max: 100, step: 10, precision: 0}, config)
    });
    widget.on('change', (v) => func(v, widget, node));
    return { widget };
}

function syncLinkedInputsToProperties(node) {
    let changed = false;

    const vx = readLinkedNumber(node, "x");
    if (vx != null) {
        const nv = Math.max(0, Math.min(100, Math.round(vx)));
        if (node.getProperty("x") !== nv) {
            node.setProperty("x", nv);
            changed = true;
        }
    }

    const vy = readLinkedNumber(node, "y");
    if (vy != null) {
        const nv = Math.max(0, Math.min(100, Math.round(vy)));
        if (node.getProperty("y") !== nv) {
            node.setProperty("y", nv);
            changed = true;
        }
    }

    const vw = readLinkedNumber(node, "width");
    if (vw != null) {
        const nv = Math.max(0, Math.min(100, Math.round(vw)));
        if (node.getProperty("w") !== nv) {
            node.setProperty("w", nv);
            changed = true;
        }
    }

    const vh = readLinkedNumber(node, "height");
    if (vh != null) {
        const nv = Math.max(0, Math.min(100, Math.round(vh)));
        if (node.getProperty("h") !== nv) {
            node.setProperty("h", nv);
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
