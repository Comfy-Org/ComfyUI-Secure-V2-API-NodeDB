import { comfy } from '/comfy/api/v2.js';

import { createAspectLock, getAspectLockedDimensions } from './canvas/aspect_ratio_math.js';
import {
    applyAutoFit,
    applyCustomCalculation,
    applyScale,
    applySnap,
    calculationConfig,
    mergePresets,
} from './calculations/secure_calculations.js';
import { presetCategories } from './presets/preset_categories.js';


const TARGET = 'ResolutionMaster';
const STORAGE_KEY = 'ResolutionMaster/custom-presets-v2.json';
const CANVAS_WIDTH = 350;
const CANVAS_HEIGHT = 190;
const instances = new Map();

const keyFor = (node) => `${String(node.graphId ?? '')}:${String(node.id)}`;
const boundedInteger = (value, fallback = 1, minimum = 1, maximum = 32768) => {
    const parsed = Math.round(Number(value));
    return Number.isFinite(parsed)
        ? Math.max(minimum, Math.min(maximum, parsed))
        : fallback;
};
const boundedNumber = (value, fallback = 1, minimum = 0, maximum = 32768) => {
    const parsed = Number(value);
    return Number.isFinite(parsed)
        ? Math.max(minimum, Math.min(maximum, parsed))
        : fallback;
};

function widget(instance, name) {
    return instance.node.widgets.get(name);
}

function widgetValue(instance, name, fallback) {
    const value = widget(instance, name)?.getValue();
    return value === undefined || value === null ? fallback : value;
}

function setWidget(instance, name, value) {
    widget(instance, name)?.setValue(value);
}

function currentDimensions(instance) {
    return {
        width: boundedInteger(widgetValue(instance, 'width', 512), 512),
        height: boundedInteger(widgetValue(instance, 'height', 512), 512),
    };
}

function createElement(factory, tag, text = '') {
    const item = factory.createElement(tag);
    if (text) item.textContent = text;
    return item;
}

function styleControl(item) {
    item.style.boxSizing = 'border-box';
    item.style.minHeight = '28px';
    item.style.color = '#eeeeff';
    item.style.background = '#1b1b28';
    item.style.border = '1px solid #4a4a63';
    item.style.borderRadius = '5px';
    item.style.padding = '3px 6px';
}

function option(factory, value, label = value) {
    const item = createElement(factory, 'option', label);
    item.value = value;
    return item;
}

function labeledControl(factory, root, labelText, control) {
    const label = createElement(factory, 'label');
    label.style.display = 'grid';
    label.style.gap = '3px';
    label.style.fontSize = '11px';
    label.style.color = '#b9b9c9';
    const title = createElement(factory, 'span', labelText);
    label.appendChild(title);
    label.appendChild(control);
    root.appendChild(label);
    return control;
}

function makeSelect(factory, values) {
    const select = createElement(factory, 'select');
    styleControl(select);
    for (const value of values) select.appendChild(option(factory, value));
    return select;
}

function makeNumber(factory, value, minimum, maximum, step = 1) {
    const input = createElement(factory, 'input');
    input.type = 'number';
    input.value = String(value);
    input.min = String(minimum);
    input.max = String(maximum);
    input.step = String(step);
    styleControl(input);
    return input;
}

function makeButton(factory, label) {
    const button = createElement(factory, 'button', label);
    button.type = 'button';
    styleControl(button);
    button.style.cursor = 'pointer';
    return button;
}

function makeCheckbox(factory, labelText, checked) {
    const label = createElement(factory, 'label');
    label.style.display = 'flex';
    label.style.alignItems = 'center';
    label.style.gap = '5px';
    label.style.fontSize = '11px';
    const input = createElement(factory, 'input');
    input.type = 'checkbox';
    input.checked = Boolean(checked);
    label.appendChild(input);
    label.appendChild(createElement(factory, 'span', labelText));
    return { label, input };
}

