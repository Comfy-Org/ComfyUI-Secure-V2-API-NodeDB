"""
File    : load_qwen34b_model.py
Purpose : Node to load the text encoder model (Qwen-3-4B) for use with Z-Image.
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
from .core.system  import logger


class LoadQwen34bModel(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("assets", "models")
    xTITLE         = '⚗️🔬| Load Qwen3-4B Model (safetensors / gguf)'
    xDESCRIPTION   = (
        "Loads the Z-Image Text Encoder (Qwen3-4B) in safetensors or GGUF format. Note that the 'ComfyUI-GGUF' custom nodes by city96 must be installed for GGUF files to be detected by this node.\n⚠️ Because this node is experimental, its parameters, behavior, or availability may change or be removed entirely without prior notice."
        )
    xCATEGORY      = '⚡Z-Image/__experimental'
    xCOMFY_NODE_ID = 'LoadQwen34bModel //ZImagePowerNodes'
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
                "load clip", "clip loader", "text encoder loader", "qwen", "qwen3", "llm loader", "gguf loader", "z-image"
            ],
            inputs=[
                io.Combo.Input  ("checkpoint", options=[], remote=io.RemoteOptions(route='/models/text_encoders', refresh_button=True),
                                 tooltip="The text encoder checkpoint, typically a variant of Qwen3-4B model."),
                io.Boolean.Input("file_filter", default=False, label_off="Show All Files", label_on="Qwen3-4B Checkpoints Only",
                                 tooltip="If True, all available checkpoints will be listed, including those that may not be compatible."),
                io.Boolean.Input("run_on_gpu", default=True,
                                 tooltip="If enabled, the text encoder will be executed on the CPU rather than the GPU. "
                                         "This will consume less VRAM but will be significantly slower."),
            ],
            outputs=[
                io.Clip.Output(tooltip="The loaded text-encoder model for encoding text prompts."),
            ]
        )

    #__ FUNCTION __________________________________________
    @classmethod
    async def execute(cls, checkpoint: str, file_filter: bool = False, run_on_gpu: bool = False):
        if checkpoint.upper().endswith(".GGUF"):
            # Native City96 text loader ignores run_on_gpu in this branch.
            output = await sdk.ctx().models.load_gguf_text_encoders([checkpoint], "lumina2")
        else:
            device = "default" if run_on_gpu else "cpu"
            output = await sdk.ctx().models.load_text_encoder(checkpoint, "lumina2", device=device)
        return io.NodeOutput(output)

    @classmethod
    def validate_inputs(cls, **kwargs):
        return True
