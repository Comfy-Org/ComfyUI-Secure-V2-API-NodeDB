"""Portrait Landscape Pixaroma — output a width/height in the chosen
orientation, optionally snapped to a multiple.

Enter (or wire) two dimensions and click Portrait or Landscape: Portrait returns
the TALL arrangement (smaller value as width), Landscape the WIDE arrangement
(larger value as width). One node replaces the WH + WH + Switch WH 'flip
orientation' setup.

The orientation AND the size multiple live on
node.properties.portraitLandscapeState and are injected into the hidden
PortraitLandscapeState input by the JS graphToPrompt hook (Resolution Pixaroma
pattern, CLAUDE.md Vue Compat #9), so no extra input slot is exposed for either.

The state used to be the bare string "portrait" / "landscape". It is JSON now,
and parse_state still accepts the old form, because a workflow saved before the
multiple existed keeps sending it until the file is re-saved.
"""

import json

# What the node face offers. "Off" is 0. Kept here so Python and the face agree
# on what is legal; anything else that arrives is treated as Off rather than
# refused, since a hand-edited API call can send anything.
ALLOWED_MULTIPLES = (0, 8, 16, 32, 64)

MAX_DIM = 16384


def snap_to_multiple(value, multiple):
    """Round `value` to the NEAREST `multiple`, ties going up.

    Integer arithmetic on purpose: `round(value / multiple) * multiple` would
    bring float representation into a whole-pixel decision, and Python's round()
    is banker's rounding, so 1.5 and 2.5 would round in opposite directions.
    This is deterministic and needs no float at all.

    Never returns 0: snapping a small number down to nothing would hand a
    zero-pixel image to whatever is downstream.
    """
    try:
        value = int(value)
        multiple = int(multiple)
    except (TypeError, ValueError):
        return value
    if multiple <= 1:
        return value
    snapped = (value + multiple // 2) // multiple * multiple
    return max(multiple, snapped)


def parse_state(raw):
    """The hidden PortraitLandscapeState -> (orientation, multiple).

    Accepts the current JSON object, and the bare "portrait" / "landscape"
    string that older saved workflows still send.
    """
    orient = "portrait"
    multiple = 0

    data = None
    if isinstance(raw, dict):
        data = raw
    elif isinstance(raw, str):
        text = raw.strip()
        if text.startswith("{"):
            try:
                loaded = json.loads(text)
            except (ValueError, TypeError, RecursionError):
                loaded = None
            if isinstance(loaded, dict):
                data = loaded
        elif text in ("portrait", "landscape"):
            orient = text

    if data is not None:
        if data.get("orient") in ("portrait", "landscape"):
            orient = data["orient"]
        try:
            candidate = int(data.get("multiple", 0))
        except (TypeError, ValueError):
            candidate = 0
        multiple = candidate if candidate in ALLOWED_MULTIPLES else 0

    return orient, multiple


class PixaromaPortraitLandscape:
    DESCRIPTION = (
        "Output a width and height in the orientation you pick. Enter your two "
        "dimensions (or wire them in from another node), then click Portrait or "
        "Landscape. Portrait gives the tall arrangement (the smaller number "
        "becomes the width), Landscape gives the wide arrangement (the larger "
        "number becomes the width). Flipping orientation is one click, with no "
        "need to keep two WH nodes and a switch. The order you enter the two "
        "numbers does not matter.\n\n"
        "Models are usually fussy about sizes, wanting them in steps of 8, 16, "
        "32 or 64. The small button at the top of the node sets that: click it "
        "to step through Off, 8, 16, 32 and 64, and both numbers are rounded to "
        "the nearest step before they go out. Each node keeps its own setting, "
        "so one workflow can hold several set up differently. Outputs width and "
        "height."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "width": ("INT", {"default": 832, "min": 8, "max": MAX_DIM, "step": 8, "tooltip": "One of your two dimensions. Type a value or wire a number in. Portrait/Landscape decides whether this becomes the long or short side, so the order you enter the two numbers does not matter."}),
                "height": ("INT", {"default": 1216, "min": 8, "max": MAX_DIM, "step": 8, "tooltip": "The other dimension. Type a value or wire a number in."}),
            },
            "hidden": {
                "PortraitLandscapeState": ("STRING", {"default": "portrait"}),
            },
        }

    RETURN_TYPES = ("INT", "INT")
    RETURN_NAMES = ("width", "height")
    OUTPUT_TOOLTIPS = (
        "The output width. In Portrait this is the smaller of your two numbers; in Landscape it is the larger. Rounded to the nearest step when one is set on the node.",
        "The output height. In Portrait this is the larger of your two numbers; in Landscape it is the smaller. Rounded to the nearest step when one is set on the node.",
    )
    FUNCTION = "orient"
    CATEGORY = "👑 Pixaroma/🔢 Values"

    def orient(self, width=832, height=1216, PortraitLandscapeState="portrait"):
        orientation, multiple = parse_state(PortraitLandscapeState)
        w = snap_to_multiple(width, multiple)
        h = snap_to_multiple(height, multiple)
        lo, hi = min(w, h), max(w, h)
        if orientation == "landscape":
            return (hi, lo)   # wide
        return (lo, hi)       # portrait / tall (default)


NODE_CLASS_MAPPINGS = {"PixaromaPortraitLandscape": PixaromaPortraitLandscape}
NODE_DISPLAY_NAME_MAPPINGS = {"PixaromaPortraitLandscape": "Portrait Landscape Pixaroma"}
