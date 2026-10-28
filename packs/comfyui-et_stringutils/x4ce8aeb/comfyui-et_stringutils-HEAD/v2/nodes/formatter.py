class ETTextFormatterNode:
    """
    Base class for nodes that take a number of inputs and format them
    into a single string.
    """

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)

    CATEGORY = "exectails/Strings"
    FUNCTION = "process"

    def process(self, format, arg0="", arg1="", arg2="", arg3="", arg4="", arg5="", arg6="", arg7="", arg8="", arg9="") -> tuple:
        result = format.format(arg0=arg0, arg1=arg1, arg2=arg2, arg3=arg3, arg4=arg4, arg5=arg5, arg6=arg6, arg7=arg7, arg8=arg8, arg9=arg9)
        return (result,)


class ETTextFormatter2Node(ETTextFormatterNode):
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "format": ("STRING", {"multiline": True}),
            },
            "optional": {
                "arg0": ("STRING", {"forceInput": True}),
                "arg1": ("STRING", {"forceInput": True}),
            }
        }


class ETTextFormatter5Node(ETTextFormatterNode):
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "format": ("STRING", {"multiline": True}),
            },
            "optional": {
                "arg0": ("STRING", {"forceInput": True}),
                "arg1": ("STRING", {"forceInput": True}),
                "arg2": ("STRING", {"forceInput": True}),
                "arg3": ("STRING", {"forceInput": True}),
                "arg4": ("STRING", {"forceInput": True}),
            }
        }


class ETTextFormatter10Node(ETTextFormatterNode):
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "format": ("STRING", {"multiline": True}),
            },
            "optional": {
                "arg0": ("STRING", {"forceInput": True}),
                "arg1": ("STRING", {"forceInput": True}),
                "arg2": ("STRING", {"forceInput": True}),
                "arg3": ("STRING", {"forceInput": True}),
                "arg4": ("STRING", {"forceInput": True}),
                "arg5": ("STRING", {"forceInput": True}),
                "arg6": ("STRING", {"forceInput": True}),
                "arg7": ("STRING", {"forceInput": True}),
                "arg8": ("STRING", {"forceInput": True}),
                "arg9": ("STRING", {"forceInput": True}),
            }
        }
