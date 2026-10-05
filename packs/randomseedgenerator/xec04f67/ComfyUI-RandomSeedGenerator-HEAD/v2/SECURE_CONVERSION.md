# Secure Nodes V2 conversion

Upstream: <https://github.com/Limbicnation/ComfyUI-RandomSeedGenerator>

Pinned commit: `ec04f6748e0aa57ea5165baa149188eedb5980b8`

Release: `xec04f67`

## Census

- Python nodes: 1 supported, 0 rejected, 0 pending.
- Frontend extensions: 0.
- Backend routes and settings: 0.

The conversion preserves fixed, random, increment, and decrement modes; the
shared counter; unsigned 64-bit wraparound; and the cache fingerprint contract.

## Security boundary

The node uses only Python's standard random and time modules in its isolated
guest. It declares no references, permissions, dependencies, filesystem,
network, subprocess, model, tensor, UI, route, or ambient host authority.