function sanitizeCustomPresets(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
    const result = {};
    for (const [category, presets] of Object.entries(value).slice(0, 64)) {
        if (!presets || typeof presets !== 'object' || Array.isArray(presets)) continue;
        const clean = {};
        for (const [name, preset] of Object.entries(presets).slice(0, 256)) {
            if (!preset || typeof preset !== 'object') continue;
            const width = boundedInteger(preset.width, 0, 1);
            const height = boundedInteger(preset.height, 0, 1);
            if (width && height && String(name).length <= 128) {
                clean[String(name)] = { width, height };
            }
        }
        if (Object.keys(clean).length) result[String(category)] = clean;
    }
    return result;
}

async function loadCustomPresets() {
    try {
        const stored = await comfy.storage.get(STORAGE_KEY);
        return sanitizeCustomPresets(stored ? JSON.parse(stored) : {});
    } catch (_error) {
        return {};
    }
}

async function persistCustomPresets(instance) {
    await comfy.storage.set(
        STORAGE_KEY, JSON.stringify(instance.customPresets),
    );
}

function activePresets(instance) {
    return mergePresets(
        instance.category.value,
        presetCategories,
        instance.customPresets,
    );
}

function syncCalculationConfig(instance) {
    const category = instance.category.value;
    const presets = activePresets(instance);
    setWidget(instance, 'selected_category', category);
    setWidget(
        instance,
        'auto_detect_presets_json',
        calculationConfig(category, presets),
    );
}

function refreshPresetOptions(instance, wanted = '') {
    const factory = instance.container.ownerDocument;
    const presets = activePresets(instance);
    instance.preset.replaceChildren(option(factory, '', 'Choose preset…'));
    for (const [name, value] of Object.entries(presets)) {
        instance.preset.appendChild(option(
            factory,
            name,
            `${name} · ${value.width}×${value.height}`,
        ));
    }
    instance.preset.value = Object.hasOwn(presets, wanted) ? wanted : '';
    syncCalculationConfig(instance);
}

function updateScaleWidget(instance) {
    const mode = instance.scaleMode.value;
    setWidget(instance, 'rescale_mode', mode);
    if (mode === 'manual') {
        setWidget(
            instance, 'upscale_value',
            boundedNumber(instance.scaleValue.value, 1, 0, 100),
        );
    } else if (mode === 'megapixels') {
        setWidget(
            instance, 'target_megapixels',
            boundedNumber(instance.scaleValue.value, 2, 0, 1000),
        );
    } else {
        setWidget(
            instance, 'target_resolution',
            boundedInteger(instance.scaleValue.value, 1080, 1),
        );
    }
}

function syncScaleInput(instance) {
    const mode = instance.scaleMode.value;
    instance.scaleValue.value = String(
        mode === 'manual'
            ? widgetValue(instance, 'upscale_value', 1)
            : mode === 'megapixels'
                ? widgetValue(instance, 'target_megapixels', 2)
                : widgetValue(instance, 'target_resolution', 1080),
    );
}

function scaleProperties(instance) {
    return {
        rescaleMode: instance.scaleMode.value,
        upscaleValue: boundedNumber(
            widgetValue(instance, 'upscale_value', 1), 1, 0, 100,
        ),
        targetResolution: boundedInteger(
            widgetValue(instance, 'target_resolution', 1080), 1080, 1,
        ),
        targetMegapixels: boundedNumber(
            widgetValue(instance, 'target_megapixels', 2), 2, 0, 1000,
        ),
        preserveScalingRatio: Boolean(
            widgetValue(instance, 'preserve_scaling_ratio', false),
        ),
    };
}

function setDimensions(instance, width, height, reason = '') {
    const nextWidth = boundedInteger(width, 512);
    const nextHeight = boundedInteger(height, 512);
    setWidget(instance, 'width', nextWidth);
    setWidget(instance, 'height', nextHeight);
    instance.widthInput.value = String(nextWidth);
    instance.heightInput.value = String(nextHeight);
    const scaled = applyScale(nextWidth, nextHeight, scaleProperties(instance));
    setWidget(instance, 'rescale_value', scaled.factor);
    instance.status.textContent = reason
        ? `${reason}: ${nextWidth} × ${nextHeight}`
        : `${nextWidth} × ${nextHeight}`;
    draw(instance);
}

