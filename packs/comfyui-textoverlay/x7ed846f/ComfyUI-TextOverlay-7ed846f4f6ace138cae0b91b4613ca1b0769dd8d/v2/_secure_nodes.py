"""One complete source node through public typed image and managed font data."""
from comfy_api.latest import io,sdk
from . import nodes as source
from . import _bounds

class TextOverlaySecure(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=('inspect','raw','assets')

    @classmethod
    def define_schema(cls):
        kinds={'IMAGE':io.Image,'STRING':io.String,'INT':io.Int,'FLOAT':io.Float}
        inputs=[]
        for name,spec in source.TextOverlay.INPUT_TYPES()['required'].items():
            attrs=dict(spec[1]) if len(spec)>1 else {}
            if isinstance(spec[0],list):
                inputs.append(io.Combo.Input(name,options=spec[0],**attrs))
            else:
                if spec[0]=='STRING':attrs.setdefault('multiline',None)
                inputs.append(kinds[spec[0]].Input(name,**attrs))
        return io.Schema(node_id='Text Overlay',category=source.TextOverlay.CATEGORY,
            inputs=inputs,outputs=[io.Image.Output()])

    @classmethod
    async def execute(cls,**values):
        shape=await _bounds.describe(values['image'])
        _bounds.plan(shape,values)
        font_data=await _bounds.font_bytes(values['font'])
        image=await _bounds.raw(values['image'])
        # Fresh first image clears each native instance cache; source cache is
        # then shared only across subsequent images of this one batch.
        instance=source.TextOverlay();instance._secure_font_data=font_data
        result=instance.batch_process(**{**values,'image':image})[0]
        if type(result) is not source.torch.Tensor:
            raise TypeError('TextOverlay source result must remain Torch tensor')
        _bounds.geometry(tuple(result.shape))
        if result.numel()*result.element_size()>_bounds.MAX_OUTPUT:
            raise _bounds.ProfileError('TextOverlay result byte budget')
        return io.NodeOutput(await sdk.ImageRef.from_value(result))

NODE_CLASS_MAPPINGS={'Text Overlay':TextOverlaySecure}
