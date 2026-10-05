# Secure Nodes V2 conversion

Upstream: `https://github.com/opj161/ComfyUI-Wan22ResolutionPresets`

Pinned commit: `170fb65d484ee5e4292e05d98ac543e0df49a86d`

## Census

- Python nodes: 2 (`Wan22ResolutionPresets`, `VideoResolutionSelector`)
- Frontend extensions: 1 (`Wan22.ResolutionPresets.Dynamic`)
- JavaScript-only nodes: 0
- backend routes: 0

Both Python nodes are converted. The dynamic resolution selector uses typed
widget handles to replace combo choices, tooltips, and invalid defaults. It no
longer patches node prototypes or widget callbacks and tears down every
listener when its node is removed.

The backend is authority-free: its resolution tables, parsing, fallback
behavior, and radial-attention calculations execute in the isolated guest.
The frontend uses no DOM, network, storage, backend, timers, or ambient graph
access. The legacy node intentionally receives no frontend augmentation, as in
the upstream extension.