function draw(instance) {
    if (!instance.active || !instance.context) return;
    const { width, height } = currentDimensions(instance);
    const context = instance.context;
    context.clearRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);
    context.fillStyle = '#101018';
    context.fillRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);
    context.strokeStyle = '#26263a';
    context.lineWidth = 1;
    for (let index = 1; index < 8; index += 1) {
        const x = index * CANVAS_WIDTH / 8;
        const y = index * CANVAS_HEIGHT / 8;
        context.beginPath();
        context.moveTo(x, 0);
        context.lineTo(x, CANVAS_HEIGHT);
        context.moveTo(0, y);
        context.lineTo(CANVAS_WIDTH, y);
        context.stroke();
    }
    const scale = Math.min(
        (CANVAS_WIDTH - 42) / width,
        (CANVAS_HEIGHT - 48) / height,
    );
    const frameWidth = Math.max(2, width * scale);
    const frameHeight = Math.max(2, height * scale);
    const left = (CANVAS_WIDTH - frameWidth) / 2;
    const top = (CANVAS_HEIGHT - frameHeight) / 2 + 10;
    context.fillStyle = 'rgba(151, 105, 255, 0.20)';
    context.fillRect(left, top, frameWidth, frameHeight);
    context.strokeStyle = '#9769ff';
    context.lineWidth = 2;
    context.strokeRect(left, top, frameWidth, frameHeight);
    context.fillStyle = '#f2efff';
    context.font = '600 14px system-ui, sans-serif';
    context.textAlign = 'center';
    context.fillText(`${width} × ${height}`, CANVAS_WIDTH / 2, 20);
    context.fillStyle = '#9b99ab';
    context.font = '10px system-ui, sans-serif';
    context.fillText(
        'drag · Shift ratio · Ctrl 1px · Shift+Ctrl ratio 1px',
        CANVAS_WIDTH / 2,
        CANVAS_HEIGHT - 8,
    );
    context.textAlign = 'start';
}

function installCanvasInteraction(instance) {
    const canvas = instance.canvas;
    canvas.addEventListener('pointerdown', (event) => {
        const current = currentDimensions(instance);
        instance.dragging = true;
        instance.aspectLock = createAspectLock(current.width, current.height);
        canvas.style.cursor = 'crosshair';
        applyCanvasPointer(instance, event);
    });
    canvas.addEventListener('pointermove', (event) => {
        if (instance.dragging) applyCanvasPointer(instance, event);
    });
    const stop = () => {
        instance.dragging = false;
        instance.aspectLock = null;
        canvas.style.cursor = 'crosshair';
    };
    canvas.addEventListener('pointerup', stop);
    canvas.addEventListener('pointercancel', stop);
}

function applyCanvasPointer(instance, event) {
    const x = Math.max(0, Math.min(CANVAS_WIDTH, Number(event.offsetX)));
    const y = Math.max(0, Math.min(CANVAS_HEIGHT, Number(event.offsetY)));
    const current = currentDimensions(instance);
    const maximumWidth = Math.max(2048, current.width * 2);
    const maximumHeight = Math.max(2048, current.height * 2);
    let targetWidth = Math.max(1, Math.round(x / CANVAS_WIDTH * maximumWidth));
    let targetHeight = Math.max(
        1, Math.round((CANVAS_HEIGHT - y) / CANVAS_HEIGHT * maximumHeight),
    );
    const snap = boundedInteger(
        widgetValue(instance, 'snap_value', 64), 64, 1,
    );
    if (event.shiftKey && instance.aspectLock) {
        const props = {
            canvas_min_x: 1,
            canvas_min_y: 1,
            canvas_max_x: 32768,
            canvas_max_y: 32768,
            canvas_step_x: event.ctrlKey ? 1 : snap,
            canvas_step_y: event.ctrlKey ? 1 : snap,
        };
        const locked = getAspectLockedDimensions(
            targetWidth,
            targetHeight,
            props,
            instance.aspectLock,
            !event.ctrlKey,
        );
        targetWidth = locked.width;
        targetHeight = locked.height;
    } else if (!event.ctrlKey) {
        const snapped = applySnap(targetWidth, targetHeight, snap);
        targetWidth = snapped.width;
        targetHeight = snapped.height;
    }
    setDimensions(instance, targetWidth, targetHeight, 'Canvas');
}

