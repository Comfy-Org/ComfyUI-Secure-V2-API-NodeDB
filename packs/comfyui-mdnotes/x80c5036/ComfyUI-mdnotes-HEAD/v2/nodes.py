"""The three model-name passthrough nodes, using host model catalogues."""

from comfy_api.latest import io


def _model_name_node(class_name, node_id, display_name, input_id, input_label, route):
    def define_schema(cls):
        return io.Schema(
            node_id=node_id, display_name=display_name, category="mdnotes",
            inputs=[io.Combo.Input(
                input_id, options=[], display_name=input_label, default=0,
                remote=io.RemoteOptions(route=route, refresh_button=True),
            )],
            outputs=[io.AnyType.Output(
                "name_of_selected_model", display_name=input_label[:-1],
            )],
        )

    def execute(cls, **kwargs):
        return io.NodeOutput(kwargs[input_id])

    return type(class_name, (io.ComfyNode,), {
        "__module__": __name__, "define_schema": classmethod(define_schema),
        "execute": classmethod(execute), "SDK_REFS": True,
        "SDK_PERMISSIONS": (),
    })


CheckpointNameList = _model_name_node(
    "CheckpointNameList", "mdnotes_ckpt_name_list", "Checkpoint Name List",
    "ckpt_name", "Checkpoint Names", "/models/checkpoints")
LoraNameList = _model_name_node(
    "LoraNameList", "mdnotes_lora_name_list", "Lora Name List",
    "lora_name", "Lora Names", "/models/loras")
DfmNameList = _model_name_node(
    "DfmNameList", "mdnotes_dfm_name_list", "Diffusion Model Name List",
    "dfm_name", "Diffusion Model Names", "/models/diffusion_models")
