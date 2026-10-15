"""Test-only raw MoCha math probe; never added to the release manifest."""
import torch
from comfy_api.latest import io
from .secure_mocha_algorithms import prepare_mocha_inputs, assemble_mocha_embeds, rope_apply_mocha


class JackWanMochaMathProbe(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="JackWanMochaMathProbe", inputs=[
            io.Custom("JACK_MOCHA_STAGE").Input("payload"),
            io.Combo.Input("mode", options=["prepare", "assemble", "rotary"])],
            outputs=[io.Custom("JACK_MOCHA_STAGE").Output()])

    @classmethod
    def execute(cls, payload, mode):
        if mode == "prepare":
            result = prepare_mocha_inputs(payload["input_video"], payload["ref1"],
                payload["dtype_marker"].dtype, payload.get("ref2"))
        elif mode == "assemble":
            args = dict(payload)
            args["dtype"] = args.pop("dtype_marker").dtype
            result = assemble_mocha_embeds(**args)
        else:
            result = {"rotary": rope_apply_mocha(**payload)}
        return io.NodeOutput(result)


NODE_CLASS_MAPPINGS = {"JackWanMochaMathProbe": JackWanMochaMathProbe}
