"""Native Single/ByName LoRA descriptors through confined public assets."""
import json
import posixpath
import struct
from comfy_api.latest import io, sdk
from .secure_lora_multi_nodes import _logical_name, _strength


def _tail():
    return [
        io.Custom("WANVIDLORA").Input("prev_lora", optional=True, tooltip="For loading multiple LoRAs"),
        io.Custom("SELECTEDBLOCKS").Input("blocks", optional=True),
        io.Boolean.Input("low_mem_load", default=False, optional=True,
                         tooltip="Load the LORA model with less VRAM usage, slower loading. This affects ALL LoRAs, not just the current one. No effect if merge_loras is False"),
        io.Boolean.Input("merge_loras", default=True, optional=True,
                         tooltip="Merge LoRAs into the model, otherwise they are loaded on the fly. Always disabled for GGUF and scaled fp8 models. This affects ALL LoRAs, not just the current one"),
    ]


async def _metadata(context, asset):
    # SafeTensors metadata is a UTF-8 JSON header, not model tensor data.
    # Public ranged reads avoid exposing or opening the host asset path.
    try:
        prefix = await context.assets.read_range(asset, offset=0, length=8)
        if len(prefix) != 8:
            raise ValueError("Truncated SafeTensors header length")
        length = struct.unpack("<Q", prefix)[0]
        if not 2 <= length <= 16 * 1024 * 1024:
            raise ValueError("SafeTensors metadata header exceeds 16 MiB")
        raw = await context.assets.read_range(asset, offset=8, length=length)
        if len(raw) != length:
            raise ValueError("Truncated SafeTensors header")
        header = json.loads(raw)
        values = header.get("__metadata__", {})
        if not isinstance(values, dict) or not all(isinstance(key, str) and isinstance(value, str) for key, value in values.items()):
            raise ValueError("SafeTensors metadata must contain string keys and values")
        return values
    except Exception as error:
        # Native selectors keep their descriptor when optional metadata fails.
        print("Could not load Wan LoRA metadata:", type(error).__name__)
        return {}


async def _select(lora, strength, blocks, prev_lora, low_mem_load, merge_loras):
    strength = _strength(strength)
    loras = list(prev_lora) if prev_lora is not None else []
    if len(loras) > 10001:
        raise ValueError("Wan previous LoRA list exceeds 10001 entries")
    # Native Single returns [] for scalar zero, preserving predecessor rows.
    # A list schedule, including an empty one, does not take this branch.
    if not isinstance(strength, list) and strength == 0.0:
        return io.NodeOutput(loras)
    if not lora or not _logical_name(lora):
        raise ValueError("Wan LoRA names must be confined logical catalogue names")
    context = sdk.current_context()
    asset = await context.assets.resolve("loras", lora)
    metadata = await _metadata(context, asset)
    blocks = {} if blocks is None else blocks
    loras.append({"path": lora, "strength": strength, "name": posixpath.splitext(lora)[0],
                  "blocks": blocks.get("selected_blocks", {}), "layer_filter": blocks.get("layer_filter", ""),
                  "low_mem_load": low_mem_load if merge_loras else False, "merge_loras": merge_loras})
    # The owned frontend renders text into its own details/table. The descriptor
    # wire remains unchanged, and no native PromptServer or host HTML is used.
    return io.NodeOutput(loras, ui={"wan_lora_metadata": [metadata]} if metadata else None)


class WanVideoLoraSelect(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("assets",)

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="WanVideoLoraSelect", display_name="WanVideo Lora Select",
                         category="WanVideoWrapper", description="Select a LoRA model from ComfyUI/models/loras",
                         inputs=[io.Combo.Input("lora", options=[],
                                                tooltip="LORA models are expected to be in ComfyUI/models/loras with .safetensors extension",
                                                remote=io.RemoteOptions(route="/models/loras", refresh_button=True, control_after_refresh="first")),
                                 io.Float.Input("strength", default=1.0, min=-1000.0, max=1000.0, step=0.0001,
                                                tooltip="LORA strength, set to 0.0 to unmerge the LORA"), *_tail()],
                         outputs=[io.Custom("WANVIDLORA").Output(display_name="lora")], hidden=[io.Hidden.unique_id])

    @classmethod
    def validate_inputs(cls, input_types=None, **kwargs):
        name = kwargs.get("lora")
        if name is not None and (not name or not _logical_name(name)):
            return "Wan LoRA names must be confined logical catalogue names"
        if "strength" in kwargs:
            try:
                _strength(kwargs["strength"])
            except ValueError as error:
                return str(error)
        return True

    @classmethod
    async def execute(cls, lora, strength, blocks=None, prev_lora=None, low_mem_load=False, merge_loras=True):
        return await _select(lora, strength, blocks, prev_lora, low_mem_load, merge_loras)


class WanVideoLoraSelectByName(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("assets",)

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="WanVideoLoraSelectByName", display_name="WanVideo Lora Select By Name",
                         category="WanVideoWrapper", description="Select a LoRA model from ComfyUI/models/loras",
                         inputs=[io.String.Input("lora_name", default="", multiline=False, tooltip="Lora filename to load"),
                                 io.Float.Input("strength", default=1.0, min=-10.0, max=10.0, step=0.0001,
                                                tooltip="LORA strength, set to 0.0 to unmerge the LORA"), *_tail()],
                         outputs=[io.Custom("WANVIDLORA").Output(display_name="lora")], hidden=[io.Hidden.unique_id])

    @classmethod
    def validate_inputs(cls, **kwargs):
        name = kwargs.get("lora_name", "")
        if not isinstance(name, str) or len(name.encode("utf-8")) > 4096 or "\x00" in name:
            return "Wan LoRA name search requires at most 4096 UTF-8 bytes"
        if "strength" in kwargs:
            try:
                _strength(kwargs["strength"])
            except ValueError as error:
                return str(error)
        return True

    @classmethod
    async def execute(cls, lora_name, strength, blocks=None, prev_lora=None, low_mem_load=False, merge_loras=True):
        if cls.validate_inputs(lora_name=lora_name, strength=strength) is not True:
            raise ValueError("Invalid Wan LoRA name search or strength")
        names = await sdk.current_context().assets.list("loras")
        if len(names) > 16384:
            raise ValueError("Wan LoRA catalogue exceeds 16384 names")
        selected = "none"
        # Preserve native last-substring-match selection, including empty search.
        for name in names:
            if lora_name in name:
                selected = name
        return await _select(selected, strength, blocks, prev_lora, low_mem_load, merge_loras)


NODE_CLASS_MAPPINGS = {"WanVideoLoraSelect": WanVideoLoraSelect, "WanVideoLoraSelectByName": WanVideoLoraSelectByName}
