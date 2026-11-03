class PixaromaVersionCheck:
    """Diagnostic label — shows ComfyUI / Frontend / Node UI / Pixaroma versions."""

    DESCRIPTION = (
        "Version Check Pixaroma - a small on-canvas panel showing the versions "
        "that matter when reporting a bug: the ComfyUI (backend) version, the "
        "ComfyUI frontend version, which node interface is active (Nodes 2.0 / "
        "Legacy), and the installed Pixaroma version. A Copy button copies all "
        "four lines as text so you can paste them straight into a bug report.\n\n"
        "Pure diagnostic - no inputs to wire, no outputs to chain, no Python "
        "work on Run. The Node UI row updates live when you switch the setting."
    )

    @classmethod
    def INPUT_TYPES(s):
        return {"required": {}}

    RETURN_TYPES = ()
    FUNCTION = "noop"
    # OUTPUT_NODE intentionally NOT set: ComfyUI skips this node on Run, so no
    # "X.Xs" timing badge is drawn over what is just an info panel. All the
    # work happens in js/version_check/index.js.
    CATEGORY = "👑 Pixaroma/🔀 Logic & Flow"

    def noop(self):
        return {}


NODE_CLASS_MAPPINGS = {
    "PixaromaVersionCheck": PixaromaVersionCheck,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "PixaromaVersionCheck": "Version Check Pixaroma",
}


# Secure V2 boundary: upstream compute above is retained verbatim.
from comfy_api.latest import io, sdk
from .. import _secure_boundary as boundary
from .._secure_schema import schema_for

_LegacyPixaromaVersionCheck = PixaromaVersionCheck

class PixaromaVersionCheck(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = []

    @classmethod
    def define_schema(cls):
        return schema_for("PixaromaVersionCheck")

    @classmethod
    async def execute(cls, **kwargs):
        out = _LegacyPixaromaVersionCheck().noop(**kwargs)
        return await boundary.output([], out)

NODE_CLASS_MAPPINGS = {"PixaromaVersionCheck": PixaromaVersionCheck}
NODE_DISPLAY_NAME_MAPPINGS = {"PixaromaVersionCheck": "Version Check Pixaroma"}
