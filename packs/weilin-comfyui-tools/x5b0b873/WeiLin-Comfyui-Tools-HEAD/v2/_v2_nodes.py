"""The three WeiLin prompt nodes (Secure Nodes V2); see __init__.py."""
import json
import os
import posixpath
import re

from comfy_api.latest import io, sdk

from ._v2_refusals import RANDOM_TEMPLATE, SecureConversionRefusal
from ._v2_trigger_words import get_first_trigger_word

# The original's non-zh_CN strings (__init__.py:46-53)
placeholder_text = "input prompt words"
placeholder_lora_text = "Lora info box"
node_name_text = "WeiLin Node Tools"


def is_json(myjson):
    try:
        json.loads(myjson)
    except ValueError:
        return False
    return True


async def _lora_asset(lora):
    """folder_paths.get_full_path("loras", lora): the same name normalisation; None when no loras folder holds it."""
    name = posixpath.relpath(posixpath.join("/", lora), "/")
    if await sdk.ctx().assets.exists("loras", name):
        return name, await sdk.ctx().assets.resolve("loras", name)
    return name, None


async def _apply_lora(model, clip, asset, strength_model, strength_clip):
    """The original's load_lora_for_models (__init__.py:808-835) through the trusted LoRA op.

    skip_zero=False keeps the original's clone-and-patch at zero strength; allow_extended_strengths keeps
    its unchecked float strengths; with no CLIP the original ignored strength_clip.
    """
    return await model.apply_lora(asset, clip, strength_model, strength_clip if clip is not None else 0.0,
                                  skip_zero=False, allow_extended_strengths=True)


# 提示词UI


