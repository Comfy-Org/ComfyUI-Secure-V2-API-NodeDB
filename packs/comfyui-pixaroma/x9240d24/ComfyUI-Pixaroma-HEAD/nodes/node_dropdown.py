"""Dropdown Pixaroma - a list you write, up to four values out.

Thin wrapper. All the real logic is pure and lives in _dropdown_helpers.py so
it can be tested without ComfyUI.
"""

from ._dropdown_helpers import MAX_OUTS, selected_values
from ._type_helpers import ANY


class PixaromaDropdown:
    DESCRIPTION = (
        "A dropdown you fill in yourself. Each entry has a short name and the value it stands "
        "for, so you pick 'warm light' instead of pasting a whole sentence every time. Handy for "
        "LoRA trigger words, favourite sizes, step counts, or any value you retype often.\n\n"
        "Open the settings from the gear on the node, add your entries, and choose what the node "
        "sends out: text, a whole number, a decimal, or on/off. The output dot renames itself to "
        "match, so you can see at a glance what will come out.\n\n"
        "One entry can carry up to four values at once. Set how many outputs you want in the "
        "settings and give each one a name, and every entry then holds one value per output, so "
        "a single pick sets several wires together: a sampler and its scheduler, a width and a "
        "height, steps and cfg. Each output has its own type, and the node shows what your pick "
        "resolved to before you run anything. With one output it behaves exactly as it always "
        "has.\n\n"
        "The small letter on the node decides which entry it sends each time you run, and you "
        "can click it to change: F keeps the entry you picked, I steps to the next one every "
        "run, and R picks any of them at random.\n\n"
        "It ignores whatever it is plugged into: the list and the type are yours, set on the "
        "node. That is the difference from Control Panel Pixaroma, whose controls copy the type "
        "of the input they are wired to.\n\n"
        "The list is saved inside the workflow, so sending someone the workflow sends your "
        "entries with it. Export and Import move a list between workflows.\n\n"
        "Find it by searching for dropdown, list, options, preset, choose, pick, combination, "
        "pair, or trigger."
    )

    @classmethod
    def INPUT_TYPES(cls):
        # Hidden, not required: a required STRING would show as a widget AND as
        # a convertible input dot in the Vue frontend (Vue Compat #9). The
        # browser injects the real value at graphToPrompt time.
        return {
            "required": {},
            "hidden": {"DropdownState": ("STRING", {"default": "{}"})},
        }

    # ANY, exactly as Control Panel declares its outputs. The TYPED appearance
    # is a frontend concern: js/dropdown/ sets node.outputs[0].type so LiteGraph
    # refuses an incompatible drag on the canvas. There is no second, server-side
    # type check behind that - same as Switch and Control Panel.
    # Four ANY outputs are always declared; the browser hides the ones beyond the
    # chosen count, exactly as Sliders Pixaroma does with its 16. Declaring them
    # here rather than growing them later keeps the node definition stable, so a
    # saved workflow never sees the def change under it.
    # RETURN_TYPES is built from MAX_OUTS while the two below are literals,
    # and ComfyUI zips the three lists BY INDEX - so a mismatch is silent,
    # costing outputs their names or tooltips. scripts/release_preflight.py
    # resolves the MAX_OUTS repeat and fails the release on it (mutation-tested
    # both directions). Raising the cap means editing FOUR places: both lists
    # below, _dropdown_helpers.MAX_OUTS, and MAX_OUTS in js/dropdown/core.mjs -
    # preflight sees the first three, the browser constant it cannot.
    # NOT an assert here: this module is imported by
    # __init__.py with no try/except, and ComfyUI answers an import failure
    # with a logging.warning, so raising would make all ~40 Pixaroma nodes
    # vanish over a console line nobody reads. It would also be stripped by
    # python -O, which preflight is not.
    RETURN_TYPES = (ANY,) * MAX_OUTS
    RETURN_NAMES = ("value", "value_2", "value_3", "value_4")
    OUTPUT_TOOLTIPS = (
        "The value behind the entry you picked. What kind of value it is follows the type set "
        "for this output: text, a whole number, a decimal, or on/off.",
        "The second value of the entry you picked. Only shown when the node is set to two or "
        "more outputs.",
        "The third value of the entry you picked. Only shown when the node is set to three or "
        "more outputs.",
        "The fourth value of the entry you picked. Only shown when the node is set to four "
        "outputs.",
    )
    FUNCTION = "run"
    CATEGORY = "👑 Pixaroma/🔢 Values"

    def run(self, DropdownState="{}"):
        return selected_values(DropdownState)


NODE_CLASS_MAPPINGS = {"PixaromaDropdown": PixaromaDropdown}
NODE_DISPLAY_NAME_MAPPINGS = {"PixaromaDropdown": "Dropdown Pixaroma"}
