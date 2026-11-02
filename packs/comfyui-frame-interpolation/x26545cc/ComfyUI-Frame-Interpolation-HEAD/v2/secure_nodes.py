"""Secure Nodes V2 registration of ComfyUI-Frame-Interpolation (pin 26545cc2).

All 16 node ids are registered with the original schemas (literals, from a census
of the pinned pack). Five run upstream's own node bodies in the guest:
- RIFE VFI;
- FILM VFI;
- IFRNet VFI (Vimeo90K checkpoints);
- Make Interpolation State List;
- VFI FloatToInt.
The upstream modules are imported lazily, inside execute. Their weights are
declared, verified safetensors (_fi_weights.py).

Every other node, and the checkpoint options whose files no longer exist
upstream, refuses by name. The reason is in each message.

INTERPOLATION_STATES was a live InterpolationStateList object. A value crossing
between guest executions must be plain data. So "Make Interpolation State List"
emits the same two fields as a token {"frame_indices": [...], "is_skip_list": bool},
and the consumers rebuild upstream's object from it before running upstream code.
"""

from comfy_api.latest import io

from . import _fi_weights

PACK = "comfyui-frame-interpolation"
VFI = "ComfyUI-Frame-Interpolation/VFI"
STATES = io.Custom("INTERPOLATION_STATES")
CONVERTED_PERMISSIONS = ("raw", "assets", "models.download")


class FrameInterpolationRefused(RuntimeError):
    """This node or checkpoint is not available in Secure Nodes V2."""


class InterpolationStatesError(ValueError):
    """An INTERPOLATION_STATES value that is not a state-list token."""


def refusal(node_id, reason):
    return f"{PACK}/{node_id} is not yet converted to Secure Nodes V2: {reason}"


def states_token(states):
    """Upstream InterpolationStateList -> the plain token that crosses the boundary."""
    return {"frame_indices": list(states.frame_indices), "is_skip_list": states.is_skip_list}


def states_from(token):
    """The token -> upstream's own InterpolationStateList (None stays None)."""
    if token is None:
        return None
    if (not isinstance(token, dict) or set(token) != {"frame_indices", "is_skip_list"}
            or not isinstance(token["frame_indices"], list)
            or not all(type(index) is int for index in token["frame_indices"])
            or type(token["is_skip_list"]) is not bool):
        raise InterpolationStatesError(
            f"{PACK}: optional_interpolation_states must come from 'Make Interpolation "
            "State List'")
    from .vfi_utils import InterpolationStateList
    return InterpolationStateList(frame_indices=list(token["frame_indices"]),
                                  is_skip_list=token["is_skip_list"])


def _frames_inputs(clear_default=10, clear_max=1000, multiplier=None):
    multiplier = multiplier or {"default": 2, "min": 2, "max": 1000}
    return [
        io.Image.Input("frames"),
        io.Int.Input("clear_cache_after_n_frames", default=clear_default, min=1, max=clear_max),
        io.Int.Input("multiplier", **multiplier),
    ]


def _states_input():
    return STATES.Input("optional_interpolation_states", optional=True)


def _image_output():
    return [io.Image.Output(display_name="IMAGE")]


# ----------------------------------------------------------------------------- converted

