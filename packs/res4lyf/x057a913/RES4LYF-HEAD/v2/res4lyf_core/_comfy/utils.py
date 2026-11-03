"""Stand-ins for ``comfy.utils``. Only refused paths reference these from the vendored loop:
- latent resizing (resample/unsample state, tiling, guides);
- packed multi-stream latents (video+audio).
"""
from ._refuse import refuse

PROGRESS_BAR_ENABLED = False


def common_upscale(*_args, **_kwargs):
    refuse("latent resizing (comfy.utils.common_upscale: resample/unsample state, tiling or guides)")


def pack_latents(*_args, **_kwargs):
    refuse("packed multi-stream latents (comfy.utils.pack_latents)")


def unpack_latents(*_args, **_kwargs):
    refuse("packed multi-stream latents (comfy.utils.unpack_latents)")
