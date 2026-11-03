"""Trigger words for a LoRA, offline (Secure Nodes V2).

The original (app/server/prompt_api/trigger_words.py:376-505) tries, in order: Civitai's API by the
file's SHA-256, cached in ./loras_tags.json in the host's working directory; the safetensors metadata
ss_tag_frequency (by training count, non-generic tags first); ss_output_name; the file name. A V2 node
has no network at runtime and no host working directory, so it starts at the second step: what the
original returns offline when its cache has no entry for the LoRA. The functions below are the
original's, reading the safetensors header through the asset catalogue instead of open().
"""
import json
import re

from comfy_api.latest import sdk

_READ_MAX = 16 * 1024 * 1024  # AssetsDomain.read_range reads at most 16 MiB per call


def _is_common_tag(tag: str) -> bool:
    """
    判断是否为常见通用标签（非触发词）

    这些标签通常出现在训练数据中，但不是真正的触发词
    """
    # 常见通用标签列表（小写）
    common_tags = {
        # 人物相关
        '1girl', '1boy', '2girls', '2boys', '3girls', '3boys', 'multiple girls', 'multiple boys',
        'solo', 'couple', 'group',
        # 身体特征
        'long hair', 'short hair', 'white hair', 'black hair', 'blonde hair', 'brown hair',
        'red hair', 'blue hair', 'green hair', 'pink hair', 'purple hair', 'silver hair',
        'gradient hair', 'multicolored hair', 'two-tone hair',
        'blue eyes', 'green eyes', 'brown eyes', 'red eyes', 'yellow eyes', 'purple eyes',
        'black eyes', 'white eyes', 'orange eyes', 'pink eyes',
        'small breasts', 'medium breasts', 'large breasts', 'huge breasts',
        # 服装相关
        'dress', 'white dress', 'black dress', 'red dress', 'blue dress', 'green dress',
        'school uniform', 'swimsuit', 'bikini', 'maid', 'nurse', 'waitress',
        'skirt', 'shorts', 'pants', 'jeans', 'shirt', 'blouse', 'jacket', 'coat',
        # 姿势相关
        'standing', 'sitting', 'lying', 'walking', 'running', 'jumping',
        'looking at viewer', 'looking away', 'from behind', 'from side', 'from above', 'from below',
        # 背景相关
        'simple background', 'white background', 'black background', 'grey background',
        'outdoors', 'indoors', 'sky', 'cloud', 'tree', 'flower', 'water', 'building',
        # 画面风格
        'highres', 'absurdres', 'best quality', 'high quality', 'normal quality', 'low quality',
        'masterpiece', 'great quality', 'good quality', 'average quality', 'bad quality',
        'worst quality', 'very bad quality',
        # 其他常见标签
        'smile', 'open mouth', 'closed mouth', 'blush', 'tears', 'sweat',
        'gloves', 'shoes', 'boots', 'socks', 'stockings', 'pantyhose',
        'hat', 'headwear', 'hair ornament', 'ribbon', 'bow', 'flower', 'jewelry',
        'bangs', 'ponytail', 'twintails', 'braid', 'ahoge', 'sidelocks',
        'pointy ears', 'animal ears', 'cat ears', 'dog ears', 'rabbit ears', 'fox ears',
        'tail', 'cat tail', 'dog tail', 'fox tail', 'rabbit tail',
        'wings', 'angel wings', 'demon wings', 'fairy wings',
        'no humans', 'scenery', 'landscape', 'cityscape', 'seascape',
    }

    tag_lower = tag.lower().strip()
    return tag_lower in common_tags


async def _read(ref, offset, count):
    """file.seek(offset); file.read(count): up to `count` bytes, fewer at the end of the file."""
    chunks = []
    while count > 0:
        chunk = await sdk.ctx().assets.read_range(ref, offset, min(count, _READ_MAX))
        if not chunk:
            break
        chunks.append(chunk)
        offset += len(chunk)
        count -= len(chunk)
    return b"".join(chunks)


