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


def empty_latent(*args, **kwargs):
    raise RuntimeError("Use the Secure V2 node execution boundary")
