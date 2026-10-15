"""Pinned WanVideoWrapper weightless scheduler model through the public SDK."""
from comfy_api.latest import io, sdk


class DummyComfyWanModelObject(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('models',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='DummyComfyWanModelObject',
            display_name='Dummy Comfy Wan Model Object',
            category='WanVideoWrapper',
            description='Helper node to create empty Wan model to use with BasicScheduler -node to get sigmas',
            inputs=[io.Float.Input('shift', default=1.0, min=-100.0, max=100.0,
                                   step=0.01, tooltip='Sigma shift value')],
            outputs=[io.Model.Output(display_name='model')],
        )

    @classmethod
    async def execute(cls, shift: float):
        model = await sdk.ctx().models.create_sampling_model(
            'discrete_flow', {'shift': shift})
        return io.NodeOutput(model)


NODE_CLASS_MAPPINGS = {'DummyComfyWanModelObject': DummyComfyWanModelObject}
