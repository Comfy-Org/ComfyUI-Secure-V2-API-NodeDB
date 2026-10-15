"""Conditioning buffers to Wan text-embedding data, with managed placement.

Only the first conditioning tensor is selected, exactly as upstream. Numeric
values/dtypes/order are unchanged. The receiving model executor owns device
placement; this data node does not discover or allocate a host compute device.
Non-buffer-safe conditioning metadata is refused by the actual value adapter,
even though upstream ignored metadata. No live host model is materialized.
"""
from comfy_api.latest import io


class WanVideoTextEmbedBridge(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="WanVideoTextEmbedBridge", display_name="WanVideo TextEmbed Bridge",
            category="WanVideoWrapper",
            description="Bridge between ComfyUI native text embedding and WanVideoWrapper text embedding",
            inputs=[io.Conditioning.Input("positive"), io.Conditioning.Input("negative", optional=True)],
            outputs=[io.Custom("WANVIDEOTEXTEMBEDS").Output(display_name="text_embeds")],
        )

    @classmethod
    def execute(cls, positive, negative=None):
        return io.NodeOutput({
            "prompt_embeds": positive[0][0],
            "negative_prompt_embeds": negative[0][0] if negative is not None else None,
        })


NODE_CLASS_MAPPINGS = {"WanVideoTextEmbedBridge": WanVideoTextEmbedBridge}
