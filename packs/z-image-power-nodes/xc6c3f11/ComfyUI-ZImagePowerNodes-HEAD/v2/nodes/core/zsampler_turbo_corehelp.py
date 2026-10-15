"""
File    : zsampler_turbo_corehelp.py
Purpose : Helper functions for "zsampler_turbo_core.py".
Author  : Martin Rizzo | <martinrizzo@gmail.com>
Date    : Mar 16, 2026
Repo    : https://github.com/martin-rizzo/ComfyUI-ZImagePowerNodes
License : MIT
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
                          ComfyUI-ZImagePowerNodes
         ComfyUI nodes designed specifically for the "Z-Image" model.
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
"""
import torch
import torch.nn.functional as F
from typing         import Callable, Any
from torch          import Tensor
from comfy.samplers import KSAMPLER, ksampler, sampler_object


#================= Adjusted Spectral Distribution Sampler ==================#

class SpectralAdjustedSampler(KSAMPLER):
    """
    Wrapper class that intercepts the noise generation process of a base
    sampler to apply custom spectral adjustments to the noise distribution.

    This sampler modifies the noise by tilting its frequency spectrum based on
    the current sigma level during the diffusion process, allowing control over
    the image noise generation characteristics.

    Args:
        alpha_tilting:   Frequency tilt applied to the spectrum.
                         If a single value is provided, it represents a constant tilt.
                         If a tuple is given, it represents the start and end tilting
                         values for a step-varying effect.
        alpha_sharpness: Sharpness of the exponential alpha interpolation curve
                         used when `alpha_tilting` is a tuple. 1.0 represents linear.
        sigma_range:     Tuple of (start, end) sigma values defining the range
                         over which the interpolation occurs.
        inner_sampler:   The base `KSAMPLER` instance to be wrapped, which will
                         handle the core diffusion sampling steps.
    Notes:
        This implementation explores specific spectral manipulation inspired by
        the energy transfer concepts found in "Colored Noise Diffusion Sampling".
        While it utilizes the fundamental premise of frequency-domain noise
        modulation, this is a custom implementation intended for experimentation
        and does not strictly map to the algorithmic specifications or the
        framework detailed in the source paper.
    References:
        Inspired by: Davidson H., Issachar N., & Benaim S. (2026). "Colored Noise Diffusion
        Sampling". arXiv preprint arXiv:2605.30332. https://arxiv.org/abs/2605.30332
    """
    def __init__(self,
                 alpha_tilting  : tuple[float,float] | float = (0.1, -1.0),
                 alpha_sharpness: float                      = 1.0,
                 sigma_range    : tuple[float,float]         = (0.9999, 0.0),
                 *,
                 inner_sampler  : KSAMPLER,
                 ):
        self._inner_sampler      = inner_sampler
        self._ea_alpha_tilting   = alpha_tilting
        self._ea_alpha_sharpness = alpha_sharpness
        self._ea_sigma_range     = sigma_range
        super().__init__(sampler_function = (lambda *a,**kw: self._inner_sampler_with_custom_noise(*a, **kw)),
                         extra_options    = inner_sampler.extra_options.copy(),
                         inpaint_options  = inner_sampler.inpaint_options.copy()
                         )

    def _inner_sampler_with_custom_noise(self,
                                         model : object,
                                         noise : Tensor,
                                         sigmas: Tensor,
                                         *args,**kwargs,
                                         ) -> Tensor:
        """Execute the inner sampler but using a custom modified noise.

        This method is registered by the class `__init__` and is invoked
        by ComfyUI multiple times during the denoising process.
        """
        # get the base noise sampler provided by ComfyUI
        base_noise_sampler = kwargs.pop("noise_sampler", None)
        if base_noise_sampler is None:
            base_noise_sampler = (lambda *a,**kw: torch.randn_like(noise))

        # get my custom noise sampler
        custom_noise_sampler = (lambda *a,**kw: self._custom_noise_sampler(base_noise_sampler, *a, **kw))

        # execute the inner sampler but with my custom noise sampler
        return self._inner_sampler.sampler_function(model, noise, sigmas, *args,
                                                    noise_sampler = custom_noise_sampler,
                                                    **kwargs)

    def _custom_noise_sampler(self,
                              base_noise_sampler: Callable,
                              sigma             : Tensor,
                              *args, **kwargs
                              ) -> Tensor:
        """Generates noise with an adjusted spectral distribution.

        This method is registered by `_inner_sampler_with_custom_noise(...)`
        and is invoked by ComfyUI multiple times during the denoising process.
        Args:
            base_noise_sampler: The original function used by ComfyUI to generate noise.
            sigma             : The sigma value for which the noise should be spectrally adjusted.
            *args, **kwargs   : Additional arguments to be passed to the base_noise_sampler.
        Returns:
            A tensor of custom noise with an adjusted spectral distribution.
        """
        sigma_f       = float(sigma.mean().detach().cpu())
        alpha_tilting = self._ea_alpha_tilting

        # calculate the value `alpha` corresponding to the current sampling step's sigma value
        if isinstance(alpha_tilting, (list, tuple)) and len(alpha_tilting) == 2:
            start_sigma, end_sigma = self._ea_sigma_range
            range    = end_sigma - start_sigma
            progress = max(0.0, min(1.0, (sigma_f - start_sigma) / range)) if range != 0 else 1.0
            alpha = alpha_tilting[0] + (progress**self._ea_alpha_sharpness) * (alpha_tilting[1] - alpha_tilting[0])
        else:
            alpha = float(alpha_tilting)

        # use the base sampler to generate standard noise and then adjust its spectral distribution
        noise = base_noise_sampler(sigma, *args, **kwargs)
        return _adjust_spectral_distribution(noise, alpha=alpha, force_zero_mean=False)


