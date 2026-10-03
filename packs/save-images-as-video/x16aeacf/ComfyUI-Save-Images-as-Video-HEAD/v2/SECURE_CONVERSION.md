# Secure Nodes V2 conversion

Upstream: `https://github.com/San4itos/ComfyUI-Save-Images-as-Video`

Pinned commit: `16aeacf0b7ed6824cce6b49c3468239bbcd067e0`

Release key: `x16aeacf`

SDK contract SHA-256: `7deb60a3226572754969eab9777ad2c2b990285f3a3fb922ad610fdbf1040d38`

## Census

All three upstream Python nodes are supported:

- `SaveFramesToVideoFFmpeg_san4itos`
- `ConvertVideoFFmpeg_san4itos`
- `LoadVideoByPath_san4itos`

The pack has no frontend extension.

## Secure architecture

The legacy pack locates an FFmpeg executable, creates temporary frame and audio
files, passes command-line arguments, and writes to host paths. The V2 pack has
none of those authorities.

- Image batches use `ctx.output.save_video()`.
- Existing videos use `ctx.output.transcode_video()`, a managed host job with
  closed container, codec, pixel-format, audio, bitrate, CRF, and preset values.
- Uploaded videos are resolved by logical input name and opened through
  `ctx.assets.load_video()` as opaque `VideoRef` handles.
- Output paths, input paths, the FFmpeg executable, process handles, and raw
  command arguments never enter the guest.

The legacy `output_file_opt` widget remains for workflow compatibility, but
secure mode accepts only `-preset <name>` from a closed preset vocabulary.
Arbitrary FFmpeg arguments are intentionally rejected because they would turn
a media broker into general process and filesystem authority.

## Behavioral evidence

The focused conversion test executes all three nodes in a real guest process.
It encodes image frames with audio, reloads the resulting video through the
managed input catalogue, transcodes it to VP9/WebM without audio, and remuxes
the original H.264/AAC streams into Matroska. PyAV verifies stream codecs,
frame count, frame dimensions, frame rate, audio presence/removal, metadata,
and output confinement. A negative test proves arbitrary FFmpeg options fail
before they reach the managed service.
