from comfy_api.latest import io, sdk

from ._saver import save_files
from ._catalogues import SAMPLERS, SCHEDULERS
from ._validation import validate_checkpoint_input, require_checkpoint


class SeedGenerator(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Seed_Generator_04cedd963306933ada265ea6',
            display_name='Seed Generator',
            category="ImageSaverTools/utils",
            inputs=[io.Int.Input('seed', default=0, min=0, max=0xffffffffffffffff)],
            outputs=[io.Int.Output()],
        )

    @classmethod
    def execute(cls, seed):
        return io.NodeOutput(seed)


class StringLiteral(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='String_Literal_5bb4d668d27398985246d1d5',
            display_name='String Literal',
            category="ImageSaverTools/utils",
            inputs=[io.String.Input('string', default="", multiline=True)],
            outputs=[io.String.Output()],
        )

    @classmethod
    def execute(cls, string):
        return io.NodeOutput(string)


class SizeLiteral(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Width_Height_Literal_5d88cd3d528e456d6aadd9fa',
            display_name='Width/Height Literal',
            category="ImageSaverTools/utils",
            inputs=[io.Int.Input('int', default=512, min=1, max=io.MAX_RESOLUTION, step=8)],
            outputs=[io.Int.Output()],
        )

    @classmethod
    def execute(cls, int):
        return io.NodeOutput(int)


class CfgLiteral(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Cfg_Literal_b9806fcd61fbfa9e078fef8e',
            display_name='Cfg Literal',
            category="ImageSaverTools/utils",
            inputs=[io.Float.Input('float', default=8.0, min=0.0, max=100.0)],
            outputs=[io.Float.Output()],
        )

    @classmethod
    def execute(cls, float):
        return io.NodeOutput(float)


class IntLiteral(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='Int_Literal_01c062f38ae3d7bd4a3894d2',
            display_name='Int Literal',
            category="ImageSaverTools/utils",
            inputs=[io.Int.Input('int', default=0, min=0, max=1000000)],
            outputs=[io.Int.Output()],
        )

    @classmethod
    def execute(cls, int):
        return io.NodeOutput(int)


class CheckpointSelector(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("assets",)

    @classmethod
    async def validate_inputs(cls, ckpt_name, input_types=None):
        return await validate_checkpoint_input(cls, "ckpt_name", ckpt_name, input_types)

    @classmethod
    def define_schema(cls):
        # The published frontend hydrates current choices. The narrow validator
        # above independently checks host catalogue membership at admission.
        # No remote route or static machine-specific checkpoint names are used.
        return io.Schema(
            node_id="Checkpoint_Selector_efcbbd2520fd995e676f4966",
            display_name="Checkpoint Selector", category="ImageSaverTools/utils",
            inputs=[io.Combo.Input("ckpt_name", options=[])],
            outputs=[io.Combo.Output(display_name="ckpt_name")],
        )

    @classmethod
    async def execute(cls, ckpt_name):
        await require_checkpoint(ckpt_name)
        return io.NodeOutput(ckpt_name)


class SamplerSelector(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Sampler_Selector_6652e5ab7bd841db459469db",
            display_name="Sampler Selector", category="ImageSaverTools/utils",
            inputs=[io.Combo.Input("sampler_name", options=SAMPLERS)],
            outputs=[io.Combo.Output(display_name="sampler_name", options=SAMPLERS)],
        )

    @classmethod
    def execute(cls, sampler_name):
        return io.NodeOutput(sampler_name)


class SchedulerSelector(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Scheduler_Selector_a46f37468d203a78b3568bbb",
            display_name="Scheduler Selector", category="ImageSaverTools/utils",
            inputs=[io.Combo.Input("scheduler", options=SCHEDULERS)],
            outputs=[io.Combo.Output(display_name="scheduler", options=SCHEDULERS)],
        )

    @classmethod
    def execute(cls, scheduler):
        return io.NodeOutput(scheduler)


class ImageSaveWithMetadata(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("assets", "output", "output.overwrite", "graph.metadata")

    @classmethod
    async def validate_inputs(cls, modelname, input_types=None):
        return await validate_checkpoint_input(cls, "modelname", modelname, input_types)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Save_Image_w_Metadata_6be3a4fb3d0e4c56fec9513e",
            display_name="Save Image w/Metadata", category="ImageSaverTools",
            is_output_node=True,
            inputs=[
                io.Image.Input("images"),
                io.String.Input("filename", default="%time_%seed", multiline=False),
                io.String.Input("path", default="", multiline=False),
                io.Combo.Input("extension", options=["png", "jpeg", "webp"]),
                io.Int.Input("steps", default=20, min=1, max=10000),
                io.Float.Input("cfg", default=8.0, min=0.0, max=100.0),
                io.Combo.Input("modelname", options=[]),
                io.Combo.Input("sampler_name", options=SAMPLERS),
                io.Combo.Input("scheduler", options=SCHEDULERS),
                io.String.Input("positive", default="unknown", multiline=True, optional=True),
                io.String.Input("negative", default="unknown", multiline=True, optional=True),
                io.Int.Input("seed_value", default=0, min=0, max=0xffffffffffffffff, optional=True),
                io.Int.Input("width", default=512, min=1, max=io.MAX_RESOLUTION, step=8, optional=True),
                io.Int.Input("height", default=512, min=1, max=io.MAX_RESOLUTION, step=8, optional=True),
                io.Boolean.Input("lossless_webp", default=True, optional=True),
                io.Int.Input("quality_jpeg_or_webp", default=100, min=1, max=100, optional=True),
                io.Int.Input("counter", default=0, min=0, max=0xffffffffffffffff, optional=True),
                io.String.Input("time_format", default="%Y-%m-%d-%H%M%S", multiline=False, optional=True),
            ], outputs=[],
        )

    @classmethod
    async def execute(cls, images, seed_value, steps, cfg, sampler_name, scheduler,
                      positive, negative, modelname, quality_jpeg_or_webp,
                      lossless_webp, width, height, counter, filename, path,
                      extension, time_format):
        await require_checkpoint(modelname)
        return io.NodeOutput(ui=await save_files(
            images, seed_value, steps, cfg, sampler_name, scheduler,
            positive, negative, modelname, quality_jpeg_or_webp,
            lossless_webp, width, height, counter, filename, path,
            extension, time_format))
