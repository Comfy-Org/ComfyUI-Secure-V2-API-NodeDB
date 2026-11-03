"""Test-only guest entry for the gate: the guest main with the host-shipped fixr1_compat applied
first, in the order guest/fixr1_compat.py's own entry uses (limits, install, main).

Production pack guests always run with that patch: sealed guests start through fixr1_compat.py,
snapshot guests install it in snapentry.py. Among other things it publishes a values-mode output
by its declared type (a MASK stays a MASK). The gate has no render root to build a sealed pack
runtime, so the parity test starts its GuestSession with this entry instead.
"""

import asyncio
import importlib.util
import os
import sys

import comfy_secure_nodes.guest as guest_package
from comfy_secure_nodes.guest import limits, main

if __name__ == "__main__":
    limits.apply()
    path = os.path.join(os.path.dirname(os.path.abspath(guest_package.__file__)), "fixr1_compat.py")
    spec = importlib.util.spec_from_file_location("comfy_fixr1_compat", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["comfy_fixr1_compat"] = module
    spec.loader.exec_module(module)
    module.install()
    asyncio.run(main())
