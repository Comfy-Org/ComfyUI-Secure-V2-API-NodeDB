"""Portrait payload attachment only; no model/tensor materialization authority."""
from comfy_api.latest import io
from .secure_tensor_nodes import _bound_payload, _bound_strings


class WanVideoAddFantasyPortrait(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="WanVideoAddFantasyPortrait", category="WanVideoWrapper",
            display_name="WanVideo Add Fantasy Portrait", inputs=[
                io.Custom("WANVIDIMAGE_EMBEDS").Input("embeds"),
                io.Custom("PORTRAIT_EMBEDS").Input("portrait_embeds"),
                io.Float.Input("strength", default=1.0, min=0.0, max=100.0, step=0.01,
                    tooltip="Strength of the portrait embedding"),
                io.Float.Input("start_percent", default=0.0, min=0.0, max=1.0, step=0.01,
                    tooltip="Start percentage of the embedding application"),
                io.Float.Input("end_percent", default=1.0, min=0.0, max=1.0, step=0.01,
                    tooltip="End percentage of the embedding application"),
                io.Float.Input("portrait_cfg", default=1.0, min=0.0, max=20.0, step=0.01,
                    tooltip="CFG scale for the portrait embedding"),
            ], outputs=[io.Custom("WANVIDIMAGE_EMBEDS").Output(display_name="image_embeds")])

    @classmethod
    def execute(cls, embeds, portrait_embeds, strength, start_percent=0.0,
                end_percent=1.0, portrait_cfg=1.0):
        # Only finite-size JSON containers may supply iterable pairs. Opaque
        # refs remain values, never resolved or treated as host dictionaries.
        if not isinstance(embeds, (dict, list, tuple, str, type(None), bool, int, float)):
            raise TypeError("Wan portrait embeds require a bounded mapping or pair sequence")
        _bound_payload((embeds, portrait_embeds, strength, start_percent, end_percent, portrait_cfg))
        if isinstance(embeds, dict):
            _bound_strings(embeds.keys())
        new_entry = {
            "adapter_proj": portrait_embeds,
            "strength": strength,
            "start_percent": start_percent,
            "end_percent": end_percent,
            "cfg_scale": portrait_cfg,
        }
        updated = dict(embeds)
        updated["portrait_embeds"] = new_entry
        _bound_strings(updated.keys())
        _bound_payload(updated)
        return io.NodeOutput(updated)


NODE_CLASS_MAPPINGS = {"WanVideoAddFantasyPortrait": WanVideoAddFantasyPortrait}
