# Secure Nodes V2 conversion

Pinned upstream commit: `93efd354a002f9c6add7e948663cf459528242da`.

## Census

- Backend: 2 supported, 0 rejected, 0 pending.
- Frontend: 1 supported, 0 rejected, 0 pending.

## Boundary and behavior

The pack still owns the camera-angle classification, prompt construction,
camera geometry, translation glossary, and interactive camera visualization.
Both backend nodes run in the sandbox with typed SDK refs. The translation node
is pure. The camera node uses only the bounded `ui.preview_images` capability
when an optional IMAGE ref is connected; the broker returns temporary preview
metadata without exposing pixels, filesystem paths, or host objects.

The legacy frontend's Vue/Three implementation depended on ComfyUI globals,
the parent document, timers, and direct WebGL DOM access. Its V2 replacement
keeps the same angle/elevation/zoom interaction and visualization pack-side,
using the isolated definition lifecycle, widget handles, and a mounted remote
canvas from `/comfy/api/v2.js`. It has no parent DOM, same-origin access,
network API, legacy app object, or host prototype mutation.

The pack has no downloads, model weights, runtime dependency installation,
filesystem access, subprocesses, credentials, vendor calls, or hardware-bound
operations. No API, weight, dependency, credential, or intended-behavior gap
remains.
