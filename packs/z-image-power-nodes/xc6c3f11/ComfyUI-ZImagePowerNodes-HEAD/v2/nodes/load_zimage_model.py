"""
File    : load_zimage_model.py
Purpose : Node to load a Z-Image/Z-Image-Turbo diffusion model.
Author  : Martin Rizzo | <martinrizzo@gmail.com>
Date    : Jul 22, 2026
Repo    : https://github.com/martin-rizzo/ComfyUI-ZImagePowerNodes
License : MIT
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
                          ComfyUI-ZImagePowerNodes
         ComfyUI nodes designed specifically for the "Z-Image" model.
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
"""
from comfy_api.latest import io, sdk
from .core.system import logger


class LoadZImageModel(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("assets", "models")
    xTITLE         = '⚗️🔬| Load Z-Image Model (safetensors / gguf)'
    xDESCRIPTION   = (
        "Load the Z-Image Diffusion Model in safetensors and GGUF format. Note that the 'ComfyUI-GGUF' custom nodes by city96 must be installed for GGUF files to be detected by this node.\n⚠️ Because this node is experimental, its parameters, behavior, or availability may change or be removed entirely without prior notice."
        )
    xCATEGORY      = '⚡Z-Image/__experimental'
    xCOMFY_NODE_ID = 'LoadZImageModel //ZImagePowerNodes'
    xDEPRECATED    = False

    #__ INPUT / OUTPUT ____________________________________
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            display_name   = cls.xTITLE,
            description    = cls.xDESCRIPTION,
            category       = cls.xCATEGORY,
            node_id        = cls.xCOMFY_NODE_ID,
            is_deprecated  = cls.xDEPRECATED,
            search_aliases = [
                "load model", "unet loader", "diffusion model loader", "z-image", "zimage", "gguf loader"
            ],
            inputs=[
                io.Combo.Input  ("checkpoint", options=[], remote=io.RemoteOptions(route='/models/diffusion_models', refresh_button=True),
                                 tooltip="The Z-Image generative diffusion model checkpoint."),
                io.Boolean.Input("file_filter", default=False, label_off="Show All Files", label_on="Z-Image Checkpoints Only",
                                 tooltip="If True, all available checkpoints will be listed, including those that may not be compatible."),
            ],
            outputs=[
                io.Model.Output(tooltip="The loaded Z-Image diffusion model."),
            ]
        )

    #__ FUNCTION __________________________________________
    @classmethod
    async def execute(cls, checkpoint: str, file_filter: bool = False):
        # file_filter changes catalogue presentation only in the native node.
        if checkpoint.upper().endswith(".GGUF"):
            output = await sdk.ctx().models.load_gguf_model(checkpoint)
        else:
            output = await sdk.ctx().models.load_diffusion_model(checkpoint)
        return io.NodeOutput(output)

    @classmethod
    def validate_inputs(cls, **kwargs):
        # Remote selection cannot be checked against an empty literal list;
        # the existing broker validates the logical catalogue name and file.
        return True
