from comfy_api.latest import io, sdk
class Probe(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='Probe',inputs=[io.Latent.Input('samples')],outputs=[])
    @classmethod
    async def execute(cls,samples):
        await samples.raw()
        return io.NodeOutput()
