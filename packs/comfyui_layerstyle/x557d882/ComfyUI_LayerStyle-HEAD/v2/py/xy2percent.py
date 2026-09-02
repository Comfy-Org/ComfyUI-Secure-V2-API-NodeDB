
class XYtoPercent:

    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(self):

        return {
            "required": {
                "background_image": ("IMAGE", ),  #
                "layer_image": ("IMAGE",),  #
                "x": ("INT", {"default": 0, "min": -99999, "max": 99999, "step": 1}),
                "y": ("INT", {"default": 0, "min": -99999, "max": 99999, "step": 1}),
            },
            "optional": {
            }
        }

    RETURN_TYPES = ("FLOAT", "FLOAT",)
    RETURN_NAMES = ("x_percent", "y_percent",)
    FUNCTION = 'xy_to_percent'
    CATEGORY = '😺dzNodes/LayerUtility/Data'

    def xy_to_percent(self, background_image, layer_image, x, y,):
        if background_image.dim() not in (3, 4) or layer_image.dim() not in (3, 4):
            raise ValueError("XY to Percent requires IMAGE tensors")
        canvas_height, canvas_width = background_image.shape[-3:-1]
        layer_height, layer_width = layer_image.shape[-3:-1]
        if canvas_width <= 0 or canvas_height <= 0:
            raise ValueError("XY to Percent requires a non-empty canvas")
        x_percent = (x + layer_width / 2) / canvas_width * 100.0
        y_percent = (y + layer_height / 2) / canvas_height * 100.0

        return (x_percent, y_percent,)

NODE_CLASS_MAPPINGS = {
    "LayerUtility: XY to Percent": XYtoPercent
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LayerUtility: XY to Percent": "LayerUtility: XY to Percent"
}
