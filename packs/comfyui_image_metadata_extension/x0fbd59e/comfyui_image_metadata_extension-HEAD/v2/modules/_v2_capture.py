"""Secure Nodes V2 replacement for the host internals the original capture code read directly.

The original patched execution.PromptExecutor.execute and execution.get_input_data
(modules/__init__.py, modules/hook.py) and then read ``PromptExecutor.caches.outputs`` through
``execution.get_input_data`` for every node of the running prompt (modules/capture.py:11-14, 45-66).
A V2 node cannot reach the executor. It asks the broker for the prompt's execution
metadata (``ctx.graph.execution_metadata(include_observations=True)``, permission
``graph.metadata``) and this module rebuilds the same ``(input_data_all, missing_keys,
hidden)`` view from that snapshot:

* a widget value becomes ``[value]``, as execution.get_input_data does for declared
  inputs. The snapshot does not carry other packs' INPUT_TYPES, so every non-link prompt
  input is passed through: frontends only emit declared widgets, and flexible-input
  nodes (rgthree's Power Lora Loader) accept any name;
* a link resolves to the upstream node's observed outputs at that slot, or ``(None,)``
  when the upstream node has produced no outputs in this prompt, as the executor's
  output cache would;
* plain values are exact; tensors are projected to shape and dtype, and host objects
  (MODEL, CLIP, CONDITIONING, ...) to opaque identities. The capture rules read plain
  values, a LATENT's shape, and whether a CLIP input is present.

The capture algorithms in capture.py, trace.py and defs/ stay as published upstream.
"""
import asyncio
import concurrent.futures
import contextvars
import threading

from . import hook


class ShapeOnlyTensor:
    """A projected tensor: the capture rules read only ``.shape`` (LatentUpscaleBy)."""

    __slots__ = ("shape", "dtype")

    def __init__(self, shape, dtype):
        self.shape = tuple(shape)
        self.dtype = dtype

    def __repr__(self):
        return f"ShapeOnlyTensor(shape={list(self.shape)}, dtype={self.dtype})"


class OpaqueValue:
    """A projected host object (MODEL, CLIP, CONDITIONING, noise...): identity only."""

    __slots__ = ("record",)

    def __init__(self, record):
        self.record = record

    def __repr__(self):
        return f"OpaqueValue({self.record.get('declared_type') or self.record.get('kind')})"


def unproject(value):
    if value is None or type(value) in (bool, int, float, str):
        return value
    if isinstance(value, dict):
        kind = value.get("kind")
        if kind == "list":
            return [unproject(item) for item in value["items"]]
        if kind == "tuple":
            return tuple(unproject(item) for item in value["items"])
        if kind == "dict":
            return {unproject(key): unproject(item) for key, item in value["items"]}
        if kind == "tensor":
            return ShapeOnlyTensor(value["shape"], value["dtype"])
        if kind in ("noise", "opaque"):
            return OpaqueValue(value)
    raise ValueError(f"unexpected execution-observation value {value!r}")


class _CacheEntry:
    __slots__ = ("outputs",)

    def __init__(self, outputs):
        self.outputs = outputs


class ObservedOutputs:
    """The executor's output cache, as observed for this prompt."""

    def __init__(self, observations):
        self._observations = observations
        self._decoded = {}

    def get_cache(self, input_unique_id, unique_id=None):
        key = str(input_unique_id)
        if key not in self._decoded:
            record = self._observations.get(key)
            outputs = record.get("outputs") if record else None
            self._decoded[key] = None if outputs is None else _CacheEntry(
                [[unproject(item) for item in slot] for slot in outputs])
        return self._decoded[key]

    # capture.py's OutputCacheCompat probes these names (ComfyUI 0.3.66-0.3.68 cache accessors)
    def get_output_cache(self, input_unique_id, unique_id=None):
        entry = self.get_cache(input_unique_id, unique_id)
        return None if entry is None else entry.outputs

    def get(self, input_unique_id):
        return self.get_output_cache(input_unique_id)


class _Executor:
    def __init__(self, outputs):
        self.caches = type("Caches", (), {"outputs": outputs})()


class _ObservedClasses:
    """``nodes.NODE_CLASS_MAPPINGS[class_type]`` for capture.py: node classes are not
    importable in the guest, so the class type itself stands in for the class."""

    def __getitem__(self, class_type):
        return class_type


NODE_CLASS_MAPPINGS = _ObservedClasses()


class DynamicPrompt:
    """Constructed by capture.py only to be passed to get_input_data."""

    def __init__(self, prompt):
        self.prompt = prompt


def _is_link(value):
    # comfy_execution.graph_utils.is_link: a two-item list of (str node id, int or float slot)
    return (isinstance(value, list) and len(value) == 2 and isinstance(value[0], str)
            and isinstance(value[1], (int, float)))


def get_input_data(inputs, class_def, unique_id, execution_list=None, dynprompt=None, extra_data=None):
    """execution.get_input_data, rebuilt from the prompt and its observations.

    The original capture loop called execution.get_input_data as imported before
    modules/__init__.py wrapped it (modules/hook.py imports nodes/node.py, which imports
    capture.py, first), so these calls did not move hook.current_save_image_node_id. This
    stand-in does not move it either.
    """
    input_data_all = {}
    missing_keys = {}
    for name, value in inputs.items():
        if _is_link(value):
            cached = execution_list.get_cache(value[0], unique_id) if execution_list is not None else None
            if cached is None or cached.outputs is None:
                missing_keys[name] = True
                input_data_all[name] = (None,)
                continue
            if value[1] >= len(cached.outputs):
                missing_keys[name] = True
                input_data_all[name] = (None,)
                continue
            input_data_all[name] = cached.outputs[value[1]]
        else:
            input_data_all[name] = [value]
    return input_data_all, missing_keys, {}


def bind_snapshot(snapshot, current_node_id, extra_data):
    """Install one prompt's execution metadata as the capture hook state."""
    hook.current_prompt = snapshot["prompt"]
    hook.current_extra_data = extra_data
    hook.prompt_executer = _Executor(ObservedOutputs(snapshot.get("observations") or {}))
    hook.current_save_image_node_id = str(current_node_id)


# --- async bridge: the original save code is synchronous and runs in a worker thread
_loop = None
# The hook globals above are process-wide, as in the original; V2 nodes are async and may
# be scheduled concurrently, so one save runs at a time.
SAVE_LOCK = threading.Lock()


def bind_loop(loop):
    global _loop
    _loop = loop


def run_async(coroutine):
    """Run an SDK coroutine on the node's event loop from the save worker thread, in the
    worker thread's context (a copy of the node's context, made by asyncio.to_thread)."""
    context = contextvars.copy_context()
    done = concurrent.futures.Future()

    def start():
        task = _loop.create_task(coroutine, context=context)

        def finish(finished):
            if finished.cancelled():
                done.cancel()
            elif finished.exception() is not None:
                done.set_exception(finished.exception())
            else:
                done.set_result(finished.result())

        task.add_done_callback(finish)

    _loop.call_soon_threadsafe(start)
    return done.result()
