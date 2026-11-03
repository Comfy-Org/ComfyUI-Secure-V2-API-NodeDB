"""Derive importable package names from every entry in the retained sealed lock."""
import builtins
import hashlib
import importlib.abc
import json
from pathlib import Path
import re
import sys


def allowed_modules(directory):
    directory = Path(directory)
    lock = (directory / "guest_common.lock").read_bytes()
    mapping = json.loads((directory / "distribution_modules.json").read_text())
    modules, distributions = set(), []
    for line in lock.decode().splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        name = re.split(r"[=<>!~ ;\[]", line, 1)[0]
        name = re.sub(r"[-_.]+", "-", name).lower()
        distributions.append(name)
        if name.startswith("nvidia-"):
            modules.add("nvidia")
        elif name in mapping:
            modules.update(mapping[name])
        else:
            raise AssertionError(f"sealed lock distribution has no wheel import-name mapping: {name}")
    return set(sys.stdlib_module_names) | modules, {"lock_sha256": hashlib.sha256(lock).hexdigest(), "distributions": distributions, "modules": sorted(modules)}


def install(root, namespace, denial_callback):
    root = Path(root).resolve()
    allowed, metadata = allowed_modules(Path(__file__).parent)
    original = builtins.__import__
    ancestors = {".".join(namespace.split(".")[:index]) for index in range(1, len(namespace.split(".")) + 1)}

    def check(name, importer):
        if not importer or not Path(importer).resolve().is_relative_to(root):
            return
        if name in ancestors or name.startswith(namespace + ".") or name.partition(".")[0] in allowed:
            return
        denial_callback({"module": name, "importer": importer})
        raise ModuleNotFoundError(f"sealed guest lock excludes {name!r} imported by {importer}", name=name.partition(".")[0])

    class Finder(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            frame = sys._getframe(1)
            while frame and (str(frame.f_code.co_filename).startswith("<frozen importlib") or frame.f_globals.get("__name__", "").startswith("importlib")):
                frame = frame.f_back
            check(fullname, frame.f_globals.get("__file__") if frame else None)
            return None

    finder = Finder()

    def guarded(name, globals=None, locals=None, fromlist=(), level=0):
        if level == 0 and globals:
            check(name, globals.get("__file__"))
        return original(name, globals, locals, fromlist, level)

    sys.meta_path.insert(0, finder)
    builtins.__import__ = guarded

    def assert_active():
        assert builtins.__import__ is guarded and finder in sys.meta_path

    def restore():
        assert_active()
        builtins.__import__ = original
        sys.meta_path.remove(finder)

    return metadata, assert_active, restore
