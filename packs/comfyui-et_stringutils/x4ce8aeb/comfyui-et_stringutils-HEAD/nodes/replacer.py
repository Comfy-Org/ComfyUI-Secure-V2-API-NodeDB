import re


class ETReplaceTextNode:
    """
    A node that replaces text in a string.
    """

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "text": ("STRING", {"default": "", "multiline": False, "tooltip": "The text to replace in."}),
                "replace": ("STRING", {"default": "", "multiline": False, "tooltip": "The text to replace."}),
                "replacement": ("STRING", {"default": "", "multiline": False, "tooltip": "The text to replace with."}),
                "mode": (["normal", "regex"], {"default": "normal", "tooltip": "The mode to use for replacing."}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)

    CATEGORY = "exectails/Strings"
    FUNCTION = "process"

    def process(self, text: str, replace: str, replacement: str, mode: str) -> tuple:
        result = ""

        if mode == "normal":
            result = text.replace(replace, replacement)
        else:
            result = re.sub(replace, replacement, text)

        return (result,)
