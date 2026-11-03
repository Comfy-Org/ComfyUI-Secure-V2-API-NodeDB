"""Krea2 Enhancer Pixaroma.

Makes a Krea 2 model follow the prompt more closely. Wire it between the model loader (and any LoRA loaders)
and the sampler. The math is in _krea2_enhancer_helpers (a port of ComfyUI-Krea2T-Enhancer by capitan01R,
MIT, whose author removed it in October 2026); this file only attaches it to the model.

It changes nothing on disk and never downloads anything: it adds a wrapper to a CLONE of the model, so the
model other nodes use is untouched.
"""
from ._krea2_enhancer_helpers import OPTION_KEY, STRENGTH_MAX, STRENGTH_MIN, WRAPPER_KEY, bounded_strength, \
    krea2_enhancer_wrapper


class Krea2EnhancerPixaroma:
    DESCRIPTION = (
        "Makes a Krea 2 model follow your prompt more closely. Put it between the model loader (and any LoRA "
        "loaders) and the sampler. Strength 0 does nothing; higher values push the model to keep more of the "
        "details you asked for. Our Krea 2 workflows use 0.1 to 0.5. It only works on "
        "Krea 2 models (any other model passes through unchanged), it changes nothing on disk and downloads "
        "nothing. Based on ComfyUI-Krea2T-Enhancer by capitan01R (MIT), whose author has removed it; the math "
        "is unchanged, so the images match the original node."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL", {
                    "tooltip": "The Krea 2 model, after any LoRA loaders. Any other model passes through unchanged.",
                }),
                "enabled": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Off = the model passes through untouched, so you can compare with and without.",
                }),
                "strength": ("FLOAT", {
                    "default": 0.5, "min": STRENGTH_MIN, "max": STRENGTH_MAX, "step": 0.05,
                    "tooltip": "How hard the model leans on the prompt. 0 = no change. Our workflows use 0.1 to 0.5. "
                               "High values can look overcooked or change logos and text.",
                }),
            },
        }

    RETURN_TYPES = ("MODEL",)
    RETURN_NAMES = ("model",)
    OUTPUT_TOOLTIPS = ("The model with the enhancer attached. Unchanged when it is off, at strength 0, or on a model "
                       "that is not Krea 2. Connect it to the sampler.",)
    FUNCTION = "apply"
    CATEGORY = "👑 Pixaroma/🧰 Utility"

    def apply(self, model, enabled=True, strength=0.5):
        import comfy.patcher_extension as pe   # at call time: a module-level import error would sink the whole pack

        patched = model.clone()
        to = patched.model_options.setdefault("transformer_options", {})
        to[OPTION_KEY] = {"enabled": bool(enabled), "strength": bounded_strength(strength)}
        # A clone copies its parent's wrappers, ours included when this node is chained twice: take it off first.
        if hasattr(patched, "remove_wrappers_with_key"):
            patched.remove_wrappers_with_key(pe.WrappersMP.DIFFUSION_MODEL, WRAPPER_KEY)
        to.get("wrappers", {}).get(pe.WrappersMP.DIFFUSION_MODEL, {}).pop(WRAPPER_KEY, None)
        patched.add_wrapper_with_key(pe.WrappersMP.DIFFUSION_MODEL, WRAPPER_KEY, krea2_enhancer_wrapper)
        return (patched,)


NODE_CLASS_MAPPINGS = {"Krea2EnhancerPixaroma": Krea2EnhancerPixaroma}
NODE_DISPLAY_NAME_MAPPINGS = {"Krea2EnhancerPixaroma": "Krea2 Enhancer Pixaroma"}
