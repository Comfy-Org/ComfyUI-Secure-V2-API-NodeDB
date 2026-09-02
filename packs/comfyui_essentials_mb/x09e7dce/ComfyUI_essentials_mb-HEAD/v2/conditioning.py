import re
import torch
from ._v2 import custom, io, sdk

MAX_RESOLUTION = io.MAX_RESOLUTION


class ConditioningZeroOut:
    def zero_out(self, conditioning):
        output = []
        for tensor, metadata in conditioning:
            metadata = metadata.copy()
            for name in ("pooled_output", "conditioning_lyrics"):
                if metadata.get(name) is not None:
                    metadata[name] = torch.zeros_like(metadata[name])
            output.append([torch.zeros_like(tensor), metadata])
        return (output,)


class ConditioningSetTimestepRange:
    def set_range(self, conditioning, start, end):
        output = []
        for tensor, metadata in conditioning:
            metadata = metadata.copy()
            metadata.update({"start_percent": start, "end_percent": end})
            output.append([tensor, metadata])
        return (output,)


class ConditioningCombine:
    def combine(self, conditioning_1, conditioning_2):
        return (conditioning_1 + conditioning_2,)

class CLIPTextEncodeSDXLSimplified:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {
            "width": ("INT", {"default": 1024.0, "min": 0, "max": MAX_RESOLUTION}),
            "height": ("INT", {"default": 1024.0, "min": 0, "max": MAX_RESOLUTION}),
            "size_cond_factor": ("INT", {"default": 4, "min": 1, "max": 16 }),
            "text": ("STRING", {"multiline": True, "dynamicPrompts": True, "default": ""}),
            "clip": ("CLIP", ),
            }}
    RETURN_TYPES = ("CONDITIONING",)
    FUNCTION = "execute"
    CATEGORY = "essentials_mb/conditioning"

    def execute(self, clip, width, height, size_cond_factor, text):
        crop_w = 0
        crop_h = 0
        width = width*size_cond_factor
        height = height*size_cond_factor
        target_width = width
        target_height = height
        text_g = text_l = text

        tokens = clip.tokenize(text_g)
        tokens["l"] = clip.tokenize(text_l)["l"]
        if len(tokens["l"]) != len(tokens["g"]):
            empty = clip.tokenize("")
            while len(tokens["l"]) < len(tokens["g"]):
                tokens["l"] += empty["l"]
            while len(tokens["l"]) > len(tokens["g"]):
                tokens["g"] += empty["g"]
        cond, pooled = clip.encode_from_tokens(tokens, return_pooled=True)
        return ([[cond, {"pooled_output": pooled, "width": width, "height": height, "crop_w": crop_w, "crop_h": crop_h, "target_width": target_width, "target_height": target_height}]], )

class ConditioningCombineMultiple:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "conditioning_1": ("CONDITIONING",),
                "conditioning_2": ("CONDITIONING",),
            }, "optional": {
                "conditioning_3": ("CONDITIONING",),
                "conditioning_4": ("CONDITIONING",),
                "conditioning_5": ("CONDITIONING",),
            },
        }
    RETURN_TYPES = ("CONDITIONING",)
    FUNCTION = "execute"
    CATEGORY = "essentials_mb/conditioning"

    def execute(self, conditioning_1, conditioning_2, conditioning_3=None, conditioning_4=None, conditioning_5=None):
        c = conditioning_1 + conditioning_2

        if conditioning_3 is not None:
            c += conditioning_3
        if conditioning_4 is not None:
            c += conditioning_4
        if conditioning_5 is not None:
            c += conditioning_5

        return (c,)

class SD3NegativeConditioning:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {
            "conditioning": ("CONDITIONING",),
            "end": ("FLOAT", {"default": 0.1, "min": 0.0, "max": 1.0, "step": 0.001 }),
        }}
    RETURN_TYPES = ("CONDITIONING",)
    FUNCTION = "execute"
    CATEGORY = "essentials_mb/conditioning"

    def execute(self, conditioning, end):
        zero_c = ConditioningZeroOut().zero_out(conditioning)[0]

        if end == 0:
            return (zero_c, )

        c = ConditioningSetTimestepRange().set_range(conditioning, 0, end)[0]
        zero_c = ConditioningSetTimestepRange().set_range(zero_c, end, 1.0)[0]
        c = ConditioningCombine().combine(zero_c, c)[0]

        return (c, )

