# ComfyUI-Color-Matcher — Secure Nodes V2 conversion

Upstream is pinned at `d2c8e69387c01fb93c63028fe16d52554eeba1e4`.

## Census

- Python nodes: 1 registered, 1 supported, 0 rejected, 0 pending.
- Frontend extensions: 0.
- JavaScript-only nodes: 0.
- Backend routes: 0.

The converted node ID is `ColorMatch`.

## Authority and behavior

The pack retains its bounded NumPy/Torch and `color-matcher` computation inside
the isolated guest. It requests only the `raw` capability required for
value-mode IMAGE tensors. ComfyUI's progress-bar update was removed because it
does not affect node output and would otherwise require ambient host access.

The conversion preserves all six algorithms, first-frame reference selection,
full target-batch order, uint8 conversion/normalization semantics, output dtype
and shape, and direct malformed-input behavior within explicit secure resource
bounds. It has no network, filesystem, route, process, environment, frontend,
or arbitrary host authority.

