# Resolution Calculator by Steve Lasmin
# https://boosty.to/stevelasmin

import math

class Resolution_Calculator_by_Steve_Lasmin:
    """
    Calculates width and height based on a maximum dimension,
    aspect ratio (as width:height), and a target multiplier.
    Ensures the final dimensions are divisible by the multiplier.

    Resolution Calculator by Steve Lasmin
    https://boosty.to/stevelasmin
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "resolution": ("INT", {
                    "default": 1024,
                    "min": 32,
                    "max": 4096,
                    "step": 16,
                    "display": "number"
                }),
                "aspect_preset": (["custom", "1:1", "3:2", "4:3", "16:9", "16:10", "21:9", "2:3", "3:4", "9:16", "9:21"], {
                    "default": "custom"
                }),
                "width_ratio": ("INT", {
                    "default": 2,
                    "min": 1,
                    "max": 999999,
                    "step": 1,
                    "display": "number"
                }),
                "height_ratio": ("INT", {
                    "default": 3,
                    "min": 1,
                    "max": 999999,
                    "step": 1,
                    "display": "number"
                }),
                "multiplier": (["16", "32", "64"], {
                    "default": "32"
                }),
            }
        }

    RETURN_TYPES = ("INT", "INT", "STRING")
    RETURN_NAMES = ("width", "height", "preview")
    FUNCTION = "calculate"
    CATEGORY = "utils"
    OUTPUT_NODE = True

    def calculate(self, resolution, aspect_preset, width_ratio, height_ratio, multiplier):
        # Parse preset if not custom
        if aspect_preset != "custom":
            w, h = aspect_preset.split(":")
            width_ratio = int(w)
            height_ratio = int(h)

        # Convert multiplier from string to int
        multiplier = int(multiplier)

        aspect = width_ratio / height_ratio

        # Resolution = maximum dimension (longest side)
        if aspect >= 1:
            width = resolution
            height = resolution / aspect
        else:
            height = resolution
            width = resolution * aspect

        # Round to nearest multiple of multiplier
        width = round(width / multiplier) * multiplier
        height = round(height / multiplier) * multiplier

        # Ensure minimum dimensions
        width = max(multiplier, width)
        height = max(multiplier, height)

        # Create preview string
        preview_text = f"Width: {int(width)} px  |  Height: {int(height)} px  |  Aspect: {width_ratio}:{height_ratio}  |  Multiplier: {multiplier}"

        return (int(width), int(height), preview_text)


NODE_CLASS_MAPPINGS = {
    "Resolution_Calculator_by_Steve_Lasmin": Resolution_Calculator_by_Steve_Lasmin,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Resolution_Calculator_by_Steve_Lasmin": "Resolution Calculator by Steve Lasmin",
}
