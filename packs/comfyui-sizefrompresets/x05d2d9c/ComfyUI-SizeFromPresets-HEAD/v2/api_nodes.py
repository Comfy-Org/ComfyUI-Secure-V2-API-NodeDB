"""Normal SDK schemas; all ten upstream purposes are retained.

The five latent nodes target an explicitly selected CPU-intermediate profile.
The trusted deployment must verify engine intermediate_device() == CPU before
adoption. Non-CPU profiles are unqualified. No schema batch range is clamped.
"""
from comfy_api.latest import io
from .nodes import node as sizes
from .nodes import random as randomized
from .nodes import similar_resolution as similar

class SizeFromPresetsSD15(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='SizeFromPresetsSD15', display_name='Size From Presets (SD1.5)',
            category='SizeFromPresets',
            inputs=[io.Combo.Input("preset", options=sizes.SizeFromPresetsSD15.SIZE_PRESETS_INPUT)],
            outputs=[io.Int.Output('w'), io.Int.Output('h')],
        )

    @classmethod
    def execute(cls, preset):
        return io.NodeOutput(*sizes.SizeFromPresetsSD15().get_size(preset))

class SizeFromPresetsSDXL(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='SizeFromPresetsSDXL', display_name='Size From Presets (SDXL)',
            category='SizeFromPresets',
            inputs=[io.Combo.Input("preset", options=sizes.SizeFromPresetsSDXL.SIZE_PRESETS_INPUT)],
            outputs=[io.Int.Output('w'), io.Int.Output('h')],
        )

    @classmethod
    def execute(cls, preset):
        return io.NodeOutput(*sizes.SizeFromPresetsSDXL().get_size(preset))

class EmptyLatentImageFromPresetsSD15(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='EmptyLatentImageFromPresetsSD15', display_name='Empty Latent Image From Presets (SD1.5)',
            category='SizeFromPresets',
            inputs=[io.Combo.Input("preset", options=sizes.EmptyLatentImageFromPresetsSD15.SIZE_PRESETS_INPUT), io.Int.Input("batch_size", default=1, min=1, max=4096)],
            outputs=[io.Latent.Output('latent'), io.Int.Output('w'), io.Int.Output('h')],
        )

    @classmethod
    async def execute(cls, preset, batch_size=1):
        return io.NodeOutput(*await sizes.EmptyLatentImageFromPresetsSD15().generate(preset, batch_size=batch_size))

class EmptyLatentImageFromPresetsSDXL(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='EmptyLatentImageFromPresetsSDXL', display_name='Empty Latent Image From Presets (SDXL)',
            category='SizeFromPresets',
            inputs=[io.Combo.Input("preset", options=sizes.EmptyLatentImageFromPresetsSDXL.SIZE_PRESETS_INPUT), io.Int.Input("batch_size", default=1, min=1, max=4096)],
            outputs=[io.Latent.Output('latent'), io.Int.Output('w'), io.Int.Output('h')],
        )

    @classmethod
    async def execute(cls, preset, batch_size=1):
        return io.NodeOutput(*await sizes.EmptyLatentImageFromPresetsSDXL().generate(preset, batch_size=batch_size))

class RandomSizeFromPresetsSD15(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='RandomSizeFromPresetsSD15', display_name='Random Size From Presets (SD1.5)',
            category='SizeFromPresets',
            inputs=[io.Int.Input("seed", default=0, min=0, max=0xffffffffffffffff)],
            outputs=[io.Int.Output('w'), io.Int.Output('h')],
        )

    @classmethod
    def execute(cls, seed):
        return io.NodeOutput(*randomized.RandomSizeFromPresetsSD15().get_size(seed))

class RandomSizeFromPresetsSDXL(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='RandomSizeFromPresetsSDXL', display_name='Random Size From Presets (SDXL)',
            category='SizeFromPresets',
            inputs=[io.Int.Input("seed", default=0, min=0, max=0xffffffffffffffff)],
            outputs=[io.Int.Output('w'), io.Int.Output('h')],
        )

    @classmethod
    def execute(cls, seed):
        return io.NodeOutput(*randomized.RandomSizeFromPresetsSDXL().get_size(seed))

class RandomEmptyLatentImageFromPresetsSD15(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='RandomEmptyLatentImageFromPresetsSD15', display_name='Random Empty Latent Image From Presets (SD1.5)',
            category='SizeFromPresets',
            inputs=[io.Int.Input("batch_size", default=1, min=1, max=4096), io.Int.Input("seed", default=0, min=0, max=0xffffffffffffffff)],
            outputs=[io.Latent.Output('latent'), io.Int.Output('w'), io.Int.Output('h')],
        )

    @classmethod
    async def execute(cls, seed, batch_size=1):
        return io.NodeOutput(*await randomized.RandomEmptyLatentImageFromPresetsSD15().generate(seed, batch_size=batch_size))

class RandomEmptyLatentImageFromPresetsSDXL(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='RandomEmptyLatentImageFromPresetsSDXL', display_name='Random Empty Latent Image From Presets (SDXL)',
            category='SizeFromPresets',
            inputs=[io.Int.Input("batch_size", default=1, min=1, max=4096), io.Int.Input("seed", default=0, min=0, max=0xffffffffffffffff)],
            outputs=[io.Latent.Output('latent'), io.Int.Output('w'), io.Int.Output('h')],
        )

    @classmethod
    async def execute(cls, seed, batch_size=1):
        return io.NodeOutput(*await randomized.RandomEmptyLatentImageFromPresetsSDXL().generate(seed, batch_size=batch_size))

class GetSimilarResolution(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='GetSimilarResolution', display_name='Get Similar Resolution',
            category='SizeFromPresets',
            inputs=[io.Image.Input("image"), io.Boolean.Input("is_sdxl", default=True)],
            outputs=[io.Int.Output('w'), io.Int.Output('h')],
        )

    @classmethod
    async def execute(cls, image, is_sdxl):
        return io.NodeOutput(*await similar.GetSimilarResolution().get_size(image, is_sdxl))

class GetSimilarResolutionEmptyLatent(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='GetSimilarResolutionEmptyLatent', display_name='Get Similar Resolution Empty Latent',
            category='SizeFromPresets',
            inputs=[io.Image.Input("image"), io.Boolean.Input("is_sdxl", default=True), io.Int.Input("batch_size", default=1, min=1, max=4096)],
            outputs=[io.Latent.Output('latent'), io.Int.Output('w'), io.Int.Output('h')],
        )

    @classmethod
    async def execute(cls, image, is_sdxl, batch_size):
        return io.NodeOutput(*await similar.GetSimilarResolutionEmptyLatent().get_size(image, is_sdxl, batch_size))

