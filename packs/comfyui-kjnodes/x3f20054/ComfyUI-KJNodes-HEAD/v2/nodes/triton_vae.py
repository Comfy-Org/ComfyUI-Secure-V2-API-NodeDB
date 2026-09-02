from __future__ import annotations
from comfy_api.latest import io as _remaining_zab_io

class PatchTritonVAESecure(_remaining_zab_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _remaining_zab_io.Schema:
        return _remaining_zab_io.Schema(node_id='PatchTritonVAESecure', display_name='🔒 Patch Triton VAE (secure)', category='KJNodes/experimental', is_experimental=True, description='Apply host-owned Triton fused norm and optional int8 convolution patches to a VAE. Execution requires Triton on an NVIDIA CUDA system.', inputs=[_remaining_zab_io.Vae.Input('vae'), _remaining_zab_io.Boolean.Input('fuse_norm_silu', default=True, tooltip='Fuse supported VAE norm and SiLU chains.'), _remaining_zab_io.Boolean.Input('channels_last', default=True, tooltip='Use channels-last convolution weights and reload callbacks.'), _remaining_zab_io.Boolean.Input('int8_conv', default=False, tooltip='Use eligible experimental int8 decoder convolutions.'), _remaining_zab_io.Boolean.Input('autotune', default=False, tooltip='Autotune Triton kernels on first use of each shape.')], outputs=[_remaining_zab_io.Vae.Output('vae', display_name='vae')])

    @classmethod
    async def execute(cls, vae, fuse_norm_silu=True, channels_last=True, int8_conv=False, autotune=False) -> _remaining_zab_io.NodeOutput:
        patched = await vae.patch_triton(fuse_norm_silu=fuse_norm_silu, channels_last=channels_last, int8_conv=int8_conv, autotune=autotune)
        return _remaining_zab_io.NodeOutput(patched)

NODE_CLASS_MAPPINGS = {
    'PatchTritonVAESecure': PatchTritonVAESecure,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    'PatchTritonVAESecure': '🔒 Patch Triton VAE (secure)',
}