#==================== EULER Ancestral Spectral Sampler =====================#

class EulerAss(SpectralAdjustedSampler):
    """
    Euler Ancestral Spectral Sampler.

    A variant of the Euler Ancestral sampler that incorporates custom frequency
    spectrum adjustments to the stochastic noise component during the diffusion
    process.

    Args:
        alpha_tilting:   Frequency tilt applied to the spectrum.
                         If a single value is provided, it represents a constant tilt.
                         If a tuple is given, it represents the start and end tilting
                         values for a step-varying effect. Default is (0.1, -1.0).
        alpha_sharpness: Sharpness of the exponential alpha interpolation curve
                         used when `alpha_tilting` is a tuple. 1.0 represents linear.
                         Default is 1.0.
        sigma_range:     Tuple of (start, end) sigma values defining the range
                         over which the interpolation occurs. Default is (0.9999, 0.0).
        eta:             The stochasticity factor (ancestral noise intensity).
                         If `None`, the default value of the underlying sampler is used.
        s_noise:         The noise scaling factor applied to the ancestral component.
                         If `None`, the default value of the underlying sampler is used.
    """
    def __init__(self,
                 alpha_tilting  : tuple[float,float] | float = (0.1, -1.0),
                 alpha_sharpness: float                      = 1.0,
                 sigma_range    : tuple[float,float]         = (0.9999, 0.0),
                 *,
                 eta    : float | None = None,
                 s_noise: float | None = None,
                 ):
        eulera_options = {}
        if eta     is not None: eulera_options["eta"]     = eta
        if s_noise is not None: eulera_options["s_noise"] = s_noise

        euler_ancestral = sampler_from_name("euler_ancestral", eulera_options)
        super().__init__(alpha_tilting, alpha_sharpness, sigma_range, inner_sampler=euler_ancestral)


#==================== DPM-Solver++ SDE Spectral Sampler ====================#

class DPMPP_SDEss(SpectralAdjustedSampler):
    """
    DPM-Solver++ SDE Spectral Sampler.

    A variant of the DPM-Solver++ SDE sampler that incorporates custom frequency
    spectrum adjustments to the stochastic noise component during the diffusion
    process.

    Args:
        alpha_tilting:   Frequency tilt applied to the spectrum.
                         If a single value is provided, it represents a constant tilt.
                         If a tuple is given, it represents the start and end tilting
                         values for a step-varying effect. Default is (0.1, -1.0).
        alpha_sharpness: Sharpness of the exponential alpha interpolation curve
                         used when `alpha_tilting` is a tuple. 1.0 represents linear.
                         Default is 1.0.
        sigma_range:     Tuple of (start, end) sigma values defining the range
                         over which the interpolation occurs. Default is (0.9999, 0.0).
        eta:             Stochasticity factor for the SDE sampler.
        s_noise:         Additional noise scaling factor.
        r:               Order parameter for the DPM-Solver++ algorithm.
        noise_device:    The device to allocate the noise generation, defaults to 'cpu'.
    """
    def __init__(self,
                 alpha_tilting  : tuple[float,float] | float = (0.1, -1.0),
                 alpha_sharpness: float                      = 1.0,
                 sigma_range    : tuple[float,float]         = (0.9999, 0.0),
                 *,
                 eta         : float | None = None,
                 s_noise     : float | None = None,
                 r           : float | None = None,
                 noise_device: str = "cpu"
                 ):
        dpmpp_options = {}
        if eta     is not None: dpmpp_options["eta"]     = eta
        if s_noise is not None: dpmpp_options["s_noise"] = s_noise
        if r       is not None: dpmpp_options["r"]       = r
        if noise_device == 'cpu':
            dpmpp_sde = sampler_from_name("dpmpp_sde", extra_options=dpmpp_options)
        else:
            dpmpp_sde = sampler_from_name("dpmpp_sde_gpu", extra_options=dpmpp_options)

        super().__init__(alpha_tilting, alpha_sharpness, sigma_range, inner_sampler=dpmpp_sde)







