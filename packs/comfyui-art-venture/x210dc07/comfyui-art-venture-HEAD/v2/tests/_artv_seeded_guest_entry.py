"""Test-only guest entry for the gate: the production entry order (limits, fixr1_compat, main), plus an optional
seed for torch's global RNG.

Production pack guests always run with fixr1_compat. For the RNG nodes (RandomInt, RandomFloat), the parity test
seeds both sides' global RNG identically before a call. The harness writes the seed to SEED_FILE before starting the
guest. This entry seeds torch's global generator with it, after the guest's own imports and before the guest main
serves any call. With no seed file present, it is the plain production order.
"""

import asyncio
import importlib.util
import os
import sys

import comfy_secure_nodes.guest as guest_package
from comfy_secure_nodes.guest import limits, main

SEED_FILE = "/tmp/artv-guest-seed"

if __name__ == "__main__":
    limits.apply()
    path = os.path.join(os.path.dirname(os.path.abspath(guest_package.__file__)), "fixr1_compat.py")
    spec = importlib.util.spec_from_file_location("comfy_fixr1_compat", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["comfy_fixr1_compat"] = module
    spec.loader.exec_module(module)
    module.install()
    if os.path.isfile(SEED_FILE):
        import torch

        with open(SEED_FILE, encoding="ascii") as handle:
            torch.manual_seed(int(handle.read().strip()))
    asyncio.run(main())
