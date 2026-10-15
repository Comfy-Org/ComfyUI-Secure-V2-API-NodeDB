"""
File    : comfy_kitchen_attention_enabler.py
Purpose : Enable the use of Comfy-Kitchen's optimized attention when supported
          by the user's installed version of comfyui.
Author  : Martin Rizzo | <martinrizzo@gmail.com>
Date    : Aug 12, 2026
Repo    : https://github.com/martin-rizzo/ComfyUI-ZImagePowerNodes
License : MIT
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
                          ComfyUI-ZImagePowerNodes
         ComfyUI nodes designed specifically for the "Z-Image" model.
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    The V3 schema documentation can be found here:
    - https://docs.comfy.org/custom-nodes/v3_migration

"""
from typing             import TypeAlias, Any
from comfy_api.latest   import io, sdk
ComfyModel: TypeAlias = Any


class ComfyKitchenAttentionEnabler(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("inspect",)
    xTITLE         = "Comfy-Kitchen Attention Enabler"
    xDESCRIPTION   = (
        "Patches the model to use the optimized Comfy-Kitchen attention mechanism, "
        "if supported. Ensures backward compatibility by falling back to standard "
        "attention in older ComfyUI versions without breaking the workflow."
    )
    xCATEGORY      = ""
    xCOMFY_NODE_ID = ""
    xDEPRECATED    = False

    #__ INPUT / OUTPUT ____________________________________
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            display_name  = cls.xTITLE,
            description   = cls.xDESCRIPTION,
            category      = cls.xCATEGORY,
            node_id       = cls.xCOMFY_NODE_ID,
            is_deprecated = cls.xDEPRECATED,
            #search_aliases=[],
            inputs=[
                io.Model.Input  ("model"),
                io.Boolean.Input("comfy_kitchen_attention",
                                 default=False,
                                 tooltip="If enabled, attempts to apply the Comfy-Kitchen attention "
                                         "optimization. The optimization will only take effect if your "
                                         "current ComfyUI version supports it.",
                                ),
            ],
            outputs=[
                io.Model.Output(tooltip="The patched model with comfy-kitchen attention enabled if possible"),
            ]
        )

    #__ FUNCTION __________________________________________
    @classmethod
    async def execute(cls, model: sdk.ModelRef, comfy_kitchen_attention: bool) -> io.NodeOutput:

        try:
            return io.NodeOutput(await model.patch(
                "attention_impl", mode="comfy_kitchen_int8" if comfy_kitchen_attention else "pytorch",
                allow_compile=True))
        except Exception as e:
            return io.NodeOutput(model)

ComfyKitchenAttentionEnabler.xTITLE = '⚡| Comfy-Kitchen Attention Enabler'
ComfyKitchenAttentionEnabler.xDESCRIPTION = 'Patches the model to use the optimized Comfy-Kitchen attention mechanism, if supported. Ensures backward compatibility by falling back to standard attention in older ComfyUI versions without breaking the workflow.'
ComfyKitchenAttentionEnabler.xCATEGORY = '⚡Z-Image/utils'
ComfyKitchenAttentionEnabler.xCOMFY_NODE_ID = 'ComfyKitchenAttentionEnabler //ZImagePowerNodes'
ComfyKitchenAttentionEnabler.xDEPRECATED = False
