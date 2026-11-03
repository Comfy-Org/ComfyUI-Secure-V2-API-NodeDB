"""Free VRAM Pixaroma - hand the graphics card's memory back, mid-workflow.

Thin wrapper. Every decision is pure and lives in _free_vram_helpers.py so it can
be tested without a GPU (harness: D:\\Claude Tests\\_free_vram_test.py).

Frontend-driven (Vue Compat #9): the mode, the switches and the threshold live on
node.properties in the browser and are injected into the hidden FreeVramState
input by the graphToPrompt hook in js/free_vram/index.js.

HOW PLACEMENT WORKS, and why there are two ways to wire it:

* OUTPUT_NODE = True, so ComfyUI runs it whether or not anything is downstream.
  Hang it off a node's output and it fires once that node has produced its
  value - "free after the VAE decode" needs only the INPUT wired. This is also
  the CHEAPEST placement: with nothing downstream, the always-run IS_CHANGED
  cannot invalidate anybody's cache.
* Wiring the value THROUGH it as well pins it BETWEEN two steps, which is what
  you want when a specific later stage must find the room already made.

A node with NOTHING wired in does nothing at all (see _free's first guard). That
guard is what makes OUTPUT_NODE safe here: without it, merely dropping this node
on the canvas to look at it would unload every model on the next run.
"""

import gc
import time

from ._type_helpers import ANY
from ._free_vram_helpers import (
    bar_segments,
    format_bytes,
    headline_freed,
    headline_label,
    parse_state,
    plan,
    should_always_run,
    should_free,
    threshold_bytes,
    uses_driver_view,
)


def _read_memory():
    """(total, free_total, free_driver, device_name) for the main torch device.

    `free_total` is what ComfyUI itself considers available - it counts torch's
    spare reserved blocks, so it is the number that decides whether the next
    model fits. `free_driver` is what the card reports and what nvidia-smi
    shows, which is what matters to anything OUTSIDE this process.
    """
    import comfy.model_management as mm

    dev = mm.get_torch_device()
    total = int(mm.get_total_memory(dev))
    free_total, free_torch = mm.get_free_memory(dev, torch_free_too=True)
    return int(total), int(free_total), int(free_total) - int(free_torch), str(dev)


