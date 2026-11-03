"""The one exception type every out-of-envelope stand-in raises."""

PREFIX = "RES4LYF/ClownsharKSampler_Beta"


class OutOfEnvelope(RuntimeError):
    """A RES4LYF code path outside the V2 reduced envelope was reached; it is refused, never approximated."""


def refuse(what: str):
    raise OutOfEnvelope(
        f"{PREFIX}: {what} is outside the V2 reduced envelope (guest-side ComfyUI core is not available); "
        f"refused instead of approximated")
