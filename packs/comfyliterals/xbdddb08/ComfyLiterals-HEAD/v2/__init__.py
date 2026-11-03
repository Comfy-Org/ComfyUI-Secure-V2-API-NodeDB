from .nodes import IntLiteral, FloatLiteral, StringLiteral, KepStringLiteral, CheckpointListLiteral, LoraListLiteral
from .operations import Operation

NODE_CLASS_MAPPINGS = {
    "Int": IntLiteral,
    "Float": FloatLiteral,
    "String": StringLiteral,
    "KepStringLiteral": KepStringLiteral,
    "Operation": Operation,
    "Checkpoint": CheckpointListLiteral,
    "Lora": LoraListLiteral,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "KepStringLiteral": "String",
}

EXTENSION_NAME = "ComfyLiterals"

# Secure Nodes V2: the original symlinked its js/ folder into the host's web/extensions at import time
# (startup_utils.symlink_web_dir). A sandboxed pack does not write to the host; the Operation node's input-hiding
# extension is not served (see SECURE_CONVERSION.md).
