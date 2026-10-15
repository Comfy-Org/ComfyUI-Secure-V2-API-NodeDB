class ResolutionAndRatio:
    MIN_SIZE = 8          # smallest manual size
    MAX_SIZE = 4096
    FREE_MAX = 32         # 8..32 are taken as typed
    STEP = 32             # anything above FREE_MAX must be a multiple of 32
    MIN_PRESET_SIZE = 512 # presets below this are hidden in the dropdown
    RESET_SIZE = 512

    @classmethod
    def INPUT_TYPES(cls):
        # sizes below MIN_PRESET_SIZE are not offered as presets
        default_presets = (
            "512x512\n512x768\n768x768\n1024x1024\n896x1216\n1216x896\n"
            "1088x1920\n1920x1088\n1152x1536\n1536x1152\n1536x2048\n2048x1536\n2048x2048"
        )

        return {
            "required": {
                "width": ("INT", {"default": 1152, "min": cls.MIN_SIZE, "max": cls.MAX_SIZE, "step": cls.STEP}),
                "height": ("INT", {"default": 1536, "min": cls.MIN_SIZE, "max": cls.MAX_SIZE, "step": cls.STEP}),
                "W_ratio": ("INT", {"default": 3, "min": 1, "max": 512}),
                "H_ratio": ("INT", {"default": 4, "min": 1, "max": 512}),
                "scale_percent": ("INT", {"default": 100, "min": 10, "max": 200, "step": 5, "display": "slider"}),
                "reset": ("BOOLEAN", {"default": False, "label_on": "RESET", "label_off": "RESET"}),
                "swap": ("BOOLEAN", {"default": False, "label_on": "SWAP", "label_off": "SWAP"}),
                "preset": (["Custom"],),
                "custom_presets": ("STRING", {"multiline": True, "default": default_presets}),
            },
        }

    RETURN_TYPES = ("INT", "INT")
    RETURN_NAMES = ("width", "height")
    FUNCTION = "get_resolution"
    CATEGORY = "CustomUtils"

    @classmethod
    def _snap_size(cls, value):
        """8..32 pass through, everything larger snaps onto the 32 grid."""
        value = int(round(float(value)))
        value = max(cls.MIN_SIZE, min(cls.MAX_SIZE, value))
        if value > cls.FREE_MAX:
            value = int(round(value / cls.STEP)) * cls.STEP
            value = max(cls.STEP, value)
        return value

    def get_resolution(self, width, height, W_ratio, H_ratio, scale_percent, reset, swap, preset, custom_presets):
        # Handle reset (mainly handled by JS, but included for completeness)
        if reset:
            width = self.RESET_SIZE
            height = self.RESET_SIZE

        # Handle swap
        if swap:
            width, height = height, width
            W_ratio, H_ratio = H_ratio, W_ratio

        return (self._snap_size(width), self._snap_size(height))

    @classmethod
    def VALIDATE_INPUTS(cls, width, height, **kwargs):
        if not (cls.MIN_SIZE <= width <= cls.MAX_SIZE):
            return f"Width must be between {cls.MIN_SIZE} and {cls.MAX_SIZE}"
        if not (cls.MIN_SIZE <= height <= cls.MAX_SIZE):
            return f"Height must be between {cls.MIN_SIZE} and {cls.MAX_SIZE}"
        return True
