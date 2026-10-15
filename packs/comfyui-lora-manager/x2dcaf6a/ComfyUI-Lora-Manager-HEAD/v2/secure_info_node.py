"""Pinned display-only Info backend; frontend lifecycle still pending."""
from comfy_api.latest import io
class LoraInfo(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='Lora Info (LoraManager)',category='Lora Manager/utils',description='Displays information (filename, notes) about the currently selected LoRA. Connect any output from a LoRA Loader or Stacker to the lora_source input, then select a LoRA in the source widget — the info updates automatically. Does not affect workflow execution.',inputs=[],outputs=[])
    @classmethod
    def execute(cls,**kwargs):
        return io.NodeOutput()
