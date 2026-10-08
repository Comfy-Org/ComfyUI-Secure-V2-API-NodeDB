import { comfy } from '/comfy/api/v2.js';
import { mountTrackRow } from './secureTrackFields.js';
import { checkedSegments, readCarrier, clearTrackData, populateTrackData } from './secureSpeakerState.js';

const states = new WeakMap();
const DURATION_KEY = 'tk_speaker_duration';
export function createSpeakerController(node, facade) {
    let alive = true, requestEpoch = 0, canvas, status, detectButton;
    const disposers = [];
    const stateWidget = node.widgets.get('track_state');
    const carrier = node.widgets.get('speaker_times');
    stateWidget?.setHidden(true);
    carrier?.setHidden(true);
    let segments = readCarrier(carrier?.getValue() ?? '');
    let duration = Number(node.getProperty(DURATION_KEY) ?? 0);
    const checkedDuration = value => {
        if (!Number.isFinite(value) || value < 0 || value > 10000)
            throw new RangeError('speaker timeline duration exceeds work bound');
        return value;
    };
    checkedDuration(duration);
    const changed = () => {
        if (!alive) return;
        stateWidget?.setValue('DataChange');
        node.setProperty('track_state', 'DataChange');
        node.setSerializeWidgets(true);
    };
    for (const widget of node.widgets.all()) {
        if (widget.name.startsWith('track_start_') || widget.name.startsWith('track_end_'))
            disposers.push(widget.on('change', changed));
    }
    for (let i = 1; i <= 7; i++) {
        const j = i + 7;
        mountTrackRow(node, `track_row_${i}`, [
            [`start_${i}`, `track_start_${i}`], [`end_${i}`, `track_end_${i}`],
            [`start_${j}`, `track_start_${j}`], [`end_${j}`, `track_end_${j}`],
        ], { speaker: true });
    }
    const applyDuration = value => {
        const next = checkedDuration(value);
        if (next > 0 && next !== duration) {
            duration = next;
            node.setProperty(DURATION_KEY, duration);
            canvas?.redraw();
        }
    };
    const receive = raw => {
        const admitted = checkedSegments(raw); // refuse before changing any widget
        carrier?.setValue(JSON.stringify(admitted));
        segments = populateTrackData(node, admitted, changed);
        canvas?.redraw();
    };
    const clear = () => {
        if (!alive) return;
        requestEpoch++;
        clearTrackData(node, changed);
        carrier?.setValue('[]');
        segments = [];
        if (detectButton) { detectButton.disabled = false; detectButton.textContent = 'DETECT SPEAKERS - LOAD GRAPH'; }
        canvas?.redraw();
    };
    const detect = async () => {
        if (!alive || detectButton?.disabled) return;
        const epoch = ++requestEpoch;
        // Pinned source resets first, even when the selected audio is absent.
        stateWidget?.setValue('DataUnchanged');
        const source = node.inputs.byName('fullaudio')?.source();
        const audio = source && facade.graph.node(source.nodeId)?.widgets.get('audio')?.getValue();
        if (typeof audio !== 'string' || !audio) {
            if (status) status.textContent = 'Please connect a Load Audio node and select an audio file.';
            return;
        }
        if (detectButton) { detectButton.textContent = 'Detecting...'; detectButton.disabled = true; }
        try {
            const threshold = node.widgets.get('silence_threshold')?.getValue() ?? 1;
            const response = await facade.backend.ownFetch('/tk/detect_speakers', {
                method: 'POST', body: JSON.stringify({ audio, silence_threshold: threshold }),
                headers: { 'Content-Type': 'application/json' },
            });
            const data = await response.json();
            if (!alive || epoch !== requestEpoch) return;
            if (!response.ok) throw Error(data?.error || 'speaker detection refused');
            if (data.speaker_times) {
                const admitted = checkedSegments(data.speaker_times);
                const newDuration = data.duration ? checkedDuration(Number(data.duration)) : duration;
                if (newDuration > 0) applyDuration(newDuration);
                receive(admitted); // source clear/populate deliberately ends DataChange
            }
            if (status) status.textContent = '';
        } catch (error) {
            if (alive && epoch === requestEpoch && status) status.textContent = String(error);
        } finally {
            if (alive && epoch === requestEpoch && detectButton) {
                detectButton.textContent = 'DETECT SPEAKERS - LOAD GRAPH';
                detectButton.disabled = false;
            }
        }
    };
    node.widgets.mount({
        name: 'footer_btns', height: 60, serialize: false, sendToPrompt: false,
        render(container) {
            const doc = container.ownerDocument;
            const labels = doc.createElement('div');
            labels.textContent = 'SPEAKER ONE                    SPEAKER TWO';
            container.append(labels);
            detectButton = doc.createElement('button');
            detectButton.textContent = 'DETECT SPEAKERS - FROM AUDIO FILE';
            const clearButton = doc.createElement('button');
            clearButton.textContent = 'Clear';
            status = doc.createElement('div');
            detectButton.addEventListener('click', detect);
            clearButton.addEventListener('click', clear);
            disposers.push(() => detectButton.removeEventListener('click', detect),
                () => clearButton.removeEventListener('click', clear));
            container.append(detectButton, clearButton, status);
        },
        destroy() { dispose(); },
    });
    canvas = node.widgets.canvas({
        name: 'speaker_timeline', height: 65, serialize: false, sendToPrompt: false,
        draw(ctx, [width]) {
            // Pinned source has no active pointer hit target; no new drag editor.
            const tx = 16, tw = width - 32, cy = 30;
            ctx.save();
            if (duration <= 0) {
                ctx.fillStyle = '#fff'; ctx.font = 'bold 14px sans-serif';
                ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
                ctx.fillText('-- MAKE SURE AUDIO FOLLOWS RULES --', tx + tw / 2, cy);
                ctx.restore(); return;
            }
            const timeToX = time => tx + (time / duration) * tw;
            ctx.beginPath(); ctx.roundRect(tx, cy - 3, tw, 6, 3);
            ctx.fillStyle = '#222'; ctx.fill();
            for (const seg of segments) {
                const x0 = timeToX(seg.start), x1 = timeToX(seg.end);
                ctx.beginPath(); ctx.roundRect(x0, cy - 9, Math.max(4, x1 - x0), 18, 2);
                ctx.fillStyle = seg.speaker === 1 ? '#2ecc71' : '#3498db';
                ctx.globalAlpha = .7; ctx.fill();
                ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
                ctx.lineWidth = 1; ctx.stroke();
            }
            ctx.globalAlpha = 1;
            const pxPerSec = tw / duration;
            for (let i = 0; i <= Math.floor(duration); i++) {
                const px = timeToX(i), five = i % 5 === 0;
                ctx.beginPath(); ctx.moveTo(px, cy + 4);
                ctx.lineTo(px, cy + 4 + (five ? 7 : 4));
                ctx.strokeStyle = five ? '#000' : '#000000'; ctx.lineWidth = five ? 1 : .5; ctx.stroke();
                if (five && i > 0 && i < duration && pxPerSec * 5 > 24) {
                    ctx.fillStyle = '#000'; ctx.font = '8px monospace';
                    ctx.textAlign = 'center'; ctx.textBaseline = 'top';
                    ctx.fillText(i + 's', px, cy + 13);
                }
            }
            ctx.restore();
        },
    });
    node.setSizeConstraints({ minHeight: 480, autoHeight: true });
    function dispose() {
        if (!alive) return;
        alive = false; requestEpoch++;
        for (const unsubscribe of disposers.splice(0)) unsubscribe();
    }
    return {
        detect, clear, dispose,
        executed(message) {
            if (!alive) return;
            if (message.duration !== undefined) {
                const raw = message.duration;
                applyDuration(parseFloat(Array.isArray(raw) ? raw[0] : raw));
            }
            if (message.speaker_times !== undefined) {
                const raw = message.speaker_times;
                let data = Array.isArray(raw) ? raw : [];
                if (data.length && Array.isArray(data[0])) data = data[0];
                const parsed = data.map(seg => ({
                    start: parseFloat(seg.start), end: parseFloat(seg.end), speaker: parseInt(seg.speaker),
                })).filter(seg => !isNaN(seg.start) && !isNaN(seg.end));
                receive(parsed);
                // Preserve source's second, unwrapped-only drawing assignment:
                // wrapped execution data populates controls but draws no blocks.
                segments = checkedSegments((Array.isArray(raw) ? raw : []).map(seg => ({
                    start: parseFloat(seg.start), end: parseFloat(seg.end), speaker: parseInt(seg.speaker),
                })).filter(seg => !isNaN(seg.start) && !isNaN(seg.end)));
                canvas.redraw();
            }
        },
        reconstructed() {
            if (!alive) return;
            segments = readCarrier(carrier?.getValue() ?? '');
            duration = checkedDuration(Number(node.getProperty(DURATION_KEY) ?? 0));
            canvas.redraw(); // Do not populate or reset restored manual widgets.
        },
    };
}
comfy.defs.extend('TKLocateSpeakersUsingSilenceBreaks', builder => {
    builder.onCreated(node => { states.set(node, createSpeakerController(node, comfy)); });
    builder.onConfigured(node => { states.get(node)?.reconstructed(); });
    builder.onExecuted((node, result) => { states.get(node)?.executed(result.raw); });
    builder.onRemoved(node => { states.get(node)?.dispose(); states.delete(node); });
});
// Active confined frontend graph; archival diagnostics are outside WEB_DIRECTORY.
