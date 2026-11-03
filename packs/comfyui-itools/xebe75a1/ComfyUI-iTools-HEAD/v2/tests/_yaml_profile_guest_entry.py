"""Test-only guest entry for the iTools profile test: the guest main with the host-shipped fixr1_compat applied
(as production pack guests run), and with pyyaml importable ONLY from /deps.

A production guest sees its sealed lock, the pack's runtime base and its declared dependency profile, not Core's
requirements; base 0cd9adec has no pyyaml. The gate image has one in its site-packages, so this entry refuses any
yaml whose files are not under /deps, before any pack code can import. /deps (the profile's pinned wheel) is on the
guest's PYTHONPATH only when the test provides it.
"""

import asyncio
import importlib.abc
import importlib.machinery
import importlib.util
import os
import sys

import comfy_secure_nodes.guest as guest_package
from comfy_secure_nodes.guest import limits, main

PROFILE_ROOT = "/deps"


class OnlyProfileYaml(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] not in ("yaml", "_yaml"):
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        locations = [spec.origin or ""] + list(spec.submodule_search_locations or []) if spec else []
        if spec is None or not all(str(loc).startswith(PROFILE_ROOT) for loc in locations if loc):
            raise ModuleNotFoundError(f"No module named {fullname!r} (only the declared profile under "
                                      f"{PROFILE_ROOT} may provide it)", name=fullname)
        return spec


if __name__ == "__main__":
    sys.meta_path.insert(0, OnlyProfileYaml())
    limits.apply()
    path = os.path.join(os.path.dirname(os.path.abspath(guest_package.__file__)), "fixr1_compat.py")
    spec = importlib.util.spec_from_file_location("comfy_fixr1_compat", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["comfy_fixr1_compat"] = module
    spec.loader.exec_module(module)
    module.install()
    asyncio.run(main())
