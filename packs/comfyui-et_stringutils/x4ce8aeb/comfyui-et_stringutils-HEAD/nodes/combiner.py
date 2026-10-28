class ETSplitTextNode:
    """
    A node splits text on a string and returns a string list.
    """

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "text": ("STRING", {"default": "", "multiline": False, "forceInput": True, "tooltip": "The text to split."}),
                "split_by": ("STRING", {"default": ",", "multiline": False, "tooltip": "The string to split the text on."}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    OUTPUT_IS_LIST = (True,)

    CATEGORY = "exectails/Strings"
    FUNCTION = "process"

    def process(self, text: str, split_by: str) -> tuple:
        result = text.split(split_by)
        return (result,)


class ETJoinTextNode:
    """
    A node that joins a list of strings.
    """

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "text": ("STRING", {"default": "", "multiline": False, "forceInput": True, "tooltip": "The text to replace in."}),
                "join_with": ("STRING", {"default": ", ", "multiline": False, "tooltip": "The string to join the elements with."}),
                "prefix": ("STRING", {"default": "", "multiline": False, "tooltip": "A string to place before the text."}),
                "suffix": ("STRING", {"default": "", "multiline": False, "tooltip": "A string to place after the text."}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    INPUT_IS_LIST = True

    CATEGORY = "exectails/Strings"
    FUNCTION = "process"

    def process(self, text: list, join_with: str, prefix: str, suffix: str) -> tuple:
        join_with = join_with[0]
        prefix = prefix[0]
        suffix = suffix[0]

        result = prefix + join_with.join(text) + suffix
        return (result,)


class ETSwitchTextNode:
    """
    A node that outputs one of two options depending on a boolean switch.
    """

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "option1": ("STRING", {"default": "", "multiline": False, "tooltip": "The option that will returned if the switch is off/false."}),
                "option2": ("STRING", {"default": "", "multiline": False, "tooltip": "The option that will returned if the switch is on/true."}),
                "switch": ("BOOLEAN", {"default": False, "label_off": "option1", "label_on": "option2", "tooltip": "The switch that determines which option to return. Option 1 if off, option 2 if on."}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)

    CATEGORY = "exectails/Strings"
    FUNCTION = "process"

    def process(self, option1: str = "", option2: str = "", switch: bool = False) -> tuple:
        result = option1 if not switch else option2
        return (result,)
