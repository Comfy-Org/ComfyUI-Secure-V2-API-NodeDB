"""Shared gate harness for the ComfyUI-Frame-Interpolation tests (pristine vs v2).

Mounts (run_in_gate.sh):
- /pack: either the snapshot dir holding ComfyUI-Frame-Interpolation-HEAD, or that pack folder itself.
- /tests: this folder.
- /deps: the verified weights, laid out as the broker installs them:
  fi-models/huggingface/<repo>/<revision>/<file>.safetensors, plus GERALD's
  film_net_fp32.ref.safetensors.

Pristine nodes never download (there is no network) and never unpickle (policy). They get their
checkpoint tensors from the same verified safetensors the v2 broker serves. GERALD verified each
file tensor-equal to the pinned upstream pickle. So both sides run their own code on identical weights.
"""

import ast
import asyncio
import contextlib
import copy
import hashlib
import importlib
import importlib.util
import shutil
import sys
from pathlib import Path

sys.path[:0] = ["/core", "/overlay", "/tests"]

from comfy.cli_args import args  # noqa: E402

args.cpu = True

import comfy.samplers  # noqa: E402,F401  (core imports it before any custom node)
import execution  # noqa: E402
import folder_paths  # noqa: E402
import nodes as core_nodes  # noqa: E402,F401  (ComfyUI's nodes.py)
import torch  # noqa: E402
from safetensors.torch import load_file  # noqa: E402

PACK_FOLDER = "ComfyUI-Frame-Interpolation-HEAD"
SLUG = "comfyui-frame-interpolation"
PIN = "26545cc2dd95bc3d27f056016300673bdeee78f5"
KEY = "x26545cc"
WEIGHTS_ROOT = Path("/deps/fi-models")
FILM_REFERENCE = Path("/deps/film_net_fp32.ref.safetensors")

V1_CLASSES = {
    "KSampler Gradually Adding More Denoise (efficient)": ("other_nodes", "Gradually_More_Denoise_KSampler"),
    "GMFSS Fortuna VFI": ("vfi_models.gmfss_fortuna", "GMFSS_Fortuna_VFI"),
    "IFRNet VFI": ("vfi_models.ifrnet", "IFRNet_VFI"),
    "IFUnet VFI": ("vfi_models.ifunet", "IFUnet_VFI"),
    "M2M VFI": ("vfi_models.m2m", "M2M_VFI"),
    "RIFE VFI": ("vfi_models.rife", "RIFE_VFI"),
    "Sepconv VFI": ("vfi_models.sepconv", "SepconvVFI"),
    "AMT VFI": ("vfi_models.amt", "AMT_VFI"),
    "FILM VFI": ("vfi_models.film", "FILM_VFI"),
    "Make Interpolation State List": ("vfi_utils", "MakeInterpolationStateList"),
    "STMFNet VFI": ("vfi_models.stmfnet", "STMFNet_VFI"),
    "FLAVR VFI": ("vfi_models.flavr", "FLAVR_VFI"),
    "CAIN VFI": ("vfi_models.cain", "CAIN_VFI"),
    "ATM VFI": ("vfi_models.atm", "ATM_VFI"),
    "MOMO VFI": ("vfi_models.momo", "MOMO_VFI"),
    "VFI FloatToInt": ("vfi_utils", "FloatToInt"),
}
# Pristine __init__.py:44-48.
V1_DISPLAY = {
    "RIFE VFI": "RIFE VFI (recommend rife4.25+)",
    "ATM VFI": "ATM VFI (only supports 2x multiplier)",
    "MOMO VFI": "MOMO VFI (only supports 2x multiplier)",
}


def pack_head() -> Path:
    root = Path("/pack")
    if (root / "v2").is_dir():
        return root
    heads = [d for d in sorted(root.iterdir()) if d.is_dir() and not d.name.startswith(".")]
    if len(heads) != 1:
        raise SystemExit(f"/pack must hold exactly one pack folder: {heads}")
    return heads[0]


