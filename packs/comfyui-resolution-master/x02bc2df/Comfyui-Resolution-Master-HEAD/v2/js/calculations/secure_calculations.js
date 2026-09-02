import {
    CALCULATION_CONFIG_KEYS,
    CALCULATION_CONFIG_VERSION,
    getSerializableModelProfile,
    modelProfiles,
} from './model_profiles.js';
import { gcd } from '../canvas/aspect_ratio_math.js';
import {
    calculateScaleFactor,
    calculateScaledDimensions,
} from '../scaling/scaling_math.js';

const TOLERANCE = 0.01;
const number = (value, fallback = 0) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
};

export function mergePresets(category, builtIns, customStore) {
    return {
        ...(builtIns?.[category] || {}),
        ...(customStore?.[category] || {}),
    };
}

export function findClosestPreset(width, height, presets) {
    const safeWidth = Math.max(1, Math.round(number(width, 1)));
    const safeHeight = Math.max(1, Math.round(number(height, 1)));
    const inputAspect = safeWidth / safeHeight;
    const inputPixels = safeWidth * safeHeight;
    const candidates = [];
    for (const [name, preset] of Object.entries(presets || {})) {
        if (!preset || preset.isHidden) continue;
        const presetWidth = Math.round(number(preset.width));
        const presetHeight = Math.round(number(preset.height));
        if (!(presetWidth > 0 && presetHeight > 0)) continue;
        for (const [candidateWidth, candidateHeight, flipped] of [
            [presetWidth, presetHeight, false],
            [presetHeight, presetWidth, true],
        ]) {
            const presetPixels = candidateWidth * candidateHeight;
            candidates.push({
                name,
                width: candidateWidth,
                height: candidateHeight,
                aspectDiff: Math.abs(
                    inputAspect - candidateWidth / candidateHeight,
                ),
                pixelDiff: Math.abs(Math.log(inputPixels / presetPixels)),
                flipped,
            });
        }
    }
    if (!candidates.length) return null;
    const minimum = Math.min(...candidates.map((item) => item.aspectDiff));
    return candidates
        .filter((item) => item.aspectDiff <= minimum + TOLERANCE)
        .sort((left, right) => (
            left.pixelDiff - right.pixelDiff
            || left.aspectDiff - right.aspectDiff
            || Number(left.flipped) - Number(right.flipped)
        ))[0];
}

function closestAspectDimensions(width, height, preset) {
    const currentPixels = width * height;
    const aspect = preset.width / preset.height;
    const optionA = { width, height: Math.round(width / aspect) };
    const optionB = { width: Math.round(height * aspect), height };
    const difference = (item) => Math.abs(
        item.width * item.height - currentPixels,
    );
    return difference(optionA) <= difference(optionB) ? optionA : optionB;
}

function exactRatioDimensions(width, height, preset) {
    const divisor = gcd(preset.width, preset.height);
    const ratioWidth = preset.width / divisor;
    const ratioHeight = preset.height / divisor;
    const scale = Math.max(1, Math.round(Math.sqrt(
        width * height / (ratioWidth * ratioHeight),
    )));
    return { width: ratioWidth * scale, height: ratioHeight * scale };
}

export function applyAutoFit(
    width, height, presets, smartFit = false, preserveRatio = false,
) {
    const closest = findClosestPreset(width, height, presets);
    if (!closest) return { width, height, selectedPreset: null };
    if (!smartFit) {
        return {
            width: closest.width,
            height: closest.height,
            selectedPreset: closest.name,
        };
    }
    const fitted = preserveRatio
        ? exactRatioDimensions(width, height, closest)
        : Math.abs(width / height - closest.width / closest.height) < TOLERANCE
            ? { width, height }
            : closestAspectDimensions(width, height, closest);
    return { ...fitted, selectedPreset: closest.name };
}

