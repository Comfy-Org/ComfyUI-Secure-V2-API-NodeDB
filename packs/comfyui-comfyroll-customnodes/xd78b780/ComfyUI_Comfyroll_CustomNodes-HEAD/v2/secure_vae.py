"""Exact canonical CR VAE calls with reviewed execution-scoped circular padding."""
from comfy_api.latest import io

class CR_VAEDecode(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR VAE Decode',display_name='⚙️ CR VAE Decode',category='🧩 Comfyroll Studio/✨ Essential/📦 Core',inputs=[io.Latent.Input('samples'),io.Vae.Input('vae'),io.Boolean.Input('tiled',default=False),io.Boolean.Input('circular',default=False)],outputs=[io.Image.Output(display_name='IMAGE'),io.String.Output(display_name='show_help')])
    @classmethod
    async def execute(cls,samples,vae,circular=False,tiled=False):
        padding_mode='circular' if circular==True else 'default'
        if tiled==True:
            image=await vae.decode_tiled_native(samples,tile_x=512,tile_y=512,padding_mode=padding_mode)
        else:
            image=await vae.decode(samples,padding_mode=padding_mode)
        return io.NodeOutput(image,'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Core-Nodes#cr-vae-decode')

NODE_CLASS_MAPPINGS={'CR VAE Decode':CR_VAEDecode}
NODE_DISPLAY_NAME_MAPPINGS={'CR VAE Decode':'⚙️ CR VAE Decode'}
