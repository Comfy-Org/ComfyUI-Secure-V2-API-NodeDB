# Secure Nodes V2 mirror of ComfyUI_smZNodes.
#
# Upstream's __init__ did four things a guest cannot and must not do:
#
#   1. `subprocess.check_call([sys.executable, "-m", "pip", "install", ...])`
#      for `compel` and `lark`, followed by a walk of `sys.modules` calling
#      `importlib.reload` on every module it did not recognise. Dependencies
#      are declared in pyproject.toml and provisioned by the pack runtime; a
#      node pack never installs software, and reloading arbitrary live modules
#      is not recoverable.
#   2. `shutil.rmtree` / `shutil.copy` into ComfyUI's own `web/extensions`
#      directory, reaching two levels up out of the pack. The mirror DECLARES
#      `WEB_DIRECTORY` and the host serves it, confined to this pack.
#   3. `add_custom_samplers()`, which mutated the process-wide
#      `comfy.samplers.KSampler.SAMPLERS` list and bolted a sampler function
#      onto `comfy.k_diffusion.sampling`. Its pack-side recurrence is retained,
#      but a host-owned declarative sampler provider is still needed to expose
#      the name without letting the pack mutate a server-wide enum.
#   4. `register_hooks()`, which replaced seven core functions in place. See
#      smZNodes.py for the per-hook disposition.
#
# The node identities, categories and display names are upstream's, unchanged.

from .nodes import (
    NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS,
    comfy_entrypoint,
    smZNodesExtension,
)

WEB_DIRECTORY = "./web"

__all__ = [
    "NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY",
    "comfy_entrypoint", "smZNodesExtension",
]
