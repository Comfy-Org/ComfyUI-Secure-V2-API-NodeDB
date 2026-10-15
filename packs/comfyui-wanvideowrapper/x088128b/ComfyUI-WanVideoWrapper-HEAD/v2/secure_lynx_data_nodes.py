"""Staged full-schema Lynx adapter; not added to release registrations.

Only the no-ref-image branch is implemented. The custom WanVAE branch must be
completed and actual registered guest/outer gates must pass before admission.
"""
from comfy_api.latest import io
from .secure_lynx_data import attach_lynx_data

class WanVideoAddLynxEmbeds(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoAddLynxEmbeds', category='WanVideoWrapper',
            inputs=[io.Custom('WANVIDIMAGE_EMBEDS').Input('embeds'),
                io.Float.Input('ip_scale', default=1.0, min=0.0, max=100.0, step=0.01, tooltip='Strength of the ip adapter face feature'),
                io.Float.Input('ref_scale', default=1.0, min=0.0, max=100.0, step=0.01, tooltip='Strength of the reference feature'),
                io.Float.Input('lynx_cfg_scale', default=1.0, min=0.0, max=10.0, step=0.01, tooltip='If above 1.0 and main cfg_scale is above 1.0, run extra pass, default value 2.0'),
                io.Float.Input('start_percent', default=0.0, min=0.0, max=1.0, step=0.01, tooltip='Start percent to apply the ref '),
                io.Float.Input('end_percent', default=1.0, min=0.0, max=1.0, step=0.01, tooltip='End percent to apply the ref '),
                io.Custom('WANVAE').Input('vae', tooltip='VAE model, only needed if ref_image is provided', optional=True),
                io.Custom('LYNXIP').Input('lynx_ip_embeds', tooltip='lynx face embeddings', optional=True),
                io.Image.Input('ref_image', optional=True),
                io.Custom('WANVIDEOTEXTEMBEDS').Input('ref_text_embed', optional=True),
                io.String.Input('ref_blocks_to_use', default='', tooltip="Comma-separated list of block indices and ranges to use for reference feature, e.g. '0-20, 25, 28, 35-39'. If empty, use all blocks.", optional=True, force_input=True)],
            outputs=[io.Custom('WANVIDIMAGE_EMBEDS').Output(display_name='image_embeds')])

    @classmethod
    def execute(cls, embeds, ip_scale, ref_scale, start_percent, end_percent,
                lynx_cfg_scale, vae=None, lynx_ip_embeds=None, ref_image=None,
                ref_text_embed=None, ref_blocks_to_use=''):
        return io.NodeOutput(*attach_lynx_data(embeds, ip_scale, ref_scale,
            start_percent, end_percent, lynx_cfg_scale, vae, lynx_ip_embeds,
            ref_image, ref_text_embed, ref_blocks_to_use))

NODE_CLASS_MAPPINGS = {'WanVideoAddLynxEmbeds': WanVideoAddLynxEmbeds}
