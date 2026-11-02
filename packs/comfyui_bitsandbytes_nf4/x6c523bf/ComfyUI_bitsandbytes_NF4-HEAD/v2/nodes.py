"""Secure Nodes V2 registration of ComfyUI_bitsandbytes_NF4 (pin 6c523bf1).

The pack has one node, CheckpointLoaderNF4. It loads a checkpoint whose linear
weights are stored as bitsandbytes 4-bit blocks (NF4 or FP4) and builds the
diffusion model with bitsandbytes 4-bit linear layers (pristine __init__.py,
lines 14-163, installed through model_options={"custom_operations": OPS} at
line 178). Those layers have to live inside the host's model loader, and on
the pinned SDK (comfy_api 0.37.0) the loader accepts only a closed set of
weight dtypes with no 4-bit option, so the node cannot load anything from a
sandboxed pack.

The node therefore stays registered with its original id, category, input and
outputs, so saved workflows still open, and it refuses when queued with a
named message. validate_inputs refuses at queue time, before any other node in
the prompt runs. execute raises the same message as a named error in case a
caller bypasses validation.
"""

from comfy_api.latest import io

PACK = "comfyui_bitsandbytes_nf4"
NODE_ID = "CheckpointLoaderNF4"

REFUSAL = (
    f"{PACK}/{NODE_ID} is not yet converted to Secure Nodes V2: it loads "
    "bitsandbytes NF4/FP4 (4-bit) checkpoints, which needs bitsandbytes 4-bit "
    "layers inside the host's model loader, and the Secure Nodes model loader "
    "has no 4-bit option yet. Use a GGUF or FP8 version of the model with the "
    "standard loaders instead."
)


class NF4LoaderUnavailableError(RuntimeError):
    """The host has no bitsandbytes 4-bit checkpoint loader."""


class CheckpointLoaderNF4(io.ComfyNode):
    # MODEL/CLIP/VAE outputs are host handles. The node calls no SDK
    # operation, so it requests no permissions.
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id=NODE_ID,
            # The original has no NODE_DISPLAY_NAME_MAPPINGS entry, so core
            # shows the id; stating it keeps /object_info identical.
            display_name=NODE_ID,
            category="loaders",
            inputs=[
                # Original: (folder_paths.get_filename_list("checkpoints"),).
                # The host fills this menu from the same checkpoints folder.
                io.Combo.Input(
                    "ckpt_name",
                    options=[],
                    remote=io.RemoteOptions(
                        route="/models/checkpoints", refresh_button=True),
                ),
            ],
            outputs=[
                io.Model.Output(display_name="MODEL"),
                io.Clip.Output(display_name="CLIP"),
                io.Vae.Output(display_name="VAE"),
            ],
        )

    @classmethod
    def validate_inputs(cls, ckpt_name):
        # Taking ckpt_name here also stops core from checking it against the
        # menu first, so the user sees this reason, not "value not in list".
        del ckpt_name
        return REFUSAL

    @classmethod
    async def execute(cls, ckpt_name):
        del ckpt_name
        raise NF4LoaderUnavailableError(REFUSAL)


NODE_CLASS_MAPPINGS = {
    NODE_ID: CheckpointLoaderNF4,
}

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "CheckpointLoaderNF4",
    "NF4LoaderUnavailableError",
    "REFUSAL",
]
