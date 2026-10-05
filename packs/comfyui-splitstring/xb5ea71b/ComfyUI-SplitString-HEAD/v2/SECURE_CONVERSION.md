# Secure Nodes V2 conversion

Upstream: <https://github.com/brayevalerien/ComfyUI-SplitString>

Pinned commit: `b5ea71bd43aca8ec9afe940782811d2b591c63dd`

Release: `xb5ea71b`

## Census

- Python nodes: 1 supported, 0 rejected, 0 pending.
- Frontend extensions: 0.
- Backend routes and settings: 0.

The conversion preserves the exact `Split String` ID, single STRING input,
twelve declared STRING outputs, double-newline splitting, twelve-part limit,
empty parts, Unicode, and the upstream variable-length result tuple.

## Security boundary

The node performs bounded Python string splitting only and declares no
references, permissions, dependencies, filesystem, network, subprocess,
model, tensor, UI, route, or ambient host authority.
