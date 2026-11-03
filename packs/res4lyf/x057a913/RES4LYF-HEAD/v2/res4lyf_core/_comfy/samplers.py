"""Stand-in for ``comfy.samplers``. The vendored helper.py imports SCHEDULER_NAMES only for its scheduler-list
helper, which the guest loop never calls. Frozen from ComfyUI core 6257422b (comfy/samplers.py SCHEDULER_HANDLERS)."""

SCHEDULER_NAMES = [
    "simple", "sgm_uniform", "karras", "exponential", "ddim_uniform", "beta", "normal", "linear_quadratic",
    "kl_optimal",
]