function fluxLike(width, height, options) {
    const maxMegapixels = Math.max(0.001, number(options.max_megapixels, 4));
    const minimum = Math.max(1, Math.round(number(options.min_dimension, 320)));
    const maximum = Math.max(
        minimum, Math.round(number(options.max_dimension, 2560)),
    );
    const multiple = Math.max(1, Math.round(number(options.multiple, 32)));
    let resultWidth = Number(width);
    let resultHeight = Number(height);
    const megapixels = resultWidth * resultHeight / 1_000_000;
    if (megapixels > maxMegapixels) {
        const scale = Math.sqrt(maxMegapixels / megapixels);
        resultWidth *= scale;
        resultHeight *= scale;
    }
    const maximumDimension = Math.max(resultWidth, resultHeight);
    if (maximumDimension > maximum) {
        const scale = maximum / maximumDimension;
        resultWidth *= scale;
        resultHeight *= scale;
    }
    const minimumDimension = Math.min(resultWidth, resultHeight);
    if (minimumDimension < minimum) {
        const scale = minimum / minimumDimension;
        resultWidth *= scale;
        resultHeight *= scale;
    }
    return {
        width: Math.max(
            minimum,
            Math.min(maximum, Math.round(resultWidth / multiple) * multiple),
        ),
        height: Math.max(
            minimum,
            Math.min(maximum, Math.round(resultHeight / multiple) * multiple),
        ),
    };
}

function pixelRange(width, height, options, multiple = null) {
    const minimum = Math.max(1, Math.round(number(options.min_pixels, 589824)));
    const maximum = Math.max(
        minimum, Math.round(number(options.max_pixels, 4194304)),
    );
    const current = width * height;
    if (minimum <= current && current <= maximum) return { width, height };
    const target = current < minimum ? minimum : maximum;
    const aspect = width / height;
    const targetHeight = Math.sqrt(target / aspect);
    const targetWidth = targetHeight * aspect;
    if (multiple === null) {
        return {
            width: Math.round(targetWidth),
            height: Math.round(targetHeight),
        };
    }
    return {
        width: Math.max(multiple, Math.round(targetWidth / multiple) * multiple),
        height: Math.max(multiple, Math.round(targetHeight / multiple) * multiple),
    };
}

export function applyCustomCalculation(width, height, category, presets) {
    const profile = modelProfiles[category];
    if (!profile) return { width, height };
    const options = profile.options || {};
    if (profile.strategy === 'closest_preset') {
        const closest = findClosestPreset(width, height, presets);
        return closest
            ? { width: closest.width, height: closest.height }
            : { width, height };
    }
    if (profile.strategy === 'closest_aspect') {
        const closest = findClosestPreset(width, height, presets);
        if (!closest || Math.abs(
            width / height - closest.width / closest.height,
        ) < TOLERANCE) return { width, height };
        return closestAspectDimensions(width, height, closest);
    }
    if (profile.strategy === 'flux_like') {
        return fluxLike(width, height, options);
    }
    if (profile.strategy === 'wan_pixel_range') {
        return pixelRange(
            width, height, options,
            Math.max(1, Math.round(number(options.multiple, 16))),
        );
    }
    if (profile.strategy === 'pixel_range') {
        return pixelRange(width, height, options);
    }
    return { width, height };
}

export function applySnap(width, height, snapValue) {
    const snap = Math.max(1, Math.round(number(snapValue, 64)));
    return {
        width: Math.max(snap, Math.round(width / snap) * snap),
        height: Math.max(snap, Math.round(height / snap) * snap),
    };
}

export function applyScale(width, height, properties) {
    const factor = calculateScaleFactor(width, height, properties);
    return {
        ...calculateScaledDimensions(
            width, height, factor, Boolean(properties.preserveScalingRatio),
        ),
        factor,
    };
}

export function calculationConfig(category, presets) {
    return JSON.stringify({
        [CALCULATION_CONFIG_KEYS.version]: CALCULATION_CONFIG_VERSION,
        [CALCULATION_CONFIG_KEYS.profile]: getSerializableModelProfile(category),
        [CALCULATION_CONFIG_KEYS.presets]: presets,
    });
}

export function targetResolutionFromScale(width, height, scale) {
    const targetPixels = Math.max(1, width * height)
        * Math.max(0, number(scale)) ** 2;
    return Math.max(1, Math.round(Math.sqrt(targetPixels / (16 / 9))));
}
