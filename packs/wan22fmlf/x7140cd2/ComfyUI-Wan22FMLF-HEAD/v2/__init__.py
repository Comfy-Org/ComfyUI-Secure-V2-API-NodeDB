# -*- coding: utf-8 -*-
"""
Wan Video Reference Nodes
Multi-frame reference conditioning for Wan2.2 A14B I2V models

Nodes:
1. WanFirstMiddleLastFrameToVideo - 3-frame reference with flexible positioning
2. WanMultiFrameRefToVideo - N-frame universal reference node
3. WanFourFrameReferenceUltimate - 4-frame reference with adjustable placeholder
4. WanAdvancedI2V - Ultimate unified node with all features (includes automatic chaining)
5. WanSVIProAdvancedI2V - SVI Pro Advanced node for seamless continuation
6. WanMultiImageLoader - Load multiple images with UI for batch selection and preview
"""

from typing_extensions import override
from comfy_api.latest import ComfyExtension

from .wan_first_middle_last import WanFirstMiddleLastFrameToVideo
from .wan_multi_frame import WanMultiFrameRefToVideo
from .wan_multi_image_loader import WanMultiImageLoader
from .wan_4_frame_ultimate import WanFourFrameReferenceUltimate
from .wan_advanced_i2v import (
    WanAdvancedI2V,
    WanAdvancedExtractLastFrames,
    WanAdvancedExtractLastImages,
)
from .wan_svi_pro_advanced import WanSVIProAdvancedI2V

WEB_DIRECTORY = "./js"

NODE_CLASS_MAPPINGS = {
    "WanFirstMiddleLastFrameToVideo": WanFirstMiddleLastFrameToVideo,
    "WanMultiFrameRefToVideo": WanMultiFrameRefToVideo,
    "WanMultiImageLoader": WanMultiImageLoader,
    "WanFourFrameReferenceUltimate": WanFourFrameReferenceUltimate,
    "WanAdvancedI2V": WanAdvancedI2V,
    "WanAdvancedExtractLastFrames": WanAdvancedExtractLastFrames,
    "WanAdvancedExtractLastImages": WanAdvancedExtractLastImages,
    "WanSVIProAdvancedI2V": WanSVIProAdvancedI2V,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    node_id: node_class.GET_SCHEMA().display_name
    for node_id, node_class in NODE_CLASS_MAPPINGS.items()
}

class WanVideoExtension(ComfyExtension):
    @override
    async def get_node_list(self):
        return [
            WanFirstMiddleLastFrameToVideo,
            WanMultiFrameRefToVideo,
            WanMultiImageLoader,
            WanFourFrameReferenceUltimate,
            WanAdvancedI2V,
            WanAdvancedExtractLastFrames,
            WanAdvancedExtractLastImages,
            WanSVIProAdvancedI2V,
        ]


async def comfy_entrypoint():
    return WanVideoExtension()


__all__ = ['WEB_DIRECTORY']
