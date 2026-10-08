import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "Comfy.ResolutionAndRatio",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== "ResolutionAndRatio") {
            return;
        }

        const MIN_SIZE = 8;           // smallest manual size
        const MAX_SIZE = 4096;
        const FREE_MAX = 32;          // 8..32 are taken as typed
        const GRID = 32;              // anything above FREE_MAX must be a multiple of 32
        const MIN_PRESET_SIZE = 512;  // presets smaller than this are hidden
        const RESET_SIZE = 512;
        const RATIO_MAX = 512;

        const clamp = (v, min, max) => Math.max(min, Math.min(max, v));
        const gcd = (a, b) => (b === 0 ? a : gcd(b, a % b));

        // 8..32 pass through, everything larger snaps onto the 32 grid
        const snapSize = (raw) => {
            const n = Math.round(Number(raw));
            if (!Number.isFinite(n)) {
                return MIN_SIZE;
            }
            const value = clamp(n, MIN_SIZE, MAX_SIZE);
            if (value <= FREE_MAX) {
                return value;
            }
            return clamp(Math.round(value / GRID) * GRID, GRID, MAX_SIZE);
        };

        const parsePreset = (text) => {
            const match = /^(\d+)\s*[x*×]\s*(\d+)$/i.exec(String(text).trim());
            if (!match) {
                return null;
            }
            const w = Number(match[1]);
            const h = Number(match[2]);
            if (!w || !h) {
                return null;
            }
            return { w, h };
        };

        const onConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function () {
            onConfigure?.apply(this, arguments);
            // widgets get their stored values after onNodeCreated, so re-apply
            // the size/ratio rules once the workflow values are in place
            setTimeout(() => this.__resolutionAndRatioSync?.(), 0);
        };

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            onNodeCreated?.apply(this, arguments);

            const getWidget = (name) => this.widgets?.find((w) => w.name === name);

            const wWidget = getWidget("width");
            const hWidget = getWidget("height");
            const rwWidget = getWidget("W_ratio");
            const rhWidget = getWidget("H_ratio");
            if (!wWidget || !hWidget || !rwWidget || !rhWidget) {
                return;
            }

            const scaleWidget = getWidget("scale_percent");
            const resetWidget = getWidget("reset");
            const swapWidget = getWidget("swap");
            const presetWidget = getWidget("preset");
            const customWidget = getWidget("custom_presets");

            // drag / arrow button increment; the frontend reads options.step2
            const setStep = (widget, step) => {
                if (!widget) {
                    return;
                }
                widget.options = widget.options || {};
                widget.options.step2 = step;
            };
            setStep(wWidget, GRID);
            setStep(hWidget, GRID);
            setStep(rwWidget, 1);
            setStep(rhWidget, 1);

            let baseWidth = snapSize(wWidget.value);
            let baseHeight = snapSize(hWidget.value);

            const markCustom = () => {
                if (presetWidget && presetWidget.value !== "Custom") {
                    presetWidget.value = "Custom";
                }
            };

            // W_ratio : H_ratio always mirror the current width : height
            const syncRatio = () => {
                const w = Math.max(1, Math.round(Number(wWidget.value) || 0));
                const h = Math.max(1, Math.round(Number(hWidget.value) || 0));
                const divisor = gcd(w, h);
                rwWidget.value = clamp(w / divisor, 1, RATIO_MAX);
                rhWidget.value = clamp(h / divisor, 1, RATIO_MAX);
            };

            const setSize = (w, h) => {
                wWidget.value = snapSize(w);
                hWidget.value = snapSize(h);
                baseWidth = wWidget.value;
                baseHeight = hWidget.value;
                if (scaleWidget) {
                    scaleWidget.value = 100;
                }
            };

            const onSizeEdited = (event) => {
                // while dragging the value is still moving, so only snap once the
                // pointer is released (drag callbacks carry a pointermove event)
                if (!/move/i.test(event?.type || "")) {
                    wWidget.value = snapSize(wWidget.value);
                    hWidget.value = snapSize(hWidget.value);
                }
                baseWidth = snapSize(wWidget.value);
                baseHeight = snapSize(hWidget.value);
                if (scaleWidget) {
                    scaleWidget.value = 100;
                }
                syncRatio();
                markCustom();
            };

            const wrapSizeCallback = (widget) => {
                const original = widget.callback;
                widget.callback = function (value, canvas, node, pos, event) {
                    const result = original?.apply(this, arguments);
                    onSizeEdited(event);
                    return result;
                };
            };
            wrapSizeCallback(wWidget);
            wrapSizeCallback(hWidget);

            rwWidget.callback = function () {
                const rw = Math.max(1, Number(rwWidget.value) || 1);
                const rh = Math.max(1, Number(rhWidget.value) || 1);
                const height = Number(hWidget.value) || MIN_SIZE;
                setSize((height / rh) * rw, height);
                syncRatio();
                markCustom();
            };

            rhWidget.callback = function () {
                const rw = Math.max(1, Number(rwWidget.value) || 1);
                const rh = Math.max(1, Number(rhWidget.value) || 1);
                const width = Number(wWidget.value) || MIN_SIZE;
                setSize(width, (width / rw) * rh);
                syncRatio();
                markCustom();
            };

            if (scaleWidget) {
                scaleWidget.callback = function () {
                    const percent = clamp(Number(scaleWidget.value) || 100, 10, 200);
                    wWidget.value = snapSize(baseWidth * percent / 100);
                    hWidget.value = snapSize(baseHeight * percent / 100);
                    syncRatio();
                    markCustom();
                };
            }

            if (resetWidget) {
                resetWidget.callback = function () {
                    setSize(RESET_SIZE, RESET_SIZE);
                    rwWidget.value = 1;
                    rhWidget.value = 1;
                    markCustom();
                    setTimeout(() => { resetWidget.value = false; }, 200);
                };
            }

            if (swapWidget) {
                swapWidget.callback = function () {
                    const width = wWidget.value;
                    wWidget.value = hWidget.value;
                    hWidget.value = width;

                    const ratioW = rwWidget.value;
                    rwWidget.value = rhWidget.value;
                    rhWidget.value = ratioW;

                    const base = baseWidth;
                    baseWidth = baseHeight;
                    baseHeight = base;

                    syncRatio();
                    markCustom();
                    setTimeout(() => { swapWidget.value = false; }, 200);
                };
            }

            const updatePresets = () => {
                if (!presetWidget) {
                    return;
                }
                const values = ["Custom"];
                const seen = new Set();
                String(customWidget?.value ?? "").split("\n").forEach((line) => {
                    const size = parsePreset(line);
                    if (!size) {
                        return;
                    }
                    if (size.w < MIN_PRESET_SIZE || size.h < MIN_PRESET_SIZE) {
                        return;
                    }
                    const label = `${size.w}x${size.h}`;
                    if (seen.has(label)) {
                        return;
                    }
                    seen.add(label);
                    values.push(label);
                });
                presetWidget.options = presetWidget.options || {};
                presetWidget.options.values = values;
                if (!values.includes(presetWidget.value)) {
                    presetWidget.value = "Custom";
                }
            };

            if (customWidget) {
                const original = customWidget.callback;
                customWidget.callback = function () {
                    const result = original?.apply(this, arguments);
                    updatePresets();
                    return result;
                };
            }

            if (presetWidget) {
                presetWidget.callback = function (value) {
                    const size = parsePreset(value);
                    if (!size) {
                        return;
                    }
                    setSize(size.w, size.h);
                    syncRatio();
                };
            }

            this.__resolutionAndRatioSync = () => {
                wWidget.value = snapSize(wWidget.value);
                hWidget.value = snapSize(hWidget.value);
                baseWidth = wWidget.value;
                baseHeight = hWidget.value;
                syncRatio();
                updatePresets();
                // a stored preset name only stays selected while it still matches
                const selected = parsePreset(presetWidget?.value);
                if (selected && (snapSize(selected.w) !== wWidget.value || snapSize(selected.h) !== hWidget.value)) {
                    presetWidget.value = "Custom";
                }
            };

            updatePresets();
            setTimeout(updatePresets, 100);
        };
    }
});
