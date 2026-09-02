from .core import logger
from .server import *
from .general import *
from comfy_api.latest import ComfyExtension, io

class CrystoolsMonitor(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return []

async def comfy_entrypoint() -> CrystoolsMonitor:
    return CrystoolsMonitor()

WEB_DIRECTORY = "./web"
