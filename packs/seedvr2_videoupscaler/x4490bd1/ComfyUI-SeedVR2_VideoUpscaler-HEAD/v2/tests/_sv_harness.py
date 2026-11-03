"""Shared gate harness for the SeedVR2 tests (pristine vs v2, CPU).

Mounts (run_in_gate.sh):
- /pack: the snapshot dir holding ComfyUI-SeedVR2_VideoUpscaler-HEAD, or that folder itself.
- /tests: this folder.
- /deps: the pinned wheels unpacked (diffusers, omegaconf, rotary_embedding_torch, gguf, cv2).
  Also the two default checkpoints, laid out twice:
  - SEEDVR2/<file> for the pristine pack (it reads models_dir/SEEDVR2);
  - sv-models/huggingface/<repo>/<revision>/<file>, where the SDK broker finds installed weights.
  The two copies are hardlinks of one sha256-checked file.
  And the two declared text-embedding files, at sv-models/huggingface/<repo>/<revision>/<file>.

Both sides run on CPU. The pristine pack's own device menus offer only GPUs, so its define_schema
is evaluated under a simulated single-CUDA host (see simulated_gpu_host).

Nothing here reads the snapshot's upstream media, example workflows or bundled model files: a
published snapshot may omit them. The pristine pack gets its two text embeddings from the same
declared files v2 uses (see pristine_embeddings).
"""

import asyncio
import contextlib
import gc
import hashlib
import importlib.util
import shutil
import sys
from pathlib import Path

sys.path[:0] = ["/core", "/overlay", "/tests"]
sys.path.append("/deps")

from comfy.cli_args import args  # noqa: E402

args.cpu = True

import comfy.samplers  # noqa: E402,F401
import execution  # noqa: E402
import folder_paths  # noqa: E402
import nodes as core_nodes  # noqa: E402,F401
import torch  # noqa: E402
from comfy_execution.utils import CurrentNodeContext  # noqa: E402

PACK_FOLDER = "ComfyUI-SeedVR2_VideoUpscaler-HEAD"
SLUG = "seedvr2_videoupscaler"
PIN = "4490bd1f482e026674543386bb2a4d176da245b9"
KEY = "x4490bd1"
DIT = "seedvr2_ema_3b_fp8_e4m3fn.safetensors"
VAE = "ema_vae_fp16.safetensors"


def pack_head() -> Path:
    root = Path("/pack")
    if (root / "v2").is_dir():
        return root
    heads = [d for d in sorted(root.iterdir()) if d.is_dir() and not d.name.startswith(".")]
    if len(heads) != 1:
        raise SystemExit(f"/pack must hold exactly one pack folder: {heads}")
    return heads[0]


def snapshot_dir() -> Path:
    """A directory holding exactly one pack folder, as packdb.load_pack requires."""
    root = Path("/pack")
    if not (root / "v2").is_dir():
        return root
    snap = Path("/tmp/sv-snapshot")
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


def setup_weights():
    # Pristine: models_dir/SEEDVR2 (src/utils/constants.py get_base_cache_dir).
    folder_paths.models_dir = "/deps"
    # V2: the in-process SDK broker reuses an installed, verified file at
    # <folder root>/huggingface/<repo>/<revision>/<file> without any network request.
    for folder in ("diffusion_models", "vae", "embeddings"):
        folder_paths.add_model_folder_path(folder, "/deps/sv-models", is_default=True)


def declared_embeddings(weights_module):
    """{pack file name: tensor} read from the declared embedding files in /deps."""
    from safetensors.torch import load_file

    tensors = {}
    for name, weight in weights_module.EMBEDDING_WEIGHTS.items():
        path = Path("/deps/sv-models/huggingface") / weight.repo_id / weight.revision / weight.filename
        if hashlib.sha256(path.read_bytes()).hexdigest() != weight.sha256:
            raise ValueError(f"{path}: sha256 differs from the declaration")
        state = load_file(str(path), device="cpu")
        key = weights_module.EMBEDDINGS[name][1]
        if list(state) != [key]:
            raise ValueError(f"{path}: holds {sorted(state)}, expected exactly {key!r}")
        tensors[name] = state[key]
    return tensors


