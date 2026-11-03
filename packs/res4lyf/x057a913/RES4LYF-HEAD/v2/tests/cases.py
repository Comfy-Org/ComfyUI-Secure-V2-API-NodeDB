"""Shared tier-1 parity fixtures for RES4LYF ClownsharKSampler_Beta: seeded tiny models, inputs and the case table.

Both gate runs import this file. The ORIGINAL reference run imports RES4LYF in its own process. The V2 run uses a
clean core in a separate process and never imports RES4LYF. Inputs are synthetic and built from fixed seeds:
no checkpoints, no workflows, no media.
"""
import torch

MODEL_SEED = 1234
INPUT_SEED = 7


def tiny_model(mb, mp, sm, kind):
    """A tiny SD1.5-shaped UNet with seeded random weights; kind 'EPS' or 'CONST' (ModelType.FLOW)."""
    unet_config = {
        "use_checkpoint": False, "image_size": 32, "out_channels": 4, "use_spatial_transformer": True,
        "legacy": False, "adm_in_channels": None, "in_channels": 4, "model_channels": 32,
        "num_res_blocks": [1, 1], "transformer_depth": [1, 1], "channel_mult": [1, 2],
        "transformer_depth_middle": 1, "use_linear_in_transformer": False, "context_dim": 32,
        "transformer_depth_output": [1, 1, 1, 1], "use_temporal_attention": False, "use_temporal_resblock": False,
    }
    config = sm.SD15(unet_config)
    config.set_inference_dtype(torch.float32, None)
    model_type = mb.ModelType.EPS if kind == "EPS" else mb.ModelType.FLOW
    model = mb.BaseModel(config, model_type=model_type, device=torch.device("cpu"))
    gen = torch.Generator().manual_seed(MODEL_SEED)
    with torch.no_grad():
        for p in model.diffusion_model.parameters():
            p.copy_(torch.randn(p.shape, generator=gen) * 0.02)
    return mp.ModelPatcher(model, load_device=torch.device("cpu"), offload_device=torch.device("cpu"))


def inputs(mask=False, batch=1, zero_latent=False):
    gen = torch.Generator().manual_seed(INPUT_SEED)
    pos = [[torch.randn((1, 8, 32), generator=gen), {}]]
    neg = [[torch.randn((1, 8, 32), generator=gen), {}]]
    samples = torch.randn((batch, 4, 8, 8), generator=gen) * 0.5
    if zero_latent:
        samples = torch.zeros_like(samples)
    latent = {"samples": samples}
    if mask:
        m = torch.zeros((1, 8, 8))
        m[:, 2:6, 1:7] = 1.0
        m[:, 4, 3] = 0.5
        latent["noise_mask"] = m
    return pos, neg, latent


BASE = dict(eta=0.5, sampler_name="multistep/res_2m", scheduler="beta57", steps=6, steps_to_run=-1, denoise=1.0,
            cfg=5.5, seed=3, sampler_mode="standard", bongmath=True)


def case_table():
    rows = []

    def add(name, model="EPS", mask=False, batch=1, zero_latent=False, expect="exact", **widgets):
        w = dict(BASE)
        w.update(widgets)
        rows.append({"name": name, "model": model, "mask": mask, "batch": batch, "zero_latent": zero_latent,
                     "expect": expect, "widgets": w})

    for model in ("EPS", "CONST"):
        for method in ("multistep/res_2m", "multistep/res_3m", "linear/euler", "exponential/res_2s",
                       "multistep/dpmpp_2m", "multistep/deis_2m", "exponential/ddim", "exponential/res_3s"):
            for eta in (0.0, 0.5):
                for bong in (True, False):
                    add(f"{model}:{method}:eta{eta}:bong{bong}", model=model, sampler_name=method, eta=eta,
                        bongmath=bong)
        for sched in ("simple", "karras", "normal", "exponential", "sgm_uniform", "ddim_uniform", "beta",
                      "linear_quadratic", "bong_tangent"):
            add(f"{model}:sched:{sched}", model=model, scheduler=sched)
        add(f"{model}:denoise0.6", model=model, denoise=0.6)
        add(f"{model}:denoise_alt-0.9", model=model, denoise=-0.9)
        add(f"{model}:steps_to_run3", model=model, steps_to_run=3)
        add(f"{model}:steps_to_run0", model=model, steps_to_run=0)
        add(f"{model}:cfg1", model=model, cfg=1.0)
        add(f"{model}:seed_big", model=model, seed=2**40 + 17)
        add(f"{model}:mask", model=model, mask=True)
        add(f"{model}:mask:denoise0.7", model=model, mask=True, denoise=0.7)
        add(f"{model}:batch2", model=model, batch=2)
        add(f"{model}:zero_latent", model=model, zero_latent=True)
        add(f"{model}:steps1", model=model, steps=1, scheduler="karras")
        add(f"{model}:implicit:crouzeix_2s", model=model, sampler_name="diag_implicit/crouzeix_2s")
    # CONST plain flow: the final sigma_min step is computed exactly; EPS-family: refused by name (V2)
    add("CONST:final_step:kl_optimal", model="CONST", scheduler="kl_optimal")
    add("EPS:final_step:kl_optimal", model="EPS", scheduler="kl_optimal", expect="refused_v2")
    # Queue-time refusals (the original runs; V2 refuses by name before sampling)
    add("EPS:refuse:resample", sampler_mode="resample", expect="refused_v2")
    add("EPS:refuse:res_4s", sampler_name="exponential/res_4s_cox_matthews", expect="refused_v2")
    add("EPS:refuse:channelwise", cfg=-5.5, expect="refused_v2")
    return rows


