# Secure Nodes V2 conversion

Upstream is pinned at `2a440145a3b858a24192d6f7b2f0d48015928dee`.

## Census

- Python nodes: **2** (`PanoramaViewerNode`, `PanoramaVideoViewerNode`)
- Frontend extensions: **1** (`Pano.Viewer`)
- HTTP routes: **0**

The conversion preserves the still-image and ordered frame-batch viewers,
max-dimension Lanczos resizing, FPS playback, drag pan, wheel zoom, node resize,
and equirectangular projection. Backend pixels cross the boundary as managed
temporary preview images rather than unbounded base64 data URLs.

The legacy installer downloaded Three.js from a CDN at installation time. The
V2 viewer instead contains a small pack-owned WebGL renderer, so it has no CDN,
runtime network dependency, or ambient host DOM access. Pointer listeners and
animation frames are owned by the mounted widget and released on teardown.

Inputs are bounded to 8,192 pixels per dimension, 32 MiPixels per frame, 512
video frames, and 128 MiPixels across a video preview. Malformed dimensions,
frame counts, FPS, and max-width values fail closed. The pack requests only the
typed raw-image and temporary-UI-preview capabilities.