class _TorchLoadSwap:
    """Forwards everything to torch, except torch.load of the pack's two bundled embeddings. That
    returns a fresh copy of the same tensor from the declared files instead of the pack's file."""

    def __init__(self, tensors):
        self._tensors = tensors

    def __getattr__(self, name):
        return getattr(torch, name)

    def load(self, f, *args, **kwargs):
        name = Path(str(f)).name
        if name in self._tensors:
            return self._tensors[name].clone()
        return torch.load(f, *args, **kwargs)


def pristine_embeddings(pristine_package_name, tensors):
    """Point only the pristine generation_utils.load_text_embeddings file reads at the declared
    tensors (its module-global torch). The function body itself runs unchanged."""
    module = sys.modules[f"{pristine_package_name}.src.core.generation_utils"]
    module.torch = _TorchLoadSwap(tensors)


@contextlib.contextmanager
def simulated_gpu_host(pristine_package_name):
    """The pristine define_schema lists only GPU devices (an empty list on CPU makes it raise).
    Simulate a host with exactly one CUDA device while the schema is built."""
    mm = sys.modules[f"{pristine_package_name}.src.optimization.memory_manager"]
    saved = (mm.is_cuda_available, mm.is_mps_available, torch.cuda.device_count)
    mm.is_cuda_available = lambda: True
    mm.is_mps_available = lambda: False
    torch.cuda.device_count = lambda: 1
    try:
        yield
    finally:
        mm.is_cuda_available, mm.is_mps_available, torch.cuda.device_count = saved


def run_pristine(cls, node_id="7", **inputs):
    with CurrentNodeContext("sv-parity", node_id, 0):
        result = cls.execute(**inputs)
    return tuple(result.result)


async def run_v2(cls, node_id="7", **inputs):
    """A v2 node through core's own V3 execution path (in-process SDK providers)."""
    cls.GET_SCHEMA()
    out = await execution._async_map_node_over_list(
        prompt_id="sv-parity", unique_id=node_id, obj=cls,
        input_data_all={key: [value] for key, value in inputs.items()},
        func=cls.FUNCTION, v3_data=None)
    first = out[0]
    if isinstance(first, asyncio.Task):
        first = await first
    return tuple(first.result) if hasattr(first, "result") else tuple(first)


def outcome(call):
    try:
        return "ok", call()
    except Exception as error:  # noqa: BLE001
        return "error", (type(error).__name__, str(error))
    finally:
        gc.collect()


def same(a, b):
    if isinstance(a, torch.Tensor) or isinstance(b, torch.Tensor):
        if not (isinstance(a, torch.Tensor) and isinstance(b, torch.Tensor)):
            return False, "tensor vs non-tensor"
        if a.dtype != b.dtype or a.shape != b.shape or a.device != b.device:
            return False, f"{a.dtype}/{tuple(a.shape)}/{a.device} vs {b.dtype}/{tuple(b.shape)}/{b.device}"
        if not torch.equal(a, b):
            diff = (a.double() - b.double()).abs()
            return False, f"values differ: max abs {diff.max().item()!r}, {int((diff > 0).sum())} elements"
        return True, None
    if isinstance(a, dict) and isinstance(b, dict):
        if list(a) != list(b):
            return False, f"keys {list(a)} vs {list(b)}"
        for key in a:
            ok, detail = same(a[key], b[key])
            if not ok:
                return False, f"[{key!r}] {detail}"
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


def frames(count, height, width, channels, seed):
    generator = torch.Generator().manual_seed(seed)
    return torch.rand(count, height, width, channels, generator=generator, dtype=torch.float32)