def queue_cases():
    """Queue-time validation of the seven widgets that V2's validate_inputs names (core then skips its own checks
    for them). The original's verdict comes from core's validate_inputs on the original node; V2's from its
    validate_inputs in a real guest. Values cover core's list/min/max checks, including DualFormatList spellings,
    and the reduced envelope."""
    rows = []

    def add(name, **widgets):
        w = dict(BASE)
        w.update(widgets)
        rows.append({"name": name, "widgets": w})

    add("defaults")
    add("sampler:plain_name", sampler_name="res_2m")
    add("sampler:other_folder", sampler_name="other/res_2m")
    add("sampler:unknown", sampler_name="no_such_method")
    add("sampler:suffix_quirk", sampler_name="x/2m")
    add("sampler:not_admitted", sampler_name="exponential/res_4s_cox_matthews")
    add("sampler:implicit_menu_entry", sampler_name="diag_implicit/crouzeix_2s")
    add("sampler:implicit_plain_name", sampler_name="crouzeix_2s")
    add("sampler:explicit_as_implicit", sampler_name="fully_implicit/res_2m")
    add("scheduler:bong_tangent", scheduler="bong_tangent")
    add("scheduler:unknown", scheduler="no_such_scheduler")
    add("steps:0", steps=0)
    add("steps:1", steps=1, scheduler="karras")
    add("steps:max+1", steps=10001)
    add("cfg:100", cfg=100.0)
    add("cfg:100.5", cfg=100.5)
    add("cfg:-100.5", cfg=-100.5)
    add("cfg:-1", cfg=-1.0)
    add("seed:-1", seed=-1)
    add("seed:-2", seed=-2)
    add("seed:max", seed=0xffffffffffffffff)
    add("denoise:0", denoise=0.0)
    add("denoise:-0.5", denoise=-0.5)
    add("denoise:-10001", denoise=-10001.0)
    add("denoise:10001", denoise=10001.0)
    add("sampler_mode:unsample", sampler_mode="unsample")
    add("sampler_mode:bogus", sampler_mode="bogus")
    add("kl_optimal:steps1", scheduler="kl_optimal", steps=1)
    return rows


QUEUE_WIDGETS = ("sampler_name", "scheduler", "steps", "cfg", "seed", "sampler_mode", "denoise")

# Core's calculate_sigmas with the two scheduler names RES4LYF registers globally (any sampler node can use them):
# the original's registration vs V2's scheduler providers.
CANCEL = {"case": "CONST:multistep/res_2m:eta0.5:bongTrue", "interrupt_at": 3}  # model evaluation number

# Every SharkOptions_Beta noise_type_init choice (NOISE_GENERATOR_NAMES_SIMPLE), plus "fractal" (not a choice there;
# the original fails on it too)
INIT_NOISE_TYPES = ["gaussian", "gaussian_backwards", "uniform", "laplacian", "studentt", "perlin", "fractal",
                    "pyramid-bilinear", "pyramid-bicubic", "pyramid-nearest", "pyramid-interpolated",
                    "pyramid-cascade_B", "hires-pyramid-bilinear", "hires-pyramid-bicubic", "hires-pyramid-nearest",
                    "brown", "pink", "white", "blue", "violet", "ultraviolet_A", "ultraviolet_B", "ultraviolet_C",
                    "none", "wavelet", "brownian"]


