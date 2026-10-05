import random
import math

class RandomIntegerNodeEfficient:
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
        # Validate inputs
        if min_value > max_value:
            raise ValueError("min_value should not be greater than max_value.")
        if divisor <= 0:
            raise ValueError("divisor must be a positive integer.")

        # Calculate the smallest multiple of divisor >= min_value
        if min_value % divisor == 0:
            min_multiple = min_value
        else:
            min_multiple = min_value + (divisor - (min_value % divisor))

        # Calculate the largest multiple of divisor <= max_value
        max_multiple = max_value - (max_value % divisor)

        # Check if there are any multiples in the range
        if min_multiple > max_multiple:
            raise ValueError(f"No multiples of {divisor} within the range [{min_value}, {max_value}].")

        # Calculate the number of possible multiples
        num_multiples = ((max_multiple - min_multiple) // divisor) + 1

        # Select a random multiple
        random_index = random.randint(0, num_multiples - 1)
        random_number = min_multiple + (random_index * divisor)

        return (random_number,)

    @classmethod
    def IS_CHANGED(cls, min_value, max_value, divisor):
        return float('nan')
