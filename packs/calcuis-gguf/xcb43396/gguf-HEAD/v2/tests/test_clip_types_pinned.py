"""Drift guard: the pinned CLIPType names equal the runtime core's comfy.sd.CLIPType members (run with core importable)."""
import importlib.util
from pathlib import Path

V2 = Path(__file__).resolve().parents[1]


def test_pinned_clip_types_equal_core():
    import comfy.sd
    spec = importlib.util.spec_from_file_location('calcuis_clip_types', V2 / 'clip_types.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert list(module.CLIP_TYPE_NAMES) == list(comfy.sd.CLIPType.__members__)
