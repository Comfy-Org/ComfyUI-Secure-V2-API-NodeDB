"""Typed scalar boundary around unchanged pack-owned preset tables."""
from comfy_api.latest import io
from .src.quicksize import NODE_CLASS_MAPPINGS as ORIGINAL, NODE_DISPLAY_NAME_MAPPINGS


def wrapper(node_id, original):
    @classmethod
    def define_schema(cls):
        inputs=[]
        for name,(kind,options) in original.INPUT_TYPES()['required'].items():
            if kind=='BOOLEAN':
                inputs.append(io.Boolean.Input(name,default=options['default']))
            else:
                inputs.append(io.Combo.Input(name,options=kind,default=options['default']))
        return io.Schema(node_id=node_id,display_name=NODE_DISPLAY_NAME_MAPPINGS[node_id],category=original.CATEGORY,
            inputs=inputs,outputs=[io.Int.Output('width'),io.Int.Output('height')])

    @classmethod
    async def execute(cls,**inputs):
        for name,value in inputs.items():
            if name=='1.5x':
                if type(value) is not bool:raise ValueError('plain Boolean 1.5x required')
            elif type(value) is not str or len(value.encode('utf-8'))>64:
                raise ValueError('bounded plain UTF8 preset selector required')
        return io.NodeOutput(*original().get_size(**inputs))

    return type(original.__name__,(io.ComfyNode,),dict(__module__=__name__,SDK_REFS=True,SDK_PERMISSIONS=(),define_schema=define_schema,execute=execute))


NODE_CLASS_MAPPINGS={node_id:wrapper(node_id,cls)for node_id,cls in ORIGINAL.items()}
globals().update({cls.__name__:cls for cls in NODE_CLASS_MAPPINGS.values()})
