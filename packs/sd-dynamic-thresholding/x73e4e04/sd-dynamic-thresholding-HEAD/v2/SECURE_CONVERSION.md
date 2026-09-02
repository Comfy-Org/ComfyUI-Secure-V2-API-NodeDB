# Secure Nodes V2 conversion

Pinned upstream: `https://github.com/mcmonkeyprojects/sd-dynamic-thresholding`
at commit `73e4e04565aa86237d66764ac58ffae1f7e40e48`.

## Exact census and status

- Backend: **2 supported**, **0 rejected**, **0 pending** of 2 exact IDs.
- Frontend: **0 supported**, **0 rejected**, **0 pending** ComfyUI
  registrations. The pristine `javascript/active.js` belongs to the separate
  AUTOMATIC1111 integration and is not loaded by ComfyUI.
- Non-node ComfyUI behavior: **0 supported**, **0 rejected**, **0 pending**.

Both backend nodes are supported through the closed
`MODEL.patch("dynamic_thresholding", ...)` transform. It clones the host model,
projects each sampler sigma through the model sampling object's canonical
timestep mapping, and installs the pinned CFG transform without exposing the
ModelPatcher or sampler callback to the guest. The full node preserves all 12
mimic and CFG schedule modes, minimum scales, schedule value, per-channel or
global statistics, mean or zero scaling, AD or STD variability, and phi
interpolation. The simple node supplies the pinned constant-mode defaults.

Differential coverage proves all 12 x 12 schedule pairs across both scaling
startpoints, both variability measures, both feature-channel settings, and the
published timeline endpoints and interior points. This includes the pinned
`999 / 998` endpoint behavior and the equal-scale fast path.

## Boundary

The V2 node implementation imports only `comfy_api.latest`; the entrypoint also
uses `typing_extensions` for its override annotation. It does not import
`comfy`, `server`, `folder_paths`, host model classes, or arbitrary modules, and
it does not install global hooks. The A1111 `scripts/` and `javascript/`
entries and the obsolete Comfy UniPC helper remain in the pristine evidence
tree but are omitted from `v2/` because they are not part of either registered
ComfyUI node.