function bindWidgetSubscriptions(instance) {
    for (const name of [
        'width', 'height', 'rescale_mode', 'upscale_value',
        'target_resolution', 'target_megapixels', 'preserve_scaling_ratio',
    ]) {
        const unsubscribe = widget(instance, name)?.on('change', () => {
            if (!instance.active) return;
            const dimensions = currentDimensions(instance);
            instance.widthInput.value = String(dimensions.width);
            instance.heightInput.value = String(dimensions.height);
            instance.scaleMode.value = String(
                widgetValue(instance, 'rescale_mode', 'resolution'),
            );
            syncScaleInput(instance);
            draw(instance);
        });
        if (typeof unsubscribe === 'function') {
            instance.unsubscribers.push(unsubscribe);
        }
    }
}

function destroy(instance) {
    if (!instance?.active) return;
    instance.active = false;
    for (const unsubscribe of instance.unsubscribers.splice(0)) unsubscribe();
    instance.container?.replaceChildren();
    instances.delete(instance.key);
}

async function createResolutionWidget(node) {
    const key = keyFor(node);
    destroy(instances.get(key));
    const customPresets = await loadCustomPresets();
    const instance = {
        key,
        node,
        customPresets,
        active: true,
        dragging: false,
        aspectLock: null,
        unsubscribers: [],
        container: null,
        canvas: null,
        context: null,
    };
    instances.set(key, instance);

    for (const item of node.widgets.all()) item.setHidden(true);
    node.widgets.mount({
        name: 'resolution_master_controls',
        height: 610,
        hideOnZoom: false,
        serialize: false,
        sendToPrompt: false,
        render(container) {
            instance.container = container;
            const factory = container.ownerDocument;
            container.style.width = '100%';
            container.style.height = '610px';
            container.style.overflow = 'hidden';
            const root = createElement(factory, 'section');
            root.style.display = 'grid';
            root.style.gap = '8px';
            root.style.padding = '6px';
            root.style.fontFamily = 'system-ui, sans-serif';
            root.style.color = '#f2efff';

            const canvas = createElement(factory, 'canvas');
            canvas.width = CANVAS_WIDTH;
            canvas.height = CANVAS_HEIGHT;
            canvas.style.width = '100%';
            canvas.style.height = `${CANVAS_HEIGHT}px`;
            canvas.style.display = 'block';
            canvas.style.cursor = 'crosshair';
            canvas.style.touchAction = 'none';
            root.appendChild(canvas);
            instance.canvas = canvas;
            instance.context = canvas.getContext('2d');
            if (!instance.context) throw new Error('2D canvas is unavailable');

            const primary = createElement(factory, 'div');
            primary.style.display = 'grid';
            primary.style.gridTemplateColumns = '1fr 1fr 1fr 1fr';
            primary.style.gap = '6px';
            instance.mode = labeledControl(
                factory,
                primary,
                'Mode',
                makeSelect(factory, [
                    'Manual', 'Manual Sliders',
                    'Common Resolutions', 'Aspect Ratios',
                ]),
            );
            instance.mode.value = String(widgetValue(instance, 'mode', 'Manual'));
            instance.latentType = labeledControl(
                factory,
                primary,
                'Latent',
                makeSelect(factory, ['latent_4x8', 'latent_128x16']),
            );
            instance.latentType.value = String(
                widgetValue(instance, 'latent_type', 'latent_4x8'),
            );
            instance.widthInput = labeledControl(
                factory,
                primary,
                'Width',
                makeNumber(factory, currentDimensions(instance).width, 1, 32768),
            );
            instance.heightInput = labeledControl(
                factory,
                primary,
                'Height',
                makeNumber(factory, currentDimensions(instance).height, 1, 32768),
            );
            root.appendChild(primary);

            const presets = createElement(factory, 'div');
            presets.style.display = 'grid';
            presets.style.gridTemplateColumns = '1fr 2fr';
            presets.style.gap = '6px';
            instance.category = labeledControl(
                factory,
                presets,
                'Category / model',
                makeSelect(factory, Object.keys(presetCategories)),
            );
            const selectedCategory = String(
                widgetValue(instance, 'selected_category', 'Standard'),
            );
            instance.category.value = Object.hasOwn(
                presetCategories, selectedCategory,
            ) ? selectedCategory : 'Standard';
            instance.preset = labeledControl(
                factory,
                presets,
                'Preset',
                makeSelect(factory, []),
            );
            root.appendChild(presets);

            const actions = createElement(factory, 'div');
            actions.style.display = 'grid';
            actions.style.gridTemplateColumns = 'repeat(4, 1fr)';
            actions.style.gap = '6px';
            const swap = makeButton(factory, 'Swap');
            const snap = makeButton(factory, 'Snap');
            const fit = makeButton(factory, 'Fit preset');
            const model = makeButton(factory, 'Model calc');
            for (const button of [swap, snap, fit, model]) actions.appendChild(button);
            root.appendChild(actions);

            const scaling = createElement(factory, 'div');
            scaling.style.display = 'grid';
            scaling.style.gridTemplateColumns = '1fr 1fr 1fr';
            scaling.style.gap = '6px';
            instance.scaleMode = labeledControl(
                factory,
                scaling,
                'Scale by',
                makeSelect(factory, ['resolution', 'manual', 'megapixels']),
            );
            instance.scaleMode.value = String(
                widgetValue(instance, 'rescale_mode', 'resolution'),
            );
            instance.scaleValue = labeledControl(
                factory,
                scaling,
                'Target / multiplier',
                makeNumber(factory, 1, 0, 32768, 0.1),
            );
            const applyScaling = makeButton(factory, 'Apply scale');
            applyScaling.style.alignSelf = 'end';
            scaling.appendChild(applyScaling);
            root.appendChild(scaling);

            const toggles = createElement(factory, 'div');
            toggles.style.display = 'grid';
            toggles.style.gridTemplateColumns = 'repeat(3, 1fr)';
            toggles.style.gap = '5px';
            const toggleDefinitions = [
                ['Auto-detect', 'auto_detect'],
                ['Auto fit', 'auto_fit_on_change'],
                ['Auto resize', 'auto_resize_on_change'],
                ['Auto snap', 'auto_snap_on_change'],
                ['Smart fit', 'smart_fit'],
                ['Model rules', 'use_custom_calc'],
                ['Preserve ratio', 'preserve_scaling_ratio'],
            ];
            instance.toggles = {};
            for (const [label, name] of toggleDefinitions) {
                const entry = makeCheckbox(
                    factory, label, Boolean(widgetValue(instance, name, false)),
                );
                toggles.appendChild(entry.label);
                instance.toggles[name] = entry.input;
                entry.input.addEventListener('change', () => {
                    setWidget(instance, name, Boolean(entry.input.checked));
                });
            }
            const snapInput = makeNumber(
                factory, widgetValue(instance, 'snap_value', 64), 1, 32768,
            );
            instance.snapInput = labeledControl(
                factory, toggles, 'Snap px', snapInput,
            );
            const batchInput = makeNumber(
                factory, widgetValue(instance, 'batch_size', 1), 1, 4096,
            );
            instance.batchInput = labeledControl(
                factory, toggles, 'Batch', batchInput,
            );
            root.appendChild(toggles);

            const custom = createElement(factory, 'div');
            custom.style.display = 'grid';
            custom.style.gridTemplateColumns = '2fr 1fr 1fr';
            custom.style.gap = '6px';
            instance.customName = createElement(factory, 'input');
            instance.customName.type = 'text';
            instance.customName.placeholder = 'Custom preset name';
            styleControl(instance.customName);
            const save = makeButton(factory, 'Save preset');
            const remove = makeButton(factory, 'Delete preset');
            custom.appendChild(instance.customName);
            custom.appendChild(save);
            custom.appendChild(remove);
            root.appendChild(custom);

            instance.status = createElement(factory, 'output');
            instance.status.style.fontSize = '11px';
            instance.status.style.color = '#bfb8dd';
            instance.status.textContent = 'Resolution Master ready';
            root.appendChild(instance.status);
            container.appendChild(root);

            instance.mode.addEventListener('change', () => {
                setWidget(instance, 'mode', instance.mode.value);
            });
            instance.latentType.addEventListener('change', () => {
                setWidget(instance, 'latent_type', instance.latentType.value);
            });
            const dimensionChange = () => setDimensions(
                instance, instance.widthInput.value, instance.heightInput.value,
                'Manual',
            );
            instance.widthInput.addEventListener('change', dimensionChange);
            instance.heightInput.addEventListener('change', dimensionChange);
            instance.category.addEventListener('change', () => {
                refreshPresetOptions(instance);
                instance.status.textContent = `${instance.category.value} presets`;
            });
            instance.preset.addEventListener('change', () => {
                const selected = activePresets(instance)[instance.preset.value];
                if (selected) setDimensions(
                    instance, selected.width, selected.height, instance.preset.value,
                );
            });
            swap.addEventListener('click', () => {
                const dimensions = currentDimensions(instance);
                setDimensions(instance, dimensions.height, dimensions.width, 'Swapped');
            });
            snap.addEventListener('click', () => {
                const dimensions = currentDimensions(instance);
                const result = applySnap(
                    dimensions.width,
                    dimensions.height,
                    boundedInteger(instance.snapInput.value, 64, 1),
                );
                setWidget(
                    instance, 'snap_value',
                    boundedInteger(instance.snapInput.value, 64, 1),
                );
                setDimensions(instance, result.width, result.height, 'Snapped');
            });
            fit.addEventListener('click', () => {
                const dimensions = currentDimensions(instance);
                const result = applyAutoFit(
                    dimensions.width,
                    dimensions.height,
                    activePresets(instance),
                    Boolean(instance.toggles.smart_fit.checked),
                    Boolean(instance.toggles.preserve_scaling_ratio.checked),
                );
                setDimensions(instance, result.width, result.height, 'Preset fit');
                instance.preset.value = result.selectedPreset || '';
            });
            model.addEventListener('click', () => {
                const dimensions = currentDimensions(instance);
                const result = applyCustomCalculation(
                    dimensions.width,
                    dimensions.height,
                    instance.category.value,
                    activePresets(instance),
                );
                setDimensions(instance, result.width, result.height, 'Model rule');
            });
            instance.scaleMode.addEventListener('change', () => {
                setWidget(instance, 'rescale_mode', instance.scaleMode.value);
                syncScaleInput(instance);
            });
            instance.scaleValue.addEventListener('change', () => {
                updateScaleWidget(instance);
                const dimensions = currentDimensions(instance);
                const result = applyScale(
                    dimensions.width, dimensions.height, scaleProperties(instance),
                );
                setWidget(instance, 'rescale_value', result.factor);
            });
            applyScaling.addEventListener('click', () => {
                updateScaleWidget(instance);
                const dimensions = currentDimensions(instance);
                const result = applyScale(
                    dimensions.width, dimensions.height, scaleProperties(instance),
                );
                setDimensions(instance, result.width, result.height, 'Scaled');
            });
            instance.snapInput.addEventListener('change', () => {
                setWidget(
                    instance, 'snap_value',
                    boundedInteger(instance.snapInput.value, 64, 1),
                );
            });
            instance.batchInput.addEventListener('change', () => {
                setWidget(
                    instance, 'batch_size',
                    boundedInteger(instance.batchInput.value, 1, 1, 4096),
                );
            });
            save.addEventListener('click', async () => {
                const name = String(instance.customName.value || '').trim();
                if (!name || name.length > 128) {
                    instance.status.textContent = 'Enter a preset name (1–128 chars)';
                    return;
                }
                const category = instance.category.value;
                instance.customPresets[category] = {
                    ...(instance.customPresets[category] || {}),
                    [name]: currentDimensions(instance),
                };
                await persistCustomPresets(instance);
                refreshPresetOptions(instance, name);
                instance.status.textContent = `Saved custom preset: ${name}`;
            });
            remove.addEventListener('click', async () => {
                const category = instance.category.value;
                const name = instance.preset.value;
                if (!Object.hasOwn(instance.customPresets[category] || {}, name)) {
                    instance.status.textContent = 'Select a custom preset to delete';
                    return;
                }
                delete instance.customPresets[category][name];
                if (!Object.keys(instance.customPresets[category]).length) {
                    delete instance.customPresets[category];
                }
                await persistCustomPresets(instance);
                refreshPresetOptions(instance);
                instance.status.textContent = `Deleted custom preset: ${name}`;
            });

            refreshPresetOptions(instance);
            syncScaleInput(instance);
            installCanvasInteraction(instance);
            draw(instance);
        },
        destroy() {
            destroy(instance);
        },
    });
    bindWidgetSubscriptions(instance);
    return instance;
}