class PixaromaFreeVram:
    DESCRIPTION = (
        "Frees up graphics memory at the exact point in the workflow you put it. Wire something "
        "into it and the same thing comes straight back out unchanged, so it drops into any wire "
        "without altering what flows through.\n\n"
        "The usual reason to want this is a workflow with two heavy stages. The first model is "
        "still sitting in memory when the second one is asked for, so the second one has nowhere "
        "to go and the run stops with an out of memory error. Put this node on the wire between "
        "the two and the first model is let go before the second is loaded.\n\n"
        "Three modes on the node face. All lets go of the models and hands the spare memory back "
        "to the card. Models lets go of the models but lets ComfyUI keep its reserved memory, "
        "which is a little faster. Cache keeps the models loaded and only hands the spare back, "
        "which is what you want when something outside ComfyUI needs the card.\n\n"
        "After a run it shows how much it got back, with a bar of the whole card. Left to right: "
        "grey is still in use, orange is what this node just released, dark is what was already "
        "free. So everything to the right of the grey is free memory, and the orange is the part "
        "of it you gained by adding this node.\n\n"
        "Open the gear for the rest: whether to collect leftovers, whether to act on every run, "
        "and a limit so it only bothers when memory is actually running low.\n\n"
        "Find it by searching for free, VRAM, memory, unload, clean, cache, or OOM."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {},
            "optional": {
                "value": (ANY, {
                    "tooltip": (
                        "Anything at all: an image, a model, a latent, some text. It comes back "
                        "out unchanged. Its only job is to say WHEN to clean up: the node waits "
                        "for this to arrive, so it runs after whatever you took the wire from. "
                        "Nothing wired here means the node does nothing."
                    ),
                }),
            },
            # Hidden, not required: a required STRING would show as a widget AND
            # as a convertible input dot (Vue Compat #9). The browser injects the
            # real value at graphToPrompt time.
            "hidden": {"FreeVramState": ("STRING", {"default": "{}"})},
        }

    RETURN_TYPES = (ANY,)
    RETURN_NAMES = ("value",)
    OUTPUT_TOOLTIPS = (
        "Exactly what you wired in, untouched. You do not have to connect this: the node runs "
        "either way. Use it when a particular later step must find the room already made, by "
        "carrying on from here instead of from the node above.",
    )
    FUNCTION = "run"
    # Runs even with nothing downstream, so hanging the node off an output is a
    # valid placement rather than a silently dead one. Safe only because _free
    # does nothing when the INPUT is unwired.
    OUTPUT_NODE = True
    CATEGORY = "👑 Pixaroma/🔀 Logic & Flow"

    @classmethod
    def IS_CHANGED(cls, FreeVramState="{}", **kwargs):
        # A node whose whole point is a side effect has to be able to opt out of
        # caching, or it is skipped in exactly the case it was added for. The
        # cost is real and is why this is a setting rather than always NaN: a
        # node that never matches its previous key forces everything downstream
        # of it to re-run too (see should_always_run).
        state = parse_state(FreeVramState)
        if should_always_run(state):
            return float("nan")
        return FreeVramState

    def run(self, value=None, FreeVramState="{}"):
        state = parse_state(FreeVramState)
        report = self._free(state, wired=value is not None)
        # A CACHED node still replays its executed event carrying this same
        # payload, so the browser needs a way to tell a real run from a replay -
        # otherwise the face would claim it freed memory on a run where it never
        # executed at all. A monotonic clock read is enough: it can only change
        # when this method actually ran.
        report["stamp"] = time.perf_counter()
        return {"ui": {"pixaroma_free_vram": [report]}, "result": (value,)}

    def _free(self, state, wired=True):
        # An OUTPUT_NODE runs on every prompt, so a node someone dropped on the
        # canvas to look at would otherwise unload every model each run. An
        # unconnected optional input never reaches the prompt at all, so it
        # arrives as None - that is the whole test.
        if not wired:
            return {
                "ok": True, "skipped": True, "reason": "nothing wired in",
                "message": "Nothing is wired into this node, so it has no moment to act on.",
                "unwired": True, "mode": state["mode"],
            }
        steps = plan(state)
        try:
            total, comfy_before, driver_before, device = _read_memory()
        except Exception as exc:  # no torch device, an exotic backend, anything
            return {
                "ok": False,
                "message": "Could not read the graphics memory: %s" % exc,
                "mode": state["mode"],
            }

        # ONE decision, taken once, drives the THRESHOLD GATE, the headline, the
        # bar and the readout - so they can never contradict each other.
        #
        # It was applied to the headline alone at first, and the two consumers
        # left behind both misbehaved in Cache mode: the gate measured ComfyUI's
        # free figure (which cache-emptying does not move), so it skipped exactly
        # when an outside app was starving; and the bar drew its orange from the
        # same unmoving pair, so the face could read "returned 6.0 GB" above a bar
        # with no orange in it. Both reproduced before this was changed.
        before = driver_before if uses_driver_view(state) else comfy_before

        go, reason = should_free(state, before)
        if not go:
            limit = threshold_bytes(state)
            used, just, was = bar_segments(total, before, before)
            return {
                "ok": True,
                "skipped": True,
                "reason": reason,
                "message": "%s free already, over the %s limit" % (
                    format_bytes(before), format_bytes(limit)),
                "mode": state["mode"], "device": device,
                "total": total, "before": before, "after": before,
                "comfyBefore": comfy_before, "comfyAfter": comfy_before,
                "driverBefore": driver_before, "driverAfter": driver_before,
                # The mode's own word even here, so a skipped Cache run does not
                # call itself "freed" when a real one would say "returned".
                "freed": 0, "label": headline_label(state),
                "bar": [used, just, was],
            }

        try:
            import comfy.model_management as mm

            # ORDER MATTERS. Unload first so the tensors are dropped, collect so
            # anything holding them in a reference cycle lets go, and only THEN
            # empty the cache - emptying it can only return blocks that are
            # already free, so doing it first would return almost nothing.
            if steps["models"]:
                mm.unload_all_models()
            if steps["gc"]:
                gc.collect()
            if steps["cache"]:
                mm.soft_empty_cache(True)
        except Exception as exc:
            return {
                "ok": False,
                "message": "Could not free memory: %s" % exc,
                "mode": state["mode"], "device": device,
            }

        try:
            _t, comfy_after, driver_after, _d = _read_memory()
        except Exception:
            comfy_after, driver_after = comfy_before, driver_before

        after = driver_after if uses_driver_view(state) else comfy_after
        freed, label = headline_freed(state, comfy_before, comfy_after,
                                      driver_before, driver_after)
        used, just, was = bar_segments(total, before, after)
        return {
            "ok": True,
            "skipped": False,
            "reason": "",
            "message": "",
            "mode": state["mode"], "device": device,
            # before/after are the pair this MODE reasons in - the bar and the
            # readout follow them. The two raw pairs ride along unchanged so the
            # hover tooltip can still show both views side by side.
            "total": total, "before": before, "after": after,
            "comfyBefore": comfy_before, "comfyAfter": comfy_after,
            "driverBefore": driver_before, "driverAfter": driver_after,
            "freed": freed, "label": label,
            "bar": [used, just, was],
        }


NODE_CLASS_MAPPINGS = {"PixaromaFreeVram": PixaromaFreeVram}
NODE_DISPLAY_NAME_MAPPINGS = {"PixaromaFreeVram": "Free VRAM Pixaroma"}
