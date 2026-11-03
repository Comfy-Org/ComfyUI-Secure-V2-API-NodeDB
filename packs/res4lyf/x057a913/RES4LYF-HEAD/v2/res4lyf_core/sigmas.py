"""Guest stand-in for upstream sigmas.py. The vendored loop imports get_sigmas only from rk_guide_func_beta (latent
guides), which are refused; the node computes outer schedules host-side (see clown.py)."""
from ._comfy._refuse import refuse


def get_sigmas(*_args, **_kwargs):
    refuse("latent guides (sigmas.get_sigmas inside the guide machinery)")
