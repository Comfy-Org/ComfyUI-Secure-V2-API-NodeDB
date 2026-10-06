import comfy.sd


class DaisyChainTextMittimi:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "text_that_comes_first": ("STRING", ),
                "text": ("STRING", {"multiline": True}),
            },
            "optional": {
                "text_that_comes_last": ("STRING", ),
            },
        }
    RETURN_TYPES = ("STRING", )
    RETURN_NAMES = ("text", )
    FUNCTION = "daisyChainTextMittimi"
    CATEGORY = "mittimiTools"

    def daisyChainTextMittimi(self, text, text_that_comes_first="", text_that_comes_last="", ):

        return(text_that_comes_first + text + text_that_comes_last, )
 

NODE_CLASS_MAPPINGS = {
    "DaisyChainTextMittimi": DaisyChainTextMittimi,   
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "DaisyChainTextMittimi": "DaisyChainText", 
}
