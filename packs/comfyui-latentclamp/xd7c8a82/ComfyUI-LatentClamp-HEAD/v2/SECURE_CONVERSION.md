# Secure conversion report

- Upstream: `https://github.com/SparknightLLC/ComfyUI-LatentClamp`
- Pinned commit: `d7c8a82d08328edfac2d944841a7ed4172b837fa`
- Python census: **1 supported, 0 rejected, 0 pending**
- Frontend census: **0 extensions, 0 JS-only nodes**
- Routes: **0**

`LatentClamp` preserves its node ID, display name, category, complete schema,
threshold and multiplier semantics, optional Gaussian noise, tensor
shape/device/dtype, and all non-sample latent metadata.

The tensor algorithm runs with only the bounded `raw` capability in the
isolated guest. It has no filesystem, network, model, storage, graph, backend,
or frontend authority. The upstream node intentionally has no seed input; its
Torch RNG use is therefore process-local and remains nondeterministic, while
guest isolation prevents it from mutating the host process RNG.

Additional rank, dimension, element-count, floating-dtype, and finite-number
checks fail closed before tensor operations.
