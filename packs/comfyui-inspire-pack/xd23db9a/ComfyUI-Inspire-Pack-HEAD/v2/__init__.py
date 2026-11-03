"""
@author: Dr.Lt.Data
@title: Inspire Pack
@nickname: Inspire Pack
@description: This extension provides various nodes to support Lora Block Weight, Regional Nodes, Backend Cache, Prompt Utils, List Utils and the Impact Pack.

Secure Nodes V2: only the nodes in secure_inspire.py are registered. The original imported all
thirteen inspire modules here (several need the Impact Pack and host modules at import) and
served ./js; see SECURE_CONVERSION.md.
"""

import logging

version_code = [1, 23]
version_str = f"V{version_code[0]}.{version_code[1]}" + (f'.{version_code[2]}' if len(version_code) > 2 else '')
logging.info(f"### Loading: ComfyUI-Inspire-Pack ({version_str})")

from .secure_inspire import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS  # noqa: E402

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
