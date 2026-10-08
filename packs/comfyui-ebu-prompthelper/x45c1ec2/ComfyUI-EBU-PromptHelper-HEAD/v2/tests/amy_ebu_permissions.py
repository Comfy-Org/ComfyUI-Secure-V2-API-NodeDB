from comfy_api.latest import io,sdk
import time
class ClockProbe(io.ComfyNode):
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='ClockProbe',outputs=[io.Int.Output()])
    @classmethod
    def execute(cls):
        return io.NodeOutput(int(time.localtime().tm_gmtoff))
class AssetProbe(io.ComfyNode):
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='AssetProbe',outputs=[])
    @classmethod
    async def execute(cls):
        await sdk.ctx().assets.list('input')
        return io.NodeOutput()
class RawProbe(io.ComfyNode):
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='RawProbe',inputs=[io.Image.Input('image')],outputs=[])
    @classmethod
    async def execute(cls,image):
        await image.raw()
        return io.NodeOutput()
