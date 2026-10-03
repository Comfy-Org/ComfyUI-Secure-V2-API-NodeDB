from comfy_api.latest import ComfyExtension
from .calculator import Calculator

class CalculatorExtension(ComfyExtension):
    async def get_node_list(self):
        return [Calculator]

async def comfy_entrypoint():
    return CalculatorExtension()

WEB_DIRECTORY = "./js"

__all__ = ["comfy_entrypoint", "WEB_DIRECTORY"]
