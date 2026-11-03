"""Test-only guest entry for the gate: the pack's dependency profile, as production serves it.

It runs the guest main in the production order (limits, fixr1_compat install, main), like
_res4_sealed_guest_entry.py, with one addition. The modules of the pack's declared dependency profile
(v2/pyproject.toml ``dependencies``) resolve ONLY from /deps, the unpacked profile wheels the gate mounts. They do
not resolve from the gate image, which happens to have them installed.
- With /deps mounted, the guest sees the profile as a deployed profile serves it.
- Without it, the guest sees what production sees before the profile is deployed: those imports fail.
Everything else (stdlib, torch, numpy, mpmath, comfy_api) resolves as in the sealed entry. Each profile import is
reported on stderr.
"""

import asyncio
import importlib.machinery
import importlib.util
import os
import re
import sys
import tomllib

import comfy_secure_nodes.guest as guest_package
from comfy_secure_nodes.guest import limits, main

PYPROJECT = "/pack/v2/pyproject.toml"
DEPS = "/deps"


def declared_profile_modules():
    with open(PYPROJECT, "rb") as handle:
        pins = tomllib.load(handle)["project"].get("dependencies", [])
    names = set()
    for pin in pins:
        distribution = re.split(r"[=<>!~;\[ ]", pin, maxsplit=1)[0]
        names.add(distribution.lower().replace("-", "_"))
    return names


class ProfileOnlyFinder:
    """Top-level profile modules come from /deps or not at all; their submodules follow the package's __path__."""

    def __init__(self, names, roots):
        self.names = frozenset(names)
        self.roots = list(roots)

    def find_spec(self, fullname, path=None, target=None):
        if "." in fullname or fullname not in self.names:
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, self.roots) if self.roots else None
        if spec is None:
            print(f"res4lyf profile: {fullname} unavailable (no profile deployed)", file=sys.stderr, flush=True)
            raise ModuleNotFoundError(f"No module named {fullname!r}", name=fullname)
        print(f"res4lyf profile: {fullname} <- {spec.origin}", file=sys.stderr, flush=True)
        return spec


if __name__ == "__main__":
    limits.apply()
    path = os.path.join(os.path.dirname(os.path.abspath(guest_package.__file__)), "fixr1_compat.py")
    spec = importlib.util.spec_from_file_location("comfy_fixr1_compat", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["comfy_fixr1_compat"] = module
    spec.loader.exec_module(module)
    module.install()
    profile = declared_profile_modules()
    # torch imports tqdm through a guarded import (torch/hub.py:64, at `import torch`); a base without tqdm makes
    # torch fall back silently. In the gate it loads the image's copy first. Such early pure-Python imports are
    # removed here, so the pack's own imports go through the profile exactly as in a guest whose base lacks them.
    # A compiled module cannot be re-imported cleanly, so an early compiled import stops the guest instead.
    early = sorted(name for name in sys.modules if name.split(".")[0] in profile)
    compiled = [name for name in early if not str(getattr(sys.modules[name], "__file__", None) or "").endswith(".py")]
    if compiled:
        raise SystemExit(f"profile modules with compiled parts were imported before the guest main: {compiled}")
    for name in early:
        del sys.modules[name]
    if early:
        print(f"res4lyf profile: removed early imports of {sorted({n.split('.')[0] for n in early})} "
              "(guarded imports outside the pack, e.g. torch.hub)", file=sys.stderr, flush=True)
    sys.meta_path.insert(0, ProfileOnlyFinder(profile, [DEPS] if os.path.isdir(DEPS) else []))
    asyncio.run(main())
