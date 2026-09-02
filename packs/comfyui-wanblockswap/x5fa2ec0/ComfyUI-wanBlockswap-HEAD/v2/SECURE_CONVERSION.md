# ComfyUI-wanBlockswap Secure Nodes V2 conversion ledger

Source tuple: `comfyui-wanblockswap`,
`https://github.com/orssorbit/ComfyUI-wanBlockswap`,
`5fa2ec0fa55879fe43a33e762fff91fc2c553a67`, `x5fa2ec0`.

Exact source census: **1 backend node ID, 0 frontend registrations, 0 routes,
0 import-time side effects.** Upstream is 60 executable lines.

## Backend ledger

- `wanBlockSwap` — **supported**.

Backend tally: **1 supported, 0 pending, 0 security-rejected.**

## Frontend ledger

Upstream ships no `web/` or `js/` directory and declares no `WEB_DIRECTORY`.
The sealed manifest declares no web directory and no frontend permissions.

Frontend tally: 0 supported, 0 pending, 0 rejected.

## What changed and why

Upstream's node cloned the `ModelPatcher` and registered an `ON_LOAD` callback
that reached into the live model — `base_model.diffusion_model.blocks`,
`.text_embedding`, `.img_emb` — calling `.to(device)` on each module. A
sandboxed pack has no model object to reach into.

The reaching was never the useful part. The node's purpose is a **memory
policy**: keep the last N transformer blocks on the GPU and park the rest in
system RAM, so a 14B WAN video model fits on a consumer card. That policy is
now the `block_swap` host transform (**D34** in `docs/v2-api-decisions.md`):
the guest supplies only the four numbers the user chose, and core owns which
modules those numbers refer to.

Block swapping is not WAN-specific — it is how every large video model is run
on consumer hardware — so it is a generic transform with a host-side
architecture table, rather than a vendor-scoped surface. A new architecture is
a row in that table, not a pack change.

Node identity is unchanged: same `node_id`, display name, category, input
names, order, defaults, bounds, and tooltips.

## Two upstream behaviours, handled differently

- **Preserved.** Upstream's `if b > blocks_to_swap` offloads blocks `0..N`
  *inclusive* — one more than the label implies. Workflows are tuned against
  that, so the transform reproduces it exactly and
  `test_block_placement_matches_upstream` pins it at five boundary values.
- **Corrected.** Upstream hardcodes `torch.device('cuda')` as the resident
  device, raising outright on Apple Silicon and CPU-only hosts. The transform
  asks core for the active compute device. On CUDA the behaviour is identical.

Two upstream defects are additionally closed by the host boundary rather than
reproduced:

- A model that is not WAN21 left `unet` unbound and raised `UnboundLocalError`
  from inside the load callback. Core now refuses by name, naming the model
  type and the architectures it supports.
- `blocks_to_swap` above the model's block count is clamped, so asking a
  30-block 1.3B model to swap 40 offloads 30 instead of indexing past the end.

## Verification

`backend/tests/test_wanblockswap_pack_conversion.py` — 16 tests: exact census,
schema and sealed manifest; AST proof that the guest imports only
`comfy_api.latest` and touches none of the module-tree attributes upstream
walked; block-placement differential against the transcribed upstream loop at
five boundary values; the inclusive-boundary count; opt-in embedding offload
with non-blocking propagation; clamping; refusal of an unsupported
architecture; source-model immutability; parameter bounds and the bool-is-int
rejection; the architecture key pinned against the real `comfy.model_base.WAN21`;
real out-of-process guest execution; and distribution-pair reconstruction.
