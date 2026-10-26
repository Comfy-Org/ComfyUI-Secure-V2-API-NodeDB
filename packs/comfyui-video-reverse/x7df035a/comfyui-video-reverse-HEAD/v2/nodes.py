from comfy_api.latest import io, sdk


class VideoReverseNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="VideoReverseNode",
            display_name="Video Reverse",
            category="SBCODE",
            inputs=[io.Image.Input("frames")],
            outputs=[io.Image.Output(display_name="frames")],
        )

    @classmethod
    async def execute(cls, frames):
        from ._upstream import VideoReverseNode as OriginalVideoReverseNode

        pixels = None if frames is None else await frames.raw()
        values = OriginalVideoReverseNode().reverse(pixels)
        if values[0] is pixels:
            return io.NodeOutput(frames)
        return io.NodeOutput(await sdk.ImageRef.from_value(values[0]))
