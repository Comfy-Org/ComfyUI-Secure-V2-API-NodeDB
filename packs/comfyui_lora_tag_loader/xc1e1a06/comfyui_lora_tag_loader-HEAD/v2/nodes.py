from pathlib import Path
import re

# Secure Nodes V2: model, clip and LoRA files stay on the host. The LoRA catalogue read and the
# LoRA application go through the SDK; the tag parsing below is upstream's, unchanged.
from comfy_api.latest import ComfyExtension, io, sdk

class LoraTagLoader(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("assets",)
    tag_pattern = "\<[0-9a-zA-Z\:\_\-\.\s\/\(\)\\\\]+\>"

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="LoraTagLoader",
            display_name="Load LoRA Tag",
            category="loaders",
            inputs=[
                io.Model.Input("model"),
                io.Clip.Input("clip"),
                io.String.Input("text", multiline=True),
            ],
            outputs=[
                io.Model.Output("output_0", display_name="MODEL"),
                io.Clip.Output("output_1", display_name="CLIP"),
                io.String.Output("output_2", display_name="STRING"),
            ],
        )

    @classmethod
    async def execute(cls, model, clip, text):
        return io.NodeOutput(*await cls.load_lora(cls, model, clip, text))

    async def load_lora(self, model, clip, text):
        # print(f"\nLoraTagLoader input text: { text }")

        founds = re.findall(self.tag_pattern, text)
        # print(f"\nfoound lora tags: { founds }")

        if len(founds) < 1:
            return (model, clip, text)

        model_lora = model
        clip_lora = clip
        
        lora_files = await sdk.ctx().assets.list("loras")
        for f in founds:
            tag = f[1:-1]
            pak = tag.split(":")
            type = pak[0]
            if type != 'lora':
                continue
            name = None
            if len(pak) > 1 and len(pak[1]) > 0:
                name = pak[1]
            else:
                continue
            wModel = wClip = 0
            try:
                if len(pak) > 2 and len(pak[2]) > 0:
                    wModel = float(pak[2])
                    wClip = wModel
                if len(pak) > 3 and len(pak[3]) > 0:
                    wClip = float(pak[3])
            except ValueError:
                continue
            if name == None:
                continue
            lora_name = None
            for lora_file in lora_files:
                if Path(lora_file).name.startswith(name) or lora_file.startswith(name):
                    lora_name = lora_file
                    break
            if lora_name == None:
                print(f"bypassed lora tag: { (type, name, wModel, wClip) } >> { lora_name }")
                continue
            print(f"detected lora tag: { (type, name, wModel, wClip) } >> { lora_name }")

            asset = await sdk.ctx().assets.resolve("loras", lora_name)
            # Upstream calls Core's load_lora_for_models directly: a zero strength still loads and
            # clones, and a strength is never range-checked. The host op does the same with these
            # two options (comfy_api 0.37.0 ModelRef.apply_lora). No LoRA state is kept between runs.
            model_lora, clip_lora = await model_lora.apply_lora(
                asset, clip_lora, wModel, wClip, skip_zero=False, allow_extended_strengths=True)

        plain_prompt = re.sub(self.tag_pattern, "", text)
        return (model_lora, clip_lora, plain_prompt)

NODE_CLASS_MAPPINGS = {
    "LoraTagLoader": LoraTagLoader,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    # Loaders
    "LoraTagLoader": "Load LoRA Tag",
}


class LoraTagLoaderExtension(ComfyExtension):
    async def get_node_list(self):
        return [LoraTagLoader]


async def comfy_entrypoint():
    return LoraTagLoaderExtension()
