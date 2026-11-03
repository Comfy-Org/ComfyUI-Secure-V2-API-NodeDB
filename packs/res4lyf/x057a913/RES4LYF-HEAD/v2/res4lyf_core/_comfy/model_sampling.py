"""Stand-ins for ``comfy.model_sampling``: the two parameterizations the reduced envelope admits.

``EPS`` and ``CONST`` are used by the vendored loop for isinstance checks (VE_MODEL, VARIANCE_PRESERVING) and for
RES4LYF's final step (rk_sampler_beta.py:2202-2209), which calls ``calculate_denoised`` without a model evaluation.
``reshape_sigma`` and both ``calculate_denoised`` bodies are exact copies of ComfyUI core
(comfy/model_sampling.py:24-37, 86-92 at 6257422b). The node only builds a CONST instance after it has proved plain
CONST with a zero-evaluation probe, and only builds an EPS instance whose ``calculate_denoised`` refuses: the
guest cannot tell EPS from V_PREDICTION/X0/EDM, which differ exactly there.
"""
import torch

from ._refuse import refuse


def reshape_sigma(sigma, noise_dim):
    if sigma.nelement() == 1:
        return sigma.view(())
    else:
        return sigma.view(sigma.shape[:1] + (1,) * (noise_dim - 1))


class EPS:
    def calculate_denoised(self, sigma, model_output, model_input):
        refuse("the final sigma_min step on a sigma-parameterized model (EPS vs V_PREDICTION/X0/EDM cannot be "
               "confirmed in the guest, and their calculate_denoised differ)")


class CONST:
    def calculate_denoised(self, sigma, model_output, model_input):
        sigma = reshape_sigma(sigma, model_output.ndim)
        return model_input - model_output * sigma


class GuestModelSampling:
    """The model_sampling object the vendored loop sees: exact scalar endpoints from the host model."""

    def __init__(self, sigma_min: float, sigma_max: float, noise_scale: float = 1.0):
        self.sigma_min = torch.tensor(sigma_min, dtype=torch.float32)
        self.sigma_max = torch.tensor(sigma_max, dtype=torch.float32)
        self.noise_scale = noise_scale


class GuestEPS(GuestModelSampling, EPS):
    pass


class GuestCONST(GuestModelSampling, CONST):
    pass
