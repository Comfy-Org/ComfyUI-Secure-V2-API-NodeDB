# Aspect Ratio Presets — Secure Nodes V2

Upstream https://github.com/budihartono/comfyui-aspect-ratio-presets at
`1c2fa94b5053aa4b0bd99cebc1747a71a8e1f028` (`x1c2fa94`).
Census: 2 Python supported, 0 rejected, 0 pending; 1 frontend supported,
0 rejected, 0 pending; 0 routes and 0 JS-only nodes.

All ordered presets, model fallback, axis/ratio math, Python round semantics,
dimension validation, output names and schemas are preserved. Native channels
and stride are SD15/SDXL 4/8; Flux.1/Krea/Qwen-Image 16/8; Flux.2 128/16.
Pack code calls public `sdk.LatentRef.empty` without raw permission or host
imports. Device placement belongs to the runtime. The broker additionally tags
its native grid with canonical `downscale_ratio_spacial`; upstream returned only
`samples`. Samples, dimensions and values remain equivalent; the canonical
metadata prevents native-grid information from being lost downstream.

The one frontend model filter uses typed definition/lifecycle/widget hooks, not
prototype patches. It preserves valid current selections, replaces an invalid
selection with the first matching preset, restores state on configuration,
isolates documents/graphs/nodes, and unsubscribes on removal or reconfiguration.
No ambient DOM, global keyboard interception, backend routes or network access.

The SDK bounds allocations to 64 images, 16,384 dimensions and 16,777,216 latent
elements; booleans/noninteger batch or primary sizes fail closed before coercion.
Oversize legacy requests are intentionally rejected. Tests compare every preset
and native model, axis math and failure cases, real zero-capability guest paths,
frontend filtering/state/cleanup, exact census/schema/manifest/contracts and
pristine-to-V2 byte-exact patch reconstruction. GPU sampling is not exercised;
these nodes only construct zero latents and filter combo choices.

Validation command (from this pack-db worktree):
`PYTHONDONTWRITEBYTECODE=1 /Users/ben/comfy/ComfyUI/.venv/bin/python -m pytest -q packs/comfyui-aspect-ratio-presets/x1c2fa94/comfyui-aspect-ratio-presets-HEAD/v2/tests/test_aspect_presets_secure_conversion.py`

The complete 35-test gate includes all 51 ordered presets, 1,092 axis/model/
reference/size combinations (including matched failures), a 64-image allocation,
12 real guest node/model cases plus allocation denials, the opaque-realm
frontend differential harness, authoritative frontend typechecking, manifest/
license/stub checks, cache hygiene and byte-exact patch roundtrip.
