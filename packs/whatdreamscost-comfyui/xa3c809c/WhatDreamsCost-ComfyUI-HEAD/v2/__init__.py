"""Secure Nodes V2 entrypoint for WhatDreamsCost-ComfyUI."""
from __future__ import annotations

from comfy_api.latest import ComfyExtension, io

from ._secure_director import LTXDirector, LTXDirectorCropGuides, LTXDirectorGuide
from .load_audio_ui import LoadAudioUI
from .load_video_ui import LoadVideoUI
from .ltx_keyframer import LTXKeyframer
from .ltx_sequencer import LTXSequencer
from .multi_image_loader import MultiImageLoader
from .speech_length_calculator import SpeechLengthCalculator


NODE_CLASS_MAPPINGS = {
    "LTXKeyframer": LTXKeyframer,
    "MultiImageLoader": MultiImageLoader,
    "LTXSequencer": LTXSequencer,
    "SpeechLengthCalculator": SpeechLengthCalculator,
    "LoadAudioUI": LoadAudioUI,
    "LoadVideoUI": LoadVideoUI,
    "LTXDirector": LTXDirector,
    "LTXDirectorGuide": LTXDirectorGuide,
    "LTXDirectorCropGuides": LTXDirectorCropGuides,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LTXKeyframer": "LTX Keyframer",
    "MultiImageLoader": "Multi Image Loader",
    "LTXSequencer": "LTX Sequencer",
    "SpeechLengthCalculator": "Speech Length Calculator",
    "LoadAudioUI": "Load Audio UI",
    "LoadVideoUI": "Load Video UI",
    "LTXDirector": "LTX Director",
    "LTXDirectorGuide": "LTX Director Guide",
    "LTXDirectorCropGuides": "LTX Director Crop Guides",
}

WEB_DIRECTORY = "./js"


class WhatDreamsCostExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return list(NODE_CLASS_MAPPINGS.values())


async def comfy_entrypoint() -> WhatDreamsCostExtension:
    return WhatDreamsCostExtension()


__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "WEB_DIRECTORY",
    "comfy_entrypoint",
]
