# Secure conversion record

Upstream is pinned at `aa97baee8bacbe0dd702e419eb6c39505b631cc3`.

## Census

- Python nodes: 1 supported, 0 rejected, 0 pending.
- Frontend extensions: 0.
- Backend routes: 0.

## Behavior and authority

The conversion preserves deterministic embedding noise, both seed modes,
beginning/ending/all-step insertion, timestep ranges, prompt-end masking, null
token protection, pass-through modes, and metadata handling.

The node declares only `raw`, required to transform conditioning tensors in its
isolated guest. Conditioning rows, tensor sizes, tensor rank, metadata size,
numeric inputs, enums, and seeds are bounded. It has no file, network, model,
UI, subprocess, or host-process authority.

The legacy implementation resets Torch's process-global RNG. The conversion
uses a device-local generator, preserving its seeded tensor results without
changing random state observed by concurrent nodes.
