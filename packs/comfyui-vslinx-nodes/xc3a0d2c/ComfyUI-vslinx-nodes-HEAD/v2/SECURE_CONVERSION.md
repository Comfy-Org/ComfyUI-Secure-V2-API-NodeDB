# Secure Nodes V2 conversion ledger

Source: `https://github.com/vslinx/ComfyUI-vslinx-nodes`  
Pinned commit: `c3a0d2c346b03d319b311ea634f256569753a68b`  
Release key: `xc3a0d2c`

This sibling is a complete Secure Nodes V2 pack. The pristine tree beside it
is byte-for-byte upstream. Only `__init__.py` is an entry point; it binds the
24 frozen schemas to `_secure_nodes.py`. Copied legacy modules that are not
imported by that entry point are inert distribution content.

## Terminal census

All 24 backend node IDs are supported. No backend intent is rejected.

- Pure pack-owned behavior: the four Boolean nodes, the three bypass/mute
  forwarding nodes, Group Bookmarks, Image to Pixel Art, multiline wildcard
  text, Fit Image Into BBox Mask, LoRA-token metadata formatting, Any/Pipe
  packing, image selection/name handling, and last-generated image decoding.
- Opaque host operations with pack-owned orchestration: upscale-by-factor,
  batched/tiled VAE decode, MultiDiffusion tiled high-resolution sampling,
  Anima LLLite per-tile and MultiDiffusion sampling, and Interactive Detailer.
- Interactive Detailer keeps detector recipes, segment ordering/filtering,
  masks, crop geometry, prompt handling, hook scheduling, compositing, and
  output formatting in the pack. It uses only typed detector/SAM/VAE/CLIP
  operations, brokered previews/interactions, sampling, and managed assets.
- Closed Impact `DETAILER_HOOK` recipes and the closed GITS scheduler recipe
  are interpreted as bounded data. Callback objects and arbitrary code are
  not accepted.

All nine frontend extension intents are supported. No frontend intent is
rejected.

- Anima tiled-VAE widget visibility uses V2 widget handles.
- Boolean flow/mode propagation uses V2 graph handles and disposes listeners.
- COMBO list compatibility is supplied natively by the V2 host. The legacy
  global `validate_node_input` monkeypatch and mutable HTTP toggle are absent.
- Group bookmarks uses the V2 sidebar, graph, property and dialog handles.
- Wildcard selection uses an authenticated backend catalogue and V2 widgets.
- Interactive Detailer uses the brokered secure interaction event/response.
- Last-output and selected-image previews use managed asset/upload endpoints
  and iframe-owned mounted DOM only.
- Model hover previews use `widgets.registerComboPreview` with the closed
  `adjacent-model-preview-v1` host policy; no pack URL or filesystem path is
  exposed.

## Behavior-level host facilities

The conversion uses small, composable host capabilities rather than moving
the nodes into core:

- `model.patch("spatial_tiled_evaluation", ...)` is an opaque per-evaluation
  crop/blend wrapper. Grid, sampling, VAE and stitch algorithms stay pack-side.
- `integrations.anima.apply_lllite(...)` is the vendor-specific, SafeTensors-
  only Anima seam. The pack chooses the tile/control image and preserves the
  wrapper; core validates model family/weights and applies the trusted patch.
- `widgets.registerComboPreview(...)` lets the host resolve adjacent preview
  media without granting arbitrary URLs or parent-DOM access.
- `vae.decode_tensor(...)` and its tiled variant perform only the bounded,
  host-owned decode without assuming RGB. MultiDiffusion keeps VAE-Utils'
  channel inspection, legacy range guard, exact `3*k^2` validation, and pixel
  shuffle in the pack. The host only supplies missing modern VAE defaults for
  legacy objects before encode/decode; it does not implement this node's
  upscale algorithm.
- The generic typed image/model/conditioning/VAE/SAM/detector/sample, managed
  asset, UI preview, and interaction facilities cover the remaining basic
  operations.

## Authority

- `raw`: bounded pack-side tensor/image algorithms and bounded managed-image
  bytes decoded by Pillow inside the sandbox.
- `sample`: explicit diffusion sampling.
- `assets`: managed input/output/controlnet asset resolution.
- `integrations.anima`: vendor-specific Anima LLLite application.
- `ui`: host-encoded managed previews.
- `ui.interact`: brokered Interactive Detailer request/response.

Every permissioned broker operation fails closed before performing its effect
when its capability is missing; capability errors are never treated as absent
or corrupt user assets. Anima model files must be relative `controlnet`
`.safetensors`/`.sft` assets. The vendor implementation additionally enforces
canonical Anima model and three-channel LLLite weight structure. Image paths
are normalized, bounded, suffix-checked managed asset names.

The pristine Interactive Detailer offers a `timeout_sec=0` indefinite wait and
values up to 24 hours. Secure execution deliberately rejects those unbounded
holds: interactive waits must be 1–540 seconds, matching the execution and
interaction broker limits. Its base-prompt, skip-detailing, and cancel policies
remain available for bounded timeouts.

## Verification

`backend/tests/test_vslinx_nodes_pack_conversion.py` proves the pristine
identity and exact 24/9 census, validates all schemas/permissions/stubs and the
sealed manifest, differentially exercises pack algorithms, runs every backend
ID through a real `GuestSession`, checks both Anima modes and Interactive
Detailer hook/scheduler behavior, proves normal and 12-channel upscale-VAE
decode (regular and tiled) with exact pack-side pixel shuffle, exercises
missing-capability and malformed-input denials, imports and operates all
frontend modules in a VM realm with no `window`, `document`, or `parent`,
proves the combo-preview bridge and absence of the old combo monkeypatch/route,
and verifies a byte-exact patch round trip.
