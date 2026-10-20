# wildcard trick is taken from pythongossss's
class AnyType(str):
    def __ne__(self, __value: object) -> bool:
        return False

any_typ = AnyType("*")

class SwapAndScale:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "IN_HEIGHT": ("INT", ),
                "IN_WIDTH": ("INT", ),
                "Swap_Width_Height": ("BOOLEAN", {"default": False}),
                "factor_32px": ("BOOLEAN", {"default": True}),
                "Limit_1MP": ("BOOLEAN", {"default": True})
            }
        }

    @staticmethod
    def adjust_x32(value):
        """Lower value to closest number in factor of 32."""
        return value if value % 32 == 0 else value - (value % 32)

    def scale_values(self, IN_HEIGHT, IN_WIDTH, max_product):
        """Scale IN_HEIGHT and IN_WIDTH proportionally while keeping them multiples of 32."""
        factor = (max_product / (IN_HEIGHT * IN_WIDTH)) ** 0.5
        new_h = int(IN_HEIGHT * factor)
        new_b = int(IN_WIDTH * factor)

        return self.adjust_x32(new_h), self.adjust_x32(new_b)

    def process_inputs(self, IN_HEIGHT, IN_WIDTH, IN_swap, factor_32px, Limit_1MP):
        """Processes inputs according to the set rules."""
    
        # Step 1: Adjust to 32px format if selected
        if factor_32px:
            IN_HEIGHT = self.adjust_x32(IN_HEIGHT)
            IN_WIDTH = self.adjust_x32(IN_WIDTH)

        # Step 2: Check if product exceeds 1MP and adjust
        if Limit_1MP and (IN_HEIGHT * IN_WIDTH > 1048576):
            IN_HEIGHT, IN_WIDTH = self.scale_values(IN_HEIGHT, IN_WIDTH, 1048576)

        # Step 3: Swap IN_HEIGHT and IN_WIDTH if selected
        if IN_swap:
            IN_HEIGHT, IN_WIDTH = IN_WIDTH, IN_HEIGHT

        return IN_HEIGHT, IN_WIDTH

    RETURN_TYPES = ("INT", "INT",)
    RETURN_NAMES = ("out_height", "out_width")
    OUTPUT_NODE = True
    CATEGORY = "Image"
    FUNCTION = "swap_and_scale"

    def swap_and_scale(
        self,
        IN_HEIGHT,
        IN_WIDTH,
        Swap_Width_Height,
        factor_32px,
        Limit_1MP,
    ):
        """Runs the processing function and returns the updated values."""
        OUT_HEIGHT, OUT_WIDTH = self.process_inputs(IN_HEIGHT, IN_WIDTH, Swap_Width_Height, factor_32px, Limit_1MP)
        
        return OUT_HEIGHT, OUT_WIDTH


NODE_CLASS_MAPPINGS = {
    "SwapAndScale": SwapAndScale,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SwapAndScale": "Swap width/height and/or scale image",
}
