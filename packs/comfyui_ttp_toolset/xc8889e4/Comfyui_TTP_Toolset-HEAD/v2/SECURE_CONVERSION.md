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

## Dependency profile (NED profile r1): opencv-python-headless 4.11.0.86
- A production guest sees only its sealed lock, the pack's runtime base and its declared dependency profile, not
  Core's requirements; the guest bases have no OpenCV.
- `TTP_toolsets.py` imports cv2 at module level (line 6), and every row's module (`_secure_nodes`) imports
  `TTP_toolsets`, so without the profile none of the 28 rows loads. Nothing else outside the base is imported
  anywhere in v2, function-local imports included.
- `pyproject.toml` pins exactly `opencv-python-headless==4.11.0.86` (cp37-abi3 manylinux_2_17 x86_64; PyPI sha256
  0e0a27c19dd1f40ddff94976cfe43066fbbe9dfbb2ec1907d66c19caef42a57b) in place of the unpinned name. It needs only
  numpy, which is in the sealed lock.
- `secure-nodes.json` gains `runtime.dependencies.profile_sha256` when the profile is built.
- `tests/test_dependency_profile.py` lets cv2, and the other modules the guest bases lack, come only from the pinned
  copy under /deps; its guest cases run TTPlanet_Tile_Preprocessor_Simple (cv2.resize, cv2.GaussianBlur) against
  the pristine upstream node.
