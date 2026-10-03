# Secure Nodes V2 conversion

Upstream: `https://github.com/bbaudio-2025/ComfyUI-FFmpeg-Video`

Pinned commit: `8f2575786b68882d9aca4dbb03c9178dddc95fb7`

Release key: `x8f25757`

SDK contract SHA-256: `7deb60a3226572754969eab9777ad2c2b990285f3a3fb922ad610fdbf1040d38`

## Census

All five upstream Python nodes are supported:

- `VideoConcat`
- `VideoAddAudio`
- `VideoExtractSegment`
- `VideoInfo`
- `VideoResize`

The pinned pack has no frontend entry point or extension registration.

## Secure architecture

The legacy implementation gives pack code host paths, process execution, the
FFmpeg executable, and unrestricted command construction. The V2 conversion
has none of those authorities.

- `VideoRef.encoded_source()` supplies bounded encoded bytes and trim metadata,
  never a source path.
- Decode, concatenation, crossfade, audio alignment, extraction, inspection,
  and resize algorithms remain pack-owned and run in the permissioned raw
  compute tier using PyAV and tensors.
- Final encoding is performed by `ctx.output.save_video()` using closed codec,
  pixel-format, CRF, preset, audio-codec, and bitrate values.
- Temporary encoded results are reopened through the managed asset catalogue
  and returned as opaque `VideoRef` handles.
- The legacy `audio_file` string now names an uploaded input asset. Arbitrary
  server filesystem paths are intentionally unavailable.

The conversion trades the upstream streaming FFmpeg filter graph for bounded
guest-side decode. This preserves node results but can use more memory; videos
over the secure decoded-pixel/frame limits fail closed instead of exhausting a
worker.

## Behavioral evidence

The focused pack test validates the exact census and schemas, exercises all
five nodes through the real guest/runtime boundary on generated media, checks
concat/crossfade, audio alignment, segment frame/audio lengths, technical
metadata, resize geometry, opaque VIDEO outputs, and host/guest PID separation.
It also confirms the pristine tree is unchanged and contains no frontend code.
