"""Qwen-VL scheduled first-row projection; inspect-only shape diagnostic.

Only admitted BHWC C3/C4 inputs use the source's first-three-channel slice.
The encoder remains canonical and host-owned; this is not trained-inference
or downstream Wan sampler/model/profile certification.
"""
from comfy_api.latest import io

LLAMA_TEMPLATE = "<|im_start|>system\nYou are a helpful assistant.<|im_end|>\n<|im_start|>user\n<|vision_start|><|image_pad|><|vision_end|>{}<|im_end|>\n<|im_start|>assistant\n"


class TextImageEncodeQwenVL(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("inspect",)

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="TextImageEncodeQwenVL", category="WanVideoWrapper",
            inputs=[io.Clip.Input("clip"),
                io.String.Input("prompt", default="", multiline=True),
                io.Image.Input("image", optional=True)],
            outputs=[io.Custom("QWENVL_EMBEDS").Output(display_name="qwenvl_embeds")])

    @classmethod
    async def execute(cls, clip, prompt, image=None):
        input_images = [] if image is None else [await image.rgb()]
        template = None if image is None else LLAMA_TEMPLATE
        conditioning = await clip.encode(prompt, images=input_images,
            llama_template=template)
        embedding = await conditioning.embedding(index=0)
        # Existing bounded inspect authority supplies inert geometry only.
        # No CONDITIONING metadata or tensor values are exported.
        description = await embedding.describe()
        print("Qwen-VL embeds shape:", "torch.Size(" + str(description["shape"]) + ")")
        return io.NodeOutput(embedding)


NODE_CLASS_MAPPINGS = {"TextImageEncodeQwenVL": TextImageEncodeQwenVL}
