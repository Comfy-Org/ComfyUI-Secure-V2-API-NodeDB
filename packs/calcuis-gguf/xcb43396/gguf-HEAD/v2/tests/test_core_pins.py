"""Drift guard for the pinned core constants (host-run test, with the run core importable)."""
import ast
import importlib.util
from pathlib import Path

V2 = Path(__file__).resolve().parents[1]


def _module(name):
    spec = importlib.util.spec_from_file_location('calcuis_gguf_' + name, V2 / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _static_list(name):
    tree = ast.parse((V2 / 'nodes.py').read_text())
    return next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == name for t in n.targets))


def test_supported_pt_extensions_equal_core():
    import folder_paths
    assert set(_module('catalogue_pins').SUPPORTED_PT_EXTENSIONS) == set(folder_paths.supported_pt_extensions)


def test_clip_type_lists_equal_core_loaders():
    import nodes
    assert _static_list('CLIP_TYPES') == list(nodes.CLIPLoader.INPUT_TYPES()['required']['type'][0])
    assert _static_list('DUAL_CLIP_TYPES') == list(nodes.DualCLIPLoader.INPUT_TYPES()['required']['type'][0])
