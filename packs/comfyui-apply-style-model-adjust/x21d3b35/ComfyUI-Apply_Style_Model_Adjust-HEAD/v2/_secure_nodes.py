"""Pack-owned prompt/style balance; the style encoder stays opaque and host-owned."""
import math
from comfy_api.latest import io,sdk
from .nodes import ApplyStyleModelAdjust as Source

class ApplyStyleModelAdjustSecure(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    FUNCTION='execute'

    @classmethod
    def define_schema(cls):
        source=Source.INPUT_TYPES()['required']
        return io.Schema(node_id='ApplyStyleModelAdjust',display_name='Apply Style Model (Adjusted)',
            category=Source.CATEGORY,inputs=[
                io.Conditioning.Input('conditioning'),io.Custom('STYLE_MODEL').Input('style_model'),
                io.ClipVisionOutput.Input('clip_vision_output'),
                io.Float.Input('strength',**source['strength'][1])],
            outputs=[io.Conditioning.Output()])

    @classmethod
    async def execute(cls,conditioning,style_model,clip_vision_output,strength):
        if isinstance(strength,bool) or not isinstance(strength,(int,float)) or not math.isfinite(strength) or abs(strength)>1000000:
            raise ValueError('finite bounded strength required')
        balanced=await conditioning.scale_embeddings(3.0-2.0*strength)
        # The existing host primitive owns get_cond/flatten/style multiplication/cat.
        result=await style_model.apply(clip_vision_output,balanced,strength*0.7)
        return io.NodeOutput(result)
