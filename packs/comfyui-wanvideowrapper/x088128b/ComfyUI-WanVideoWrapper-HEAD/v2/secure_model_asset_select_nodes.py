"""Model resource selection: keep logical names; never return host paths.

The native path field becomes a confined model-catalogue name. The owned

model-loader consumer must resolve it again in its own admitted context.

The selector validates existence with the public asset broker; asset refs

are not embedded in plain data (which the host could unwrap to paths).
"""
from ._wan_catalogue import valid_catalogue_name
from comfy_api.latest import io, sdk

class WanVideoVACEModelSelect(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("assets",)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoVACEModelSelect', display_name='WanVideo VACE Module Select',
            category="WanVideoWrapper", description="VACE model to use when not using model that has it included, loaded from 'ComfyUI/models/diffusion_models'",
            inputs=[io.Combo.Input('vace_model', options=[], tooltip="These models are loaded from the 'ComfyUI/models/diffusion_models' VACE model to use when not using model that has it included")],
            outputs=[io.Custom("VACEPATH").Output(display_name="extra_model")])
    @classmethod
    def validate_inputs(cls, input_types=None, **kwargs):
        name = kwargs.get("vace_model")
        return True if name is None or valid_catalogue_name(name) else "Model selection requires a confined logical catalogue name"

    @classmethod
    async def execute(cls, vace_model):
        # Resolve solely to validate the admitted logical resource. Its
        # host-owned path/ref is deliberately not put into output data.
        if not valid_catalogue_name(vace_model):
            raise ValueError("Model selection requires a confined logical catalogue name")
        await sdk.current_context().assets.resolve("diffusion_models", vace_model)
        selected = {"path": vace_model}
        return io.NodeOutput([selected])


class WanVideoExtraModelSelect(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("assets",)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoExtraModelSelect', display_name='WanVideo Extra Model Select',
            category="WanVideoWrapper", description="Extra model to load and add to the main model, ie. VACE or MTV Crafter 'ComfyUI/models/diffusion_models'",
            inputs=[io.Combo.Input('extra_model', options=[], tooltip="These models are loaded from the 'ComfyUI/models/diffusion_models' path to extra state dict to add to the main model"),
                io.Custom("VACEPATH").Input("prev_model", optional=True, tooltip="For loading multiple extra models")],
            outputs=[io.Custom("VACEPATH").Output(display_name="extra_model")])
    @classmethod
    def validate_inputs(cls, input_types=None, **kwargs):
        name = kwargs.get("extra_model")
        return True if name is None or valid_catalogue_name(name) else "Model selection requires a confined logical catalogue name"

    @classmethod
    async def execute(cls, extra_model, prev_model=None):
        # Resolve solely to validate the admitted logical resource. Its
        # host-owned path/ref is deliberately not put into output data.
        if not valid_catalogue_name(extra_model):
            raise ValueError("Model selection requires a confined logical catalogue name")
        await sdk.current_context().assets.resolve("diffusion_models", extra_model)
        selected = {"path": extra_model}
        if prev_model is not None and isinstance(prev_model, list):
            return io.NodeOutput(prev_model + [selected])
        return io.NodeOutput([selected])


NODE_CLASS_MAPPINGS = {'WanVideoVACEModelSelect': WanVideoVACEModelSelect, 'WanVideoExtraModelSelect': WanVideoExtraModelSelect}
