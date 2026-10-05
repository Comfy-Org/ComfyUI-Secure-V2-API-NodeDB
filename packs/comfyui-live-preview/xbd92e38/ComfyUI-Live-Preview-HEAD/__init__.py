WEB_DIRECTORY = "./js"

class LivePreview:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "passthrough"
    CATEGORY = "image"
    DESCRIPTION = "Pass-through node that activates the large live preview overlay window."

    def passthrough(self, images):
        return (images,)


NODE_CLASS_MAPPINGS = {
    "LivePreview": LivePreview,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LivePreview": "Live Preview (Large)",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