async def get_metadata_trigger_words(ref, lora_file: str) -> list:
    """
    从safetensors文件元数据获取触发词（按训练频率排序）

    (Secure Nodes V2: reads the header through the asset catalogue; the original opened lora_path.)
    """
    if not lora_file.endswith(".safetensors"):
        return []

    try:
        # 读取header大小
        header_size = int.from_bytes(await _read(ref, 0, 8), "little", signed=False)

        if header_size <= 0:
            return []

        header = await _read(ref, 8, header_size)
        if header is None:
            return []

        header_json = json.loads(header)
        metadata = header_json.get("__metadata__", {})

        if not metadata:
            return []

        # 从 ss_tag_frequency 提取并按频率排序
        if "ss_tag_frequency" in metadata:
            tag_freq_data = metadata["ss_tag_frequency"]

            # 如果是字符串，需要解析JSON
            if isinstance(tag_freq_data, str):
                try:
                    tag_freq_data = json.loads(tag_freq_data)
                except json.JSONDecodeError:
                    return []

            if not isinstance(tag_freq_data, dict):
                return []

            # 统计每个标签的总训练次数
            tag_counts = {}
            for bucket_value in tag_freq_data.values():
                if isinstance(bucket_value, dict):
                    for tag, count in bucket_value.items():
                        tag = str(tag).strip()
                        if tag:
                            tag_counts[tag] = tag_counts.get(tag, 0) + count

            # 按训练次数降序排序
            sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)

            # 智能过滤：优先保留非通用标签
            non_common_tags = []
            common_tags_list = []

            for tag, count in sorted_tags:
                if not _is_common_tag(tag):
                    non_common_tags.append((tag, count))
                else:
                    common_tags_list.append((tag, count))

            # 如果有非通用标签，将它们放在前面
            if non_common_tags:
                result = [tag for tag, count in non_common_tags] + [tag for tag, count in common_tags_list]
            else:
                result = [tag for tag, count in sorted_tags]

            return result

    except Exception as e:
        print(f"[TriggerWords] 读取元数据失败: {e}")

    return []


async def get_output_name_trigger_words(ref, lora_file: str) -> str:
    """
    从元数据的 ss_output_name 获取触发词

    (Secure Nodes V2: reads the header through the asset catalogue; the original opened lora_path.)
    """
    if not lora_file.endswith(".safetensors"):
        return ""

    try:
        header_size = int.from_bytes(await _read(ref, 0, 8), "little", signed=False)

        if header_size <= 0:
            return ""

        header = await _read(ref, 8, header_size)
        if header is None:
            return ""

        header_json = json.loads(header)
        metadata = header_json.get("__metadata__", {})

        if "ss_output_name" in metadata:
            output_name = metadata["ss_output_name"]
            if output_name and isinstance(output_name, str):
                output_name = output_name.strip()
                # 去除常见的版本号后缀 (如 -v1, -v2, _v1, _v2 等)
                output_name = re.sub(r"[-_]v?[0-9]+$", "", output_name)
                return output_name

    except Exception as e:
        print(f"[TriggerWords] 读取ss_output_name失败: {e}")

    return ""


def get_filename_trigger_words(lora_name: str) -> str:
    """
    使用LoRA文件名作为触发词（最后的回退选项）
    """
    if lora_name and lora_name.strip():
        trigger_word = lora_name.strip()
        # 去除版本号后缀
        trigger_word = re.sub(r"[-_]v?[0-9]+$", "", trigger_word)
        return trigger_word
    return ""


async def get_first_trigger_word(ref, lora_file: str, lora_name: str) -> str:
    """The original's get_first_trigger_word (trigger_words.py:473-505) without its Civitai step (see above)."""
    metadata_words = await get_metadata_trigger_words(ref, lora_file)
    if metadata_words:
        return metadata_words[0]

    output_name = await get_output_name_trigger_words(ref, lora_file)
    if output_name:
        return output_name

    filename_word = get_filename_trigger_words(lora_name)
    if filename_word:
        return filename_word

    return ""
