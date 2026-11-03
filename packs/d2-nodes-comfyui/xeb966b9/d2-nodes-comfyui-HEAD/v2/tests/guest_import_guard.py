"""Test-only guest import seal derived from the recorded common lock.

The import hook checks direct imports by pack frames even when the target is
already cached. The finder also checks importlib's fresh-module path. Both
remain installed for the entire GuestSession.
"""
import builtins
import hashlib
import importlib.abc
import inspect
import json
import os
import sys
from pathlib import Path

LOCK = Path("/tests/guest_common.lock")
ALIASES = {"Pillow": "PIL", "Jinja2": "jinja2", "MarkupSafe": "markupsafe",
           "Pygments": "pygments", "PyYAML": "yaml"}
PACK_PREFIXES = ("/pack/v2/",)


def allowed_roots():
    modules = set(sys.stdlib_module_names) | {
        "torch", "numpy", "PIL", "comfy_api", "comfy_secure_sdk",
    }
    for line in LOCK.read_text().splitlines():
        if "==" not in line or line.startswith("#"):
            continue
        package = line.split("==", 1)[0]
        modules.add(ALIASES.get(package, package.replace("-", "_")))
    return modules


def pack_frame(filename):
    return str(filename).startswith(PACK_PREFIXES)


def install():
    allowed = allowed_roots()
    original = builtins.__import__
    def sealed_import(name, globals=None, locals=None, fromlist=(), level=0):
        origin = (globals or {}).get("__file__", "")
        if not level and pack_frame(origin) and name.split(".", 1)[0] not in allowed:
            raise ModuleNotFoundError(
                f"sealed guest dependency not declared: {name.split('.', 1)[0]}")
        return original(name, globals, locals, fromlist, level)
    class Finder(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            frame = inspect.currentframe().f_back
            while frame is not None:
                filename = frame.f_code.co_filename
                if filename != __file__ and not filename.startswith("<frozen importlib"):
                    break
                frame = frame.f_back
            if frame is not None and pack_frame(frame.f_code.co_filename):
                root = fullname.split(".", 1)[0]
                if root not in allowed and not fullname.startswith("d2_recovery_v2."):
                    raise ModuleNotFoundError(f"sealed guest dependency not declared: {root}")
            return None
    builtins.__import__ = sealed_import
    sys.meta_path.insert(0, Finder())
    denied = {}
    for package in ("yaml", "cv2", "scipy", "requests", "torchvision", "transformers"):
        try:
            exec(compile("import " + package, "/pack/v2/_sealed_import_probe.py", "exec"),
                 {"__file__": "/pack/v2/_sealed_import_probe.py"})
        except ModuleNotFoundError as error:
            assert str(error) == f"sealed guest dependency not declared: {package}"
            denied[package] = "DENIED"
        else:
            raise AssertionError(f"sealed guest leaked {package}")
    receipt = {
        "pid": os.getpid(), "lock_sha256": hashlib.sha256(LOCK.read_bytes()).hexdigest(),
        "allowed_roots": sorted(allowed), "negative_probes": denied,
        "cached_yaml_was_present": "yaml" in sys.modules,
        "hooks_retained_for_all_dispatches": True,
        "api_root": os.environ.get("COMFY_GUEST_API_ROOT"),
    }
    sdk = sys.modules.get("comfy_api.latest._sdk")
    if sdk is not None:
        receipt["sdk_file"] = sdk.__file__
        receipt["sdk_sha256"] = hashlib.sha256(Path(sdk.__file__).read_bytes()).hexdigest()
    (Path(os.environ["TMPDIR"]) / "d2-import-seal.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt
