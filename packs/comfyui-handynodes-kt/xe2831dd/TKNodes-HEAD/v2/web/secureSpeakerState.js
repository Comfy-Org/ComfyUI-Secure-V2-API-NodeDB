// Existing STRING socket owns the complete ordered workflow auto carrier.
export const MAX_CARRIER_BYTES = 65536;
export const MAX_SEGMENTS = 4096;

export function checkedSegments(raw) {
    if (!Array.isArray(raw) || raw.length > MAX_SEGMENTS) throw new RangeError('speaker segment workload refused');
    const segments = raw.map(seg => {
        if (!seg || typeof seg !== 'object' || Array.isArray(seg)) throw new TypeError('invalid speaker segment');
        const start = parseFloat(seg.start), end = parseFloat(seg.end), speaker = parseInt(seg.speaker);
        if (![start, end, speaker].every(Number.isFinite)) throw new TypeError('speaker segment must be finite');
        return { start, end, speaker };
    });
    if (new TextEncoder().encode(JSON.stringify(segments)).length > MAX_CARRIER_BYTES) throw new RangeError('speaker carrier exceeds bounds');
    return segments;
}

export function readCarrier(value) {
    if (typeof value !== 'string') throw new TypeError('speaker carrier must be text');
    if (new TextEncoder().encode(value).length > MAX_CARRIER_BYTES) throw new RangeError('speaker carrier exceeds bounds');
    return value === '' ? [] : checkedSegments(JSON.parse(value));
}

export function clearTrackData(node, changed) {
    for (const widget of node.widgets.all()) {
        if (widget.name.startsWith('track_start_') || widget.name.startsWith('track_end_')) {
            widget.setValue(0);
            // Source callback fires even for zero->zero; public commit does not.
            // Retain the state transition explicitly, not a false activation.
            changed();
        }
    }
}

export function populateTrackData(node, segments, changed) {
    const admitted = checkedSegments(segments);
    clearTrackData(node, changed);
    const sorted = [...admitted].sort((a, b) => a.speaker !== b.speaker
        ? String(a.speaker).localeCompare(String(b.speaker)) : a.start - b.start);
    let currentSpeaker = null, currentCount = 0, columnOffset = 0;
    for (const seg of sorted) {
        if (currentSpeaker !== null && String(seg.speaker) !== String(currentSpeaker)) {
            columnOffset += 7;
            currentCount = 0;
            if (columnOffset >= 14) break;
        }
        currentSpeaker = seg.speaker;
        currentCount++;
        if (currentCount <= 7) {
            for (const [kind, value] of [['start', seg.start], ['end', seg.end]]) {
                const widget = node.widgets.get(`track_${kind}_${columnOffset + currentCount}`);
                if (widget) { widget.setValue(parseFloat(value || 0)); changed(); }
            }
        }
    }
    return admitted;
}
// Active confined frontend graph; archival diagnostics are outside WEB_DIRECTORY.
