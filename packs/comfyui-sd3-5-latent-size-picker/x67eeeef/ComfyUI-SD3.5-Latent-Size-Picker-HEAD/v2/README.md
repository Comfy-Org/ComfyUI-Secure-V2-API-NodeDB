# SD3.5 and Flux Latent Size Pickers — Secure Nodes V2

The original `SD3_5EmptyLatent` and `FluxEmptyLatent` IDs, controls, preset order,
and output slots are preserved. SD3.5 floors dimensions to multiples of 64;
Flux rounds represented dimensions up to the selected latent cell size.

Both nodes use public `sdk.LatentRef.empty` with zero permissions. No Torch,
ComfyUI internals, raw tensors, model weights, filesystem, or network is needed.
The existing secure allocator permits batch 1–64 and at most 16,777,216 latent
elements. Legacy workflows retain the original batch widget schema (max 4096),
but excessive execution allocations are rejected before allocation.
