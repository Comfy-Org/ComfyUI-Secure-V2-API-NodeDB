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
            # Shape-only descriptions do not carry a structured dtype. Check
            # their minimum byte footprint, then meter the actual dense dtype
            # before executing the original allocation-heavy method.
            for name in names:_bounds.geometry(await _bounds.describe(values[name]))
            original={name:values[name] for name in names}
            dense={name:await _bounds.raw(values[name]) for name in names}
            _bounds.plan(node_id,[dense[name] for name in names],values)
            instance=native()
            if node_id=='AsciiArt':instance._secure_font=buffers.BytesIO(await _bounds.font_bytes())
            result=getattr(instance,native.FUNCTION)(**{**values,**dense})
            published=[]
            for kind,value in zip(native.RETURN_TYPES,result,strict=True):
                if type(value) is not torch.Tensor:raise TypeError('source result must remain a dense Torch tensor')
                _,count=_bounds.geometry(tuple(value.shape))
                _bounds.check_bytes(count*value.element_size(),'result')
                identity=next((original[name] for name,tensor in dense.items() if value is tensor),None)
                if identity is not None:
                    published.append(identity)
                else:
                    # HSV/Canny declare IMAGE but return BHW. Preserve their
                    # image socket and pixel bytes as a grayscale BHW1 view.
                    if kind=='IMAGE' and value.ndim==3:value=value.unsqueeze(-1)
                    published.append(await sdk.ImageRef.from_value(value))
            return io.NodeOutput(*published)
    Converted.__name__=native.__name__+'Secure'
    Converted.__qualname__=Converted.__name__
    Converted.__module__=__name__
    return Converted

NODE_CLASS_MAPPINGS={name:create(name,native) for name,native in source.NODE_CLASS_MAPPINGS.items()}
globals().update({cls.__name__:cls for cls in NODE_CLASS_MAPPINGS.values()})
