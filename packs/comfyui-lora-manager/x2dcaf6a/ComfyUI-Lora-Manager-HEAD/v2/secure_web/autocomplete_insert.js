// Native autocomplete insertion math over actually observed producer data.
// This module does not fetch, authenticate, mount, intercept keys, or fabricate
// missing producer responses. The retained Loader entry remains unchanged.
function parseUsageTipNumber(value) {
    if (typeof value === 'number' && Number.isFinite(value)) {
        return value;
    }
    if (typeof value === 'string') {
        const parsed = parseFloat(value);
        if (Number.isFinite(parsed)) {
            return parsed;
        }
    }
    return null;
}

function splitRelativePath(relativePath = '') {
    const parts = relativePath.split(/[/\\]+/).filter(Boolean);
    const fileName = parts.pop() ?? '';
    return {
        directories: parts,
        fileName,
    };
}

function removeLoraExtension(fileName = '') {
    return fileName.replace(/\.(safetensors|ckpt|pt|bin)$/i, '');
}

export function createSyntaxSelection() {
    // Native cache transition rules, scoped to the owner that actually reads
    // settings. No host cache epoch/global module state is introduced.
    let cached = null;
    return {
        get() { return cached !== null ? cached : 'legacy'; },
        received(data) {
            if (data && data.success && data.settings) {
                cached = data.settings.lora_syntax_format || 'legacy';
                return;
            }
            if (cached === null) cached = 'legacy';
        },
        failed() { if (cached === null) cached = 'legacy'; }
    };
}

export function planLoraInsertion(relativePath, effectiveSyntaxFormat, data, appendComma) {
    // Inputs must come from a selected real producer. An omitted producer is
    // not treated as a native no-tip response or a default-strength success.
    if (arguments.length !== 4 || data === undefined) throw new Error('Actual insertion inputs required');
    const { directories, fileName } = splitRelativePath(relativePath);
    const baseName = removeLoraExtension(fileName);
    const folder = directories.length ? directories.join('/') + '/' : '';
    const loraName = folder + baseName;
    const resultName = effectiveSyntaxFormat === 'legacy' ? baseName : loraName;
    let strength = 1.0;
    let hasStrength = false;
    let clipStrength = null;
    try {
        if (data.success && data.usage_tips) {
            const usageTips = JSON.parse(data.usage_tips);
            const parsedStrength = parseUsageTipNumber(usageTips.strength);
            if (parsedStrength !== null) {
                strength = parsedStrength;
                hasStrength = true;
            }
            const clipSource = usageTips.clip_strength ?? usageTips.clipStrength;
            const parsedClipStrength = parseUsageTipNumber(clipSource);
            if (parsedClipStrength !== null) {
                clipStrength = parsedClipStrength;
                if (!hasStrength) strength = 1.0;
            }
        }
    } catch (parseError) {
        console.warn('Failed to parse usage tips JSON:', parseError);
    }
    const raw = clipStrength !== null
        ? `<lora:${resultName}:${strength}:${clipStrength}>`
        : `<lora:${resultName}:${strength}>`;
    const trimmed = raw.trim();
    if (!trimmed) return '';
    // Exact source comma behavior: comma with NO trailing space; its tooltip
    // says comma-space but that is not its implemented native algorithm.
    return appendComma ? `${trimmed},` : `${trimmed} `;
}
