"""Secure Nodes V2 conversion of comfyui-mdnotes."""

from .nodes import CheckpointNameList, DfmNameList, LoraNameList

NODE_CLASS_MAPPINGS = {
    "mdnotes_ckpt_name_list": CheckpointNameList,
    "mdnotes_lora_name_list": LoraNameList,
    "mdnotes_dfm_name_list": DfmNameList,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    node_id: node.GET_SCHEMA().display_name
    for node_id, node in NODE_CLASS_MAPPINGS.items()
}
WEB_DIRECTORY = "web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
