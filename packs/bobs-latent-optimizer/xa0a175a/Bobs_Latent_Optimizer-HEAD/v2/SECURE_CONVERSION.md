# Secure conversion report

- Upstream: `https://github.com/BobsBlazed/Bobs_Latent_Optimizer`
- Pinned commit: `a0a175aed20bc9e42bdd03f99b9f6dcfd1ecbf40`
- Python census: **2 supported, 0 rejected, 0 pending**
- Frontend census: **0 extensions, 0 JS-only nodes**
- Routes: **0**

Both node IDs preserve their full schemas, model-family table, deterministic
sizing/tiling math, image versus video latent ranks, temporal compression, and
zero-filled LATENT output.

The nodes have only the standard `raw` tensor capability. Direct inputs are
bounded to the published schema, aspect-ratio strings are capped at 128
characters, and latent allocation fails closed above 268,435,456 elements.
