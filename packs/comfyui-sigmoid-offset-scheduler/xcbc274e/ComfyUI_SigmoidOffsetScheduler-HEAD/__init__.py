import torch
import math
import logging
import numpy
from comfy.samplers import SchedulerHandler, SCHEDULER_HANDLERS, SCHEDULER_NAMES

def _sigmoid_fn(x_norm, k=1.0, shift=0.0, range_start=-4.0, range_end=4.0):
    """
    Sigmoid function maps a normalized input (0-1) to an output (approx. 0-1).
    For x_norm [0,1], output is approx [0,1] if shift=0, k=1, range_start=-4, range_end=4.
    """
    x_mapped = (range_end - range_start) * x_norm + range_start
    shift_param_scaled = shift * 4.0
    val_for_exp = -k * (x_mapped + shift_param_scaled)
    k_x_clipped = numpy.clip(val_for_exp, -700, 700)
    return 1.0 / (1.0 + numpy.exp(k_x_clipped))

def sigmoid_offset_scheduler(model_sampling, steps: int, square_k: float = 1.0, base_c: float = 0.5) -> torch.FloatTensor:
    """
    Generates a DESCENDING sigma schedule using a sigmoid function to resample
    from model_sampling.sigmas.
    Assumes:
    - model_sampling.sigmas is a non-empty torch.Tensor, in ASCENDING order for target models.
    - steps >= 1.
    """

    total_timesteps = len(model_sampling.sigmas) - 1
    x_norm_values = numpy.linspace(0, 1, steps + 1, endpoint=True)
    sigmoid_shift_for_fn = 2.0 * (base_c - 0.5)
    raw_sigmoid = _sigmoid_fn(x_norm_values, k=square_k, shift=sigmoid_shift_for_fn)
    sig_min = _sigmoid_fn(0.0, k=square_k, shift=sigmoid_shift_for_fn)
    sig_max = _sigmoid_fn(1.0, k=square_k, shift=sigmoid_shift_for_fn)
    normalized_sigmoid = (raw_sigmoid - sig_min) / (sig_max - sig_min)
    transformed_ts_values = 1.0 - normalized_sigmoid
    ts = numpy.rint(transformed_ts_values * total_timesteps).astype(int)
    ts = numpy.clip(ts, 0, total_timesteps) # Ensure ts are valid.
    sigs = []
    last_t = -1
    for t in ts:
        if t != last_t or not sigs:
            sigs += [float(model_sampling.sigmas[t].item())]
            last_t = t

    sigma_floor = float(model_sampling.sigma_min)
    if sigs[-1] <= sigma_floor:
        sigs[-1] = 0.0
    else:
        sigs += [0.0]

    result = torch.FloatTensor(sigs)
    return result

scheduler_name = "sigmoid_offset"
if scheduler_name not in SCHEDULER_HANDLERS:
    scheduler_handler = SchedulerHandler(handler=sigmoid_offset_scheduler, use_ms=True)
    SCHEDULER_HANDLERS[scheduler_name] = scheduler_handler
    if scheduler_name not in SCHEDULER_NAMES:
        SCHEDULER_NAMES.append(scheduler_name)

class SigmoidOffsetScheduler:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
                "steps": ("INT", {"default": 30, "min": 1, "max": 10000}),
                "square_k": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 10.0, "step": 0.01, "tooltip": "Sigmoid steepness. Higher = steeper transition."}),
                "base_c": ("FLOAT", {"default": 0.5, "min": -5.0, "max": 5.0, "step": 0.01, "tooltip": "Shifts sigmoid curve. <0.5: More steps at high sigmas (early denoising); >0.5: More steps at low sigmas (late denoising)."}),
                "start_sigma": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.001, "tooltip": "Rescales the sigma to enable softer start. Set to 0.983 for old behaviour. 1.0 = no rescaling."}),
            }
        }
    RETURN_TYPES = ("SIGMAS",)
    CATEGORY = "sampling/custom_sampling/schedulers"
    FUNCTION = "get_sigmas"

    def get_sigmas(self, model, steps, square_k, base_c, start_sigma):
        sigmas = sigmoid_offset_scheduler(
            model.get_model_object("model_sampling"),
            steps,
            square_k=square_k,
            base_c=base_c,
        )
        if start_sigma != 1.0:
            s_min = sigmas.min()
            s_max = sigmas.max()
            sigmas = ((sigmas - s_min) * (start_sigma - 0.0)) / (s_max - s_min) + 0.0
        return (sigmas,)

NODE_CLASS_MAPPINGS = {
    "SigmoidOffsetScheduler": SigmoidOffsetScheduler,
}