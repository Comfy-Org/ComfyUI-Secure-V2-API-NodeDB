"""Default public VAE decode; tiled/circular facilities remain explicitly pending."""
from comfy_api.latest import io
PENDING='Comfyroll tiled/circular VAE capability pending: native tile_x/tile_y and circular padding must be preserved by the runtime'

class CR_VAEDecode(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR VAE Decode',display_name='⚙️ CR VAE Decode',category='🧩 Comfyroll Studio/✨ Essential/📦 Core',inputs=[io.Latent.Input('samples'),io.Vae.Input('vae'),io.Boolean.Input('tiled',default=False),io.Boolean.Input('circular',default=False)],outputs=[io.Image.Output(display_name='IMAGE'),io.String.Output(display_name='show_help')])
    @classmethod
    def validate_inputs(cls,circular=False,tiled=False):
        return PENDING if circular==True or tiled==True else True
    @classmethod
    async def execute(cls,samples,vae,circular=False,tiled=False):
        if circular==True or tiled==True:raise RuntimeError(PENDING)
        # This branch matches the original's ordinary vae.decode(samples).
        # Pixel-sized decode_tiled is not the original's native tile geometry.
        image=await vae.decode(samples)
        return io.NodeOutput(image,'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Core-Nodes#cr-vae-decode')

NODE_CLASS_MAPPINGS={'CR VAE Decode':CR_VAEDecode}
NODE_DISPLAY_NAME_MAPPINGS={'CR VAE Decode':'⚙️ CR VAE Decode'}
