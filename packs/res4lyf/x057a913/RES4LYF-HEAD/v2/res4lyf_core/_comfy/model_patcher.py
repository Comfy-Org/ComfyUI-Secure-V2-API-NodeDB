"""Stand-in for ``comfy.model_patcher``. Only channelwise CFG (cfg < 0 / SharkOptions channelwise_cfg) reaches it."""
from ._refuse import refuse


def set_model_options_post_cfg_function(*_args, **_kwargs):
    refuse("channelwise CFG (a post-CFG model patch)")
