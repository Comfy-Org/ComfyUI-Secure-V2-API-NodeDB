"""ComfyUI-EasyCivitai-XTNodes, Secure Nodes V2 entrypoint.

Round 1 registers the two prompt nodes (civitaiNodes/prompt_concatenate.py), whose value handling runs unchanged.
The original imported every module matched by civitaiNodes/**/*.py and added the pack folder to sys.path. The Civitai
URL loaders and the local loaders with previews are not registered in this round. The web/ extension (result-text
widgets and loader previews) is not served. See SECURE_CONVERSION.md.
"""
from .xt_prompt_nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
