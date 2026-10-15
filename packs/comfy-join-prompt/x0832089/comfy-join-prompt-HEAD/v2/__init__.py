from comfy_api.latest import ComfyExtension
from .nodes import JoinPrompt, JoinStrings

NODE_CLASS_MAPPINGS = {
    "jupo.JoinPrompt.JoinStrings": JoinStrings,
    "jupo.JoinPrompt.JoinPrompt": JoinPrompt,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "jupo.JoinPrompt.JoinStrings": "Join Strings",
    "jupo.JoinPrompt.JoinPrompt": "Join Prompt",
}
WEB_DIRECTORY = "./web"


class Extension(ComfyExtension):
    async def get_node_list(self):
        return [JoinStrings, JoinPrompt]


async def comfy_entrypoint():
    return Extension()
