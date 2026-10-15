"""Unregistered test-only assets call to prove actual denied guest capability."""
from comfy_api.latest import io, sdk

class AssetsProbe(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('assets',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='NedComfyrollTestOnlyAssetsProbe', inputs=[], outputs=[io.String.Output()])
    @classmethod
    async def execute(cls):
        await sdk.ctx().assets.list('input')
        return io.NodeOutput('unexpected-authority')
