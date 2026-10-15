"""Uni3C payload composition; the model itself remains an opaque input."""
from comfy_api.latest import io, sdk
from .secure_tensor_nodes import _bound_payload


class WanVideoUni3C_embeds(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoUni3C_embeds', display_name='WanVideo Uni3C Embeds',
            category='WanVideoWrapper',
            inputs=[
                io.Custom('WANVIDEOCONTROLNET').Input('controlnet'),
                io.Float.Input('strength', default=1.0, min=0.0, max=10.0, step=0.001),
                io.Float.Input('start_percent', default=0.0, min=0.0, max=1.0, step=0.01,
                               tooltip='Start percent of the steps to apply the controlnet'),
                io.Float.Input('end_percent', default=1.0, min=0.0, max=1.0, step=0.01,
                               tooltip='End percent of the steps to apply the controlnet'),
                io.Latent.Input('render_latent', optional=True),
                io.Mask.Input('render_mask', optional=True, tooltip='NOT IMPLEMENTED!'),
                io.Boolean.Input('offload', optional=True, default=True,
                                 tooltip='If enabled, the controlnet model will be offloaded before main model block processing to save VRAM.'),
            ],
            outputs=[io.Custom('UNI3C_EMBEDS').Output(display_name='uni3c_embeds')],
        )

    @classmethod
    async def execute(cls, controlnet, strength, start_percent, end_percent,
                      render_latent=None, render_mask=None, offload=True):
        latent_mask = latents = None
        if render_latent is not None:
            # Materialize only buffer-safe LATENT data under the raw grant.
            # Never resolve the controlnet handle or inspect its host object.
            payload = await render_latent.value() if isinstance(render_latent, sdk.LatentRef) else render_latent
            _bound_payload(payload)
            latents = payload['samples']
        if render_mask is not None:
            raise NotImplementedError('render_mask is not implemented at this time')
        if latents is not None:
            latents = await sdk.ValueRef.from_value(latents)
        result = {
            'controlnet': controlnet,
            'controlnet_weight': strength,
            'start': start_percent,
            'end': end_percent,
            'render_latent': latents,
            'render_mask': latent_mask,
            'camera_embedding': None,
            'offload': offload,
        }
        _bound_payload(result)
        return io.NodeOutput(result)


NODE_CLASS_MAPPINGS = {'WanVideoUni3C_embeds': WanVideoUni3C_embeds}
