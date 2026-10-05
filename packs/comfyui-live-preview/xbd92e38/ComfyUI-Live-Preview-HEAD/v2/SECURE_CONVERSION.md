# Secure conversion report

Upstream: `https://github.com/TechnoWarrior2/comfyui-live-preview`

Pinned commit: `bd92e38cc9a8dfbf01bb1a434daac2d4b9f75504`

## Census

- Python nodes: 1 (`LivePreview`), supported 1, rejected 0, pending 0.
- Frontend extensions: 1 (`LivePreview`), supported 1, rejected 0, pending 0.
- Backend routes: 0.

## Authority and behavior

The Python node preserves opaque IMAGE reference identity and needs no capability. The frontend has only `ui.graph-overlay`; backend events, pack storage, graph queries, and the host action bar use the ordinary typed API.

The draggable and resizable preview, automatic first-frame display, explicit hide behavior, step/FPS/status display, aspect-fit rendering, geometry persistence, and resource cleanup are preserved. The floating legacy page button is represented by a host-owned action-bar button. Input outside the bounded header and resize grip passes through to the graph canvas.

Preview blobs are restricted to PNG, JPEG, or WebP, 32 MiB encoded size, 8192 pixels per dimension, and 64 megapixels. Geometry storage is bounded to 4 KiB. Stale frame decodes are discarded and every replaced bitmap is closed.

The upstream package declares MIT in `pyproject.toml` but does not ship a license file at this pin; this conversion records that fact and does not invent a missing file.

## Remaining gaps

None.
