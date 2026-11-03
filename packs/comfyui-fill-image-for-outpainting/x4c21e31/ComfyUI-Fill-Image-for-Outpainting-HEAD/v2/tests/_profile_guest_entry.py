"""Test-only guest entry for a dependency-profile test: the guest main with the host-shipped fixr1_compat applied
(as production pack guests run), and with the named modules present ONLY under /deps.

A production guest sees its sealed lock, the pack's runtime base and its declared dependency profile, not Core's
requirements. The gate image has Core's requirements in its site-packages, so before any pack code can import, this
entry makes every path-entry finder outside /deps (the profile's pinned wheels) blind to the named modules. To an
import and to importlib.util.find_spec they are absent there, as in a guest that lacks them. The modules are named in
the NED_PROFILE_MODULES environment variable (comma-separated top-level names): the profile's modules and the modules
the guest bases lack. /deps is on the guest's PYTHONPATH only when the test provides it.
"""

import asyncio
import importlib.machinery
import importlib.util
import os
import sys

import comfy_secure_nodes.guest as guest_package
from comfy_secure_nodes.guest import limits, main

PROFILE_ROOT = "/deps"
MODULES = {name for name in os.environ.get("NED_PROFILE_MODULES", "").split(",") if name}


class ProfileOnlyFileFinder(importlib.machinery.FileFinder):
    def find_spec(self, fullname, target=None):
        if fullname.split(".")[0] in MODULES and not (self.path == PROFILE_ROOT
                                                      or self.path.startswith(PROFILE_ROOT + "/")):
            return None
        return super().find_spec(fullname, target)


def hide_outside_profile():
    loaders = [(importlib.machinery.ExtensionFileLoader, importlib.machinery.EXTENSION_SUFFIXES),
               (importlib.machinery.SourceFileLoader, importlib.machinery.SOURCE_SUFFIXES),
               (importlib.machinery.SourcelessFileLoader, importlib.machinery.BYTECODE_SUFFIXES)]
    already = sorted(name for name in sys.modules if name.split(".")[0] in MODULES)
    if already:
        raise SystemExit(f"profile entry: {already} were imported before the profile could be enforced")
    sys.path_hooks.insert(0, ProfileOnlyFileFinder.path_hook(*loaders))
    sys.path_importer_cache.clear()


if __name__ == "__main__":
    hide_outside_profile()
    limits.apply()
    path = os.path.join(os.path.dirname(os.path.abspath(guest_package.__file__)), "fixr1_compat.py")
    spec = importlib.util.spec_from_file_location("comfy_fixr1_compat", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["comfy_fixr1_compat"] = module
    spec.loader.exec_module(module)
    module.install()
    asyncio.run(main())
