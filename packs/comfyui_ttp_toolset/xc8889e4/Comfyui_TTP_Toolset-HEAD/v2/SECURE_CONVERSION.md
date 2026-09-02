# Secure Nodes V2 conversion ledger

- Pack: `comfyui_ttp_toolset`
- Upstream: `https://github.com/TTPlanetPig/Comfyui_TTP_Toolset`
- Commit: `c8889e40e90e293226cc6810c7d27b9c17300da6`
- Release key: `xc8889e4`
- Backend nodes converted: 28/28
- Supported backend nodes: 28
- Rejected nodes: 0
- Pending backend nodes: 0
- Frontend extensions converted: 1/1
- Supported frontend extensions: 1
- Rejected frontend extensions: 0
- Pending frontend extensions: 0

The pack retains its tiling, crop/layout, prompt construction, ordering,
blending, colour, loop, LTX frame-control, and TeaCache speed interpolation
algorithms. Pack-specific tensors use the bounded, permissioned raw tier.
Managed input assets and output persistence replace direct paths. Model, CLIP,
VAE, upscaler, sampler, noise, guider, sigma, and latent values remain opaque.

The conversion uses three basic reusable host capabilities rather than moving
node algorithms into core:

- generic text-conditioned image grounding on an official SAM3/SAM3.1 model;
- bounded sigma schedule step-count metadata;
- the canonical sampler service's EasyCache policy and optional denoised result.

The legacy transformer monkeypatch used by TeaCache is intentionally not
carried across the boundary. Its intended cache behavior is represented by the
canonical EasyCache sampling option while the pack owns its preset/custom-speed
mapping. QwenVL uses a host-owned, catalogue-selected SafeTensors text encoder;
the node performs no network access or execution-time download.

The frontend uses only `/comfy/api/v2.js`, mounted widgets, owner-document DOM,
node lifecycle hooks, backend URL construction, and the V2 queue facade. It has
no host prototype mutation, ambient page access, direct network access, or
backend event subscription.
