from .nodes import EmptyLatentAspectByAxis, EmptyLatentAspectPreset

# Node IDs are referenced by users' saved workflows — never rename.
NODE_CLASS_MAPPINGS = {
    "CAS Empty Latent Aspect Ratio Preset": EmptyLatentAspectPreset,
    "CAS Empty Latent Aspect Ratio Axis": EmptyLatentAspectByAxis,
}

WEB_DIRECTORY = "web"

__all__ = ["NODE_CLASS_MAPPINGS", "WEB_DIRECTORY"]
