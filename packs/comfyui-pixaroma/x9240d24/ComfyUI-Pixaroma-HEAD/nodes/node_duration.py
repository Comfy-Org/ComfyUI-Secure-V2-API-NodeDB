"""Duration Pixaroma - pick a length in seconds, send the frame count.

Thin wrapper. All the maths is pure and lives in _duration_helpers.py so it can
be tested without ComfyUI (harness: D:\\Claude Tests\\_duration_test.py).

Frontend-driven (Vue Compat #9): the allowed durations, the picked value and the
recipe all live on node.properties in the browser and are injected into the
hidden DurationState input by the graphToPrompt hook in js/duration/index.js.
Because DurationState is part of the node's inputs, changing the duration
changes the cache signature, so a run picks up the new value with no IS_CHANGED.
"""

from ._duration_helpers import compute


class PixaromaDuration:
    DESCRIPTION = (
        "Pick how long a video should be in seconds, and this works out the frame count the "
        "model actually wants. It replaces the pair of nodes people normally wire up for this: "
        "one to hold the number of seconds, and one doing maths on it.\n\n"
        "Video models are fussy about length. Most will not accept just any frame count: they "
        "want it to land on a particular pattern, like every 17th frame plus 5 for MiniMax H3, "
        "or every 4th frame plus 1 for Wan and Hunyuan. Open the settings from the gear on the "
        "node, choose your model from the list, and the node handles that for you. You can also "
        "type the frame rate, the step and the plus yourself for a model that is not listed, or "
        "switch to Custom and write your own formula.\n\n"
        "You decide what durations are allowed, so the node only ever offers lengths that make "
        "sense for the workflow it is in. Give it a short list like 3, 5 and 10 and you get "
        "buttons to click. Give it a range and you get a slider. Two of these nodes on the same "
        "canvas can be set up completely differently.\n\n"
        "The node shows you what it will send before you run, including the true length, "
        "because snapping to the model's pattern usually changes it a little: 5 seconds at 24 "
        "frames per second becomes 124 frames, which is really 5.17 seconds.\n\n"
        "Find it by searching for duration, seconds, length, frames, fps, or video length."
    )

    @classmethod
    def INPUT_TYPES(cls):
        # Hidden, not required: a required STRING would show as a widget AND as a
        # convertible input dot in the Vue frontend (Vue Compat #9). The browser
        # injects the real value at graphToPrompt time.
        return {
            "required": {},
            "hidden": {"DurationState": ("STRING", {"default": "{}"})},
        }

    RETURN_TYPES = ("INT", "FLOAT")
    RETURN_NAMES = ("frames", "seconds")
    OUTPUT_TOOLTIPS = (
        "The number of frames to generate, already adjusted to the pattern your model accepts. "
        "Wire this into the length or frame count input of your video node.",
        "How long the video will really be, in seconds. This is the frame count divided by the "
        "frame rate, so it matches the picture exactly. Use it for anything that has to line up "
        "with the video, such as audio length. It can differ slightly from the number you picked, "
        "because rounding to the model's pattern changes the length a little.",
    )
    FUNCTION = "run"
    CATEGORY = "👑 Pixaroma/🔢 Values"

    def run(self, DurationState="{}"):
        frames, seconds = compute(DurationState)
        return (frames, seconds)


NODE_CLASS_MAPPINGS = {"PixaromaDuration": PixaromaDuration}
NODE_DISPLAY_NAME_MAPPINGS = {"PixaromaDuration": "Duration Pixaroma"}