class WeiLinPromptUI(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("assets",)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="WeiLinPromptUI",
            display_name="All-Round WeiLin Prompt Editor",
            category=node_name_text,
            is_output_node=True,
            inputs=[
                io.String.Input("positive", multiline=True, default="", placeholder=placeholder_text),
                io.Boolean.Input("auto_random", default=False),
                io.String.Input("lora_str", multiline=True, default="", placeholder=placeholder_lora_text, optional=True),
                io.String.Input("temp_str", multiline=True, default="", placeholder="temp prompt words", optional=True),
                io.String.Input("temp_lora_str", multiline=True, default="", placeholder="temp prompt words", optional=True),
                io.String.Input("random_template", multiline=True, default="", placeholder="random template path name", optional=True),
                io.AnyType.Input("opt_text", optional=True, extra_dict={"default": ""}),
                io.Clip.Input("opt_clip", optional=True),
                io.Model.Input("opt_model", optional=True),
            ],
            outputs=[
                io.String.Output(display_name="STRING"),
                io.Conditioning.Output(display_name="CONDITIONING"),
                io.Clip.Output(display_name="CLIP"),
                io.Model.Output(display_name="MODEL"),
            ],
        )

    @classmethod
    def fingerprint_inputs(cls, auto_random=False, **kwargs):
        if auto_random:
            return float("nan")

    # 加载Lora
    @classmethod
    async def execute(
        cls,
        positive="",
        auto_random=False,
        lora_str="",
        temp_str="",
        temp_lora_str="",
        random_template="",
        opt_text="",
        opt_clip=None,
        opt_model=None,
    ):

        model_lora_secondA = opt_model
        clip_lora_secondA = opt_clip

        text_dec = ""
        lora_list = None

        if is_json(positive):
            json_object = json.loads(positive)
            lora_list = json_object.get("lora", None)
            if len(opt_text) > 0:
                text_dec = opt_text + ", " + json_object.get("prompt", "")
            else:
                text_dec = json_object.get("prompt", "")
        else:
            if len(opt_text) > 0:
                text_dec = opt_text + ", " + positive
            else:
                text_dec = positive
        if len(lora_str) > 0:
            json_object = json.loads(lora_str)
            lora_list = json_object

        if auto_random:
            if len(random_template) > 0:
                # Secure Nodes V2: was go_run_node_auto_random_tag(random_template) (app/server)
                raise SecureConversionRefusal(RANDOM_TEMPLATE.format(node="WeiLinPromptUI"))

        # 匹配两种格式：
        # 旧格式(3参数): <wlr:name:model_weight:clip_weight>
        # 新格式(4参数): <wlr:name:model_weight:clip_weight:trigger_weight>
        # 注意：必须先匹配新格式，再匹配旧格式，避免旧格式误匹配新格式标签
        wlr_pattern_new = r"<wlr:([^:]+):([^:]+):([^:]+):([^>]+)>"
        wlr_pattern_old = r"<wlr:([^:]+):([^:]+):([^:>]+)>"

        wlr_matches_new = re.findall(wlr_pattern_new, text_dec)

        # 从文本中移除新格式标签，再匹配旧格式，避免重复匹配
        text_dec_without_new = re.sub(wlr_pattern_new, "", text_dec)
        wlr_matches_old = re.findall(wlr_pattern_old, text_dec_without_new)

        # 如果找到了wlr标签，创建lora列表
        if wlr_matches_new or wlr_matches_old:
            extracted_loras = []

            # 处理新格式(4参数)
            for lora_path, model_weight, text_weight, trigger_weight in wlr_matches_new:
                extracted_loras.append(
                    {
                        "lora": lora_path.strip() + ".safetensors",
                        "weight": float(model_weight.strip()),
                        "text_encoder_weight": float(text_weight.strip()),
                        "trigger_weight": float(trigger_weight.strip()),
                    }
                )

            # 处理旧格式(3参数)
            for lora_path, model_weight, text_weight in wlr_matches_old:
                extracted_loras.append(
                    {
                        "lora": lora_path.strip() + ".safetensors",
                        "weight": float(model_weight.strip()),
                        "text_encoder_weight": float(text_weight.strip()),
                        "trigger_weight": float(
                            text_weight.strip()
                        ),  # 旧格式使用 clip_weight 作为 trigger_weight
                    }
                )

            # 从text_dec中移除这些标签
            clean_text_dec = re.sub(wlr_pattern_new, "", text_dec)
            clean_text_dec = re.sub(wlr_pattern_old, "", clean_text_dec)
            # 清理连续的逗号
            clean_text_dec = re.sub(r",\s*,", ",", clean_text_dec)
            # 清理开头和结尾的逗号
            clean_text_dec = clean_text_dec.strip().strip(",").strip()
            text_dec = clean_text_dec

            # 如果已经有lora_list，需要去重合并
            # 避免同一个Lora被重复处理（来自JSON的lora字段和prompt中的<wlr:...>标签）
            if lora_list is not None:
                # 获取已存在的lora名称集合
                existing_lora_names = {
                    item["lora"].replace(".safetensors", "") for item in lora_list
                }
                # 只添加不存在的lora
                for extracted in extracted_loras:
                    extracted_name = extracted["lora"].replace(".safetensors", "")
                    if extracted_name not in existing_lora_names:
                        lora_list.append(extracted)
            else:
                lora_list = extracted_loras

        # 当模型不为空时
        if opt_model is not None and lora_list is not None:
            # 收集所有触发词
            all_trigger_words = []

            for str_lora_item in lora_list:
                strength_model = float(str_lora_item["weight"])
                strength_clip = float(str_lora_item["text_encoder_weight"])
                # 获取触发词权重（用于提示词中的权重标记）
                trigger_weight = float(
                    str_lora_item.get("trigger_weight", strength_clip)
                )

                lora_file, lora_asset = await _lora_asset(str_lora_item["lora"])
                if lora_asset is None:
                    raise ValueError(f"无法找到Lora文件: {str_lora_item['lora']}")

                # 获取触发词
                lora_name = os.path.splitext(str_lora_item["lora"])[0]
                trigger_word = await get_first_trigger_word(lora_asset, lora_file, lora_name)

                # 收集触发词（带权重）
                if trigger_word:
                    # 格式: 触发词:触发词权重
                    trigger_with_weight = f"{trigger_word}:{trigger_weight}"
                    all_trigger_words.append(trigger_with_weight)

                model_lora_secondA, clip_lora_secondA = await _apply_lora(
                    model_lora_secondA,
                    clip_lora_secondA,
                    lora_asset,
                    strength_model,
                    strength_clip,
                )

            # 将所有触发词添加到提示词开头
            if all_trigger_words:
                trigger_text = ", ".join(all_trigger_words) + ", "
                text_dec = trigger_text + text_dec

        conditioning_output = None
        if opt_clip is not None:
            try:
                # Secure Nodes V2: the original built [[cond, pooled]] from encode_from_tokens(...,
                # return_pooled=True, return_dict=True); without hooks encode_from_tokens_scheduled
                # returns the same (core comfy/sd.py:340-350).
                tokensA = await clip_lora_secondA.tokenize(text_dec)
                conditioning_output = await clip_lora_secondA.encode_from_tokens_scheduled(tokensA)
            except Exception as e:
                print(f"[ERROR] CONDITIONING编码失败: {e}")
                conditioning_output = None

        if auto_random:
            return io.NodeOutput(text_dec, conditioning_output, clip_lora_secondA, model_lora_secondA,
                                 ui={"positive": [str(positive)]})
        return io.NodeOutput(text_dec, conditioning_output, clip_lora_secondA, model_lora_secondA)


