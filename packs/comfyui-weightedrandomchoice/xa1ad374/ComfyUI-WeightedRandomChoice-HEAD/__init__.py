# wildcard trick is taken from pythongossss's
class AnyType(str):

	def __ne__(self, __value: object) -> bool:
		return False


def get_default_value(example_input):
	if isinstance(example_input, str):
		return ""
	elif isinstance(example_input, int):
		return 0
	elif isinstance(example_input, float):
		return 0.0
	else:
		return ""


class WeightedRandomChoiceNode:
	"""
	Takes `input_a` and `input_b` and makes a choice between them based on the outcome of `chance`.
	"""

	def __init__(self):
		pass

	@classmethod
	def INPUT_TYPES(cls):
		return {
		    "required": {
		        "chance": ("FLOAT", {
		            "default": 0.5,
		            "min": 0.0,
		            "max": 1.0,
		            "step": 0.01,
		        }),
		        "seed": ("INT", {
		            "default": 0,
		            "min": 0,
		            "max": 0xffffffffffffffff,
		            "step": 1,
		        }),
		    },
		    "optional": {
		        "input_a": (AnyType("*"), {
		            "default": ""
		        }),
		        "input_b": (AnyType("*"), {
		            "default": ""
		        }),
		    },
		}

	RETURN_TYPES = (AnyType("*"), )

	FUNCTION = "run"

	def run(self, **kwargs):
		"""
		Returns a value based on the chance value.
		"""
		import random

		random.seed(kwargs.get("seed"))

		# Determine a default value based on the datatype of the inputs
		if kwargs.get("input_a") is not None:
			default_value = get_default_value(kwargs.get("input_a"))
		elif kwargs.get("input_b") is not None:
			default_value = get_default_value(kwargs.get("input_b"))
		else:
			return ""

		if kwargs.get("chance") >= random.random():
			input_a = kwargs.get("input_a")
			return (default_value if input_a is None else input_a, )
		else:
			input_b = kwargs.get("input_b")
			return (default_value if input_b is None else input_b, )


# Set the web directory, any .js file in that directory will be loaded by the frontend as a frontend extension
# WEB_DIRECTORY = "./somejs"

# A dictionary that contains all nodes you want to export with their names
# NOTE: names should be globally unique
NODE_CLASS_MAPPINGS = {
    "WeightedRandomChoice": WeightedRandomChoiceNode,
}

# A dictionary that contains the friendly/humanly readable titles for the nodes
NODE_DISPLAY_NAME_MAPPINGS = {"WeightedRandomChoice": "Weighted Random Choice"}
