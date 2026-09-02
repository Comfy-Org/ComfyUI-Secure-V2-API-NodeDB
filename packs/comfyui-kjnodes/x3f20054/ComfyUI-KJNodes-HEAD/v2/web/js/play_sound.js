import { comfy } from '/comfy/api/v2.js';

// Handles hold no arbitrary properties, so the per-node playback state lives
// here and the entry is dropped in onRemoved.
const playback = new Map();

comfy.defs.extend("PlaySoundKJ", (b) => {
    b.onExecuted((node, output) => {
        const audios = output.raw.audio;
        if (!audios?.length) return;

        const modeWidget = node.widgets.get("mode");
        const volumeWidget = node.widgets.get("volume");
        const durationWidget = node.widgets.get("duration");
        const mode = modeWidget?.getValue() ?? "always";
        const volume = volumeWidget?.getValue() ?? 0.5;
        const duration = durationWidget?.getValue() ?? 0;

        const state = playback.get(node.id) ?? {};
        playback.set(node.id, state);

        // on_change: skip if audio content hasn't changed
        if (mode === "on_change") {
            const audioHash = output.raw.audio_hash?.[0];
            if (audioHash != null && state._kjLastAudioHash === audioHash) return;
            state._kjLastAudioHash = audioHash;
        }

        // Clean up previous state
        if (state._kjStatusListener) {
            state._kjStatusListener();
            state._kjStatusListener = null;
        }
        clearTimeout(state._kjQueueDebounce);
        state._kjPendingAudio = null;

        if (state._kjPlayingAudio) {
            state._kjPlayingAudio.pause();
            state._kjPlayingAudio = null;
        }
        if (state._kjPlayTimer != null) {
            clearTimeout(state._kjPlayTimer);
            state._kjPlayTimer = null;
        }

        const startPlayback = () => {
            const { filename, subfolder, type } = audios[0];
            const params = new URLSearchParams({
                filename: filename ?? "",
                subfolder: subfolder ?? "",
                type: type ?? "temp",
            });
            const url = comfy.backend.url(`/view?${params.toString()}`);
            const audio = new Audio(url);
            audio.volume = Math.max(0, Math.min(1, volume));
            audio.play().catch(() => {});
            state._kjPlayingAudio = audio;
            if (duration > 0) {
                state._kjPlayTimer = setTimeout(() => {
                    audio.pause();
                    state._kjPlayingAudio = null;
                    state._kjPlayTimer = null;
                }, duration * 1000);
            }
        };

        if (mode === "on_empty_queue") {
            state._kjPendingAudio = startPlayback;
            state._kjStatusListener = comfy.backend.on("status", (detail) => {
                const remaining = detail?.exec_info?.queue_remaining ?? 0;
                if (remaining === 0) {
                    // Debounce: confirm queue is truly empty
                    // (status can briefly show 0 between dispatches)
                    clearTimeout(state._kjQueueDebounce);
                    state._kjQueueDebounce = setTimeout(() => {
                        if (state._kjPendingAudio) {
                            state._kjPendingAudio();
                            state._kjPendingAudio = null;
                        }
                        state._kjStatusListener?.();
                        state._kjStatusListener = null;
                    }, 1000);
                } else {
                    clearTimeout(state._kjQueueDebounce);
                }
            });
        } else {
            startPlayback();
        }
    });

    b.onRemoved((node) => {
        playback.get(node.id)?._kjStatusListener?.();
        playback.delete(node.id);
    });
});
