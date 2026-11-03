"""Test-only guest entry for the gate.

It runs the guest main with the host-shipped fixr1_compat applied first, in the order guest/fixr1_compat.py's own
entry uses: limits, install, main.

Production pack guests always run with that patch (sealed guests through fixr1_compat.py, snapshot guests via
snapentry.py). The gate has no render root to build a sealed pack runtime, so the tests start their GuestSession
with this entry instead.

Two test controls, both set by the test through the guest environment (GuestSession._adjust_guest_env):

* WLSH_GUARD_ROOT (the pack's v2 root): the guest import audit. While the guest runs, an import statement in a module
  under that root may name only the standard library, the sealed guest lock (guest_lock_modules.json) or the pack's
  declared dependency profile (pyproject.toml). Anything else raises ModuleNotFoundError there, as it would in a
  production guest. The gate image has more packages than a guest (scipy, cv2, kornia, ...), so without this, parity
  could pass on a node that fails with ImportError in production. Only imports made by pack code are judged, so the
  guest runtime's own imports are unaffected. WLSH_GUARD_PROFILE names the pyproject.toml that declares the profile
  (default: <root>/pyproject.toml); WLSH_GUARD_LOG names a file that gets one JSON line per refused import.
* WLSH_GUEST_SEED and WLSH_GUEST_THREADS: seed torch's global generator and set its intra-op thread count before
  the guest serves anything (unused by this pack's tests, which draw no random numbers in the guest).
* WLSH_GUEST_REPORT: a file that gets the guest's numerical runtime (versions, paths, threads), for the record.
"""

import asyncio
import builtins
import importlib.util
import json
import os
import re
import sys
import tomllib

import comfy_secure_nodes.guest as guest_package
from comfy_secure_nodes.guest import limits, main


def install_import_guard(root, pyproject, log_path):
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "guest_lock_modules.json"), encoding="utf-8") as handle:
        lock_modules = set(json.load(handle)["modules"])
    with open(pyproject, "rb") as handle:
        dependencies = tomllib.load(handle).get("project", {}).get("dependencies", [])
    profile = {re.split(r"[=<>!~ ;\[]", dep, maxsplit=1)[0].strip().lower().replace("-", "_") for dep in dependencies}
    allowed = set(sys.stdlib_module_names) | lock_modules | profile
    prefix = os.path.join(os.path.realpath(root), "")
    real_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if level == 0 and globals:
            importer = globals.get("__file__") or ""
            top = name.partition(".")[0]
            if top not in allowed and os.path.realpath(importer).startswith(prefix):
                if log_path:
                    try:
                        with open(log_path, "a", encoding="utf-8") as log:
                            log.write(json.dumps({"module": name, "importer": importer, "pid": os.getpid()}) + "\n")
                    except OSError:
                        pass
                raise ModuleNotFoundError(f"guest import audit: {name!r} is not in the guest (not stdlib, the sealed "
                                          f"lock or the declared profile); imported by {importer}", name=top)
        return real_import(name, globals, locals, fromlist, level)

    builtins.__import__ = guarded_import


def write_report(path):
    """The guest's numerical runtime, for the test's record (WLSH_GUEST_REPORT)."""
    import numpy
    import PIL
    import torch

    facts = {"python": sys.version, "executable": sys.executable, "torch": torch.__version__,
             "torch_file": torch.__file__, "torch_threads": torch.get_num_threads(),
             "torch_interop_threads": torch.get_num_interop_threads(), "numpy": numpy.__version__,
             "numpy_file": numpy.__file__, "pillow": PIL.__version__, "pillow_file": PIL.__file__,
             "thread_env": {k: os.environ.get(k) for k in ("OMP_NUM_THREADS", "MKL_NUM_THREADS",
                                                           "OPENBLAS_NUM_THREADS")}}
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(facts, handle, sort_keys=True)


if __name__ == "__main__":
    limits.apply()
    path = os.path.join(os.path.dirname(os.path.abspath(guest_package.__file__)), "fixr1_compat.py")
    spec = importlib.util.spec_from_file_location("comfy_fixr1_compat", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["comfy_fixr1_compat"] = module
    spec.loader.exec_module(module)
    module.install()
    if os.environ.get("WLSH_GUARD_ROOT"):
        root = os.environ["WLSH_GUARD_ROOT"]
        install_import_guard(root, os.environ.get("WLSH_GUARD_PROFILE") or os.path.join(root, "pyproject.toml"),
                             os.environ.get("WLSH_GUARD_LOG"))
    if os.environ.get("WLSH_GUEST_THREADS"):
        import torch

        torch.set_num_threads(int(os.environ["WLSH_GUEST_THREADS"]))
    if os.environ.get("WLSH_GUEST_SEED"):
        import torch

        torch.manual_seed(int(os.environ["WLSH_GUEST_SEED"]))
    if os.environ.get("WLSH_GUEST_REPORT"):
        write_report(os.environ["WLSH_GUEST_REPORT"])
    asyncio.run(main())