def snapshot_dir() -> Path:
    """A directory holding exactly one pack folder, as packdb.load_pack requires.

    If /pack is the pack root itself (the reviewer's mount), copy it once into /tmp under its real
    folder name. A symlink would fail packdb's source-confinement check.
    """
    root = Path("/pack")
    if not (root / "v2").is_dir():
        return root
    snap = Path("/tmp/fi-snapshot")
    if not (snap / PACK_FOLDER).is_dir():
        shutil.copytree(root, snap / PACK_FOLDER,
                        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    return snap


def load_package(name: str, folder: Path):
    spec = importlib.util.spec_from_file_location(
        name, folder / "__init__.py", submodule_search_locations=[str(folder)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def register_weights():
    folder_paths.add_model_folder_path("frame_interpolation", str(WEIGHTS_ROOT), is_default=True)


def pristine_classes() -> dict:
    """The pristine node classes, imported as upstream's __init__.py does (pack root on sys.path).

    The pack's own __init__.py is never run.
    """
    head = str(pack_head())
    if head not in sys.path:
        sys.path.insert(0, head)
    return {node_id: getattr(importlib.import_module(module), name)
            for node_id, (module, name) in V1_CLASSES.items()}


def blob_id(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def converted_file(weights_module, model_type: str, ckpt_name: str) -> Path:
    filename, _digest, _source = weights_module.FILES[(model_type, ckpt_name)]
    return (WEIGHTS_ROOT / "huggingface" / weights_module.REPO_ID / weights_module.REVISION
            / filename)


@contextlib.contextmanager
def pristine_weights(pristine_module, weights_module, film_model_factory=None):
    """Run one pristine node module with its checkpoint served from the verified safetensors.

    Only the two upstream lines that fetch and deserialize change:
    - load_file_from_github_release returns a sentinel instead of downloading;
    - torch.load (RIFE, IFRNet) on that sentinel returns the safetensors tensors;
    - torch.jit.load (FILM) on it returns film_model_factory(state_dict).
    Every other line of the pristine node runs as written.
    """
    sentinel = "verified-safetensors://"
    original_fetch = pristine_module.load_file_from_github_release
    original_load = torch.load
    original_jit_load = torch.jit.load

    def fetch(model_type, ckpt_name):
        return f"{sentinel}{model_type}/{ckpt_name}"

    def tensors(path):
        model_type, ckpt_name = path[len(sentinel):].split("/", 1)
        return load_file(str(converted_file(weights_module, model_type, ckpt_name)))

    def load(path, *rest, **kwargs):
        if isinstance(path, str) and path.startswith(sentinel):
            return tensors(path)
        return original_load(path, *rest, **kwargs)

    def jit_load(path, *rest, **kwargs):
        if isinstance(path, str) and path.startswith(sentinel) and film_model_factory:
            return film_model_factory(tensors(path))
        raise RuntimeError("TorchScript loading is not allowed in this harness")

    pristine_module.load_file_from_github_release = fetch
    torch.load = load
    torch.jit.load = jit_load
    try:
        yield
    finally:
        pristine_module.load_file_from_github_release = original_fetch
        torch.load = original_load
        torch.jit.load = original_jit_load


async def run_v2(cls, **inputs):
    """Run a v2 node through core's own V3 execution path (in-process SDK providers)."""
    cls.GET_SCHEMA()
    out = await execution._async_map_node_over_list(
        prompt_id="fi-parity", unique_id="7", obj=cls,
        input_data_all={key: [value] for key, value in inputs.items()},
        func=cls.FUNCTION, v3_data=None)
    first = out[0]
    if isinstance(first, asyncio.Task):
        first = await first
    return tuple(first.result) if hasattr(first, "result") else tuple(first)


def outcome(call):
    """('ok', value) or ('error', (type name, message))."""
    try:
        return "ok", call()
    except Exception as error:  # noqa: BLE001
        return "error", (type(error).__name__, str(error))


def same(a, b):
    """Exact equality: tensors by dtype, shape, device and torch.equal; everything else by type and value."""
    if isinstance(a, torch.Tensor) or isinstance(b, torch.Tensor):
        if not (isinstance(a, torch.Tensor) and isinstance(b, torch.Tensor)):
            return False, f"tensor vs {type(b).__name__ if isinstance(a, torch.Tensor) else type(a).__name__}"
        if a.dtype != b.dtype or a.shape != b.shape or a.device != b.device:
            return False, f"{a.dtype}/{tuple(a.shape)}/{a.device} vs {b.dtype}/{tuple(b.shape)}/{b.device}"
        if not torch.equal(a, b):
            diff = (a.double() - b.double()).abs()
            return False, f"values differ: max abs {diff.max().item()!r}, {int((diff > 0).sum())} elements"
        return True, None
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if type(a) is not type(b) or len(a) != len(b):
            return False, f"{type(a).__name__}[{len(a)}] vs {type(b).__name__}[{len(b)}]"
        for index, (x, y) in enumerate(zip(a, b)):
            ok, detail = same(x, y)
            if not ok:
                return False, f"[{index}] {detail}"
        return True, None
    if type(a) is not type(b) or a != b:
        return False, f"{a!r} vs {b!r}"
    return True, None


def frames(count, height, width, seed):
    generator = torch.Generator().manual_seed(seed)
    return torch.rand(count, height, width, 3, generator=generator, dtype=torch.float32)


def module_level_imports(path: Path) -> list:
    """Absolute module-level imports of a file (relative imports excluded)."""
    tree = ast.parse(path.read_bytes())
    names = []
    for item in tree.body:
        if isinstance(item, ast.Import):
            names += [alias.name for alias in item.names]
        elif isinstance(item, ast.ImportFrom) and item.level == 0:
            names.append(item.module)
    return names


def deepcopy_schema(cls):
    return copy.deepcopy(cls.GET_SCHEMA())