class FluxAttentionSeeker:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {
            "clip": ("CLIP",),
            "apply_to_query": ("BOOLEAN", { "default": True }),
            "apply_to_key": ("BOOLEAN", { "default": True }),
            "apply_to_value": ("BOOLEAN", { "default": True }),
            "apply_to_out": ("BOOLEAN", { "default": True }),
            **{f"clip_l_{s}": ("FLOAT", { "display": "slider", "default": 1.0, "min": 0, "max": 5, "step": 0.05 }) for s in range(12)},
            **{f"t5xxl_{s}": ("FLOAT", { "display": "slider", "default": 1.0, "min": 0, "max": 5, "step": 0.05 }) for s in range(24)},
        }}

    RETURN_TYPES = ("CLIP",)
    FUNCTION = "execute"

    CATEGORY = "essentials_mb/conditioning"

    def execute(self, clip, apply_to_query, apply_to_key, apply_to_value, apply_to_out, **values):
        if not apply_to_key and not apply_to_query and not apply_to_value and not apply_to_out:
            return (clip, )

        m = clip.clone()
        sd = m.patcher.model_state_dict()
        
        for k in sd:
            if "self_attn" in k:
                layer = re.search(r"\.layers\.(\d+)\.", k)
                layer = int(layer.group(1)) if layer else None

                if layer is not None and values[f"clip_l_{layer}"] != 1.0:
                    if (apply_to_query and "q_proj" in k) or (apply_to_key and "k_proj" in k) or (apply_to_value and "v_proj" in k) or (apply_to_out and "out_proj" in k):
                        m.add_patches({k: (None,)}, 0.0, values[f"clip_l_{layer}"])
            elif "SelfAttention" in k:
                block = re.search(r"\.block\.(\d+)\.", k)
                block = int(block.group(1)) if block else None

                if block is not None and values[f"t5xxl_{block}"] != 1.0:
                    if (apply_to_query and ".q." in k) or (apply_to_key and ".k." in k) or (apply_to_value and ".v." in k) or (apply_to_out and ".o." in k):
                        m.add_patches({k: (None,)}, 0.0, values[f"t5xxl_{block}"])

        return (m, )

class SD3AttentionSeekerLG:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {
            "clip": ("CLIP",),
            "apply_to_query": ("BOOLEAN", { "default": True }),
            "apply_to_key": ("BOOLEAN", { "default": True }),
            "apply_to_value": ("BOOLEAN", { "default": True }),
            "apply_to_out": ("BOOLEAN", { "default": True }),
            **{f"clip_l_{s}": ("FLOAT", { "display": "slider", "default": 1.0, "min": 0, "max": 5, "step": 0.05 }) for s in range(12)},
            **{f"clip_g_{s}": ("FLOAT", { "display": "slider", "default": 1.0, "min": 0, "max": 5, "step": 0.05 }) for s in range(32)},
        }}

    RETURN_TYPES = ("CLIP",)
    FUNCTION = "execute"

    CATEGORY = "essentials_mb/conditioning"

    def execute(self, clip, apply_to_query, apply_to_key, apply_to_value, apply_to_out, **values):
        if not apply_to_key and not apply_to_query and not apply_to_value and not apply_to_out:
            return (clip, )

        m = clip.clone()
        sd = m.patcher.model_state_dict()
        
        for k in sd:
            if "self_attn" in k:
                layer = re.search(r"\.layers\.(\d+)\.", k)
                layer = int(layer.group(1)) if layer else None

                if layer is not None:
                    if "clip_l" in k and values[f"clip_l_{layer}"] != 1.0:
                        if (apply_to_query and "q_proj" in k) or (apply_to_key and "k_proj" in k) or (apply_to_value and "v_proj" in k) or (apply_to_out and "out_proj" in k):
                            m.add_patches({k: (None,)}, 0.0, values[f"clip_l_{layer}"])
                    elif "clip_g" in k and values[f"clip_g_{layer}"] != 1.0:
                        if (apply_to_query and "q_proj" in k) or (apply_to_key and "k_proj" in k) or (apply_to_value and "v_proj" in k) or (apply_to_out and "out_proj" in k):
                            m.add_patches({k: (None,)}, 0.0, values[f"clip_g_{layer}"])

        return (m, )

