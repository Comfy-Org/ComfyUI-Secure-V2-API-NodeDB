# preset_resolution_sd15_node.py
# ComfyUI Custom Node: Quick Size (SD 1.5)
# Outputs two INTs: width, height

class QuickSizeSD15Node:
    """
    Quick Size (SD 1.5)
    - 'preset' shows ratios (e.g., '1:1', '4:3', '16:9')
    - '1.5x' toggle scales up to ~768/1152 size tier
    - Orientation:
        * horizontal -> width := larger, height := smaller
        * vertical   -> height := larger, width := smaller
    """

    ASPECT_KEYS = ["1:1", "3:2", "2:3", "4:3", "16:9", "9:16"]

    RES_1X = {
        "1:1":  (512, 512),
        "3:2":  (768, 512),
        "2:3":  (512, 768),
        "4:3":  (768, 576),
        "16:9": (912, 512),
    }

    RES_15X = {
        "1:1":  (768, 768),
        "3:2":  (1152, 768),
        "2:3":  (768, 1152),
        "4:3":  (1152, 864),
        "16:9": (1360, 768),
    }

    RETURN_TYPES = ("INT", "INT")
    RETURN_NAMES = ("width", "height")
    FUNCTION = "get_size"
    CATEGORY = "image/utils"
    OUTPUT_NODE = False

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "preset": (cls.ASPECT_KEYS, {"default": "1:1"}),
                "orientation": (["horizontal", "vertical"], {"default": "horizontal"}),
                "1.5x": ("BOOLEAN", {"default": False}),
            }
        }

    def get_size(self, preset: str, orientation: str, **kwargs):
        is_15x = kwargs.get("1.5x", False)
        table = self.RES_15X if is_15x else self.RES_1X
        aspect = preset if preset in table else "1:1"

        w, h = table[aspect]
        larger, smaller = (w, h) if w >= h else (h, w)
        if orientation == "horizontal":
            width, height = larger, smaller
        else:
            width, height = smaller, larger
        return (int(width), int(height))


# ---- ComfyUI registration ----
NODE_CLASS_MAPPINGS = {
    "QuickSizeSD15Node": QuickSizeSD15Node,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "QuickSizeSD15Node": "Quick Size (SD 1.5)",
}

