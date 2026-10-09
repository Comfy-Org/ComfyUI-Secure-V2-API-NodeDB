"""All 23 source effects through public typed tensor and asset facilities."""
import io as buffers
import torch
from comfy_api.latest import io,sdk
from . import post_processing_nodes as source
from . import _bounds
KINDS={'IMAGE':io.Image,'INT':io.Int,'FLOAT':io.Float,'BOOLEAN':io.Boolean,'STRING':io.String}

def schema(node_id,native):
    inputs=[]
    for group in ('required','optional'):
        for name,spec in native.INPUT_TYPES().get(group,{}).items():
            options=dict(spec[1]) if len(spec)>1 else {}
            if group=='optional':options['optional']=True
            if isinstance(spec[0],list):inputs.append(io.Combo.Input(name,options=spec[0],**options))
            else:inputs.append(KINDS[spec[0]].Input(name,**options))
    return io.Schema(node_id=node_id,category=native.CATEGORY,inputs=inputs,
                     outputs=[KINDS[k].Output() for k in native.RETURN_TYPES])

def create(node_id,native):
    class Converted(io.ComfyNode):
        SDK_REFS=True
        SDK_PERMISSIONS=('inspect','raw','assets') if node_id=='AsciiArt' else ('inspect','raw')
        @classmethod
        def define_schema(cls):return schema(node_id,native)
        @classmethod
        async def execute(cls,**values):
            specs=native.INPUT_TYPES()['required']
            names=[name for name,spec in specs.items() if spec[0]=='IMAGE']
            _bounds.plan(node_id,[await _bounds.describe(values[name]) for name in names],values)
            original={name:values[name] for name in names}
            dense={name:await _bounds.raw(values[name]) for name in names}
            instance=native()
            if node_id=='AsciiArt':instance._secure_font=buffers.BytesIO(await _bounds.font_bytes())
            result=getattr(instance,native.FUNCTION)(**{**values,**dense})
            published=[]
            for value in result:
                if type(value) is not torch.Tensor:raise TypeError('source result must remain a dense Torch tensor')
                _,count=_bounds.geometry(tuple(value.shape))
                if count*value.element_size()>_bounds.MAX_OUTPUT:raise ValueError('Post Processing result byte budget exceeded')
                identity=next((original[name] for name,tensor in dense.items() if value is tensor),None)
                published.append(identity if identity is not None else await sdk.ImageRef.from_value(value))
            return io.NodeOutput(*published)
    Converted.__name__=native.__name__+'Secure'
    Converted.__qualname__=Converted.__name__
    Converted.__module__=__name__
    return Converted

NODE_CLASS_MAPPINGS={name:create(name,native) for name,native in source.NODE_CLASS_MAPPINGS.items()}
globals().update({cls.__name__:cls for cls in NODE_CLASS_MAPPINGS.values()})
