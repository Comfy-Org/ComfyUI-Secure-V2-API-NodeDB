import random

class RandomIntegerNodeList:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "min_value": ("INT", {"default": 0}),
                "max_value": ("INT", {"default": 100}),
                "divisor": ("INT", {"default": 1}),
            }
        }

    RETURN_TYPES = ("INT",)
    FUNCTION = "generate_random_integer"
    CATEGORY = "Custom/Random"

    def generate_random_integer(self, min_value, max_value, divisor):
        # Basic checks to avoid nonsensical parameters
        if min_value > max_value:
            raise ValueError("Minimum value should not be greater than maximum value.")
        if divisor <= 0:
            raise ValueError("Divisor should be a positive integer.")

        # Find the smallest multiple of 'divisor' at or above min_value
        start = min_value + (-min_value % divisor)
        # Find the largest multiple of 'divisor' at or below max_value
        end = max_value - (max_value % divisor)

        # If there's no valid multiple within the range, handle accordingly
        if start > end:
            raise ValueError("No multiples of the divisor exist within the given range.")

        # Build a list of valid multiples
        valid_multiples = list(range(start, end + divisor, divisor))
        # Randomly pick one
        return (random.choice(valid_multiples),)
        
    @classmethod
    def IS_CHANGED(cls, *args, **kwargs):
        return float('nan')
