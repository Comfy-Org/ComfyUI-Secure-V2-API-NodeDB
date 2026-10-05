# Secure Nodes V2 conversion

Upstream is pinned at `38da10b0d4655098d867c14af10093baa76a85c4`.

## Census

- Python nodes supported: 2/2 (`TextEncodeKrea2`, `Krea2SystemPrompt`)
- Frontend extensions supported: 1/1
- HTTP routes: 0
- Security-rejected or pending nodes: 0

## Boundary

The encoder materializes only declared image and mask refs under the `raw`
capability for bounded crop and area resize. Vision-aware tokenization and
conditioning encoding happen together on the trusted host through
`ClipRef.encode(images=..., llama_template=...)`; tensor-bearing token data
never crosses into the guest. The frontend uses typed slot handles to maintain
at most 16 image/mask pairs and does not access ambient canvas, DOM, graph, or
network authority.

The conversion preserves the pinned prompt templates, slot ordering, union-mask
crop, padding, no-upscale megapixel cap, multi-image labels, output schemas, and
the actionable FP8 vision-path error. There are no known behavior gaps.

Canonical contracts:

- `comfy-api.d.ts`: SHA-256 `bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f`
- `comfy-api.pyi`: SHA-256 `5c85bd4742059f3206d98c22aa79f44e445330a405cad1d7056bf33728ffca1b`
