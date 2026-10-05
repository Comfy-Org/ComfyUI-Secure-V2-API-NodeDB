# Secure conversion record

Upstream is pinned at `f10579b4846ff3ff9701d88b37ea0a838ba30025`.

## Census

- Python nodes: 2 supported, 0 rejected, 0 pending.
- Frontend extensions: 0.
- Backend routes: 0.
- JavaScript-only nodes: 0.

The registered pack consists only of the camera-control and relighting prompt
generators. The bundled workflow and archive are inert assets and do not add
registered nodes, frontend extensions, routes, or runtime authority.

## Behavior and authority

`CameraControlPromptNode` preserves all horizontal, vertical, forward,
rotation, and special-view controls, including their order and exact bilingual
string composition. `RelightingPromptNode` preserves all ten directions, both
language modes, and the source's front-direction fallback for unexpected
values. Node IDs, display names, categories, input order, combo choices,
defaults, integer bounds and step, slider presentation, output type and output
name match the pinned source.

Both nodes are deterministic string composition and declare no permissions.
They have no model, tensor, file, network, subprocess, storage, UI, route, or
host-global authority.
