"""Stand-in for ``comfy.ldm.common_dit``: only style-transfer guides use it, and they are refused."""
from .._refuse import refuse


def pad_to_patch_size(*_args, **_kwargs):
    refuse("style-transfer guides (comfy.ldm.common_dit.pad_to_patch_size)")
