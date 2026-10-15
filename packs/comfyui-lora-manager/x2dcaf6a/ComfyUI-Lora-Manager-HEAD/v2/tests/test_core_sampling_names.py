"""Drift guard for Load Image Metadata's sampler and scheduler names.

The deployed secure SDK (backend 745b88f) has no sampling-catalogue API, so the node validates
recovered names against lists pinned to the deployed core (ComfyUI 6257422) in
secure_algorithms/core_sampling_names.py. Run with that core importable: any drift between the
pinned lists and core's own comfy.samplers.KSampler lists fails here.
"""
import importlib.util
from pathlib import Path

V2 = Path(__file__).resolve().parents[1]


def _pinned():
    spec = importlib.util.spec_from_file_location(
        'lora_manager_core_sampling_names', V2 / 'secure_algorithms' / 'core_sampling_names.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pinned_samplers_equal_core():
    import comfy.samplers
    assert list(_pinned().SAMPLERS) == list(comfy.samplers.KSampler.SAMPLERS)


def test_pinned_schedulers_equal_core():
    import comfy.samplers
    assert list(_pinned().SCHEDULERS) == list(comfy.samplers.KSampler.SCHEDULERS)
