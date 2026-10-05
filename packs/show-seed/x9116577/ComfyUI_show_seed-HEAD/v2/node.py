"""Secure IMAGE passthrough with prompt seed reporting."""

from typing import Any

from comfy_api.latest import ComfyExtension, io, sdk


class ShowSeed(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Show Seed",
            display_name="Show Seed",
            category="image",
            inputs=[io.Image.Input("images")],
            outputs=[
                io.Image.Output("images"),
                io.String.Output("seed_info"),
            ],
            hidden=[io.Hidden.prompt],
        )

    @staticmethod
    def extract_seed(prompt: Any):
        try:
            if isinstance(prompt, tuple):
                prompt = prompt[1]
            if isinstance(prompt, dict):
                for node_data in prompt.values():
                    if isinstance(node_data, dict):
                        class_type = node_data.get("class_type", "")
                        if "KSampler" in class_type:
                            inputs = node_data.get("inputs", {})
                            if "seed" in inputs:
                                return inputs["seed"]
            return None
        except Exception as error:
            print(f"Error extracting seed: {error}")
            return None

    @classmethod
    def execute(
        cls, images: sdk.ImageRef, prompt: Any = None,
    ) -> io.NodeOutput:
        seed = cls.extract_seed(prompt)
        seed_text = f"Seed: {seed}" if seed is not None else "Seed not found"
        return io.NodeOutput(images, seed_text)


NODE_CLASS_MAPPINGS = {"Show Seed": ShowSeed}
NODE_DISPLAY_NAME_MAPPINGS = {"Show Seed": "Show Seed"}


class ShowSeedExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [ShowSeed]


async def comfy_entrypoint() -> ComfyExtension:
    return ShowSeedExtension()
