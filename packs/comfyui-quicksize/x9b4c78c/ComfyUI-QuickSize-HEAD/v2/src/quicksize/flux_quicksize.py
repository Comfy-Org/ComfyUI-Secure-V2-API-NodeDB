# preset_resolution_flux_node.py
# ComfyUI Custom Node: Quick Size (Flux)
# Outputs two INTs: width, height

# src/resolution_list/reslist_flux.py

class QuickSizeFluxNode:
    """
    Quick Size (Flux)
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
            "1:1":  (1024, 1024),
            "2:3":  (832, 1216),
            "4:3":  (1152, 896),
            "16:9": (1344, 768),
            "21:9": (1536, 640),
        },
        "1.5": {
            "1:1":  (1536, 1536),
            "2:3":  (1248, 1824),
            "4:3":  (1728, 1344),
            "16:9": (2016, 1152),
            "21:9": (2304, 960),
        },
        "2.0": {
            "1:1":  (1408, 1408),
            "2:3":  (1728, 1152),  # fixed typo from (17281152)
            "4:3":  (1664, 1216),
            "16:9": (1920, 1088),
            "21:9": (2176, 960),
        },
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
    "QuickSizeFluxNode": QuickSizeFluxNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "QuickSizeFluxNode": "Quick Size (Flux)",
}

