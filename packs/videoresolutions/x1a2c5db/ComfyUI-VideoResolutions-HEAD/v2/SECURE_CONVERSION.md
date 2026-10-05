# Secure Nodes V2 conversion

Upstream: <https://github.com/HellerCommaA/ComfyUI-VideoResolutions>

Pinned commit: `1a2c5db1768dc0c1260082a5e5653dca9274786c`

Release: `x1a2c5db`

## Census

- Python nodes: 1 supported, 0 rejected, 0 pending.
- Frontend extensions: 0.
- Backend routes and settings: 0.

The conversion preserves the exact `HunyuanResolutions` ID, schema, ordered
preset catalogue, heading behavior, 16-pixel normalization, output names, and
legacy malformed-value errors.

## Security boundary

The node performs scalar string parsing only and declares no references,
permissions, dependencies, filesystem, network, subprocess, model, tensor,
UI, route, or ambient host authority.
