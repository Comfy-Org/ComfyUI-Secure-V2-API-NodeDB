from comfy_api.latest import io, sdk
from ._secure_boundary import SecureConversionRefusal, data_input


class D2_ModelAndCLIPMergeSDXL(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 Model and CLIP Merge SDXL', display_name='D2 Model and CLIP Merge SDXL', category='D2/Merge', inputs=[io.Model.Input('model1'), io.Model.Input('model2'), io.Clip.Input('clip1'), io.Clip.Input('clip2'), io.String.Input('weights')], outputs=[io.Model.Output(display_name='MODEL'), io.Clip.Output(display_name='CLIP')])

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 Model and CLIP Merge SDXL is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 Model and CLIP Merge SDXL is not yet converted to Secure Nodes V2: This node is outside the completed backend subset; its original implementation is not imported into the guest.')


NODE_CLASS_MAPPINGS = {
    "D2 Model and CLIP Merge SDXL": D2_ModelAndCLIPMergeSDXL,
}