class SD3AttentionSeekerT5:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {
            "clip": ("CLIP",),
            "apply_to_query": ("BOOLEAN", { "default": True }),
            "apply_to_key": ("BOOLEAN", { "default": True }),
            "apply_to_value": ("BOOLEAN", { "default": True }),
            "apply_to_out": ("BOOLEAN", { "default": True }),
            **{f"t5xxl_{s}": ("FLOAT", { "display": "slider", "default": 1.0, "min": 0, "max": 5, "step": 0.05 }) for s in range(24)},
        }}

    RETURN_TYPES = ("CLIP",)
    FUNCTION = "execute"

    CATEGORY = "essentials_mb/conditioning"

    def execute(self, clip, apply_to_query, apply_to_key, apply_to_value, apply_to_out, **values):
        if not apply_to_key and not apply_to_query and not apply_to_value and not apply_to_out:
            return (clip, )

        m = clip.clone()
        sd = m.patcher.model_state_dict()
        
        for k in sd:
            if "SelfAttention" in k:
                block = re.search(r"\.block\.(\d+)\.", k)
                block = int(block.group(1)) if block else None

                if block is not None and values[f"t5xxl_{block}"] != 1.0:
                    if (apply_to_query and ".q." in k) or (apply_to_key and ".k." in k) or (apply_to_value and ".v." in k) or (apply_to_out and ".o." in k):
                        m.add_patches({k: (None,)}, 0.0, values[f"t5xxl_{block}"])

        return (m, )

class FluxBlocksBuster:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {
            "model": ("MODEL",),
            "blocks": ("STRING", {"default": "## 0 = 1.0\n## 1 = 1.0\n## 2 = 1.0\n## 3 = 1.0\n## 4 = 1.0\n## 5 = 1.0\n## 6 = 1.0\n## 7 = 1.0\n## 8 = 1.0\n## 9 = 1.0\n## 10 = 1.0\n## 11 = 1.0\n## 12 = 1.0\n## 13 = 1.0\n## 14 = 1.0\n## 15 = 1.0\n## 16 = 1.0\n## 17 = 1.0\n## 18 = 1.0\n# 0 = 1.0\n# 1 = 1.0\n# 2 = 1.0\n# 3 = 1.0\n# 4 = 1.0\n# 5 = 1.0\n# 6 = 1.0\n# 7 = 1.0\n# 8 = 1.0\n# 9 = 1.0\n# 10 = 1.0\n# 11 = 1.0\n# 12 = 1.0\n# 13 = 1.0\n# 14 = 1.0\n# 15 = 1.0\n# 16 = 1.0\n# 17 = 1.0\n# 18 = 1.0\n# 19 = 1.0\n# 20 = 1.0\n# 21 = 1.0\n# 22 = 1.0\n# 23 = 1.0\n# 24 = 1.0\n# 25 = 1.0\n# 26 = 1.0\n# 27 = 1.0\n# 28 = 1.0\n# 29 = 1.0\n# 30 = 1.0\n# 31 = 1.0\n# 32 = 1.0\n# 33 = 1.0\n# 34 = 1.0\n# 35 = 1.0\n# 36 = 1.0\n# 37 = 1.0", "multiline": True, "dynamicPrompts": True}),
            #**{f"double_block_{s}": ("FLOAT", { "display": "slider", "default": 1.0, "min": 0, "max": 5, "step": 0.05 }) for s in range(19)},
            #**{f"single_block_{s}": ("FLOAT", { "display": "slider", "default": 1.0, "min": 0, "max": 5, "step": 0.05 }) for s in range(38)},
        }}
    RETURN_TYPES = ("MODEL", "STRING")
    RETURN_NAMES = ("MODEL", "patched_blocks")
    FUNCTION = "patch"

    CATEGORY = "essentials_mb/conditioning"

    def patch(self, model, blocks):
        if blocks == "":
            return (model, )

        m = model.clone()
        sd = model.model_state_dict()
        patched_blocks = []

        r"""
        Also compatible with the following format:

        double_blocks\.0\.(img|txt)_(mod|attn|mlp)\.(lin|qkv|proj|0|2)\.(weight|bias)=1.1
        single_blocks\.0\.(linear[12]|modulation\.lin)\.(weight|bias)=1.1

        The regex is used to match the block names
        """

        blocks = blocks.split("\n")
        blocks = [b.strip() for b in blocks if b.strip()]

        for k in sd:
            for block in blocks:
                block = block.split("=")
                value = float(block[1].strip()) if len(block) > 1 else 1.0
                block = block[0].strip()
                if block.startswith("##"):
                    block = r"double_blocks\." + block[2:].strip() + r"\.(img|txt)_(mod|attn|mlp)\.(lin|qkv|proj|0|2)\.(weight|bias)"
                elif block.startswith("#"):
                    block = r"single_blocks\." + block[1:].strip() + r"\.(linear[12]|modulation\.lin)\.(weight|bias)"

                if value != 1.0 and re.search(block, k):
                    m.add_patches({k: (None,)}, 0.0, value)
                    patched_blocks.append(f"{k}: {value}")

        patched_blocks = "\n".join(patched_blocks)

        return (m, patched_blocks,)


