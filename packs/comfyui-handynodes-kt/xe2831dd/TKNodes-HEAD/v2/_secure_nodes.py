"""Complete 29-entry draft V3 surface, with algorithms retained pack-side."""
import torch
from comfy_api.latest import io, sdk
from . import _algorithms, _broker, _limits
from ._speaker_algorithms import TKLocateSpeakersUsingSilenceBreaks

TYPES = {"STRING": io.String, "INT": io.Int, "FLOAT": io.Float,
         "BOOLEAN": io.Boolean, "IMAGE": io.Image, "AUDIO": io.Audio,
         "*": io.AnyType, "TK_IMAGE_LIST": io.Custom("TK_IMAGE_LIST"),
         "TK_IMAGE_PROMPT_LIST": io.Custom("TK_IMAGE_PROMPT_LIST")}
SCALARS = {"TKPromptEnhanced", "TKVideoUserInputs", "TKPhotoUserInputs",
           "TKVideoUserInputsBasic", "TKCalcLTXFrames", "TKTotalTracksInAudio",
           "TKAudioSpeakerTalkTime", "TKSnapFrames"}

class MultiPrompt:
    DESCRIPTION = "Used for purpose of looping thru a collection of Images and Prompts.  Note: you can also chain these if you need more prompts.  Requires for start/end workflow. You will need PromptLooperAdv to process this prompts"
    CATEGORY = "TKNodes/image"
    RETURN_TYPES = ("TK_IMAGE_PROMPT_LIST",)
    RETURN_NAMES = ("image_prompt_list",)
    NUM_SLOTS = 4
    @classmethod
    def INPUT_TYPES(cls):
        rows = {}
        for slot in range(1, cls.NUM_SLOTS + 1):
            rows["prompt_" + str(slot)] = ("STRING", {"multiline": True, "default": ""})
            rows["image_" + str(slot)] = ([""], {})
        return {"required": rows, "optional": {"image_prompt_list": ("TK_IMAGE_PROMPT_LIST",)}}

class MultiSelect:
    DESCRIPTION = "Used for purpose of selecting up to 12 images to feed into a Looping workflow. Use PromptLooperAdv to select the desired image. "
    CATEGORY = "TKNodes/image"
    RETURN_TYPES = ("TK_IMAGE_LIST",)
    RETURN_NAMES = ("image_list",)
    NUM_SLOTS = 12
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"image_" + str(slot): ([""], {}) for slot in range(1, 13)}}

SOURCES = dict(_algorithms.NODE_CLASS_MAPPINGS)
SOURCES.update(TKLocateSpeakersUsingSilenceBreaks=TKLocateSpeakersUsingSilenceBreaks,
               TKMultiImagePrompt=MultiPrompt, TKMultiImageSelect=MultiSelect)
_algorithms.detect_silence = _limits.detect_silence

def typed_input(name, spec, optional=False, node_id=""):
    kind = spec[0]
    options = dict(spec[1]) if len(spec) > 1 else {}
    if type(kind) is list:
        remote = io.RemoteOptions("/secure-nodes/assets/input?kind=image", True, static_options=[""], initial_selection="first") if name.startswith("image_") and node_id in ("TKMultiImagePrompt", "TKMultiImageSelect") else None
        return io.Combo.Input(name, options=kind, optional=optional, remote=remote, extra_dict=options)
    constructor = {}
    for key in ("default", "min", "max", "step", "multiline", "tooltip", "lazy"):
        if key in options:
            constructor[key] = options.pop(key)
    if "forceInput" in options:
        constructor["force_input"] = options.pop("forceInput")
    return TYPES[kind].Input(name, optional=optional, extra_dict=options, **constructor)

def schema(source, node_id):
    spec = source.INPUT_TYPES()
    names = getattr(source, "RETURN_NAMES", source.RETURN_TYPES)
    lists = getattr(source, "OUTPUT_IS_LIST", [False] * len(source.RETURN_TYPES))
    return io.Schema(node_id=node_id,
        display_name=_algorithms.NODE_DISPLAY_NAME_MAPPINGS[node_id],
        category=source.CATEGORY, description=getattr(source, "DESCRIPTION", ""),
        inputs=[typed_input(name, value, section == "optional", node_id)
                for section, rows in spec.items() for name, value in rows.items()],
        outputs=[TYPES[kind].Output(display_name=name, is_output_list=flag)
                 for kind, name, flag in zip(source.RETURN_TYPES, names, lists)],
        is_input_list=getattr(source, "INPUT_IS_LIST", False),
        is_output_node=getattr(source, "OUTPUT_NODE", False))

async def print_projection(value, budget=None):
    if budget is None:
        budget = {"bytes": 0, "text": 0, "items": 0}
    if isinstance(value, sdk.TensorRef):
        projected = await value.raw()
        _limits.value_work(projected, _budget=budget)
        return projected
    if isinstance(value, sdk.Ref):
        return value  # Managed diagnostic only; never recover a live host object.
    if type(value) is dict:
        return {key: await print_projection(item, budget) for key, item in value.items()}
    if type(value) in (tuple, list):
        return type(value)([await print_projection(item, budget) for item in value])
    return value

def make(source, node_id):
    class Secure(io.ComfyNode):
        SDK_REFS = node_id == "TKPrintValueToLog"
        SDK_PERMISSIONS = ("assets", "raw") if node_id in ("TKMultiImagePrompt", "TKMultiImageSelect") else () if node_id in SCALARS else ("raw",)
        @classmethod
        def define_schema(cls):
            return schema(source, node_id)
        @classmethod
        async def execute(cls, **kwargs):
            _limits.preflight(node_id, kwargs)
            with _limits.scope():
                if node_id == "TKPrintValueToLog":
                    projected = {**kwargs, "value": await print_projection(kwargs["value"])}
                    _limits.value_work(projected)
                    getattr(source(), source.FUNCTION)(**projected)
                    result = (kwargs["value"],)  # Return original typed handles/tree.
                elif node_id in ("TKMultiImagePrompt", "TKMultiImageSelect"):
                    result = await _broker.collect(node_id, kwargs)
                elif node_id == "TKLocateSpeakersUsingSilenceBreaks":
                    result = _broker.locate(kwargs)
                else:
                    if node_id == "TKMergeAudioList":
                        kwargs["audio_list"] = [
                            {**item, "waveform": item["waveform"].clone()}
                            for item in kwargs["audio_list"]]
                    result = getattr(source(), source.FUNCTION)(**kwargs)
            _limits.value_work(result)
            if type(result) is dict and "result" in result:
                return io.NodeOutput(*result["result"], ui=result.get("ui"))
            return io.NodeOutput(*result)
    Secure.__name__ = node_id + "Secure"
    globals()[Secure.__name__] = Secure
    if node_id in ("TKMultiImagePrompt", "TKMultiImageSelect"):
        async def fingerprint(cls, **kwargs):
            return await _broker.fingerprint(node_id, kwargs)
        Secure.fingerprint_inputs = classmethod(fingerprint)
    return Secure

NODE_CLASS_MAPPINGS = {node_id: make(source, node_id) for node_id, source in SOURCES.items()}
NODE_DISPLAY_NAME_MAPPINGS = dict(_algorithms.NODE_DISPLAY_NAME_MAPPINGS)
