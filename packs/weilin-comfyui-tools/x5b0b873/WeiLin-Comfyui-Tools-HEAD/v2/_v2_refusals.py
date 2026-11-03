"""Behaviours of the original that Secure Nodes V2 cannot reproduce exactly; each is refused
by name instead of being changed silently (SECURE_CONVERSION.md, "Known differences")."""

PACK = "weilin-comfyui-tools"


class SecureConversionRefusal(RuntimeError):
    """A behaviour of the original that the Secure Nodes V2 conversion refuses by name."""


RANDOM_TEMPLATE = (
    f"{PACK}/{{node}}: auto_random with a random_template is not supported on Secure Nodes V2. The original "
    "draws tags from random-tag templates and a database kept by its web editor in the pack folder (app/server); "
    "that editor and its data are not part of the V2 pack. Clear random_template or turn auto_random off."
)
