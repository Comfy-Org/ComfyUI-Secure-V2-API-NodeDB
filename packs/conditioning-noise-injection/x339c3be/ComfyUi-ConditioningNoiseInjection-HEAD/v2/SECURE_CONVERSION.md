# Secure conversion record

Upstream is pinned at `339c3be4ffaa67a2807e86112a2143620d878b6f`.

## Census

- Python nodes: 1 supported, 0 rejected, 0 pending.
- Frontend extensions: 1 behavior migrated into the node, 0 rejected, 0 pending.
- Backend routes: 0.

## Behavior and authority

The conversion preserves seeded conditioning noise, batch expansion, threshold
splitting, prior schedule intersection, metadata, and cache fingerprints. The
legacy frontend globally replaced `api.queuePrompt` only to copy the first
active sampler's seed and latent batch size into hidden inputs. V2 obtains the
same bounded values from its brokered hidden prompt, so no frontend extension or
global queue mutation remains.

The tensor algorithm remains pack-owned and declares only `raw`. Conditioning
rows, metadata, rank, batch, total elements, prompt nodes, seeds, and numeric
parameters are bounded. A local CPU generator preserves upstream random values
without changing process-global RNG state. The pack has no file, network,
model, UI, subprocess, or host-process authority.

The pinned upstream project declares a LICENSE file that is absent from the
pinned repository. The conversion does not invent one.