COND_CLASS_MAPPINGS = {
    "CLIPTextEncodeSDXL+": CLIPTextEncodeSDXLSimplified,
    "ConditioningCombineMultiple+": ConditioningCombineMultiple,
    "SD3NegativeConditioning+": SD3NegativeConditioning,
    "FluxAttentionSeeker+": FluxAttentionSeeker,
    "SD3AttentionSeekerLG+": SD3AttentionSeekerLG,
    "SD3AttentionSeekerT5+": SD3AttentionSeekerT5,
    "FluxBlocksBuster+": FluxBlocksBuster,
}


async def _clip_text_encode_sdxl_v2(
    cls, clip, width, height, size_cond_factor, text
):
    width = width * size_cond_factor
    height = height * size_cond_factor
    tokens = await clip.tokenize(text)
    tokens["l"] = (await clip.tokenize(text))["l"]
    if len(tokens["l"]) != len(tokens["g"]):
        empty = await clip.tokenize("")
        while len(tokens["l"]) < len(tokens["g"]):
            tokens["l"] += empty["l"]
        while len(tokens["l"]) > len(tokens["g"]):
            tokens["g"] += empty["g"]
    conditioning = await clip.encode_from_tokens_scheduled(
        tokens,
        add_dict={
            "width": width,
            "height": height,
            "crop_w": 0,
            "crop_h": 0,
            "target_width": width,
            "target_height": height,
        },
    )
    return io.NodeOutput(conditioning)


async def _conditioning_combine_multiple_v2(
    cls, conditioning_1, conditioning_2, conditioning_3=None,
    conditioning_4=None, conditioning_5=None
):
    output = await conditioning_1.combine(conditioning_2)
    for item in (conditioning_3, conditioning_4, conditioning_5):
        if item is not None:
            output = await output.combine(item)
    return io.NodeOutput(output)


async def _sd3_negative_conditioning_v2(cls, conditioning, end):
    source = await conditioning.value()
    zero = ConditioningZeroOut().zero_out(source)[0]
    if end == 0:
        output = zero
    else:
        active = ConditioningSetTimestepRange().set_range(
            source, 0, end
        )[0]
        zero = ConditioningSetTimestepRange().set_range(
            zero, end, 1.0
        )[0]
        output = zero + active
    return io.NodeOutput(await sdk.CondRef.from_value(output))


async def _attention_scale_v2(
    clip, apply_to_query, apply_to_key, apply_to_value, apply_to_out,
    *, clip_l=None, clip_g=None, t5xxl=None
):
    if not any((apply_to_query, apply_to_key, apply_to_value, apply_to_out)):
        return clip
    return await clip.scale_attention_weights(
        clip_l=clip_l,
        clip_g=clip_g,
        t5xxl=t5xxl,
        query=apply_to_query,
        key=apply_to_key,
        value=apply_to_value,
        output=apply_to_out,
    )


async def _flux_attention_seeker_v2(
    cls, clip, apply_to_query, apply_to_key, apply_to_value, apply_to_out,
    **values
):
    output = await _attention_scale_v2(
        clip, apply_to_query, apply_to_key, apply_to_value, apply_to_out,
        clip_l=[values[f"clip_l_{index}"] for index in range(12)],
        t5xxl=[values[f"t5xxl_{index}"] for index in range(24)],
    )
    return io.NodeOutput(output)


async def _sd3_attention_lg_v2(
    cls, clip, apply_to_query, apply_to_key, apply_to_value, apply_to_out,
    **values
):
    output = await _attention_scale_v2(
        clip, apply_to_query, apply_to_key, apply_to_value, apply_to_out,
        clip_l=[values[f"clip_l_{index}"] for index in range(12)],
        clip_g=[values[f"clip_g_{index}"] for index in range(32)],
    )
    return io.NodeOutput(output)


