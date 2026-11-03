"""Named unqualified purposes; no upstream dependency is imported here."""
from comfy_api.latest import io
from ._v2 import SCHEMAS, schema_for


class EssentialsPurposeRefusal(RuntimeError):
    """A source purpose has no qualified implementation in this scoped repair."""


def make_refusal(node_id):
    def define_schema(cls):
        return schema_for(node_id)

    def validate_inputs(cls):
        return f"comfyui_essentials/{node_id} is not yet converted to Secure Nodes V2"

    async def execute(cls, **kwargs):
        raise EssentialsPurposeRefusal(validate_inputs(cls))

    cls = type(SCHEMAS[node_id]["class"], (io.ComfyNode,), {
        "__module__": __name__, "SDK_REFS": True, "SDK_PERMISSIONS": (),
        "define_schema": classmethod(define_schema),
        "validate_inputs": classmethod(validate_inputs),
        "execute": classmethod(execute),
    })
    globals()[cls.__name__] = cls
    return cls


NODE_CLASS_MAPPINGS = {
    node_id: make_refusal(node_id) for node_id in SCHEMAS
    if node_id not in {"ImageBatchMultiple+", "GetImageSize+"}
}
