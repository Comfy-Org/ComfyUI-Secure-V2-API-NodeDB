"""ATI canonical MODEL adapter using the public prompt-owned concat callback."""
from comfy_api.latest import io, sdk

from ._wan_ati_concat_math import prepare_ati_tracks
from ._wan_ati_concat_callback import ati_concat_callback


class WanVideoATI_comfy(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('models', 'closures')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoATI_comfy', display_name='WanVideo ATI Comfy',
            category='WanVideoWrapper', inputs=[
                io.Model.Input('model'),
                io.Int.Input('width', default=832, min=64, max=2048, step=8,
                    tooltip='Width of the image to encode'),
                io.Int.Input('height', default=480, min=64, max=29048, step=8,
                    tooltip='Height of the image to encode'),
                io.String.Input('tracks'),
                io.Float.Input('temperature', default=220.0, min=0.0, max=1000.0, step=0.1),
                io.Int.Input('topk', default=2, min=1, max=10, step=1)],
            outputs=[io.Model.Output(display_name='model')])

    @classmethod
    async def execute(cls, model: sdk.ModelRef, width: int, height: int, tracks: str,
                      temperature: float, topk: int):
        prepared_tracks = prepare_ati_tracks(tracks, width, height)

        async def callback(invocation: sdk.ModelConcatInvocation, noise,
                           metadata: sdk.ModelConcatMetadata):
            return await ati_concat_callback(invocation, noise, metadata,
                tracks=prepared_tracks, temperature=temperature, topk=topk)

        closure = await sdk.ctx().closures.retain('model_concat_conditioning', callback)
        model_clone = await sdk.ctx().closures.attach_model(closure, model)
        return io.NodeOutput(model_clone)


NODE_CLASS_MAPPINGS = {'WanVideoATI_comfy': WanVideoATI_comfy}
