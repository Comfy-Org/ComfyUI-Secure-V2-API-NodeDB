"""Original frozen XY schema; full refusal for unmatched global session lifecycle."""
from comfy_api.latest import io
from .._secure_schema import schema_for

_REFUSAL = "comfyui-pixaroma/PixaromaXYPlot is not yet converted to Secure Nodes V2"
_LIFECYCLE = (_REFUSAL + ": the source process-global eight-session LRU evicts cells "
              "and deletes grid PNGs; per-session KV does not preserve this lifecycle")

class PixaromaXYPlot(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = []

    @classmethod
    def define_schema(cls):
        return schema_for("PixaromaXYPlot")

    @classmethod
    def validate_inputs(cls, **kwargs):
        return _REFUSAL

    @classmethod
    async def execute(cls, **kwargs):
        raise RuntimeError(_LIFECYCLE)

    @classmethod
    async def fingerprint_inputs(cls, **kwargs):
        raise RuntimeError(_LIFECYCLE)

NODE_CLASS_MAPPINGS = {"PixaromaXYPlot": PixaromaXYPlot}
NODE_DISPLAY_NAME_MAPPINGS = {"PixaromaXYPlot": "XY Plot Pixaroma"}
