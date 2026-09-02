"""Import one module out of a pack, inside a guest, without running the pack.

A converted node reuses upstream's compute verbatim, so it has to import the
module that compute lives in. Two things make that harder than
`spec_from_file_location`:

* **Packs use relative imports.** `nodes/batchcrop_nodes.py` opens with
  `from ..utility.utility import tensor2pil, ...`, which only resolves if the
  module is loaded AS PART OF A PACKAGE. Loaded standalone it raises
  ``ImportError: attempted relative import beyond top-level package``.
* **The pack's `__init__.py` is not guest-safe.** Importing the package the
  ordinary way runs that file, which for most packs reaches `folder_paths`,
  `nodes` and the rest of the host surface at module scope — the guest refuses
  all of it, correctly.

So this builds a SYNTHETIC package: namespace modules whose `__path__` points
at the pack's directories, registered under a private name, with no
`__init__.py` executed anywhere. Relative imports resolve against it, and only
the leaf module a node actually needs is executed.

`ROOT` is the pristine pack immediately above v2. Override with
`COMFY_KJNODES_ROOT` only in a
conversion test that deliberately compares against another snapshot.
"""
from __future__ import annotations

import os
import sys
import types
from importlib.util import module_from_spec, spec_from_file_location

def _default_root() -> str:
    return os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))


ROOT = os.environ.get("COMFY_KJNODES_ROOT", _default_root())

#: Private package name. Deliberately not the pack's own directory name — this
#: is a partial view of the pack, and giving it the real name would let an
#: ordinary `import` land here and get something incomplete.
PKG = "_kjnodes_partial"


def _ensure_package(name: str, path: str) -> types.ModuleType:
    """A namespace package rooted at `path`, with no `__init__.py` executed."""
    existing = sys.modules.get(name)
    if existing is not None:
        return existing
    pkg = types.ModuleType(name)
    pkg.__path__ = [path]  # marks it a package, so submodule import works
    pkg.__package__ = name
    sys.modules[name] = pkg
    return pkg


def load(relpath: str) -> types.ModuleType:
    """Import `relpath` (e.g. ``"nodes/batchcrop_nodes.py"``) from the pack.

    Returns the executed module. Cached, because a guest serves node after node
    from the same pack and re-executing a module per dispatch would re-pay its
    import cost every time.
    """
    parts = relpath.replace("\\", "/").split("/")
    modname = f"{PKG}." + ".".join(p[:-3] if p.endswith(".py") else p
                                   for p in parts)
    cached = sys.modules.get(modname)
    if cached is not None:
        return cached

    _ensure_package(PKG, ROOT)
    # Every intermediate directory becomes a namespace package, so a relative
    # import that walks upward (`..utility.utility`) has something to walk to.
    walked = PKG
    here = ROOT
    for part in parts[:-1]:
        here = os.path.join(here, part)
        walked = f"{walked}.{part}"
        _ensure_package(walked, here)

    target = os.path.join(ROOT, *parts)
    if not os.path.exists(target):
        raise FileNotFoundError(
            f"{target} does not exist; the pack moved or changed shape and the "
            f"conversion that imports it must be revisited")

    spec = spec_from_file_location(modname, target)
    mod = module_from_spec(spec)
    mod.__package__ = walked
    sys.modules[modname] = mod
    try:
        spec.loader.exec_module(mod)
    except BaseException:
        # A half-executed module left in sys.modules would be served to the
        # next caller as though it had imported cleanly.
        sys.modules.pop(modname, None)
        raise
    return mod
