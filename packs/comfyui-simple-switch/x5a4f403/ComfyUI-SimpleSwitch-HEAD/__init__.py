from .simple_switch import (
    SimpleAudioLatentSwitch,
    SimpleLatentSwitch,
    SimpleSwitch,
    SimpleVideoLatentSwitch,
)

NODE_CLASS_MAPPINGS = {
    "SimpleSwitch": SimpleSwitch,
    "SimpleLatentSwitch": SimpleLatentSwitch,
    "SimpleAudioLatentSwitch": SimpleAudioLatentSwitch,
    "SimpleVideoLatentSwitch": SimpleVideoLatentSwitch,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SimpleSwitch": "Simple Switch (6 Inputs)",
    "SimpleLatentSwitch": "Simple Latent Switch (6 Inputs)",
    "SimpleAudioLatentSwitch": "Simple Audio Latent Switch (6 Inputs)",
    "SimpleVideoLatentSwitch": "Simple Video Latent Switch (6 Inputs)",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
