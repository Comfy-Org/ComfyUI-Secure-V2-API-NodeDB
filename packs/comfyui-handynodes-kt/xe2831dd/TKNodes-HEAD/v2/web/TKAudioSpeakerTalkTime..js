import { comfy } from '/comfy/api/v2.js';
import { mountTrackRow } from './secureTrackFields.js';

// extTKAudioSpeakerTalkTime: both renderers; no timers or prototype mutation.
comfy.defs.extend('TKAudioSpeakerTalkTime', builder => {
    builder.onCreated(node => {
        for (let i = 1; i <= 10; i++) {
            mountTrackRow(node, `track_row_${i}`, [
                [`start_${i}`, `track_start_${i}`],
                [`end_${i}`, `track_end_${i}`],
            ]);
        }
        node.setSizeConstraints({ autoHeight: true });
    });
});
// Active confined frontend graph; archival diagnostics are outside WEB_DIRECTORY.