def option_cases():
    """Sampler cases fed by OPTIONS chains built from the options nodes (each step: node id, its widget inputs).
    EPS cases use karras (no final sigma_min step), so they compare instead of refusing."""
    rows = []

    def add(name, chain, model="CONST", expect="exact", **widgets):
        w = dict(BASE)
        w.update(widgets)
        rows.append({"name": name, "model": model, "expect": expect, "widgets": w, "chain": chain})

    def shark(**kw):
        base = {"noise_type_init": "gaussian", "s_noise_init": 1.0, "denoise_alt": 1.0, "channelwise_cfg": False}
        base.update(kw)
        return ("SharkOptions_Beta", base)

    def detail(**kw):
        base = {"weight": 1.0, "method": "model", "mode": "hard", "eta": 0.5, "start_step": 1, "end_step": 4}
        base.update(kw)
        return ("ClownOptions_DetailBoost_Beta", base)

    for noise_type in INIT_NOISE_TYPES:
        add(f"opt:CONST:shark:noise_type_init={noise_type}", [shark(noise_type_init=noise_type)])
    add("opt:CONST:shark:s_noise_init0.8", [shark(s_noise_init=0.8)])
    add("opt:CONST:shark:denoise_alt0.9", [shark(denoise_alt=0.9)])
    add("opt:EPS:shark:s_noise_init1.2", [shark(s_noise_init=1.2)], model="EPS", scheduler="karras")
    add("opt:CONST:shark:channelwise", [shark(channelwise_cfg=True)], expect="refused_v2")
    for method in ("sampler", "sampler_normal", "sampler_substep", "sampler_substep_normal", "model",
                   "model_alpha"):  # DETAIL_BOOST_METHODS (beta/samplers_extensions.py:216-223)
        add(f"opt:CONST:detail:{method}", [detail(method=method)])
    for mode in ("soft", "sinusoidal", "exp", "lorentzian"):
        add(f"opt:CONST:detail:model:{mode}", [detail(mode=mode)])
    add("opt:CONST:detail:weight-1:start0:end-1", [detail(weight=-1.0, start_step=0, end_step=-1)])
    add("opt:EPS:detail:model", [detail()], model="EPS", scheduler="karras")
    add("opt:CONST:detail->shark", [detail(), shark(s_noise_init=0.9, denoise_alt=0.95)])
    add("opt:CONST:shark->detail", [shark(s_noise_init=0.9), detail(method="sampler")])

    def sigma(**kw):  # ClownOptions_SigmaScaling_Beta: its widget defaults, then the case's values
        base = {"s_noise": 1.0, "s_noise_substep": 1.0, "noise_anchor_sde": 1.0, "lying": 1.0, "lying_inv": 1.0,
                "lying_start_step": 0, "lying_inv_start_step": 1}
        base.update(kw)
        return ("ClownOptions_SigmaScaling_Beta", base)

    s32 = torch.linspace(1.2, 0.8, 6, dtype=torch.float32)  # SIGMAS inputs (per-step s_noise factors)
    s64 = torch.linspace(0.9, 1.1, 7, dtype=torch.float64)
    add("opt:CONST:sigma:defaults", [sigma()])
    add("opt:EPS:sigma:defaults", [sigma()], model="EPS", scheduler="karras")
    add("opt:CONST:sigma:s_noise1.05", [sigma(s_noise=1.05)])
    add("opt:CONST:sigma:s_noise1.1:eta0", [sigma(s_noise=1.1)], eta=0.0)
    add("opt:CONST:sigma:s_noise_substep0.9:res_2s", [sigma(s_noise_substep=0.9)], sampler_name="exponential/res_2s")
    add("opt:CONST:sigma:noise_anchor0.5", [sigma(noise_anchor_sde=0.5)])
    add("opt:CONST:sigma:noise_anchor0.5:res_3s", [sigma(noise_anchor_sde=0.5)], sampler_name="exponential/res_3s")
    add("opt:CONST:sigma:lying0.95@0", [sigma(lying=0.95)])
    add("opt:CONST:sigma:lying0.97@2", [sigma(lying=0.97, lying_start_step=2)])
    add("opt:CONST:sigma:lying1.05@0", [sigma(lying=1.05)])
    add("opt:CONST:sigma:lying1.05@2", [sigma(lying=1.05, lying_start_step=2)])  # then divided by sigma_max
    add("opt:CONST:sigma:lying_inv1.03@3", [sigma(lying_inv=1.03, lying_inv_start_step=3)])
    add("opt:CONST:sigma:lying0.95@1+inv1.02@4", [sigma(lying=0.95, lying_start_step=1, lying_inv=1.02,
                                                        lying_inv_start_step=4)])
    add("opt:CONST:sigma:lying0.9@6", [sigma(lying=0.9, lying_start_step=6)])  # after the last step
    add("opt:CONST:sigma:s_noises_f32", [sigma(s_noises=s32.clone())])
    add("opt:CONST:sigma:s_noises+substep_f64:res_2s", [sigma(s_noise=1.02, s_noises=s64.clone(),
                                                              s_noises_substep=s64.flip(0).clone())],
        sampler_name="exponential/res_2s")
    add("opt:EPS:sigma:karras:lying0.95@1", [sigma(lying=0.95, lying_start_step=1)], model="EPS",
        scheduler="karras")
    add("opt:EPS:sigma:karras:s_noises_f32", [sigma(s_noises=s32.clone())], model="EPS", scheduler="karras")
    # EPS-family final sigma_min step: rescaled away during the loop it no longer fires (exact); rescaled at the
    # start, prepare_sigmas clamps the last sigma back up to sigma_min and it fires (refused by name in V2)
    add("opt:EPS:sigma:kl_optimal:lying0.95@2", [sigma(lying=0.95, lying_start_step=2)], model="EPS",
        scheduler="kl_optimal")
    add("opt:EPS:sigma:kl_optimal:lying0.95@0", [sigma(lying=0.95)], model="EPS", scheduler="kl_optimal",
        expect="refused_v2")
    add("opt:CONST:sigma:kl_optimal:lying0.95@2", [sigma(lying=0.95, lying_start_step=2)], scheduler="kl_optimal")
    add("opt:CONST:sigma:kl_optimal:lying0.95@0", [sigma(lying=0.95)], scheduler="kl_optimal")
    add("opt:CONST:sigma:steps_to_run3:lying0.95@2", [sigma(lying=0.95, lying_start_step=2)], steps_to_run=3)
    # Factors the host cannot evaluate at (negative or non-finite sigmas): refused by name in V2
    add("opt:CONST:sigma:lying0", [sigma(lying=0.0)], expect="refused_v2")
    add("opt:CONST:sigma:lying-0.5", [sigma(lying=-0.5)], expect="refused_v2")
    add("opt:CONST:sigma:lying_inv0@2", [sigma(lying_inv=0.0, lying_inv_start_step=2)], expect="refused_v2")
    add("opt:CONST:detail->sigma", [detail(), sigma(s_noise=1.04, lying=0.98, lying_start_step=1)])
    add("opt:CONST:sigma->shark", [sigma(s_noise=1.04), shark(s_noise_init=0.9)])
    return rows

