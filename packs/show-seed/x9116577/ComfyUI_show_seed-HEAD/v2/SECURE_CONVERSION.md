# Secure Nodes V2 conversion

Upstream: <https://github.com/dreamhartley/ComfyUI_show_seed>

Pinned commit: `9116577f49444ce33e9cd091da71d445dd12e1a9`

Release: `x9116577`

## Census

- Python nodes: 1 supported, 0 rejected, 0 pending.
- Frontend extensions: 0.
- Backend routes and settings: 0.

The conversion preserves the exact `Show Seed` node ID, IMAGE identity,
KSampler substring matching, first matching seed, tuple prompt handling, and
the `Seed not found` fallback.

## Security boundary

The IMAGE remains an opaque reference. The hidden prompt is inert workflow
data supplied by the host. The node declares no permissions and receives no
raw tensor, filesystem, network, subprocess, model, UI, or route authority.

The pinned upstream package declares a `LICENSE` file in `pyproject.toml` but
does not contain one. This conversion does not invent missing license text.
