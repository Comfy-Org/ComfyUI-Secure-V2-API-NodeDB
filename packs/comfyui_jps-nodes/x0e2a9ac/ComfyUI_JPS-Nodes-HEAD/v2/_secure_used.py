"""Secure Nodes V2 classes for ComfyUI_JPS-Nodes' converted node types (pin 0e2a9aca02b1).

Each schema is the original's, frozen in the lane gate (_frozen_schema.py; list-valued RETURN_TYPES are COMBO outputs
with the original's choices); the LoRA menu is the host's catalogue (/models/loras, with the original's "None" first).
Each execute runs the original method from _jps_upstream.py (verbatim class bodies), except Lora Loader (JPS), whose
host steps (the LoRA file, patching MODEL and CLIP) go through the SDK in a line-for-line port.
  - values (numbers, strings, image size, integer switch): public V2 value mode, the original methods.
  - Model Switch / Latent Switch: the selected reference passes through, as the original passes the object.
"""
import inspect

from comfy_api.latest import io, sdk

from . import _jps_upstream as up
from ._frozen_schema import schema_for


def _value_node(node_id, cls_name, upstream_cls, method, permissions=(), refs=False, fingerprint=None):
    def define_schema(cls):
        return schema_for(node_id)

    async def execute(cls, **kwargs):
        return io.NodeOutput(*getattr(upstream_cls(), method)(**kwargs))

    namespace = {
        "SDK_REFS": refs,
        "SDK_PERMISSIONS": tuple(permissions),
        "define_schema": classmethod(define_schema),
        "execute": classmethod(execute),
        "__module__": __name__,
        "__qualname__": cls_name,
    }
    if fingerprint is not None:
        namespace["fingerprint_inputs"] = classmethod(fingerprint)
    return type(cls_name, (io.ComfyNode,), namespace)


def _date_fingerprint(cls, style=None):
    # Get_Date_Time_String.IS_CHANGED: the formatted time, so the node reruns when it changes.
    return up.Get_Date_Time_String.IS_CHANGED(style)[0]


SDXL_Resolutions = _value_node("SDXL Resolutions (JPS)", "SDXL_Resolutions", up.SDXL_Resolutions, "get_resolutions")
Text_Prompt = _value_node("Text Prompt (JPS)", "Text_Prompt", up.Text_Prompt, "text_prompt")
Text_Prompt_Combo = _value_node("Text Prompt Combo (JPS)", "Text_Prompt_Combo", up.Text_Prompt_Combo, "give_values")
SDXL_Prompt_Handling = _value_node("SDXL Prompt Handling (JPS)", "SDXL_Prompt_Handling", up.SDXL_Prompt_Handling,
                                   "pick_handling")
Math_Resolution_Multiply = _value_node("Resolution Multiply (JPS)", "Math_Resolution_Multiply",
                                       up.Math_Resolution_Multiply, "get_newres")
Math_Largest_Integer = _value_node("Largest Int (JPS)", "Math_Largest_Integer", up.Math_Largest_Integer, "get_lrg")
Math_Multiply_INT_FLOAT = _value_node("Multiply Int Float (JPS)", "Math_Multiply_INT_FLOAT", up.Math_Multiply_INT_FLOAT,
                                      "get_multiply_int_float")
Text_Concatenate = _value_node("Text Concatenate (JPS)", "Text_Concatenate", up.Text_Concatenate, "get_contxt")
Get_Date_Time_String = _value_node("Get Date Time String (JPS)", "Get_Date_Time_String", up.Get_Date_Time_String,
                                   "get_time", fingerprint=_date_fingerprint)
Sampler_Scheduler_Settings = _value_node("Sampler Scheduler Settings (JPS)", "Sampler_Scheduler_Settings",
                                         up.Sampler_Scheduler_Settings, "get_samsched")
Integer_Switch = _value_node("Integer Switch (JPS)", "Integer_Switch", up.Integer_Switch, "get_int")
Get_Image_Size = _value_node("Get Image Size (JPS)", "Get_Image_Size", up.Get_Image_Size, "get_imagesize",
                             permissions=("raw",))
Model_Switch = _value_node("Model Switch (JPS)", "Model_Switch", up.Model_Switch, "get_model", refs=True)
Latent_Switch = _value_node("Latent Switch (JPS)", "Latent_Switch", up.Latent_Switch, "get_latent", refs=True)


class IO_Lora_Loader(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("assets",)

    @classmethod
    def define_schema(cls):
        schema = schema_for("Lora Loader (JPS)")
        for item in schema.inputs:
            if item.id == "lora_name":
                item.remote = io.RemoteOptions(route="/models/loras", refresh_button=True)
        return schema

    @classmethod
    async def execute(cls, model, clip, switch, lora_name, strength_model, strength_clip):
        # jps_nodes.py IO_Lora_Loader.load_lora (L2576-2618), ported line for line. The original keeps the last
        # LoRA's tensors on the node instance (a cache only); the engine reads the file each time.
        if strength_model == 0 and strength_clip == 0:
            return io.NodeOutput(model, clip)

        if switch == "Off" or lora_name == "None":
            return io.NodeOutput(model, clip)

        # folder_paths.get_full_path("loras", lora_name) + comfy.utils.load_torch_file + comfy.sd.load_lora_for_models
        lora = await sdk.ctx().assets.resolve("loras", lora_name)
        model_lora, clip_lora = await _load_lora_for_models(model, clip, lora, strength_model, strength_clip)
        return io.NodeOutput(model_lora, clip_lora)


async def _load_lora_for_models(model, clip, lora, strength_model, strength_clip):
    """comfy.sd.load_lora_for_models through ModelRef.apply_lora (the corpus' comfyui-easy-use r3 pattern).

    The native loader ignores strength_clip when there is no CLIP; the SDK requires it to be zero then. Where
    apply_lora takes skip_zero / allow_extended_strengths (base 0cd9adec), the native loader's behaviour is kept for
    every strength. Base 0b86765f's apply_lora takes neither: there strengths outside [-100, 100] (or not finite) are
    refused by name, and a LoRA whose effective strengths are both zero returns the inputs (the original returns a
    zero-strength clone, which computes the same values).
    """
    if clip is None:
        strength_clip = 0.0
    if {"skip_zero", "allow_extended_strengths"} <= set(inspect.signature(model.apply_lora).parameters):
        return await model.apply_lora(lora, clip, strength_model, strength_clip, skip_zero=False,
                                      allow_extended_strengths=True)
    return await model.apply_lora(lora, clip, strength_model, strength_clip)


NODE_CLASS_MAPPINGS = {
    "SDXL Resolutions (JPS)": SDXL_Resolutions,
    "Text Prompt (JPS)": Text_Prompt,
    "Text Prompt Combo (JPS)": Text_Prompt_Combo,
    "SDXL Prompt Handling (JPS)": SDXL_Prompt_Handling,
    "Resolution Multiply (JPS)": Math_Resolution_Multiply,
    "Largest Int (JPS)": Math_Largest_Integer,
    "Multiply Int Float (JPS)": Math_Multiply_INT_FLOAT,
    "Text Concatenate (JPS)": Text_Concatenate,
    "Get Date Time String (JPS)": Get_Date_Time_String,
    "Sampler Scheduler Settings (JPS)": Sampler_Scheduler_Settings,
    "Integer Switch (JPS)": Integer_Switch,
    "Get Image Size (JPS)": Get_Image_Size,
    "Model Switch (JPS)": Model_Switch,
    "Latent Switch (JPS)": Latent_Switch,
    "Lora Loader (JPS)": IO_Lora_Loader,
}
