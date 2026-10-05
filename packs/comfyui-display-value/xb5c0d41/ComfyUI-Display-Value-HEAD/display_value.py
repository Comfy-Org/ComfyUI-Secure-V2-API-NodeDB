import json
from comfy.comfy_types.node_typing import IO

class DisplayValue:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "value": (IO.ANY, {}),
            },
        }

    INPUT_IS_LIST = True
    RETURN_TYPES = ("STRING",)
    FUNCTION = "main"
    OUTPUT_NODE = True
    OUTPUT_IS_LIST = (True,)
    CATEGORY = "utils"

    @staticmethod
    def format_value(value):
        if isinstance(value, list):
            value = value[0]
        if isinstance(value, (str, int, float, bool)):
            return str(value)
        if value is not None:
            try:
                return json.dumps(value)
            except Exception:
                try:
                    return str(value)
                except Exception:
                    return "source exists, but could not be serialized."
        return "None"

    def main(self, value=None):
        value_str = self.format_value(value)

        return {"ui": {"value": [value_str]}, "result": ([value_str],)}
