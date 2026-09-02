# (c) City96 || Apache-2.0 (apache.org/licenses/LICENSE-2.0)
from comfy_api.latest import io, sdk

# Catalogue keys this pack contributes to the host model catalogue.  The legacy
# module mutated ``folder_paths.folder_names_and_paths`` at import time; a
# mirror may not touch the host from the guest, so the mapping is DECLARED here
# and the trusted plane performs the registration.
GGUF_FOLDER_KEYS = {
    "unet_gguf": ("diffusion_models", "unet"),
    "clip_gguf": ("text_encoders", "clip"),
}

# Mirrors the policies ``dequantize_tensor`` accepts.  ``target`` defers to the
# compute dtype; the rest name a fixed torch dtype.  The host maps these onto a
# per-load derived ``GGMLOps.Linear`` subclass, so one load never mutates the
# dependency's process-global class.
DTYPES = ["default", "target", "float32", "float16", "bfloat16"]

# Literal copies of core's ``CLIPLoader``/``DualCLIPLoader`` type lists.  The
# legacy node read these out of ``nodes.CLIPLoader.INPUT_TYPES()``, which must
# not happen in ``define_schema``: that runs in the HOST process on the
# /object_info and prompt-validation paths.  Drift against core is asserted by
# backend/tests/test_gguf_pack_conversion.py rather than found silently.
CLIP_TYPES = [
    "stable_diffusion", "stable_cascade", "sd3", "stable_audio", "mochi",
    "ltxv", "pixart", "cosmos", "lumina2", "wan", "hidream", "chroma", "ace",
    "omnigen2", "qwen_image", "hunyuan_image", "flux2", "ovis",
    "longcat_image", "cogvideox", "lens", "pixeldit", "ideogram4", "boogu",
    "krea2", "joyimage", "mage", "minimax",
]
DUAL_CLIP_TYPES = [
    "sdxl", "sd3", "flux", "hunyuan_video", "hidream", "hunyuan_image",
    "hunyuan_video_15", "kandinsky5", "kandinsky5_image", "ltxv", "newbie",
    "ace",
]

def _validate_name(name, field):
    """Reject anything that is not a confined logical catalogue name.

    This never turns a name into a path.  ``ctx.models`` stays the
    authoritative existence and containment check; this only stops core from
    rejecting a legitimate remote-combo selection against an empty static
    options list, and fails obviously malformed values early.
    """
    if not isinstance(name, str) or not name:
        return f"{field} must be a non-empty catalogue name"
    logical = name.replace("\\", "/")
    if (
        "\x00" in logical
        or logical.startswith("/")
        or (len(logical) > 1 and logical[1] == ":")
        or any(part == ".." for part in logical.split("/"))
    ):
        return f"{field} must be a confined catalogue name"
    return True


def _validate_names(names):
    for index, name in enumerate(names, start=1):
        checked = _validate_name(name, f"clip_name{index}")
        if checked is not True:
            return checked
    return True


def _unet_input():
    return io.Combo.Input(
        "unet_name",
        options=[],
        remote=io.RemoteOptions(
            route="/models/gguf/choices", refresh_button=True),
    )


def _clip_input(name):
    return io.Combo.Input(
        name,
        options=[],
        remote=io.RemoteOptions(
            route="/models/gguf/clip_choices", refresh_button=True),
    )


async def _load_text_encoders(names, clip_type):
    """Ask the trusted plane for a CLIP built from catalogued weights.

    The guest sends logical names and a closed type string only: no path, no
    state dict, no operations class and no patcher crosses the boundary.
    """
    checked = _validate_names(names)
    if checked is not True:
        raise ValueError(checked)
    return await sdk.ctx().models.load_gguf_text_encoders(
        list(names), clip_type=clip_type)


class UnetLoaderGGUF(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("models",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="UnetLoaderGGUF",
            display_name="Unet Loader (GGUF)",
            category="bootleg",
            description=(
                "Load a catalogued GGUF diffusion model. The quantized "
                "weights, the dequantization ops class and the patcher all "
                "stay inside the trusted process."
            ),
            inputs=[_unet_input()],
            outputs=[io.Model.Output()],
        )

    @classmethod
    def validate_inputs(cls, unet_name):
        return _validate_name(unet_name, "unet_name")

    @classmethod
    async def execute(cls, unet_name) -> io.NodeOutput:
        return io.NodeOutput(
            await sdk.ctx().models.load_gguf_model(unet_name))


class UnetLoaderGGUFAdvanced(UnetLoaderGGUF):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="UnetLoaderGGUFAdvanced",
            display_name="Unet Loader (GGUF/Advanced)",
            category="bootleg",
            description=(
                "Load a catalogued GGUF diffusion model with explicit "
                "dequantization and patch dtype policy. Each load receives "
                "its own derived Linear class, so one load never changes the "
                "dtype policy of another."
            ),
            inputs=[
                _unet_input(),
                io.Combo.Input(
                    "dequant_dtype", options=DTYPES, default="default"),
                io.Combo.Input(
                    "patch_dtype", options=DTYPES, default="default"),
                io.Boolean.Input("patch_on_device", default=False),
            ],
            outputs=[io.Model.Output()],
        )

    @classmethod
    async def execute(
        cls, unet_name, dequant_dtype, patch_dtype, patch_on_device,
    ) -> io.NodeOutput:
        return io.NodeOutput(await sdk.ctx().models.load_gguf_model(
            unet_name,
            dequant_dtype=dequant_dtype,
            patch_dtype=patch_dtype,
            patch_on_device=patch_on_device,
        ))


