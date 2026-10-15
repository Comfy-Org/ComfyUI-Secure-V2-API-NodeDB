"""Test-only entrypoint copied into scratch, never registered in release."""
from comfy_api.latest import io, sdk
from .secure_vision_algorithms import encode_native_vision


class JackWanNativeVisionProbe(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='JackWanNativeVisionProbe', inputs=[
            io.Custom('CLIP_VISION').Input('clip_vision'), io.Image.Input('image_1'),
            io.Image.Input('image_2', optional=True), io.Image.Input('negative_image', optional=True),
            io.Custom('VISION_OPTIONS').Input('options')],
            outputs=[io.Custom('WANVIDIMAGE_CLIPEMBEDS').Output()])

    @classmethod
    async def execute(cls, clip_vision, image_1, options, image_2=None, negative_image=None):
        output = await encode_native_vision(clip_vision, image_1,
            image_2=image_2, negative_image=negative_image, **options)
        return io.NodeOutput({key:await sdk.TensorRef.from_value(value) if value is not None else None
            for key,value in output.items()})


class JackWanImageAdmissionProbe(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='JackWanImageAdmissionProbe', inputs=[
            io.Custom('CLIP_VISION').Input('clip_vision'), io.Image.Input('image')],
            outputs=[io.Int.Output()])

    @classmethod
    async def execute(cls, clip_vision, image):
        batch = await image.batch_size()
        await clip_vision.encode_image(image)
        return io.NodeOutput(batch)


NODE_CLASS_MAPPINGS = {'JackWanNativeVisionProbe': JackWanNativeVisionProbe,
    'JackWanImageAdmissionProbe': JackWanImageAdmissionProbe}