class RIFE_VFI(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = CONVERTED_PERMISSIONS
    SDK_REQUIRED_WEIGHTS = _fi_weights.declared_for("rife")

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="RIFE VFI",
            display_name="RIFE VFI (recommend rife4.25+)",
            category=VFI,
            inputs=[
                io.Combo.Input("ckpt_name", options=[
                    "sudo_rife4_269.662_testV1_scale1.pth", "rife47.pth", "rife49.pth",
                    "rife417.pth", "rife426.pth"], default="rife49.pth"),
                *_frames_inputs(multiplier={"default": 2, "min": 1}),
                io.Boolean.Input("fast_mode", default=True),
                io.Boolean.Input("ensemble", default=True),
                io.Combo.Input("scale_factor", options=[0.25, 0.5, 1.0, 2.0, 4.0], default=1.0),
                io.Combo.Input("dtype", options=["float32", "float16", "bfloat16"], default="float32"),
                io.Boolean.Input("torch_compile", default=False, tooltip=(
                    "Compile the model with torch.compile() for 10-30% faster inference "
                    "after the first (warm-up) run. Requires PyTorch 2.0+.")),
                io.Int.Input("batch_size", default=1, min=1, max=64, tooltip=(
                    "Number of interpolation tasks per GPU call. Higher values improve "
                    "throughput but use more VRAM. Set to 1 for the most conservative behaviour.")),
                _states_input(),
            ],
            outputs=_image_output(),
        )

    @classmethod
    async def execute(cls, ckpt_name, frames, clear_cache_after_n_frames, multiplier,
                      fast_mode, ensemble, scale_factor, dtype, torch_compile, batch_size,
                      optional_interpolation_states=None):
        from .vfi_models.rife import RIFE_VFI as Upstream, MODEL_TYPE
        state_dict = await _fi_weights.load(MODEL_TYPE, ckpt_name)
        with _fi_weights.supplied(MODEL_TYPE, ckpt_name, state_dict):
            result = Upstream().vfi(
                ckpt_name=ckpt_name, frames=frames,
                clear_cache_after_n_frames=clear_cache_after_n_frames, multiplier=multiplier,
                fast_mode=fast_mode, ensemble=ensemble, scale_factor=scale_factor, dtype=dtype,
                torch_compile=torch_compile, batch_size=batch_size,
                optional_interpolation_states=states_from(optional_interpolation_states))
        return io.NodeOutput(*result)


class FILM_VFI(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = CONVERTED_PERMISSIONS
    SDK_REQUIRED_WEIGHTS = _fi_weights.declared_for("film")

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="FILM VFI", display_name="FILM VFI", category=VFI,
            inputs=[io.Combo.Input("ckpt_name", options=["film_net_fp32.pt"]),
                    *_frames_inputs(), _states_input()],
            outputs=_image_output(),
        )

    @classmethod
    async def execute(cls, ckpt_name, frames, clear_cache_after_n_frames, multiplier,
                      optional_interpolation_states=None):
        from .vfi_models.film import FILM_VFI as Upstream, MODEL_TYPE
        state_dict = await _fi_weights.load(MODEL_TYPE, ckpt_name)
        with _fi_weights.supplied(MODEL_TYPE, ckpt_name, state_dict):
            result = Upstream().vfi(
                ckpt_name=ckpt_name, frames=frames,
                clear_cache_after_n_frames=clear_cache_after_n_frames, multiplier=multiplier,
                optional_interpolation_states=states_from(optional_interpolation_states))
        return io.NodeOutput(*result)


IFRNET_CKPTS = ["IFRNet_S_Vimeo90K.pth", "IFRNet_L_Vimeo90K.pth", "IFRNet_S_GoPro.pth",
                "IFRNet_L_GoPro.pth"]
IFRNET_GONE = {"IFRNet_S_GoPro.pth", "IFRNet_L_GoPro.pth"}


class IFRNet_VFI(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = CONVERTED_PERMISSIONS
    SDK_REQUIRED_WEIGHTS = _fi_weights.declared_for("ifrnet")

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="IFRNet VFI", display_name="IFRNet VFI", category=VFI,
            inputs=[io.Combo.Input("ckpt_name", options=list(IFRNET_CKPTS)),
                    *_frames_inputs(),
                    io.Combo.Input("scale_factor", options=[0.25, 0.5, 1.0, 2.0, 4.0], default=1.0),
                    _states_input()],
            outputs=_image_output(),
        )

    @classmethod
    def validate_inputs(cls, ckpt_name):
        # Taking ckpt_name stops core's own menu check, so repeat it here.
        if ckpt_name in IFRNET_GONE:
            return refusal("IFRNet VFI", (
                f"the {ckpt_name} checkpoint is no longer downloadable upstream (404 on every "
                "URL the pack tries). Use IFRNet_S_Vimeo90K.pth or IFRNet_L_Vimeo90K.pth."))
        if ckpt_name not in IFRNET_CKPTS:
            return f"Value not in list: ckpt_name: '{ckpt_name}' not in {IFRNET_CKPTS}"
        return True

    @classmethod
    async def execute(cls, ckpt_name, frames, clear_cache_after_n_frames, multiplier,
                      scale_factor, optional_interpolation_states=None):
        if ckpt_name in IFRNET_GONE:
            raise FrameInterpolationRefused(cls.validate_inputs(ckpt_name))
        from .vfi_models.ifrnet import IFRNet_VFI as Upstream, MODEL_TYPE
        state_dict = await _fi_weights.load(MODEL_TYPE, ckpt_name)
        with _fi_weights.supplied(MODEL_TYPE, ckpt_name, state_dict):
            result = Upstream().vfi(
                ckpt_name=ckpt_name, frames=frames,
                clear_cache_after_n_frames=clear_cache_after_n_frames, multiplier=multiplier,
                scale_factor=scale_factor,
                optional_interpolation_states=states_from(optional_interpolation_states))
        return io.NodeOutput(*result)


