"""Gate-only selected-base entry with a lock-derived guard active on every call."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import sys

import comfy_secure_nodes.guest as guest_package
from comfy_secure_nodes.guest import limits, main

sys.path.insert(0, "/tests")
import guest_lock

if __name__ == "__main__":
    limits.apply()
    compat = Path(guest_package.__file__).parent / "fixr1_compat.py"
    spec = importlib.util.spec_from_file_location("essentials_selected_host_entry", compat)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.install()
    from comfy_api.latest import sdk
    expected_api = Path(os.environ["COMFY_GUEST_API_ROOT"]).resolve()
    assert Path(sdk.__file__).resolve().is_relative_to(expected_api)
    def denied(row):
        row["pid"] = os.getpid()
        with Path(os.environ["ESSENTIALS_GUARD_DENIALS"]).open("a") as stream:
            stream.write(json.dumps(row, sort_keys=True) + "\n")
    metadata, active, restore = guest_lock.install(
        os.environ["ESSENTIALS_GUARD_ROOT"], os.environ["ESSENTIALS_GUARD_NAMESPACE"], denied
    )
    Path(os.environ["ESSENTIALS_GUARD_REPORT"]).write_text(json.dumps({
        **metadata, "pid": os.getpid(), "sdk_file": sdk.__file__,
        "sdk_sha256": __import__("hashlib").sha256(Path(sdk.__file__).read_bytes()).hexdigest(),
        "root": os.environ["ESSENTIALS_GUARD_ROOT"],
        "entry": "selected native limits + fixr1_compat; then lock finder and builtins guard; then guest.main",
        "profile_dependencies": [], "guard_active": True,
    }, indent=2, sort_keys=True) + "\n")
    active()
    asyncio.run(main())
