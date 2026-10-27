# -*- coding: utf-8 -*-


class TextConcatenateDJ:
    """把最多 12 个文本输入按序拼接成一个字符串。"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "分隔符": ("STRING", {"default": ""}),
                "清理首尾空白": (["是", "否"], {"default": "否"}),
            },
            "optional": {
                "文本1": ("STRING", {"forceInput": True}),
                "文本2": ("STRING", {"forceInput": True}),
                "文本3": ("STRING", {"forceInput": True}),
                "文本4": ("STRING", {"forceInput": True}),
                "文本5": ("STRING", {"forceInput": True}),
                "文本6": ("STRING", {"forceInput": True}),
                "文本7": ("STRING", {"forceInput": True}),
                "文本8": ("STRING", {"forceInput": True}),
                "文本9": ("STRING", {"forceInput": True}),
                "文本10": ("STRING", {"forceInput": True}),
                "文本11": ("STRING", {"forceInput": True}),
                "文本12": ("STRING", {"forceInput": True}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("文本",)
    FUNCTION = "run"
    CATEGORY = "DJ/TextConcat"

    def run(self, 分隔符, 清理首尾空白, **kwargs):
        # 分隔符为 "\n" 字面量时转成真换行
        if 分隔符 in ("\\n",):
            分隔符 = "\n"

        parts = []
        for key in sorted(kwargs.keys()):
            val = kwargs[key]
            if not isinstance(val, str):
                continue
            if 清理首尾空白 == "是":
                val = val.strip()
            if val != "":
                parts.append(val)

        return (分隔符.join(parts),)