class MakeInterpolationStateList(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Make Interpolation State List", display_name="Make Interpolation State List",
            category=VFI,
            inputs=[io.String.Input("frame_indices", multiline=True, default="1,2,3"),
                    io.Boolean.Input("is_skip_list", default=True)],
            outputs=[STATES.Output(display_name="INTERPOLATION_STATES")],
        )

    @classmethod
    def execute(cls, frame_indices, is_skip_list):
        from .vfi_utils import MakeInterpolationStateList as Upstream
        (states,) = Upstream().create_options(frame_indices=frame_indices, is_skip_list=is_skip_list)
        return io.NodeOutput(states_token(states))


class FloatToInt(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="VFI FloatToInt", display_name="VFI FloatToInt",
            category="ComfyUI-Frame-Interpolation",
            inputs=[io.Float.Input("float", default=0, min=0, step=0.01)],
            outputs=[io.Int.Output(display_name="INT")],
        )

    @classmethod
    def execute(cls, float):  # noqa: A002 (upstream's input name)
        from .vfi_utils import FloatToInt as Upstream
        return io.NodeOutput(*Upstream().convert(float))


# ----------------------------------------------------------------------------- refused

NOT_CONVERTED_WEIGHTS = (
    "its checkpoints ({names}) are pickle files that have not yet been converted to "
    "declared, verified weights")


class _Refused(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()
    NODE_ID = ""

    @classmethod
    def reason(cls, ckpt_name):
        raise NotImplementedError

    @classmethod
    def validate_inputs(cls, ckpt_name):
        return refusal(cls.NODE_ID, cls.reason(ckpt_name))

    @classmethod
    async def execute(cls, ckpt_name, **_ignored):
        raise FrameInterpolationRefused(refusal(cls.NODE_ID, cls.reason(ckpt_name)))


def _vfi_refused(node_id, ckpt_options, reason_text, extra_inputs=(), clear_default=10,
                 clear_max=1000, multiplier=None, display_name=None):
    def define_schema(cls):
        return io.Schema(
            node_id=node_id, display_name=display_name or node_id, category=VFI,
            inputs=[io.Combo.Input("ckpt_name", options=list(ckpt_options)),
                    *_frames_inputs(clear_default, clear_max, multiplier),
                    *[make() for make in extra_inputs],
                    _states_input()],
            outputs=_image_output(),
        )

    def reason(cls, ckpt_name):
        return reason_text

    return type(node_id.replace(" ", "_") + "_Refused", (_Refused,), {
        "NODE_ID": node_id,
        "define_schema": classmethod(define_schema),
        "reason": classmethod(reason),
        "__module__": __name__,
    })


GMFSS_ID = "GMFSS Fortuna VFI"


class GMFSS_Fortuna_VFI(_Refused):
    NODE_ID = GMFSS_ID

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id=GMFSS_ID, display_name=GMFSS_ID, category=VFI,
            inputs=[io.Combo.Input("ckpt_name", options=["GMFSS_fortuna_union", "GMFSS_fortuna"]),
                    *_frames_inputs(), _states_input()],
            outputs=_image_output(),
        )

    @classmethod
    def reason(cls, ckpt_name):
        kernels = ("GMFSS runs CUDA softsplat kernels through cupy "
                   "(vfi_models/ops), which a Secure Nodes guest cannot run")
        if ckpt_name == "GMFSS_fortuna_union":
            return ("GMFSS_fortuna_union needs rife46.pth, which is no longer downloadable "
                    f"upstream (404 on every URL the pack tries), and {kernels}")
        return kernels


