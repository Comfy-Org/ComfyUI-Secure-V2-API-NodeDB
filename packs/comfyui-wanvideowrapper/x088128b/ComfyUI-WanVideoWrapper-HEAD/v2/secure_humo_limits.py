"""Pack-owned HuMo boundary/workspace accounting; does not execute a model.

The default video lives inside the guest. It is not a graph-edge buffer.
Model/allocator peak must additionally be admitted and measured by the host.
"""
import math

MAX_BOUNDARY_BYTES = 64 * 1024**2
MAX_EXPLICIT_WORK_BYTES = 2 * 1024**3
MAX_FRAMES = 81
MAX_EDGE = 832
MAX_PIXELS = 832 * 480
MAX_REFERENCES = 4
MAX_AUDIO_SAMPLES_16K = 30 * 16000


def projected_humo_bytes(num_frames, width, height, reference_count=0,
                         audio_samples=None, audio_sample_rate=None,
                         vae_precision='fp32', whisper_precision='fp32'):
    """Return exact public shapes and conservative explicit temporary bytes.

All dimensions are scalar metadata. This function never allocates a tensor.
The audio upper bound keeps the entire original audio output, including when
it is longer than the requested video. Native 30-second feature padding and
33 retained hidden states are accounted independently from the video length.
"""
    if not all(type(value) is int for value in (num_frames, width, height, reference_count)):
        return None
    if audio_samples is not None:
        if (type(audio_samples) is not int or type(audio_sample_rate) is not int
                or audio_samples < 0 or audio_sample_rate <= 0):
            return None
        resampled = (audio_samples * 16000 + audio_sample_rate - 1) // audio_sample_rate
        audio_frames = resampled // 640
        if resampled > MAX_AUDIO_SAMPLES_16K:
            raise ValueError('HuMo audio exceeds the bounded 30 second domain')
    else:
        resampled = 0
        audio_frames = num_frames
    frames = audio_frames if num_frames == -1 else num_frames
    frames = 4 * ((frames - 1) // 4) + 1
    # Preserve native validation/error paths for non-positive dimensions.
    if min(frames, width, height) <= 0 or reference_count < 0:
        return None
    if frames > MAX_FRAMES:
        raise ValueError('HuMo exceeds the bounded 81 frame domain')
    if max(width, height) > MAX_EDGE or width * height > MAX_PIXELS:
        raise ValueError('HuMo exceeds the bounded 832 by 480 pixel area')
    if reference_count > MAX_REFERENCES:
        raise ValueError('HuMo exceeds the bounded four reference image domain')
    vae_size = 2 if vae_precision in ('bf16', 'fp16') else 4
    whisper_size = 2 if whisper_precision in ('bf16', 'fp16') else 4
    latent_frames = (frames - 1) // 4 + 1 + reference_count
    lh, lw = height // 8, width // 8
    # Original full VAE encoder returns float32 even for half precision VAE.
    condition_bytes = 2 * 20 * latent_frames * lh * lw * 4
    audio_bytes = 2 * max(0, audio_frames) * 5 * 1280 * 4
    boundary_bytes = condition_bytes + audio_bytes
    if boundary_bytes > MAX_BOUNDARY_BYTES:
        raise ValueError('HuMo published conditioning exceeds 64 MiB')
    zero_bytes = 3 * (frames + 4 * reference_count) * height * width * vae_size
    reference_bytes = 3 * reference_count * height * width * 4 * 3
    latent_and_mask_bytes = (16 * 4 + 4 * vae_size) * latent_frames * lh * lw
    # Original extraction pads one <=30 s audio window to 3000 mel frames.
    # Tuple, stacked list, concatenation and retained block intermediates can
    # coexist; account four complete hidden-state stacks without changing them.
    hidden_bytes = 4 * 33 * 1500 * 1280 * whisper_size if audio_samples is not None else 0
    mel_bytes = 3 * 128 * 3000 * 4 if audio_samples is not None else 0
    work_bytes = zero_bytes + reference_bytes + latent_and_mask_bytes + 3 * boundary_bytes + hidden_bytes + mel_bytes
    if work_bytes > MAX_EXPLICIT_WORK_BYTES:
        raise ValueError('HuMo explicit temporary tensors exceed 2 GiB')
    return {'frames': frames, 'latent_frames': latent_frames, 'audio_frames': audio_frames,
        'resampled_audio_samples': resampled, 'condition_bytes': condition_bytes,
        'audio_fp32_upper_bytes': audio_bytes, 'boundary_bytes': boundary_bytes,
        'zero_frames_bytes': zero_bytes, 'reference_workspace_bytes': reference_bytes,
        'retained_audio_hidden_upper_bytes': hidden_bytes,
        'explicit_work_bytes': work_bytes,
        'model_and_backend_activation_bytes_excluded': True}
