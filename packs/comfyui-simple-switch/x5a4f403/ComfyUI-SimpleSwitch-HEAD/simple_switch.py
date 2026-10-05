"""Standalone renamed switch node for ComfyUI.

Derived from `EGRYQHNode` in `nodes/egryqh.py` from:
https://github.com/11dogzi/Comfyui-ergouzi-Nodes
Original author: 11dogzi
"""


class AnyType(str):
    """Wildcard type that compares equal to every ComfyUI type."""

    def __ne__(self, _value: object) -> bool:
        return False

any_type = AnyType("*")
ANY_TYPE = any_type
LATENT_TYPE = "LATENT"


def is_context_empty(ctx):
    return not ctx or all(v is None for v in ctx.values())


def is_none(value):
    if value is not None:
        if isinstance(value, dict) and "model" in value and "clip" in value:
            return is_context_empty(value)
    return value is None


def _is_context_empty(ctx):
    return is_context_empty(ctx)


def _is_none(value):
    return is_none(value)


def _get_latent_samples(value):
    if not isinstance(value, dict):
        return None
    return value.get("samples")


def _is_nested_tensor(value):
    return bool(getattr(value, "is_nested", False))


def _get_samples_ndim(samples):
    return getattr(samples, "ndim", None)


def _is_latent(value):
    return _get_latent_samples(value) is not None


def _is_audio_latent(value):
    if not isinstance(value, dict):
        return False

    samples = _get_latent_samples(value)
    if samples is None:
        return False

    # LTX AV latents are valid for audio decode because the decoder unwraps the
    # nested container and selects the audio branch internally.
    if _is_nested_tensor(samples):
        return True

    ndim = _get_samples_ndim(samples)
    if ndim != 4:
        return False

    if value.get("type") == "audio":
        return True

    return "sample_rate" in value


def _is_video_latent(value):
    if not isinstance(value, dict):
        return False

    samples = _get_latent_samples(value)
    if samples is None or _is_nested_tensor(samples):
        return False

    return _get_samples_ndim(samples) == 5


def _describe_audio_latent(value, index):
    if not isinstance(value, dict):
        return f"input{index:02d}=non-latent:{type(value).__name__}"

    samples = _get_latent_samples(value)
    if samples is None:
        return f"input{index:02d}=latent-without-samples"

    shape = getattr(samples, "shape", None)
    ndim = getattr(samples, "ndim", None)
    latent_type = value.get("type", "unknown")
    nested = _is_nested_tensor(samples)
    return (
        f"input{index:02d}=type:{latent_type},nested:{nested},"
        f"ndim:{ndim},shape:{tuple(shape) if shape is not None else 'unknown'}"
    )


class SimpleSwitch:
    """Return the first non-empty value from input01..input06."""

    CATEGORY = "Simple Switch"
    FUNCTION = "switch"
    RETURN_TYPES = (any_type,)
    RETURN_NAMES = ("output",)

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {},
            "optional": {
                "input01": (any_type,),
                "input02": (any_type,),
                "input03": (any_type,),
                "input04": (any_type,),
                "input05": (any_type,),
                "input06": (any_type,),
            },
        }

    def switch(
        self,
        input01=None,
        input02=None,
        input03=None,
        input04=None,
        input05=None,
        input06=None,
    ):
        any_value = None
        if not is_none(input01):
            any_value = input01
        elif not is_none(input02):
            any_value = input02
        elif not is_none(input03):
            any_value = input03
        elif not is_none(input04):
            any_value = input04
        elif not is_none(input05):
            any_value = input05
        elif not is_none(input06):
            any_value = input06
        return (any_value,)


class SimpleLatentSwitch:
    """Return the first non-empty latent from input01..input06."""

    CATEGORY = "Simple Switch"
    FUNCTION = "switch"
    RETURN_TYPES = (LATENT_TYPE,)
    RETURN_NAMES = ("output",)

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {},
            "optional": {
                "input01": (LATENT_TYPE,),
                "input02": (LATENT_TYPE,),
                "input03": (LATENT_TYPE,),
                "input04": (LATENT_TYPE,),
                "input05": (LATENT_TYPE,),
                "input06": (LATENT_TYPE,),
            },
        }

    def switch(
        self,
        input01=None,
        input02=None,
        input03=None,
        input04=None,
        input05=None,
        input06=None,
    ):
        for candidate in (input01, input02, input03, input04, input05, input06):
            if not _is_none(candidate) and _is_latent(candidate):
                return (candidate,)

        return (None,)


class SimpleAudioLatentSwitch:
    """Return the first non-empty audio-compatible latent from input01..input06."""

    CATEGORY = "Simple Switch"
    FUNCTION = "switch"
    RETURN_TYPES = (LATENT_TYPE,)
    RETURN_NAMES = ("output",)

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {},
            "optional": {
                "input01": (LATENT_TYPE,),
                "input02": (LATENT_TYPE,),
                "input03": (LATENT_TYPE,),
                "input04": (LATENT_TYPE,),
                "input05": (LATENT_TYPE,),
                "input06": (LATENT_TYPE,),
            },
        }

    def switch(
        self,
        input01=None,
        input02=None,
        input03=None,
        input04=None,
        input05=None,
        input06=None,
    ):
        rejected = []
        for index, candidate in enumerate(
            (input01, input02, input03, input04, input05, input06),
            start=1,
        ):
            if _is_none(candidate):
                continue

            if _is_audio_latent(candidate):
                return (candidate,)

            rejected.append(_describe_audio_latent(candidate, index))

        if rejected:
            raise ValueError(
                "No compatible audio latent found. "
                "Expected an LTX audio latent (`type='audio'`) or a nested AV latent. "
                f"Rejected candidates: {', '.join(rejected)}"
            )

        return (None,)


class SimpleVideoLatentSwitch:
    """Return the first non-empty video-compatible latent from input01..input06."""

    CATEGORY = "Simple Switch"
    FUNCTION = "switch"
    RETURN_TYPES = (LATENT_TYPE,)
    RETURN_NAMES = ("output",)

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {},
            "optional": {
                "input01": (LATENT_TYPE,),
                "input02": (LATENT_TYPE,),
                "input03": (LATENT_TYPE,),
                "input04": (LATENT_TYPE,),
                "input05": (LATENT_TYPE,),
                "input06": (LATENT_TYPE,),
            },
        }

    def switch(
        self,
        input01=None,
        input02=None,
        input03=None,
        input04=None,
        input05=None,
        input06=None,
    ):
        rejected = []
        for index, candidate in enumerate(
            (input01, input02, input03, input04, input05, input06),
            start=1,
        ):
            if _is_none(candidate):
                continue

            if _is_video_latent(candidate):
                return (candidate,)

            rejected.append(_describe_audio_latent(candidate, index))

        if rejected:
            raise ValueError(
                "No compatible video latent found. "
                "Expected a non-nested 5D video latent. "
                f"Rejected candidates: {', '.join(rejected)}"
            )

        return (None,)
