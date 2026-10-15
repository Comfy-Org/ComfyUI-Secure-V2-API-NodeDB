# reslist_wan_video.py
# ComfyUI Custom Node: Quick Size (WAN )
# Outputs two INTs: width, height

class QuickSizeWanNode:
    """
    Select a WAN model size, video size (480p or 720p), and aspect preset,
    then orient horizontally or vertically.

    Model size:
      - "Wan 5B"  -> tuned for 480p; 720p uses the model's native 708px short side (e.g., 1280x708)
      - "Wan 14B" -> tuned for 720p; also works well at 480p

    Video size:
      - "480p": smaller tier (~480 short side)
      - "720p": larger tier (~720 short side; 5B uses 708 to match its native grid)

    Orientation rules:
      - horizontal: width := larger,  height := smaller
      - vertical  : height := larger, width := smaller
    """

    # Include official and commonly used (unofficial but known-to-work) aspect ratios.
    ASPECT_KEYS = [
        "1:1",
        "3:2", "2:3",
        "4:3", "3:4",
        "16:9", "9:16",
        "21:9", "9:21",
    ]

    # Resolution tables by model size and tier.
    # Each tuple is (w, h) BEFORE orientation swapping.
    # Notes:
    # - 5B @ 720p uses a native short side of 708 (e.g., 1280x708) to avoid downstream math.
    # - 14B @ 720p uses standard 1280x720.
    # - 480p entries use widely working grids aligned with internal downsampling.
    RESOLUTIONS_BY_MODEL = {
        "Wan 5B": {
            "480p": {
                "16:9": (832, 480),
                "9:16": (480, 832),
                "4:3":  (640, 480),
                "3:4":  (480, 640),
                "1:1":  (576, 576),
                "21:9": (896, 384),
                "9:21": (384, 896),
                "3:2":  (720, 480),
                "2:3":  (480, 720),
            },
            "720p": {
                # Short side = 708px for the 5B native grid
                "16:9": (1280, 708),
                "9:16": (708, 1280),

                "4:3":  (944, 708),   # 708 * 4/3 = 944
                "3:4":  (708, 944),

                "1:1":  (708, 708),

                "21:9": (1652, 708),  # 708 * 21/9 = 1652
                "9:21": (708, 1652),

                "3:2":  (1062, 708),  # 708 * 3/2 = 1062
                "2:3":  (708, 1062),
            },
        },
        "Wan 14B": {
            "480p": {
                "16:9": (832, 480),
                "9:16": (480, 832),
                "4:3":  (640, 480),
                "3:4":  (480, 640),
                "1:1":  (576, 576),
                "21:9": (896, 384),
                "9:21": (384, 896),
                "3:2":  (720, 480),
                "2:3":  (480, 720),
            },
            "720p": {
                "16:9": (1280, 720),
                "9:16": (720, 1280),
                "4:3":  (960, 720),
                "3:4":  (720, 960),
                "1:1":  (720, 720),
                "21:9": (1680, 720),
                "9:21": (720, 1680),
                "3:2":  (1080, 720),
                "2:3":  (720, 1080),
            },
        },
    }

    RETURN_TYPES = ("INT", "INT")
    RETURN_NAMES = ("width", "height")
    FUNCTION = "get_size"
    CATEGORY = "video/utils"
    OUTPUT_NODE = False

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model_size": (["Wan 14B", "Wan 5B"], {"default": "Wan 14B"}),
                "video_size": (["720p", "480p"], {"default": "720p"}),
                "preset": (cls.ASPECT_KEYS, {"default": "16:9"}),
                "orientation": (["horizontal", "vertical"], {"default": "horizontal"}),
            }
        }

    def get_size(self, model_size: str, video_size: str, preset: str, orientation: str):
        model_table = self.RESOLUTIONS_BY_MODEL.get(model_size, self.RESOLUTIONS_BY_MODEL["Wan 14B"])
        size_table = model_table.get(video_size, model_table["720p"])
        aspect = preset if preset in size_table else "16:9"

        w, h = size_table[aspect]
        larger, smaller = (w, h) if w >= h else (h, w)

        if orientation == "horizontal":
            width, height = larger, smaller
        else:
            width, height = smaller, larger

        return (int(width), int(height))


# ---- ComfyUI registration ----
NODE_CLASS_MAPPINGS = {
    "QuickSizeWan": QuickSizeWanNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ResolutionListWan": "Quick Size (WAN )",
}