async def _sd3_attention_t5_v2(
    cls, clip, apply_to_query, apply_to_key, apply_to_value, apply_to_out,
    **values
):
    output = await _attention_scale_v2(
        clip, apply_to_query, apply_to_key, apply_to_value, apply_to_out,
        t5xxl=[values[f"t5xxl_{index}"] for index in range(24)],
    )
    return io.NodeOutput(output)


_DOUBLE_PATTERN = re.compile(
    r"double_blocks\\\.(\d+)\\\.\(img\|txt\)_\(mod\|attn\|mlp\)"
    r"\\\.\(lin\|qkv\|proj\|0\|2\)\\\.\(weight\|bias\)"
)
_SINGLE_PATTERN = re.compile(
    r"single_blocks\\\.(\d+)\\\.\(linear\[12\]\|modulation\\\.lin\)"
    r"\\\.\(weight\|bias\)"
)


def _parse_flux_blocks(source):
    double = [1.0] * 19
    single = [1.0] * 38
    report = []
    for raw_line in source.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        selector, separator, raw_value = line.partition("=")
        value = float(raw_value.strip()) if separator else 1.0
        if not 0.0 <= value <= 5.0:
            raise ValueError("Flux block scale must be in [0, 5]")
        selector = selector.strip()
        family = None
        index = None
        if selector.startswith("##"):
            family, index = "double", int(selector[2:].strip())
        elif selector.startswith("#"):
            family, index = "single", int(selector[1:].strip())
        else:
            match = _DOUBLE_PATTERN.fullmatch(selector)
            if match is not None:
                family, index = "double", int(match.group(1))
            else:
                match = _SINGLE_PATTERN.fullmatch(selector)
                if match is not None:
                    family, index = "single", int(match.group(1))
        target = double if family == "double" else single if family == "single" else None
        if target is None or index is None or not 0 <= index < len(target):
            raise ValueError(
                "Flux block selector must name double block 0-18 or "
                "single block 0-37"
            )
        target[index] = value
        if value != 1.0:
            report.append(f"{family}_blocks.{index}: {value}")
    return double, single, "\n".join(report)


async def _flux_blocks_buster_v2(cls, model, blocks):
    if not blocks.strip():
        return io.NodeOutput(model, "")
    double, single, report = _parse_flux_blocks(blocks)
    output = await model.patch(
        "flux_block_scales",
        double_blocks=double,
        single_blocks=single,
    )
    return io.NodeOutput(output, report)


_COND_CUSTOM = {
    "CLIPTextEncodeSDXL+": (_clip_text_encode_sdxl_v2, "CLIPTextEncodeSDXLV2", ()),
    "ConditioningCombineMultiple+": (
        _conditioning_combine_multiple_v2, "ConditioningCombineMultipleV2", ()
    ),
    "SD3NegativeConditioning+": (
        _sd3_negative_conditioning_v2, "SD3NegativeConditioningV2", ("raw",)
    ),
    "FluxAttentionSeeker+": (
        _flux_attention_seeker_v2, "FluxAttentionSeekerV2", ()
    ),
    "SD3AttentionSeekerLG+": (
        _sd3_attention_lg_v2, "SD3AttentionSeekerLGV2", ()
    ),
    "SD3AttentionSeekerT5+": (
        _sd3_attention_t5_v2, "SD3AttentionSeekerT5V2", ()
    ),
    "FluxBlocksBuster+": (_flux_blocks_buster_v2, "FluxBlocksBusterV2", ()),
}
COND_CLASS_MAPPINGS = {
    node_id: custom(
        node_id,
        execute,
        module=__name__,
        class_name=class_name,
        permissions=permissions,
    )
    for node_id, (execute, class_name, permissions) in _COND_CUSTOM.items()
}

COND_NAME_MAPPINGS = {
    "CLIPTextEncodeSDXL+": "🔧 SDXL CLIPTextEncode",
    "ConditioningCombineMultiple+": "🔧 Cond Combine Multiple",
    "SD3NegativeConditioning+": "🔧 SD3 Negative Conditioning",
    "FluxAttentionSeeker+": "🔧 Flux Attention Seeker",
    "SD3AttentionSeekerLG+": "🔧 SD3 Attention Seeker L/G",
    "SD3AttentionSeekerT5+": "🔧 SD3 Attention Seeker T5",
    "FluxBlocksBuster+": "🔧 Flux Model Blocks Buster",
}
