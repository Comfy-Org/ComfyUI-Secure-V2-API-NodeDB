"""Gate-only entry: production compat entry order and child-process import guard."""
import asyncio
import builtins
import hashlib
import importlib.util
import importlib.abc
import json
import os
from pathlib import Path
import re
import sys
import tomllib

import comfy_secure_nodes.guest as guest_package
from comfy_secure_nodes.guest import limits, main


def install_guard():
    tests = Path(__file__).parent
    lock = (tests / "guest_common.lock").read_bytes()
    mapping = json.loads((tests / "guest_lock_modules.json").read_text())
    assert hashlib.sha256(lock).hexdigest() == mapping["lock_sha256"]
    root = Path(os.environ["PIXAROMA_GUARD_ROOT"]).resolve()
    project = tomllib.loads((root / "pyproject.toml").read_text())
    dependencies = project.get("project", {}).get("dependencies", [])
    profile = {re.split(r"[=<>!~ ;\[]", value, maxsplit=1)[0].strip().lower().replace("-", "_") for value in dependencies}
    allowed = set(sys.stdlib_module_names) | set(mapping["modules"]) | profile
    log = Path(os.environ["PIXAROMA_GUARD_LOG"])
    report = Path(os.environ["PIXAROMA_GUARD_REPORT"])
    report.write_text(json.dumps({"pid": os.getpid(), "lock_sha256": mapping["lock_sha256"],
        "root": str(root), "allowed_modules": sorted(allowed), "profile": sorted(profile),
        "entry": "limits,fixr1_compat.install,guard,guest.main"}, sort_keys=True))
    original = builtins.__import__
    log.touch(exist_ok=True)
    def check(name, importer):
        top = name.partition(".")[0]
        if importer and Path(importer).resolve().is_relative_to(root) and top not in allowed:
            with log.open("a") as stream:
                stream.write(json.dumps({"module": name, "importer": importer, "pid": os.getpid()}) + "\n")
            raise ModuleNotFoundError(f"guest profile excludes {name!r} imported by {importer}", name=top)
    class LockedFinder(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            # Inspect the immediate non-importlib caller, so broker-owned
            # dependencies are never attributed to a distant pack frame.
            frame = sys._getframe(1)
            while frame and (str(frame.f_code.co_filename).startswith('<frozen importlib') or frame.f_globals.get('__name__','').startswith('importlib')):
                frame=frame.f_back
            check(fullname, frame.f_globals.get('__file__') if frame else None)
            return None
    sys.meta_path.insert(0, LockedFinder())
    def guarded(name, globals=None, locals=None, fromlist=(), level=0):
        if level == 0 and globals:
            check(name, globals.get("__file__"))
        return original(name, globals, locals, fromlist, level)
    builtins.__import__ = guarded


if __name__ == "__main__":
    limits.apply()
    compat = Path(guest_package.__file__).parent / "fixr1_compat.py"
    spec = importlib.util.spec_from_file_location("pixaroma_gate_compat", compat)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.install()
    install_guard()
    asyncio.run(main())
