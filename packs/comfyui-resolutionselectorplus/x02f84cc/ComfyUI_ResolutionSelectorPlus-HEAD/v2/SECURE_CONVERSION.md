# Secure Nodes V2 conversion

Upstream: `https://github.com/bradsec/ComfyUI_ResolutionSelectorPlus`

Pinned commit: `02f84ccb230a3dcbe1215556780799fd7484f847`

The conversion supports the one registered Python node and one frontend
extension. The model-specific preset tables, custom dimensions, multipliers,
batch controls, latent channel counts, dropdown filtering, saved values, and
output contracts are retained.

Empty latents are created through `LatentRef.empty`; no raw tensors or host
permissions are exposed. The optional custom output retains upstream's valid
8-by-8 disabled placeholder, represented by one latent cell. The frontend uses
typed widget and node handles and holds no ambient DOM, network, storage, or
backend authority.