AMT_VFI = _vfi_refused(
    "AMT VFI", ["amt-s.pth", "amt-l.pth", "amt-g.pth", "gopro_amt-s.pth"],
    NOT_CONVERTED_WEIGHTS.format(names="amt-*.pth"), clear_default=1, clear_max=100)
ATM_VFI = _vfi_refused(
    "ATM VFI", ["atm-vfi-base.pt", "atm-vfi-lite.pt", "atm-vfi-base-pct.pt"],
    NOT_CONVERTED_WEIGHTS.format(names="atm-vfi-*.pt") + ", and it needs the timm package",
    extra_inputs=(lambda: io.Combo.Input("global_motion", options=[
        "On", "On with Ensemble (slowest)", "Off (fastest)"]),),
    multiplier={"default": 2, "min": 2, "max": 2},
    display_name="ATM VFI (only supports 2x multiplier)")
CAIN_VFI = _vfi_refused(
    "CAIN VFI", ["pretrained_cain.pth"], NOT_CONVERTED_WEIGHTS.format(names="pretrained_cain.pth"))
FLAVR_VFI = _vfi_refused(
    "FLAVR VFI", ["FLAVR_2x.pth", "FLAVR_4x.pth", "FLAVR_8x.pth"],
    NOT_CONVERTED_WEIGHTS.format(names="FLAVR_*.pth"),
    extra_inputs=(lambda: io.Boolean.Input("duplicate_first_last_frames", default=False),),
    multiplier={"default": 2, "min": 2, "max": 2})
IFUnet_VFI = _vfi_refused(
    "IFUnet VFI", ["IFUNet.pth"], NOT_CONVERTED_WEIGHTS.format(names="IFUNet.pth"),
    extra_inputs=(
        lambda: io.Float.Input("scale_factor", default=1.0, min=0.1, max=100, step=0.1),
        lambda: io.Boolean.Input("ensemble", default=True)))
M2M_VFI = _vfi_refused(
    "M2M VFI", ["M2M.pth"],
    NOT_CONVERTED_WEIGHTS.format(names="M2M.pth")
    + ", and it runs CUDA kernels through cupy, which a Secure Nodes guest cannot run")
MOMO_VFI = _vfi_refused(
    "MOMO VFI", ["momo-base.pth", "momo-lite.pth"],
    NOT_CONVERTED_WEIGHTS.format(names="momo-*.pth")
    + ", and it downloads torchvision RAFT weights at run time",
    extra_inputs=(lambda: io.Int.Input("num_inference_steps", default=8, min=2, max=20),),
    multiplier={"default": 2, "min": 2, "max": 2},
    display_name="MOMO VFI (only supports 2x multiplier)")
STMFNet_VFI = _vfi_refused(
    "STMFNet VFI", ["stmfnet.pth"],
    NOT_CONVERTED_WEIGHTS.format(names="stmfnet.pth")
    + ", and it runs CUDA kernels through cupy, which a Secure Nodes guest cannot run",
    extra_inputs=(lambda: io.Boolean.Input("duplicate_first_last_frames", default=False),),
    multiplier={"default": 2, "min": 2, "max": 2})
SepconvVFI = _vfi_refused(
    "Sepconv VFI", ["sepconv.pth"],
    NOT_CONVERTED_WEIGHTS.format(names="sepconv.pth")
    + ", and it runs CUDA kernels through cupy, which a Secure Nodes guest cannot run")

# Frozen copies of core's KSampler menus at ComfyUI 6257422b. The refusal
# validator takes both inputs, so a saved value missing from these lists still
# gets the refusal, not "value not in list".
SAMPLERS = [
    "euler", "euler_cfg_pp", "euler_ancestral", "euler_ancestral_cfg_pp", "heun", "heunpp2",
    "exp_heun_2_x0", "exp_heun_2_x0_sde", "dpm_2", "dpm_2_ancestral", "lms", "dpm_fast",
    "dpm_adaptive", "dpmpp_2s_ancestral", "dpmpp_2s_ancestral_cfg_pp", "dpmpp_sde",
    "dpmpp_sde_gpu", "dpmpp_2m", "dpmpp_2m_cfg_pp", "dpmpp_2m_sde", "dpmpp_2m_sde_gpu",
    "dpmpp_2m_sde_heun", "dpmpp_2m_sde_heun_gpu", "dpmpp_3m_sde", "dpmpp_3m_sde_gpu",
    "ddpm", "lcm", "ipndm", "ipndm_v", "deis", "cfgpp_ud10_ab", "res_multistep", "res_multistep_cfg_pp",
    "res_multistep_ancestral", "res_multistep_ancestral_cfg_pp", "gradient_estimation",
    "gradient_estimation_cfg_pp", "er_sde", "seeds_2", "seeds_3", "sa_solver",
    "sa_solver_pece", "ddim", "uni_pc", "uni_pc_bh2"]
