# preset_resolution_flux_node.py
# ComfyUI Custom Node: Quick Size (Qwen)
# Outputs two INTs: width, height

class QuickSizeQwenNode:
    """
    Select a megapixel tier and aspect preset, then orient horizontally or vertically.
    - If orientation == 'horizontal': width := larger, height := smaller
    - If orientation == 'vertical'  : height := larger, width := smaller
    - 'preset' shows ratios only (e.g., '4:3', '16:9')
    - 'megapixels' selects a size table
    - Orientation:
        * horizontal -> width := larger, height := smaller
        * vertical   -> height := larger, width := smaller
    """

    # Use aspect keys directly; no label mapping needed.
    ASPECT_KEYS = ["1:1", "2:3", "4:3", "16:9", "21:9"]

    # Resolution tables by megapixel tier
    # (All tuples are (w, h) before orientation swapping.)
    RESOLUTIONS_BY_MP = {
        "1.0": {
            "1:1":  (1328, 1328),
            "2:3":  (1056, 1584),
            "4:3":  (1472, 1104),
            "16:9": (1664, 928),
            "21:9": (1536, 640),
        },
        "1.5": {
            "1:1":  (1992, 1992),
            "2:3":  (1584, 2376),
            "4:3":  (2208, 1656),
            "16:9": (2496, 1392),
            "21:9": (2304, 960),
        }
    }

    # Static labels shown in the preset dropdown
    _PRESET_LABELS_1P0 = {
        "1:1",
        "2:3",
        "4:3",
        "16:9",
        "21:9",
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
                "megapixels": (["1.0", "1.5", "2.0"], {"default": "1.0"}),
                #"preset": (preset_items, {"default": cls._PRESET_LABELS_1P0["1:1"]}),
                "preset": (cls.ASPECT_KEYS, {"default": "1:1"}),  # ratios only
                "orientation": (["horizontal", "vertical"], {"default": "horizontal"}),
            }
        }

    def get_size(self, megapixels: str, preset: str, orientation: str):
        # 'preset' is the aspect key directly
        mp_table = self.RESOLUTIONS_BY_MP.get(megapixels, self.RESOLUTIONS_BY_MP["1.0"])
        aspect = preset if preset in mp_table else "1:1"

        w, h = mp_table[aspect]
        larger, smaller = (w, h) if w >= h else (h, w)

        if orientation == "horizontal":
            width, height = larger, smaller
        else:
            width, height = smaller, larger

        return (int(width), int(height))

# ---- ComfyUI registration ----
NODE_CLASS_MAPPINGS = {
    "QuickSizeQwen": QuickSizeQwenNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "QuickSizeQwenNode": "Quick Size (Qwen)",
}

