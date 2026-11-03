"""The empty LATENT that Sizes Pixaroma and Resolution Pixaroma hand out.

It is ComfyUI's own Empty Latent Image at the chosen size and batch size, so
wiring it is exactly the same as wiring width and height into that node. Core's
samplers (KSampler, SamplerCustomAdvanced) adapt an empty latent to the model
before the noise is made (comfy.sample.fix_empty_latent_channels), so the same
output works for SD 1.5, SDXL, SD3, Flux, Flux 2, Qwen Image and the other image
models.

The batch size comes from the node's hidden state (`batch`, set with the small
stepper beside the latent output; absent = 1, so a workflow saved before it
existed still makes one picture). js/shared/latent_batch.mjs clamps the same way.
"""

import json

BATCH_MIN = 1
BATCH_MAX = 64


def batch_of(state_json):
    """The batch size stored in a node's serialized state; anything unusable = 1."""
    try:
        state = json.loads(state_json)
        b = int(round(float(state.get("batch", 1))))
    except Exception:
        return 1
    return max(BATCH_MIN, min(BATCH_MAX, b))


def empty_latent(width, height, batch=1):
    w, h = int(width), int(height)
    b = max(BATCH_MIN, min(BATCH_MAX, int(batch)))
    try:
        # ComfyUI's top-level nodes.py (already loaded before any custom node),
        # NOT this pack's nodes/ folder, which is only ever imported relatively.
        # Calling core's node keeps the result identical on every ComfyUI
        # version, including the downscale key the samplers read.
        import nodes as core_nodes
        return core_nodes.EmptyLatentImage().generate(w, h, b)[0]
    except Exception:
        import torch
        import comfy.model_management as mm
        kw = {"device": mm.intermediate_device()}
        if hasattr(mm, "intermediate_dtype"):
            kw["dtype"] = mm.intermediate_dtype()
        return {"samples": torch.zeros([b, 4, h // 8, w // 8], **kw), "downscale_ratio_spacial": 8}