SCHEDULERS = ["simple", "sgm_uniform", "karras", "exponential", "ddim_uniform", "beta",
              "normal", "linear_quadratic", "kl_optimal"]
KSAMPLER_ID = "KSampler Gradually Adding More Denoise (efficient)"
KSAMPLER_REASON = (
    "it runs ComfyUI's sampler step by step inside the node, once per latent and denoise "
    "level, and Secure Nodes V2 has no sampling operation a node can call that way yet")


class Gradually_More_Denoise_KSampler(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id=KSAMPLER_ID, display_name=KSAMPLER_ID,
            category="ComfyUI-Frame-Interpolation/others", is_output_node=True,
            inputs=[
                io.Model.Input("model"),
                io.Conditioning.Input("positive"),
                io.Conditioning.Input("negative"),
                io.Latent.Input("latent_image"),
                io.Int.Input("seed", default=0, min=0, max=0xffffffffffffffff),
                io.Int.Input("steps", default=20, min=1, max=10000),
                io.Float.Input("cfg", default=8.0, min=0.0, max=100.0),
                io.Combo.Input("sampler_name", options=list(SAMPLERS)),
                io.Combo.Input("scheduler", options=list(SCHEDULERS)),
                io.Float.Input("start_denoise", default=0.0, min=0.0, max=1.0, step=0.01),
                io.Float.Input("denoise_increment", default=0.1, min=0.0, max=1.0, step=0.1),
                io.Int.Input("denoise_increment_steps", default=20, min=1, max=10000),
                io.Vae.Input("optional_vae", optional=True),
            ],
            outputs=[io.Model.Output(display_name="MODEL"),
                     io.Conditioning.Output(display_name="CONDITIONING+"),
                     io.Conditioning.Output(display_name="CONDITIONING-"),
                     io.Latent.Output(display_name="LATENT"),
                     io.Vae.Output(display_name="VAE")],
        )

    @classmethod
    def validate_inputs(cls, sampler_name, scheduler):
        return refusal(KSAMPLER_ID, KSAMPLER_REASON)

    @classmethod
    async def execute(cls, **_ignored):
        raise FrameInterpolationRefused(refusal(KSAMPLER_ID, KSAMPLER_REASON))


# Original NODE_CLASS_MAPPINGS order (pristine __init__.py:24-42).
NODE_CLASS_MAPPINGS = {
    KSAMPLER_ID: Gradually_More_Denoise_KSampler,
    GMFSS_ID: GMFSS_Fortuna_VFI,
    "IFRNet VFI": IFRNet_VFI,
    "IFUnet VFI": IFUnet_VFI,
    "M2M VFI": M2M_VFI,
    "RIFE VFI": RIFE_VFI,
    "Sepconv VFI": SepconvVFI,
    "AMT VFI": AMT_VFI,
    "FILM VFI": FILM_VFI,
    "Make Interpolation State List": MakeInterpolationStateList,
    "STMFNet VFI": STMFNet_VFI,
    "FLAVR VFI": FLAVR_VFI,
    "CAIN VFI": CAIN_VFI,
    "ATM VFI": ATM_VFI,
    "MOMO VFI": MOMO_VFI,
    "VFI FloatToInt": FloatToInt,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RIFE VFI": "RIFE VFI (recommend rife4.25+)",
    "ATM VFI": "ATM VFI (only supports 2x multiplier)",
    "MOMO VFI": "MOMO VFI (only supports 2x multiplier)",
}

CONVERTED = ("RIFE VFI", "FILM VFI", "IFRNet VFI", "Make Interpolation State List",
             "VFI FloatToInt")
