import comfy.sd


class RecalculateSizeMittimi01:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {
                    "Width": ("INT", {"default": 512, "min": 1, "max": 2147483647} ),
                    "Height": ("INT", {"default": 512, "min": 1, "max": 2147483647} ),
                    "Magnification": ("FLOAT", {"default": 1.00, "min": 0.01, "max": 9999.99, "step": 0.01})
                }
        }

    RETURN_TYPES = ("INT", "INT", )
    RETURN_NAMES = ("width", "height", )
    FUNCTION = "runRecalculateSize"
    CATEGORY = "mittimiTools"

    def runRecalculateSize(self, Width, Height, Magnification, ):

        w = Width * Magnification
        h = Height * Magnification
        return(int(w), int(h), )


NODE_CLASS_MAPPINGS = {
    "RecalculateSizeMittimi01": RecalculateSizeMittimi01,   
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "RecalculateSizeMittimi01": "RecalculateSize01", 
}
