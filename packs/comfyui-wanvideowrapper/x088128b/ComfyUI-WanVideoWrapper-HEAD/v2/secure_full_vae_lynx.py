"""Original Lynx reference sampling and metadata through the bounded Wan VAE."""
import torch
from comfy_api.latest import io
from .secure_tensor_nodes import _bound_payload
from .secure_full_vae_nodes import rebuild_full_vae
from .secure_full_vae_encode import _image

device = offload_device = torch.device('cpu')

def _lynx_boundary(embeds,lynx_ip_embeds,ref_image,ref_text_embed,ref_blocks_to_use):
    _bound_payload({'embeds':embeds,'ip':lynx_ip_embeds,'image':ref_image,'text':ref_text_embed})
    if not isinstance(ref_blocks_to_use,str) or len(ref_blocks_to_use)>4096:
        raise ValueError('Lynx block selection exceeds the bounded string domain')
    # Bound range expansion before running the unchanged native parser.
    for item in ref_blocks_to_use.split(','):
        item=item.strip()
        if '-' in item and not item.startswith('-'):
            try:
                start,end=item.split('-',1)
                start,end=int(start.strip()),int(end.strip())
            except ValueError:
                continue
            if end-start>4096:
                raise ValueError('Lynx block range exceeds the bounded expansion domain')
    if ref_image is not None:
        _image(ref_image)

class WanVideoAddLynxEmbeds(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw','assets','models.download')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoAddLynxEmbeds',display_name='WanVideo Add Lynx Embeds',category='WanVideoWrapper',
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
                io.String.Input('ref_blocks_to_use', default='', force_input=True, tooltip="Comma-separated list of block indices and ranges to use for reference feature, e.g. '0-20, 25, 28, 35-39'. If empty, use all blocks.", optional=True)],outputs=[io.Custom('WANVIDIMAGE_EMBEDS').Output(display_name='image_embeds')])

    @classmethod
    async def execute(cls, embeds, ip_scale, ref_scale, start_percent, end_percent, lynx_cfg_scale, vae=None, lynx_ip_embeds=None, ref_image=None, ref_text_embed=None, ref_blocks_to_use=''):
        _lynx_boundary(embeds,lynx_ip_embeds,ref_image,ref_text_embed,ref_blocks_to_use)
        if ref_image is not None and ref_text_embed is not None:
            vae, _ = await rebuild_full_vae(vae)
        with torch.inference_mode():
            if ref_image is not None and ref_text_embed is None:
                raise ValueError('If ref_image is provided, ref_text_embed must also be provided.')
            if ref_image is not None:
                vae.to(device)
                ref_image_in = (ref_image[..., :3].permute(3, 0, 1, 2) * 2 - 1).to(device, vae.dtype)
                ref_latent = vae.encode([ref_image_in], device, tiled=False, sample=True)
                ref_latent_uncond = vae.encode([torch.zeros_like(ref_image_in)], device, tiled=False, sample=True)
                vae.to(offload_device)
            if ref_blocks_to_use.strip() == '':
                ref_blocks_to_use = None
            else:
                blocks = []
                for item in ref_blocks_to_use.split(','):
                    item = item.strip()
                    if '-' in item and (not item.startswith('-')):
                        try:
                            start, end = item.split('-', 1)
                            start, end = (int(start.strip()), int(end.strip()))
                            blocks.extend(list(range(start, end + 1)))
                        except ValueError:
                            print(f'Invalid range format: {item}')
                    elif item.isdigit():
                        blocks.append(int(item))
                    else:
                        print(f'Invalid block specification: {item}')
                ref_blocks_to_use = sorted(list(set(blocks)))
                print('Using ref blocks:', ref_blocks_to_use)
            new_entry = {'ip_x': lynx_ip_embeds['ip_x'] if lynx_ip_embeds is not None else None, 'ip_x_uncond': lynx_ip_embeds['ip_x_uncond'] if lynx_ip_embeds is not None else None, 'ref_latent': ref_latent if ref_image is not None else None, 'ref_latent_uncond': ref_latent_uncond if ref_image is not None else None, 'ref_text_embed': ref_text_embed if ref_text_embed is not None else None, 'ip_scale': ip_scale, 'ref_scale': ref_scale, 'cfg_scale': lynx_cfg_scale, 'start_percent': start_percent, 'end_percent': end_percent, 'ref_blocks_to_use': ref_blocks_to_use}
            updated = dict(embeds)
            updated['lynx_embeds'] = new_entry
        _bound_payload(updated)
        return io.NodeOutput(updated)

NODE_CLASS_MAPPINGS = {'WanVideoAddLynxEmbeds':WanVideoAddLynxEmbeds}
