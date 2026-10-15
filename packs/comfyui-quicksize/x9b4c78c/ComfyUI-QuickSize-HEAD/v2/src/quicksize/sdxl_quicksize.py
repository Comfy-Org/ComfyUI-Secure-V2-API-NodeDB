# sdxl_quicksize.py
# ComfyUI Custom Node: Quick Size (SDXL)
# Outputs two INTs: width, height

class QuickSizeSDXLNode:
    """
    Quick Size (SDXL)
    - 'preset' shows ratios only (e.g., '1:1', '4:3', '16:9', '21:9')
    - '1.5x' toggle scales up to the 1.5 Mpx tier
    - Orientation:
        * horizontal -> width := larger, height := smaller
        * vertical   -> height := larger, width := smaller
    """

    ASPECT_KEYS = ["1:1", "3:2", "2:3", "4:3", "3:4", "16:9", "21:9"]

    # Base 1.0× table (≈1 Mpx)
    RES_1X = {
        "1:1":  (1024, 1024),
        "3:2":  (1216, 832),
        "2:3":  (832, 1216),
        "4:3":  (1152, 864),
        "3:4":  (864, 1152),
        "16:9": (1344, 768),
        "21:9": (1536, 640),
    }

    # 1.5× table (≈1.5 Mpx)
    RES_15X = {
        "1:1":  (1536, 1536),
        "3:2":  (1824, 1216),
        "2:3":  (1216, 1824),
        "4:3":  (1728, 1296),
        "3:4":  (1296, 1728),
        "16:9": (2016, 1152),
        "21:9": (2304, 960),
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
    "QuickSizeSDXLNode": QuickSizeSDXLNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "QuickSizeSDXLNode": "Quick Size (SDXL)",
}

