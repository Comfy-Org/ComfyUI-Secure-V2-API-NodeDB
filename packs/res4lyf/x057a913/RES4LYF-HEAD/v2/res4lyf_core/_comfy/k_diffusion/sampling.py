"""Stand-in for ``comfy.k_diffusion.sampling``: only the brownian noise types use it, and they are refused."""
from .._refuse import refuse


class BrownianTreeNoiseSampler:
    def __init__(self, *_args, **_kwargs):
        refuse("brownian noise types (BrownianTreeNoiseSampler)")
