"""
File    : zsampler_turbo_legacy_method.py
Purpose : The legacy method for the "Z-Sampler Turbo" process.
          This code is deprecated and may be removed in the future,
          it is kept only for backward compatibility.
Author  : Martin Rizzo | <martinrizzo@gmail.com>
Date    : Feb 1, 2026
Repo    : https://github.com/martin-rizzo/ComfyUI-ZImagePowerNodes
License : MIT
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
                          ComfyUI-ZImagePowerNodes
         ComfyUI nodes designed specifically for the "Z-Image" model.
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
"""
import torch
import comfy.utils
import comfy.sample
import comfy.samplers
import comfy.sampler_helpers
from typing         import Any
from .progress_bar  import ProgressPreview


def zsampler_turbo_legacy_method(latent_input             : dict[str, Any],
                                 model                    : Any,
                                 positive                 : list,
                                 *,
                                 seed                     : int,
                                 steps                    : int,
                                 denoise                  : float,
                                 initial_noise_calibration: float,
                                 noise_bias_estimation    : str,
                                 noise_bias_sample_size   : str | int | None,
                                 noise_bias_scale         : float,
                                 noise_overdose           : float,
                                 progress_preview         : ProgressPreview
                                 ) -> dict[str, Any]:
    """
    This code is deprecated and may be removed in the future,
    it is kept only for backward compatibility.
    """
    performing_inpainting = denoise < 0.999
    denoise = denoise ** 0.5

    # calibration level determines the amount of adjustment applied
    noise_bias_scale *= initial_noise_calibration
    noise_overdose   *= initial_noise_calibration

    # the "accurate" estimation method has a more sensitive scale
    if noise_bias_estimation == "accurate":
        noise_bias_scale /= 2

    # only "euler" sampler has been tested with this technique
    sampler  = comfy.samplers.sampler_object("euler")

    # `forced_size` is noise_bias_size converted to integer (pixels)
    # or None if "source" option was selected
    forced_size = None
    if isinstance(noise_bias_sample_size, str) and noise_bias_sample_size.endswith("px"):
        forced_size = int(noise_bias_sample_size[:-2])
    elif isinstance(noise_bias_sample_size, (int,float)):
        forced_size = int(noise_bias_sample_size)


    # Sigmas are divided into 3 stages:
    #
    #   Stages 1 and 2 combined function similarly to a standard denoising process,
    #   but with two key conditions:
    #     - stage 1 always has 2 steps and fixed sigmas, regardless of the total number of steps used.
    #     - there's a jump-back in sigmas between stage 1 and stage 2, there's no continuity. I'm not
    #       sure why it works, but after hundreds of tests where the final image consistently had better
    #       quality, I had to accept that this was a rule and it needed to be this way.
    #
    #   Once stages 1 and 2 are complete (acting as a standard denoising process), stage 3 begins.
    #   This is essentially a refining stage, where we go back with the sigmas, add the corresponding
    #   noise, and then do denoising from there.
    #
    #   The transition from Stage 2 to Stage 3 can also be thought of as applying an "Euler-ancestral"
    #   sampling method instead of the standard "Euler", but only for that single step between stages.
    #
    if steps>=9:
        sigmas1 = [0.991, 0.980, 0.920]                 #< +2 steps
        sigmas2 = [0.935, 0.90, 0.875, 0.750, 0.0000]   #< +4 steps
        sigmas3 = [0.6582, 0.4556, 0.2000, 0.0000]      #< +3 steps

    elif steps==8:
        sigmas1 = [0.991, 0.980, 0.920]                 #< +2 steps
        sigmas2 = [0.935, 0.90, 0.875, 0.750, 0.0000]   #< +4 steps
        sigmas3 = [0.6582, 0.3019, 0.0000]              #< +2 steps

    elif steps==7:
        sigmas1 = [0.991, 0.980, 0.920]                 #< +2 steps
        sigmas2 = [0.9350, 0.8916, 0.7600, 0.0000]      #< +3 steps
        sigmas3 = [0.6582, 0.3019, 0.0000]              #< +2 steps

    elif steps==6:
        sigma0  = 1.000
        sigmas1 = [0.991, 0.980, 0.920]                 #< +2 steps
        sigmas2 = [0.942, 0.780, 0.000]                 #< +2 steps
        sigmas3 = [0.6582, 0.3019, 0.0000]              #< +2 steps

    elif steps==5:
        sigmas1 = [0.991, 0.980, 0.920]                 #< +2 steps
        sigmas2 = [0.942, 0.780, 0.000]                 #< +2 steps
        sigmas3 = [0.6200, 0.0000]                      #< +1 step

    elif steps<=4:
        sigmas1 = [0.991, 0.980, 0.920]                 #< +2 steps
        sigmas2 = [0.942, 0.000]                        #< +1 steps
        sigmas3 = [0.790, 0.000]                        #< +1 steps

    # sigma0 is used only for estimating the initial noise bias (optional first step)
    # (denoising for that estimation step goes from sigma0 to sigmas1[0])
    sigma0 = 1.000


    # if inpainting is being performed, we combine the first two stages into one
    if performing_inpainting:
        sigmas1 = sigmas1[:-1]
        sigmas1.extend( sigmas2 )
        sigmas2 = None


    # these parameters determine the bias and amplitude of the initial noise added
    # to the latent space. vaguely speaking, they can be thought of as modifiers
    # influencing brightness and contrast/saturation of the final image.
    # given that the first sigma value is always set to "0.991", these values
    # play a role in supplementing the very low-frequency component that might
    # be lacking in the early stages of image generation.
    initial_noise_bias      = 0
    initial_noise_amplitude = 1+noise_overdose if noise_overdose>=0 else 1/(1-noise_overdose)

    # `initial_noise_bias` is calculated ONLY if the user set a non-zero scale
    # (this calculation adds an extra step to the diffusion process)
    if noise_bias_scale != 0 and noise_bias_estimation != "none" and denoise >= 0.99:
        bias = calculate_denoise_bias(latent_input, model, seed, positive, positive,
                                      sampler     = sampler,
                                      sigmas      = [sigma0, sigmas1[0]],
                                      method      = noise_bias_estimation,
                                      forced_size = forced_size,
                                      progress_preview = ProgressPreview( 100, parent=(progress_preview,0,100//steps) ),
                                      )
        initial_noise_bias = (bias / 10.0) * noise_bias_scale

    # execute the 3-stage denoising process
    latent_output = execute_3_stage_denoising(latent_input,
                                              model, seed, 1.0, positive, positive,
                                              sampler                 = sampler,
                                              sigmas1                 = sigmas1,
                                              sigmas2                 = sigmas2,
                                              sigmas3                 = sigmas3,
                                              sigma_limit             = denoise,
                                              initial_noise_bias      = initial_noise_bias,
                                              initial_noise_amplitude = initial_noise_amplitude,
                                              progress_preview = ProgressPreview( 100, parent=(progress_preview,100//steps,100) ),
                                              )
    return latent_output


    #----------------------------------------------------------------------------
    # Alternative 8/7-step sigma sequences discarded in the early stages of development
    # if steps==8:
    #     sigma0  = 1.000
    #     sigmas1 = [0.991, 0.980, 0.920]
    #     sigmas2 = [0.935, 0.8916, 0.7895, 0.000],
    #     sigmas3 = [0.6582, 0.3019, 0.0000]
    # if steps==7:
    #     sigma0  = 1.000
    #     sigmas1 = [0.991, 0.980, 0.920]
    #     sigmas2 = [0.935, 0.770, 0.000]
    #     sigmas3 = [0.6582, 0.3019, 0.0000]
    #----------------------------------------------------------------------------


def execute_3_stage_denoising(latent_image,
                                model    : Any,
                                seed     : int,
                                cfg      : float,
                                positive : list,
                                negative : list,
                                *,
                                sampler     : comfy.samplers.KSAMPLER,
                                sigmas1     : torch.Tensor | list | None,
                                sigmas2     : torch.Tensor | list | None,
                                sigmas3     : torch.Tensor | list | None,
                                sigma_limit : float | None = None,
                                initial_noise_bias     : torch.Tensor | float | int | None = None,
                                initial_noise_amplitude: torch.Tensor | float | int | None = 1.0,
                                progress_preview       : ProgressPreview,
                                ):
    """
    Executes a three-stage denoising process on the provided latent image.

    Args:
        latent_image: Dictionary containing data about the initial latent image to be processed.
                        Includes keys like "samples" and optional "noise_mask", "batch_index".
        model       : ComfyUI object representing the model to use for denoising.
        seed        : The seed used to generate random noise.
        cfg (float) : Classifier-free guidance scale that controls the influence of negative prompts.
                        A value of 1.0 means the negative prompt has no effect on generation.
        positive    : Positive prompts or conditioning applied to the model during denoising.
        negative    : Negative prompts or conditioning applied to the model during denoising.
        sampler     : ComfyUI object representing the sampler used for each denoising step.
        sigmas1     : Sigma values for the first stage of denoising. Can be a tensor, list, or None.
        sigmas2     : Sigma values for the second stage of denoising. Can be a tensor, list, or None.
        sigmas3     : Sigma values for the third stage of denoising. Can be a tensor, list, or None.
        initial_noise_bias: An optional constant bias applied to the initial noise.
                            Can be a tensor, scalar, or None.
                            If tensor, it must have shape [batch_size, channels, 1, 1].
                            (0.0 or None = no bias)
        initial_noise_amplitude: An optional amplitude factor applied to the initial noise.
                                    Can be a tensor, scalar, or None.
                                    If tensor, it must have shape [batch_size, channels, 1, 1].
                                    (0.0 = nothing ; 1.0 = standard deviation)

    Returns:
        A dictionary with the updated latent image data after all three denoising stages.
    """

    # if sigmas is a list then convert it to pytorch tensor
    if isinstance(sigmas1, list):
        sigmas1 = torch.tensor(sigmas1, device='cpu')
    if isinstance(sigmas2, list):
        sigmas2 = torch.tensor(sigmas2, device='cpu')
    if isinstance(sigmas3, list):
        sigmas3 = torch.tensor(sigmas3, device='cpu')

    if isinstance(sigma_limit, (float,int)):
        sigmas1 = truncate_sigmas(sigmas1, sigma_limit)
        sigmas2 = truncate_sigmas(sigmas2, sigma_limit)
        sigmas3 = truncate_sigmas(sigmas3, sigma_limit)

    # calculate the progress level for each step
    prog0 = 0
    prog1 = prog0 + (sigmas1.shape[-1] - 1 if sigmas1 is not None else 0)
    prog2 = prog1 + (sigmas2.shape[-1] - 1 if sigmas2 is not None else 0)
    total = prog2 + (sigmas3.shape[-1] - 1 if sigmas3 is not None else 0)



    #-- THREE-STAGE PROCESS ---------------------------

    if sigmas1 is not None:
        add_noise = True
        latent_image = execute_sampler(latent_image,
                            model, seed, cfg, positive, negative,
                            sampler          = sampler,
                            sigmas           = sigmas1,
                            noise_bias       = initial_noise_bias,
                            noise_amplitude  = initial_noise_amplitude if add_noise else 0.0,
                            keep_masked_area = True,
                            progress_preview = ProgressPreview( prog1-prog0,
                                    parent=(progress_preview, 100*prog0//total, 100*prog1//total)),
                            )



    if sigmas2 is not None:
        add_noise = False
        # normally this stage should NOT add noise (stage1 and stage2 must behave
        # as a single donoise process) but if no first stage was executed then
        # this stage is the first and therefore it must add noise
        if sigmas1 is None: add_noise = True
        latent_image = execute_sampler(latent_image,
                        model, seed, cfg, positive, negative,
                        sampler          = sampler,
                        sigmas           = sigmas2,
                        noise_bias       = 0,
                        noise_amplitude  = 1.0 if add_noise else 0.0,
                        keep_masked_area = True,
                        progress_preview = ProgressPreview( prog2-prog1,
                                   parent=(progress_preview, 100*prog1//total, 100*prog2//total)),
                        )


    if sigmas3 is not None:
        add_noise = True
        latent_image = execute_sampler(latent_image,
                        model, 696969, cfg, positive, negative,
                        sampler          = sampler,
                        sigmas           = sigmas3,
                        noise_bias       = 0,
                        noise_amplitude  = 1.0 if add_noise else 0.0,
                        keep_masked_area = True,
                        progress_preview = ProgressPreview( total-prog2,
                                parent=(progress_preview, 100*prog2//total, 100*total//total)),
                        )
    return latent_image



def execute_sampler(latent_image    : dict[str, Any],
                    model           : Any,
                    noise_seed      : int,
                    cfg             : float,
                    positive        : list,
                    negative        : list,
                    *,
                    sampler         : comfy.samplers.KSAMPLER,
                    sigmas          : list | torch.Tensor,
                    noise_bias      : torch.Tensor | float | int | None,
                    noise_amplitude : torch.Tensor | float | int | None,
                    keep_masked_area: bool = False,
                    fix_empty_latent: bool = True,
                    progress_preview: ProgressPreview | None = None,
                    ) -> dict[str, Any]:
    """
    Emulates comfyui's 'SamplerCustom' node with some extra functionality.
    Args:
        latent_image: Dictionary containing data about the initial latent image to denoise.
                        (contains keys like "samples" and optional "noise_mask", "batch_index").
        model       : ComfyUI object representing the model to use for denoising.
        noise_seed  : The seed used to generate random noise.
        cfg         : Classifier-free guidance scale that controls the strength of negative prompts.
                        A value of 1.0 means the negative prompt has no effect on generation.
        positive    : Positive prompts or conditioning applied to the model during denoising.
        negative    : Negative prompts or conditioning applied to the model during denoising.
        sampler     : ComfyUI object representing the sampler used for each denoising step.
        sigmas      : Sigma values for each diffusion process step (can be list or torch.Tensor).
        noise_bias  : A constant bias applied to the initial noise.
                        If it is a tensor, it must have shape [batch_size, channels, 1, 1].
                        Can also be a scalar value or None.
        keep_masked_area: If True, the masked area of the latent image will be kept unchanged.
                            Comfyui tries to keep masked area unchanged when there's a mask active
                            but activating this flag we're sure that no change will happen at all.
        noise_amplitude : The amplitude of noise added to the latent image before denoising.
                            (0.0 = no noise ; 1.0 = standard deviation)
        progress_preview: Optional callback for tracking progress. Defaults to None.

    Returns:
        A dictionary with the updated latent image data after denoising,
        including "samples" and any other relevant information.

    Notes:
        - If `sigmas` is provided as a list, it will be converted to a torch.Tensor.
        - The function automatically handles cases where `noise_bias` or `noise_amplitude` are zero scalars.
        - The initial noise is scaled using `noise_amplitude`, and then the bias from `noise_bias` is applied.
    """

    # if sigmas is a list then convert it to tensor
    if isinstance(sigmas, list):
        sigmas = torch.tensor(sigmas, device='cpu')

    # if `noise_bias` is a torch.Tensor
    # then it should have shape [batch_size, channels, 1, 1]
    if isinstance(noise_bias, torch.Tensor):
        if noise_bias.ndim != 4 or noise_bias.shape[2:] != (1, 1):
            raise ValueError(f"Invalid `noise_bias` shape: expected [batch_size, channels, 1, 1], "
                                f"but got {list(noise_bias.shape)}")

    # if `noise_amplitude` is a torch.Tensor
    # then it should have shape [batch_size, channels, 1, 1]
    if isinstance(noise_amplitude, torch.Tensor):
        if noise_amplitude.ndim != 4 or noise_amplitude.shape[2:] != (1, 1):
            raise ValueError(f"Invalid `noise_amplitude` shape: expected [batch_size, channels, 1, 1], "
                                f"but got {list(noise_amplitude.shape)}")

    # if `noise_bias` or `noise_amplitude` is zero scalar then ignore it
    if isinstance(noise_bias, (float,int)) and noise_bias == 0:
        noise_bias = None
    if isinstance(noise_amplitude, (float,int)) and noise_amplitude == 0:
        noise_amplitude = None


    # extract all info that comes packaged in the `latent_image` dictionary
    latent      = latent_image.copy()
    samples     = comfy.sample.fix_empty_latent_channels(model, latent["samples"]) if fix_empty_latent else latent["samples"]
    noise_mask  = latent.get("noise_mask")
    batch_index = latent.get("batch_index")
    steps       = int( sigmas.shape[-1] )

    # store original values in case the user is doing inpainting with a mask
    original_samples : torch.Tensor | None = samples
    original_mask    : torch.Tensor | None = noise_mask

    # scale initial noise using `noise_amplitude`.
    # (0.0 results in no noise; 1.0 represents standard unit variance)
    if noise_amplitude is None:
        noise = torch.zeros(samples.shape, dtype=samples.dtype, layout=samples.layout, device="cpu")
    else:
        noise = comfy.sample.prepare_noise(samples, noise_seed, batch_index) * noise_amplitude

    # apply a constant bias using `noise_bias`
    if noise_bias is not None:
        noise = noise + noise_bias

    # this wrapper increments by 1 the steps count reported by comfyui.
    # comfyui reports the end of the first denoising step as 0 (0% completion)
    # breaking internal ProgressPreview calculation, the wrapper solves that
    progress_wrapper = ProgressPreview( steps, parent=(progress_preview, 1, steps+1) )

    # generates the denoised latent using a native function from comfyui.
    disable_pbar = not comfy.utils.PROGRESS_BAR_ENABLED
    samples = comfy.sample.sample_custom(model, noise, cfg, sampler, sigmas, positive, negative,
                                            samples, noise_mask=noise_mask, callback=progress_wrapper,
                                            disable_pbar=disable_pbar, seed=noise_seed)

    # when there's an inpainting mask, it seems like comfyui does not merge the
    # original image at the end of `sample_custom(..)`, so we manually merge it here
    if keep_masked_area and (original_mask is not None) and (original_samples is not None):
        original_mask = comfy.sampler_helpers.prepare_mask( original_mask, original_samples.shape, original_samples.device)
        if original_mask is not None:
            samples = samples * original_mask + ( 1.0 - original_mask ) * original_samples

    out = latent_image.copy()
    out["samples"] = samples
    return out



def calculate_denoise_bias(latent_image,
                           model    : Any,
                           seed     : int,
                           positive : list,
                           negative : list,
                           *,
                           sampler  : comfy.samplers.KSAMPLER,
                           sigmas   : list | torch.Tensor,
                           method   : str = 'accurate',  #< "accurate" or "experimental"
                           forced_size     : int | None = None,  #< optional, forced size of the sample
                           progress_preview: ProgressPreview
                           ) -> torch.Tensor:
    """
    Calculates the denoised bias for a given sigma value.

    The bias is determined by generating a denoised sample from pure noise
    using specified sigma values, then calculating the mean across each
    channel of this resulting sample.

    Args:
        latent_image: Dictionary containing information about the initial latent image,
                        only its width and height are used.
        model       : ComfyUI object representing the model to use for denoising.
        seed        : The seed used to generate random noise.
        positive    : Positive prompts or conditioning applied to the model during denoising.
        negative    : Negative prompts or conditioning applied to the model during denoising.
        sampler     : ComfyUI object representing the sampler used for each denoising step.
        sigmas      : Sigma values for each diffusion process step (can be list or torch.Tensor).
        method      : Calculation method, can be 'accurate' or 'experimental'.
        progress_preview: An object for reporting progress.

    Returns:
        A tensor containing the calculated noise bias. The shape of
        this tensor is [batch_size, channels, 1, 1], corresponding to each
        channel's average value in the latent space.
    """

    if method not in ['accurate', 'experimental']:
        raise ValueError(f'invalid bias calculation method: {method}')
    if isinstance(sigmas, list):
        sigmas = torch.tensor(sigmas, device='cpu')

    # calculate the number of diffusion steps (for the progress bar)
    steps = sigmas.shape[-1] - 1

    if isinstance(forced_size, (int, float)) and forced_size >= 8:
        samples : torch.Tensor = latent_image["samples"]
        samples_shape = samples.shape[:-2] + ( int(forced_size//8), int(forced_size//8) )
        latent_image  = latent_image.copy()
        latent_image["samples"] =  torch.zeros(samples_shape, dtype=samples.dtype, layout=samples.layout, device="cpu")


    # run the sampler on pure noise and calculate the mean of the result
    latent_image = execute_sampler(latent_image,
                                   model, seed, 1.0, positive, negative,
                                   sampler          = sampler,
                                   sigmas           = sigmas,
                                   noise_bias       = 0,
                                   noise_amplitude  = 1.0 if method=="accurate" else 0.1,
                                   progress_preview = ProgressPreview( steps,
                                           parent=(progress_preview, 0, 100)),
                                   )

    return torch.mean(latent_image["samples"], dim=[2, 3], keepdim=True)



def truncate_sigmas(sigmas: torch.Tensor | None, limit: float) -> torch.Tensor | None:
    """
    Truncates a descending tensor of sigmas at a specific limit.

    Args:
        sigmas: A tensor containing descending sigma values to be truncated.
        limit : The threshold value to cap the tensor.
    Returns:
        A new tensor with values > limit followed by the limit itself.
    """
    if sigmas is None:
        return None

    # create the mask to filter out values > limit
    mask = sigmas < limit
    if not mask.any():
        return None
    if mask.all():
        return sigmas

    # filter the tensor using the mask and add the limit
    truncated_sigmas = sigmas[mask]
    limit_sigma = torch.tensor([limit], dtype=sigmas.dtype, device=sigmas.device)
    return torch.cat((limit_sigma, truncated_sigmas))