class CLIPLoaderGGUF(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("models",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="CLIPLoaderGGUF",
            display_name="CLIPLoader (GGUF)",
            category="bootleg",
            description=(
                "Load one catalogued GGUF or SafeTensors text encoder as a "
                "CLIP."
            ),
            inputs=[
                _clip_input("clip_name"),
                io.Combo.Input(
                    "type", options=CLIP_TYPES, default="stable_diffusion"),
            ],
            outputs=[io.Clip.Output()],
        )

    @classmethod
    def validate_inputs(cls, clip_name):
        return _validate_name(clip_name, "clip_name1")

    @classmethod
    async def execute(cls, clip_name, type) -> io.NodeOutput:
        return io.NodeOutput(await _load_text_encoders([clip_name], type))


class DualCLIPLoaderGGUF(CLIPLoaderGGUF):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DualCLIPLoaderGGUF",
            display_name="DualCLIPLoader (GGUF)",
            category="bootleg",
            description=(
                "Load two catalogued GGUF or SafeTensors text encoders as one "
                "CLIP."
            ),
            inputs=[
                _clip_input("clip_name1"),
                _clip_input("clip_name2"),
                io.Combo.Input(
                    "type", options=DUAL_CLIP_TYPES, default="sdxl"),
            ],
            outputs=[io.Clip.Output()],
        )

    @classmethod
    def validate_inputs(cls, clip_name1, clip_name2):
        return _validate_names((clip_name1, clip_name2))

    @classmethod
    async def execute(cls, clip_name1, clip_name2, type) -> io.NodeOutput:
        return io.NodeOutput(
            await _load_text_encoders([clip_name1, clip_name2], type))


class TripleCLIPLoaderGGUF(CLIPLoaderGGUF):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="TripleCLIPLoaderGGUF",
            display_name="TripleCLIPLoader (GGUF)",
            category="bootleg",
            description=(
                "Load three catalogued GGUF or SafeTensors text encoders as "
                "one SD3 CLIP."
            ),
            inputs=[
                _clip_input("clip_name1"),
                _clip_input("clip_name2"),
                _clip_input("clip_name3"),
            ],
            outputs=[io.Clip.Output()],
        )

    @classmethod
    def validate_inputs(cls, clip_name1, clip_name2, clip_name3):
        return _validate_names((clip_name1, clip_name2, clip_name3))

    @classmethod
    async def execute(
        cls, clip_name1, clip_name2, clip_name3,
    ) -> io.NodeOutput:
        # The legacy node has no ``type`` widget and defaults to sd3.
        return io.NodeOutput(await _load_text_encoders(
            [clip_name1, clip_name2, clip_name3], "sd3"))


class QuadrupleCLIPLoaderGGUF(CLIPLoaderGGUF):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="QuadrupleCLIPLoaderGGUF",
            display_name="QuadrupleCLIPLoader (GGUF)",
            category="bootleg",
            description=(
                "Load four catalogued GGUF or SafeTensors text encoders as "
                "one CLIP."
            ),
            inputs=[
                _clip_input("clip_name1"),
                _clip_input("clip_name2"),
                _clip_input("clip_name3"),
                _clip_input("clip_name4"),
            ],
            outputs=[io.Clip.Output()],
        )

    @classmethod
    def validate_inputs(cls, clip_name1, clip_name2, clip_name3, clip_name4):
        return _validate_names(
            (clip_name1, clip_name2, clip_name3, clip_name4))

    @classmethod
    async def execute(
        cls, clip_name1, clip_name2, clip_name3, clip_name4,
    ) -> io.NodeOutput:
        # The legacy node has no ``type`` widget and defaults to
        # stable_diffusion.
        return io.NodeOutput(await _load_text_encoders(
            [clip_name1, clip_name2, clip_name3, clip_name4],
            "stable_diffusion",
        ))


NODE_CLASS_MAPPINGS = {
    "UnetLoaderGGUF": UnetLoaderGGUF,
    "CLIPLoaderGGUF": CLIPLoaderGGUF,
    "DualCLIPLoaderGGUF": DualCLIPLoaderGGUF,
    "TripleCLIPLoaderGGUF": TripleCLIPLoaderGGUF,
    "QuadrupleCLIPLoaderGGUF": QuadrupleCLIPLoaderGGUF,
    "UnetLoaderGGUFAdvanced": UnetLoaderGGUFAdvanced,
}