def sampler_from_name(name: str, extra_options={}) -> KSAMPLER:
    if not isinstance(name,str):
        raise ValueError(f"Sampler name must be a string, not '{type(name)}'")

    if name == "euler_ancestral":
        return ksampler("euler_ancestral", extra_options=extra_options)

    elif name == "dpmpp_sde":
        return ksampler("dpmpp_sde", extra_options=extra_options)

    elif name == "dpmpp_sde_gpu":
        return ksampler("dpmpp_sde_gpu", extra_options=extra_options)

    elif name == "euler_ass":
        return EulerAss()

    else:
        return sampler_object(name)


#============================ NOISE PROCESSING =============================#

def generate_noise(seed           : int,
                   shape          : tuple[int, ...],
                   *,
                   noise_bias     : Tensor | float | int | None = None,
                   noise_scale    : Tensor | float | int | None = None,
                   batch_subseeds : list[int] | None                  = None,
                   dtype          : torch.dtype,
                   layout         : torch.layout,
                   device         : str | torch.device = "cpu"
                   ):
    """
    Generate batched noise with optional per-sample 'virtual' sub-seeds.
    """
    generator = torch.manual_seed(seed)
    return _generate_noise(generator, shape, dtype, layout, noise_bias, noise_scale, batch_subseeds, device)


def _generate_noise(generator      : torch.Generator,
                    shape          : tuple[int, ...],
                    dtype          : torch.dtype,
                    layout         : torch.layout,
                    noise_bias     : Tensor | float | int | None = None,
                    noise_scale    : Tensor | float | int | None = None,
                    batch_subseeds : list[int] | None            = None,
                    device         : str | torch.device          = "cpu"
                    ):
    """
    Generate batched noise with optional per-sample 'virtual' sub-seeds.

    Args:
        generator      : A `torch.Generator` object for generating random numbers.
        shape          : Noise shape. The first dimension is the batch size.
        dtype          : The floating-point dtype of the generated tensor.
        layout         : torch.strided or torch.sparse_coo, etc.
        noise_bias     : Optional constant offset added to the noise.
                          if `None` or not provided, this is set to 0.0
        noise_scale    : Optional scale factor applied to the raw normal noise.
                          if `None` or not provided, this is set to 1.0
        batch_subseeds : Optional list of small integers (0, 1, 2, …) that act as virtual seeds
                          for every sample in the batch. Repetitions are allowed; repeated indices
                          yield identical noise for those samples. If `None` or empty, every sample
                          receives independent noise.
        device         : Target device for the generated tensor.
    Returns:
        A noise tensor of the requested shape, already biased and scaled.
    """
    if batch_subseeds:
        # batch subseeds were provided, indicating the virtual seed value for
        # generating noise for each batch element. These values should be small
        # integers like [0, 1, 2, 3] or [0, 1, 0, 1], or even [0, 0, 0, 0] if
        # identical noise is desired for all elements in the batch.
        subseeds_tensor = torch.tensor(batch_subseeds, device="cpu")
        unique_tensor, inverse_tensor = torch.unique(subseeds_tensor, return_inverse=True)
        unique_subseeds = unique_tensor.tolist()
        inverse         = inverse_tensor.tolist()

        # define shape for a single sample (batch size = 1)
        subnoise_shape = (1, *shape[1:])

        # generate unique noise samples for each unique sub-seed
        subnoises : list[Tensor] = []
        max_subseed = int(unique_subseeds.max())
        for subseed in range(max_subseed+1):
            subnoise = torch.randn(subnoise_shape, dtype=dtype, layout=layout, generator=generator, device=device)
            if subseed in unique_subseeds:
                subnoises.append(subnoise)
        noise = torch.cat( [subnoises[idx] for idx in inverse] )
    else:
        # if no batch subseeds are provided, generate a single noise tensor for
        # the entire batch with fully random values.
        noise = torch.randn(shape, dtype=dtype, layout=layout, generator=generator, device=device)

     # apply noise bias and scale if provided
    if noise_scale is not None: noise *= noise_scale
    if noise_bias  is not None: noise += noise_bias
    return noise


