"""Five ordered LoRA descriptors; only admitted logical asset names cross out."""
import math
import posixpath
from comfy_api.latest import io, sdk


def _logical_name(value):
    if not isinstance(value, str) or len(value.encode("utf-8")) > 4096:
        return False
    if "\x00" in value or "\\" in value or ":" in value or value.startswith("/"):
        return False
    return all(part not in (".", "..") for part in value.split("/"))


def _strength(value):
    values = value if isinstance(value, list) else [value]
    if len(values) > 10001:
        raise ValueError("Wan LoRA strength schedule exceeds10001values")
    if not all(isinstance(item, (int, float)) and math.isfinite(item) for item in values):
        raise ValueError("Wan LoRA strength requires finite numeric values")
    return value if isinstance(value, list) else round(value, 4)


class WanVideoLoraSelectMulti(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("assets",)

    @classmethod
    def define_schema(cls):
        inputs = []
        for index in range(5):
            # The pack UI populates names via the authenticated public model
            # catalogue while retaining this native sentinel/default. A raw
            # remote combo would replace none with the first actual model.
            inputs.extend([
                io.Combo.Input("lora_" + str(index), options=["none"], default="none"),
                io.Float.Input("strength_" + str(index), default=1.0, min=-10.0, max=10.0, step=0.0001,
                               tooltip="LORA strength, set to 0.0 to unmerge the LORA"),
            ])
        inputs.extend([
            io.Custom("WANVIDLORA").Input("prev_lora", optional=True, tooltip="For loading multiple LoRAs"),
            io.Custom("SELECTEDBLOCKS").Input("blocks", optional=True),
            io.Boolean.Input("low_mem_load", default=False, optional=True,
                             tooltip="Load the LORA model with less VRAM usage, slower loading. No effect if merge_loras is False"),
            io.Boolean.Input("merge_loras", default=True, optional=True,
                             tooltip="Merge LoRAs into the model, otherwise they are loaded on the fly. Always disabled for GGUF and scaled fp8 models. This affects ALL LoRAs, not just the current one"),
        ])
        return io.Schema(node_id="WanVideoLoraSelectMulti", display_name="WanVideo Lora Select Multi",
                         category="WanVideoWrapper", description="Select a LoRA model from ComfyUI/models/loras",
                         inputs=inputs, outputs=[io.Custom("WANVIDLORA").Output(display_name="lora")])

    @classmethod
    def validate_inputs(cls, input_types=None, **kwargs):
        # Host-safe validation bypasses the static sentinel list. This never
        # imports native pack code, resolves an asset or discovers a host path.
        for index in range(5):
            name = kwargs.get("lora_" + str(index), "none")
            if not _logical_name(name):
                return "Wan LoRA names must be confined logical catalogue names"
            value = kwargs.get("strength_" + str(index))
            if value is not None:
                try:
                    _strength(value)
                except ValueError as error:
                    return str(error)
        return True

    @classmethod
    async def execute(cls, lora_0, strength_0, lora_1, strength_1, lora_2, strength_2,
                      lora_3, strength_3, lora_4, strength_4, blocks=None, prev_lora=None,
                      low_mem_load=False, merge_loras=True):
        if not merge_loras:
            low_mem_load = False
        blocks = {} if blocks is None else blocks
        loras_list = list(prev_lora) if prev_lora else []
        if len(loras_list) > 10001:
            raise ValueError("Wan previous LoRA list exceeds10001entries")
        lora_inputs = [(lora_0, strength_0), (lora_1, strength_1), (lora_2, strength_2),
                       (lora_3, strength_3), (lora_4, strength_4)]
        for name, strength in lora_inputs:
            s = _strength(strength)
            if not name or name == "none" or s == 0.0:
                continue
            if not _logical_name(name):
                raise ValueError("Wan LoRA names must be confined logical catalogue names")
            # Existence and confinement remain authoritative broker decisions.
            # Discard its AssetRef rather than allowing host path unwrapping.
            await sdk.current_context().assets.resolve("loras", name)
            loras_list.append({"path": name, "strength": s, "name": posixpath.splitext(name)[0],
                               "blocks": blocks.get("selected_blocks", {}),
                               "layer_filter": blocks.get("layer_filter", ""),
                               "low_mem_load": low_mem_load, "merge_loras": merge_loras})
        return io.NodeOutput(None if len(loras_list) == 0 else loras_list)


NODE_CLASS_MAPPINGS = {"WanVideoLoraSelectMulti": WanVideoLoraSelectMulti}