PROVIDER_CASES = [(kind, name, steps) for kind in ("EPS", "CONST") for name in ("beta57", "bong_tangent")
                  for steps in (1, 2, 6, 30, 97)]


CHAIN = [
    # upstream node widgets, downstream node widgets (standard, all three inputs connected)
    {"name": "chain:EPS:res_2m->res_2m", "model": "EPS",
     "up": dict(BASE, steps=6), "down": dict(BASE, steps=6, denoise=0.5, seed=11)},
    {"name": "chain:CONST:res_3m->euler", "model": "CONST",
     "up": dict(BASE, sampler_name="multistep/res_3m", steps=5),
     "down": dict(BASE, sampler_name="linear/euler", steps=4, denoise=0.4, seed=12, eta=0.0)},
    {"name": "chain:EPS:steps_to_run->standard", "model": "EPS",
     "up": dict(BASE, steps=6, steps_to_run=3), "down": dict(BASE, steps=6, denoise=0.6, seed=13)},
    # the downstream loop runs no step: the original's output state is the upstream state (its denoised estimate)
    {"name": "chain:CONST:res_2m->steps_to_run0", "model": "CONST",
     "up": dict(BASE, steps=5), "down": dict(BASE, steps=5, denoise=0.5, seed=14, steps_to_run=0)},
]