function syncFromWidgets(instance) {
    if (!instance?.active) return;
    const dimensions = currentDimensions(instance);
    instance.widthInput.value = String(dimensions.width);
    instance.heightInput.value = String(dimensions.height);
    instance.mode.value = String(widgetValue(instance, 'mode', 'Manual'));
    instance.latentType.value = String(
        widgetValue(instance, 'latent_type', 'latent_4x8'),
    );
    instance.scaleMode.value = String(
        widgetValue(instance, 'rescale_mode', 'resolution'),
    );
    syncScaleInput(instance);
    draw(instance);
}

comfy.defs.extend(TARGET, (builder) => {
    builder.onCreated(async (node) => {
        const size = node.getSize();
        node.setSize({
            width: Math.max(Number(size.width), 390),
            height: Math.max(Number(size.height), 670),
        });
        node.setSizeConstraints({ minWidth: 390, minHeight: 670 });
        await createResolutionWidget(node);
    });
    builder.onConfigured((node) => {
        syncFromWidgets(instances.get(keyFor(node)));
    });
    builder.onConnectionsChanged((node, event) => {
        if (event.side !== 'input') return;
        if (event.name && event.name !== 'input_image') return;
        const instance = instances.get(keyFor(node));
        if (!instance) return;
        if (event.connected) {
            setWidget(instance, 'auto_detect_source', 'backend');
            instance.status.textContent = 'Input connected; backend shape detection armed';
        } else {
            setWidget(instance, 'auto_detect_source', 'frontend-empty');
            setWidget(instance, 'auto_detect_width', 0);
            setWidget(instance, 'auto_detect_height', 0);
            instance.status.textContent = 'Input disconnected';
        }
    });
    builder.onExecuted((node, result) => {
        const instance = instances.get(keyFor(node));
        if (!instance) return;
        const payload = result.raw?.resolution_master;
        if (!payload || typeof payload !== 'object') return;
        if (payload.source_empty) {
            setWidget(instance, 'auto_detect_source', 'frontend-empty');
            instance.status.textContent = 'Auto-detect source has no active selection';
            return;
        }
        if (Number(payload.detected_width) > 0 && Number(payload.detected_height) > 0) {
            setWidget(instance, 'auto_detect_source', 'frontend');
            setWidget(instance, 'auto_detect_width', Number(payload.detected_width));
            setWidget(instance, 'auto_detect_height', Number(payload.detected_height));
        }
        setWidget(instance, 'rescale_value', Number(payload.rescale_factor));
        setDimensions(instance, payload.width, payload.height, 'Executed');
    });
    builder.onRemoved((node) => destroy(instances.get(keyFor(node))));
});
