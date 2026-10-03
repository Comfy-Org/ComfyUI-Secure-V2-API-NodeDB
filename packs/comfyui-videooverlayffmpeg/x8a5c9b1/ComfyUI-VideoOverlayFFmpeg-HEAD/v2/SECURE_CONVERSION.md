# Secure Nodes V2 conversion

Upstream: `https://github.com/GuardSkill/ComfyUI-VideoOverlayFFmpeg`

Pinned commit: `8a5c9b193ae70c0f9ff5c32c38149703586a648c`

Release key: `x8a5c9b1`

SDK contract SHA-256: `7deb60a3226572754969eab9777ad2c2b990285f3a3fb922ad610fdbf1040d38`

## Census

The pinned release registers four Python nodes and one frontend extension. All
four Python nodes are supported:

- `VideoOverlayNode`
- `VideoOverlayWithSubtitlesNode`
- `Alignment2StringNode`
- `String2AlignmentNode`
- Converted frontend: `VideoOverlay.Preview`, as one V2 definition extension
  applied to the two video node types.

The 16 bundled TTF fonts are retained as pack resources. The upstream
`node.zip` and workflow PNG remain in the pristine tree but are not executable
V2 resources.

## Secure architecture

The upstream nodes accept arbitrary filesystem paths and directly construct
and run an FFmpeg filter graph. The V2 schemas retain the three input IDs but
replace path text boxes with managed input-video selectors. The guest resolves
those logical names to opaque `VideoRef` handles.

The frontend preview is a host-mounted widget. It does not monkey-patch node
prototypes, import the legacy app object, or access the parent window.

## Reusable host facility

`output.transcode_video()` cannot express the upstream operation, so this
conversion uses the bounded `output.compose_video()` service. It accepts three
opaque videos and typed fields for:

- masked scale/position/opacity overlay;
- independent 0.25–4.0 playback speeds and pad/loop duration policy;
- two 0.0–2.0 volume gains and audio mixing;
- optional timed text segments using a declared bundled font;
- fixed H.264/AAC MP4 output.

The service imposes encoded-size, duration, frame-count, dimensions,
subtitle-count and text-length limits; resolves pack font assets without
exposing paths; uses a host-configured FFmpeg binary; confines temporary and
output files; and rejects raw filters, arguments, protocols, paths and
subprocess handles. Subtitles are rendered into bounded transparent pack-font
cards by the trusted host, so support does not depend on FFmpeg's optional
`drawtext` build feature.

## Behavioral evidence

The focused conversion test runs both compositor nodes in a real isolated
guest. It creates three real H.264 inputs, exercises masked top-left overlay,
background looping, independent audio gains, duration matching, fixed H.264
and AAC output, a bundled-font timed subtitle, and output confinement. PyAV
verifies stream codecs, frame count, dimensions, audio presence, and red/blue
placement. A second real-guest check proves the custom alignment value crosses
the secure transport boundary. The frontend VM harness executes in an opaque
realm and proves both definitions mount a managed video preview with hover and
click playback controls.