# 提示词UI - 仅使用Lora堆
class WeiLinPromptUIOnlyLoraStack(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("assets",)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="WeiLinPromptUIOnlyLoraStack",
            display_name="WeiLin Lora Stack",
            category=node_name_text,
            inputs=[
                io.Clip.Input("clip"),
                io.Model.Input("model"),
                io.String.Input("lora_str", multiline=True, default="", placeholder="lora info box", optional=True),
                io.String.Input("temp_lora_str", multiline=True, default="", placeholder="temp prompt words", optional=True),
            ],
            outputs=[
                io.Clip.Output(display_name="CLIP"),
                io.Model.Output(display_name="MODEL"),
            ],
        )

    # 加载Lora
    @classmethod
    async def execute(cls, clip=None, model=None, lora_str="", temp_lora_str=""):
        model_lora_secondA = model
        clip_lora_secondA = clip

        lora_list = None

        if len(lora_str) > 0:
            json_object = json.loads(lora_str)
            lora_list = json_object

        # 当模型不为空时
        if model is not None and lora_list is not None:
            for str_lora_item in lora_list:
                strength_model = float(str_lora_item["weight"])
                strength_clip = float(str_lora_item["text_encoder_weight"])

                lora_file, lora_asset = await _lora_asset(str_lora_item["lora"])
                if lora_asset is None:
                    raise ValueError(f"无法找到Lora文件: {str_lora_item['lora']}")

                model_lora_secondA, clip_lora_secondA = await _apply_lora(
                    model_lora_secondA,
                    clip_lora_secondA,
                    lora_asset,
                    strength_model,
                    strength_clip,
                )

        return io.NodeOutput(clip_lora_secondA, model_lora_secondA)


# 提示词UI - 不加载Lora


class WeiLinPromptUIWithoutLora(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="WeiLinPromptUIWithoutLora",
            display_name="WeiLin Prompt Editor",
            category=node_name_text,
            is_output_node=True,
            inputs=[
                io.String.Input("positive", multiline=True, default="", placeholder=placeholder_text),
                io.Boolean.Input("auto_random", default=False),
                io.String.Input("temp_str", multiline=True, default="", placeholder="temp prompt words", optional=True),
                io.String.Input("random_template", multiline=True, default="", placeholder="random template path name", optional=True),
                io.AnyType.Input("opt_text", optional=True, extra_dict={"default": ""}),
                io.Clip.Input("opt_clip", optional=True),
            ],
            outputs=[
                io.String.Output(display_name="STRING"),
                io.Conditioning.Output(display_name="CONDITIONING"),
                io.Clip.Output(display_name="CLIP"),
            ],
            hidden=[io.Hidden.unique_id, io.Hidden.extra_pnginfo],
        )

    @classmethod
    def fingerprint_inputs(cls, auto_random=False, **kwargs):
        if auto_random:
            return float("nan")

    @classmethod
    async def execute(
        cls,
        positive="",
        auto_random=False,
        temp_str="",
        random_template="",
        opt_text="",
        opt_clip=None,
    ):
        text_dec = ""
        if is_json(positive):
            json_object = json.loads(positive)
            if len(opt_text) > 0:
                text_dec = opt_text + ", " + json_object.get("prompt", "")
            else:
                text_dec = json_object.get("prompt", "")
        else:
            if len(opt_text) > 0:
                text_dec = opt_text + ", " + positive
            else:
                text_dec = positive

        if auto_random:
            if len(random_template) > 0:
                # Secure Nodes V2: was go_run_node_auto_random_tag(random_template) (app/server)
                raise SecureConversionRefusal(RANDOM_TEMPLATE.format(node="WeiLinPromptUIWithoutLora"))

        conditioning_output = None
        if opt_clip is not None:
            try:
                tokens = await opt_clip.tokenize(text_dec)
                conditioning_output = await opt_clip.encode_from_tokens_scheduled(tokens)
            except Exception as e:
                print(f"[ERROR] CONDITIONING编码失败: {e}")
                conditioning_output = None

        if auto_random:
            return io.NodeOutput(text_dec, conditioning_output, opt_clip, ui={"positive": [str(positive)]})
        return io.NodeOutput(text_dec, conditioning_output, opt_clip)
