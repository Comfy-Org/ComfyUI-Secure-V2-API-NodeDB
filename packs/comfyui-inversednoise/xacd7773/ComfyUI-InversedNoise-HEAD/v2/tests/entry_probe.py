"""Only tests the real guest ctx.sample route; not part of the node census."""
from comfy_api.latest import io, sdk
from ..nodes import SamplerInversedEulerNode

class InverseEntryProbe(io.ComfyNode):
    SDK_REFS = True
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='InverseEntryProbe', inputs=[io.Model.Input('model'),io.Latent.Input('latent'),io.Custom('SIGMAS').Input('sigmas'),io.Conditioning.Input('positive'),io.Conditioning.Input('negative')],outputs=[io.Latent.Output()])
    @classmethod
    async def execute(cls,model,latent,sigmas,positive,negative):
        sampler=(await SamplerInversedEulerNode.execute()).result[0]
        return io.NodeOutput(await sdk.ctx().sample(latent,2,model=model,sampler=sampler,sigmas=sigmas,cfg=1.,disable_noise=True,positive=positive,negative=negative))
