# -*- coding: utf-8 -*-
"""
ComfyUI-StringCompareNumber
ComfyUI 节点入口文件
"""

from .string_compare_node import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]

WEB_DIRECTORY = "./web"  # 预留，目前无前端资源

print("\033[92m[ComfyUI-StringCompareNumber]\033[0m 节点加载成功: String Compare Number")