def inject_freq_noise(x    : Tensor,
                      seed : int,
                      *,
                      noise_freqs : int   | tuple[int,...]   = 1024,
                      noise_scales: float | tuple[float,...] = 1.0,
                      ) -> Tensor:
    """
    Injects noise at specified "frequencies" into the input tensor `x`.

    This function generates noise at different resolutions based on the provided
    frequencies, resulting in a range of low-frequency noise effects when applied
    to the input tensor.

    Args:
        x            : Input tensor to which noise will be added.
        seed         : Seed for random noise generation to ensure reproducibility.
        noise_freqs  : Frequency factors that determine the resolutions at which
                       noise is generated. Multiple frequencies can be specified as a tuple,
                       resulting in multiple layers of noise with varying smoothness.
                       A lower value results in smoother noise. For example, a noise_freq of 1024
                       means noise is injected into every pixel, while a noise_freq of 512 means
                       noise is injected every second pixel, with intermediate pixels being interpolated.
        noise_scales : Scale factors for the noise intensities corresponding to each frequency.
                       Multiple scales can be specified as a tuple. Default is 1.0.
                       A 0.0 value disables noise injection for that particular scale and frequency pair.

    Returns:
        The input tensor x with low-frequency noise injected according to
        the provided frequencies and scales.
    """
    h, w  = x.shape[-2:]

    # force `freqs` and `scales` to be tuples
    freqs : tuple[int, ...]   = noise_freqs  if isinstance(noise_freqs , tuple) else (noise_freqs,)
    scales: tuple[float, ...] = noise_scales if isinstance(noise_scales, tuple) else (noise_scales,)
    if len(freqs) != len(scales):
        raise ValueError("noise_freqs and noise_scales must have the same length")

    # iterate over pairs of frequency/scale injecting the corresponding noise
    for freq, scale in zip(freqs, scales):
        if scale <= 0.0  or  freq < (1024/h)  or  freq < (1024/w):
            continue

        # generate a small size noise
        low_res_shape = ( *x.shape[:-2], (h * freq) // 1024, (w * freq) // 1024 )
        seed += 1
        noise = generate_noise(seed,
                               noise_scale = scale,
                               shape       = low_res_shape,
                               dtype       = x.dtype,
                               layout      = x.layout,
                               device      = x.device)

        # inject the noise, interpolating it to the input tensor size
        x = x + F.interpolate(noise,
                              size          = (h, w),
                              mode          = 'bilinear',
                              align_corners = False)

    return x


def _adjust_spectral_distribution(noise: Tensor,
                                  *,
                                  alpha                : float,
                                  power_gamma          : float = 0.5,
                                  normalize_per_channel: bool  = False,
                                  force_zero_mean      : bool  = False,
                                  energy_scale         : float = 1.0,
                                  eps                  : float = 1e-06,
                                  ) -> Tensor:
    """
    Apply frequency-based scaling to a noise tensor, shaping its spectral power distribution.
    Args:
        noise                : The input tensor with the noise to adjust the spectral power distribution.
                                shape = [batch, channels, height, width]
        alpha                : Scaling factor that dictates the decay of power across frequencies.
        power_gamma          : Base exponent for frequency scaling. Default is 0.5.
        normalize_per_channel: If False (default/recommended), normalize each sample/image as
                                a unit (Instance Normalization).
                                If True, normalizes each channel independently, keeping channels
                                independent (Channel Normalization). Default is False.
        force_zero_mean      : If True, the function will subtract the mean of the noise tensor
                                before applying the spectral adjustments. Default is False.
        energy_scale         : Scaling factor for the final energy. Default is 1.0.
        eps                  : Small constant for numerical stability during division or clamping.
    Returns:
        A tensor with adjusted frequency characteristics.
    """
    device, dtype = noise.device, noise.dtype
    B, C, H, W    = noise.shape

    # define spatial normalization dimensions
    norm_dims = (2, 3) if normalize_per_channel else (1, 2, 3)

    # create 2D frequency grid (squared frequency magnitude)
    u = torch.fft.fftfreq(H, device=device, dtype=dtype).view(H, 1)
    v = torch.fft.fftfreq(W, device=device, dtype=dtype).view(1, W)
    spectral_scale_grid = u**2 + v**2

    # avoid division by zero in the DC component (frequency)
    spectral_scale_grid[0, 0] = 1.0

    # calculate the filter magnitude
    # [note: in 2d physics often use "(alpha+1.0)" to match 1D energy decay]
    spectral_filter = spectral_scale_grid ** (power_gamma * alpha)

    # optional spatial domain mean normalization
    if force_zero_mean:
        noise = noise - noise.mean(dim=norm_dims, keepdim=True)

    # transform to frequency domain, filter, and return to spatial domain
    noise_fft = torch.fft.fft2(noise, dim=(-2, -1))
    noise_fft = noise_fft / spectral_filter  #< automatic broadcasting over [B, C, H, W]

    # return to spatial domain (keep the real part)
    filtered = torch.fft.ifft2(noise_fft, dim=(-2, -1)).real

    # final intensity/energy normalization
    std = filtered.std(dim=norm_dims, keepdim=True).clamp(min=eps)
    return filtered * (energy_scale / std)


#============================ SIGMA OPERATIONS =============================#

def truncate_sigmas_by_step_range(sigmas    : Tensor | None,
                                  step_range: tuple[int,int] | list[int] | None,
                                  *,
                                  first_sigma_step: int = 0,
                                  ) -> Tensor | None:
    """
    Truncate sigmas tensor based on step range.

    Args:
        sigmas          : Tensor of sigma values.
        step_range      : Tuple or list of (start_step, end_step) inclusive-exclusive.
        first_sigma_step: The step number of the first sigma value in the tensor.

    Returns:
        Truncated sigmas tensor, or None if sigmas is invalid.
    """
    if sigmas is None or sigmas.numel() <= 1:
        return None
    if not isinstance(step_range, (list, tuple)) or len(step_range) < 2:
        return sigmas

    start_step = max(0, step_range[0] - first_sigma_step)  # first step (inclusive)
    end_step   = max(0, step_range[1] - first_sigma_step)  # last step (exclusive)
    sigmas = sigmas[start_step:end_step + 1]
    if sigmas.numel()<2:
        return None
    return sigmas


def truncate_sigmas_by_value_range(sigmas      : Tensor | None,
                                   value_range : list[float] | tuple[float,float] | None,
                                   ) -> Tensor | None:
    """
    Truncates a *descending* tensor of sigmas inside a restricted range.

    The returned tensor keeps the original order and contains only the values
    that fall between `limits[0]` and `limits[1]`; if the original tensor
    is clipped at either end, the corresponding limit value is appended
    so that the final result always includes both boundaries.
    If no value satisfies this condition the function returns `None`.

    Args:
        sigmas:
            1-D tensor with sigma values sorted in **descending** order.
        limits:
            Sequence with at least two elements.
            The first and second elements are used as the `(min, max)` range
            that defines the interval for filtering.

    Returns:
        A new tensor with the sigmas that lie inside `[min, max]`.
        The tensor preserves the original descending order.
        If `sigmas` is `None` the function returns `None`.
        If `sigmas` is totally outside the limits, the function returns `None`.
    """
    if sigmas is None or sigmas.numel()<=1:
        return None

    if value_range is None:
        return sigmas
    if not isinstance(value_range, (list, tuple)) or len(value_range) < 2:
        raise ValueError("`limits` must be a list or tuple with at least 2 elements")
    if not (sigmas[0] >= sigmas[-1]):
        raise ValueError("`sigmas` must be sorted in descending order")

    # extract the lower and upper limits
    lower, upper = value_range[0], value_range[1]
    if lower > upper:
        lower, upper = upper, lower

    # if the range of sigmas is totally outside the limits
    # then none of the sigmas should be returned
    if sigmas[-1] >= upper or lower >= sigmas[0]:
        return None

    # create the mask to filter out values outside the range
    valid_mask = (upper > sigmas) & (sigmas > lower)
    if valid_mask.all():
        return sigmas

    # filter the tensor using the mask
    truncated_sigmas = sigmas[valid_mask]

    # add the lower/upper limits to the tensor if it was actually truncated
    if not valid_mask[0]:
        upper_sigma = torch.tensor([upper], dtype=sigmas.dtype, device=sigmas.device)
        truncated_sigmas = torch.cat((upper_sigma, truncated_sigmas))
    if not valid_mask[-1]:
        lower_sigma = torch.tensor([lower], dtype=sigmas.dtype, device=sigmas.device)
        truncated_sigmas = torch.cat((truncated_sigmas, lower_sigma))

    return truncated_sigmas


def refine_sigma_sequence(sigmas: list[float] | None, insert_count: int) -> list[float]:
    """
    Refines a sequence of sigmas by inserting midpoints between neighbors.

    Args:
        sigmas      : List of sigmas (e.g., [0.948, 0.858, ..., 0.0])
        insert_count: Total number of new sigmas to insert into the list
    Returns:
        A new list containing the original points plus the added midpoints
    """
    if not sigmas or len(sigmas)<2:
        sigmas = [1.0, 0.0]

    # keep looping until there are no more sigmas to insert
    while insert_count > 0:
        new_sequence = [ sigmas[0] ]

        for i in range(len(sigmas) - 1):
            # insert a midpoint between current sigma and next sigma
            if insert_count > 0:
                new_sequence.append( (sigmas[i] + sigmas[i+1]) / 2 )
                insert_count -= 1
            # re-insert the original sigma
            new_sequence.append( sigmas[i+1] )

        sigmas = new_sequence

    return sigmas

def merge_sigmas(sigmas1: Tensor | None, 
                  sigmas2: Tensor | None
                  ) -> Tensor | None:
    """
    Merges two descendingly ordered sigma tensors, removing overlapping values.
    Args:
        sigmas1: First tensor of sigmas.
        sigmas2: Second tensor of sigmas.
    Returns:
        Combined tensor with overlapping values removed and maintained in descending order.
        If both tensors are None, returns None.
    """
    if sigmas1 is None:
        return sigmas2
    if sigmas2 is None:
        return sigmas1

    # ensure tensors are on the same device and data type for concatenation
    sigmas2 = sigmas2.to(device=sigmas1.device, dtype=sigmas1.dtype)

    # find the cut-off point where elements in sigmas1 are
    # strictly greater than the first element of sigmas2
    cut = (sigmas1 > sigmas2[0]).sum()
    return torch.cat((sigmas1[:cut], sigmas2))


#============================ IMAGE SCRAMBLING =============================#

def scramble_tensor(x     : Tensor,
                    counts: tuple[int,int,int,int],
                    *,
                    seed  : int,
                    ) -> Tensor:
    """
    Scrambles the input latent image tensor.

    The function scrambles the tensor by dividing it into fragments,
    randomly reordering and flipping them, and then combining them while
    preserving the overall standard deviation and mean of the original tensor.

    Args:
        x     : Input tensor of shape (B, C, H, W) representing the latent image.
        counts: Tuple of four signed integers (left, top, right, bottom) that
                 control how many fragments are combined for each alignment.
                 Zero means “no fragments for this side”, a positive value adds
                 normal fragments, a negative value adds fragments that are also
                 randomly flipped (horizontally and vertically).
                 Passing `(0,0,0,0)` leaves the tensor unchanged.
        seed  : The seed for random number generation to ensure reproducibility.
    Returns:
        A new tensor with the same shape as `x`, where fragments of the
        original image are scrambled in a random and potentially flipped manner.
    """
    ANCHOR_NAMES = ('left', 'top', 'right', 'bottom' )
    if x.dim() != 4:
        raise ValueError("Input tensor must be (B, C, H, W).")

    # if all counts are zero, return the tensor as is
    if not any(counts):
        return x

    x_scale   = x.std (dim=(2,3), keepdim=True)
    x_bias    = x.mean(dim=(2,3), keepdim=True)
    generator = torch.Generator().manual_seed(seed)

    result = torch.zeros_like(x)
    for anchor_idx in range(4):
        for i in range( abs(counts[anchor_idx]) ):
            result +=  _random_tensor_fragment(x, generator,
                                              size   = (0.50,0.75),
                                              anchor = ANCHOR_NAMES[anchor_idx],
                                              random_horizontal_flip = counts[anchor_idx]<0,
                                              random_vertical_flip   = counts[anchor_idx]<0
                                              )

    result_scale = result.std (dim=(2,3), keepdim=True)
    result_bias  = result.mean(dim=(2,3), keepdim=True)

    # re-scale/shift to match original features
    scale_factor  = x_scale / result_scale.clamp(min=1e-6)
    combined_bias = x_bias - (result_bias * scale_factor)
    return result * scale_factor + combined_bias


def _random_tensor_fragment(x                      : Tensor,
                            generator              : torch.Generator,
                            size                   : tuple[float, float] = (0.50, 0.75),
                            anchor                 : str = 'left',
                            random_horizontal_flip : bool = True,
                            random_vertical_flip   : bool = True,
                            ) -> Tensor:
    """
    Extracts a random rectangular fragment from a 4-dimensional tensor.

    This function generates a random fragment by selecting a random rectangle
    within the tensor and then resizing it to match the original tensor's dimensions.

    Args:
        x         : Input tensor of shape (B, C, H, W) representing an image or feature map.
        generator : Random number generator for reproducibility.
        size      : Minimum and maximum relative size of the fragment as a
                     ratio of the input tensor's width. Defaults to (0.50, 0.75)
        anchor    : Specifies the side to which the fragment is anchored.
                     Can be either 'left' or 'right'. Defaults to 'left'.
    Returns:
        A tensor of the same shape as the input tensor, containing a randomly selected fragment.
    """
    if x.dim() != 4:
        raise ValueError("Input tensor must be 4-D (B, C, H, W).")
    if anchor not in {"left", "top", "right", "bottom"}:
        raise ValueError("anchor must be either 'left' or 'right'.")

    B, C, H, W = x.shape

    # give the rectangle a random size within the provided limits.
    min_size, max_size = size
    ratio = torch.rand(1, generator=generator, device=x.device) * (max_size - min_size) + min_size
    frag_width  = int(W * ratio)
    frag_height = int(H * ratio)

    # place the rectangle in a random position inside the tensor
    if anchor == "left" or anchor == "right":
        top  = torch.randint(0, H - frag_height + 1, (1,), generator=generator, device="cpu").item()
        left = 0 if anchor == "left" else W - frag_width
    else:
        left = torch.randint(0, W - frag_width + 1, (1,), generator=generator, device="cpu").item()
        top  = 0 if anchor == "top" else H - frag_height

    # fragment = (B, C, fh, fw)
    fragment = x[..., top:top + frag_height, left:left + frag_width]

    # optional random horizontal flip
    if random_horizontal_flip and torch.rand(1, generator=generator, device="cpu").item() > 0.5:
        fragment = torch.flip(fragment, dims=[-1])

    # optional random vertical flip
    if random_vertical_flip and torch.rand(1, generator=generator, device="cpu").item() > 0.5:
        fragment = torch.flip(fragment, dims=[-2])

    # return = (B, C, H, W)
    return F.interpolate(fragment, size=(H, W), mode='bilinear', align_corners=False)


#================================= HELPERS =================================#

def get_latent_size(comfy_latent: dict[str, Any]) -> tuple[int, int] | None:
    """
    Retrieve the spatial dimensions of a ComfyUI latent tensor.
    Args:
        comfy_latent: A ComfyUI LATENT dictionary containing the "samples" tensor.
    Returns:
        A tuple containing (width, height) of the latent tensor,
        or `None` if some error occurs.
    """
    latents: torch.Tensor | None = comfy_latent.get("samples")
    if latents is None:
        return None
    return latents.shape[-1], latents.shape[-2]


def adjust_latent_size(comfy_latent: dict[str, Any], size: tuple[int, int]) -> dict[str, Any]:
    """
    Resize the ComfyUI latent tensor to the specified dimensions.
    Args:
        comfy_latent: A ComfyUI LATENT dictionary containing the "samples" tensor to be resized.
        size        : A tuple specifying the target (width, height) for the latent tensor.
    Returns:
        A new ComfyUI LATENT dictionary with the resized "samples" tensor.
    """
    latents: torch.Tensor | None = comfy_latent.get("samples")
    if latents is None:
        return comfy_latent
    current_size = latents.shape[-1], latents.shape[-2]
    if current_size == size:
        return comfy_latent

    resized_latents = torch.nn.functional.interpolate(latents, size=(size[1], size[0]), mode='bilinear')
    comfy_latent = comfy_latent.copy()
    comfy_latent["samples"] = resized_latents
    return comfy_latent
