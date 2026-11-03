"""Guest stand-in for upstream style_transfer.py. The loop imports two helpers that only style guides call."""
from ._comfy._refuse import refuse


def apply_scattersort_spatial(*_args, **_kwargs):
    refuse("style guides (apply_scattersort_spatial)")


def apply_adain_spatial(*_args, **_kwargs):
    refuse("style guides (apply_adain_spatial)")
