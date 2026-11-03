"""Test-only guest entry: selected base, production compatibility fix, import seal."""
import asyncio
import hashlib
import json
import os
import random
import sys
from pathlib import Path

sys.path.insert(0, "/tests")
# Deliberately cached before the seal: the pack import hook must still deny it.
import yaml

from comfy_secure_nodes.guest import limits, main
from comfy_secure_nodes.guest.fixr1_compat import install as install_compat
from guest_import_guard import install as install_seal


def install_rng_audit():
    """Test-only observer around the stock adapter; no pack method replacement."""
    from comfy_secure_nodes.guest import adapter
    invoke = adapter.invoke

    async def audited(cls, inputs, method="execute", input_mode="refs", node_id=""):
        if cls.__name__ not in {"D2_XYSeed", "D2_XYSeed2"}:
            return await invoke(cls, inputs, method, input_mode=input_mode, node_id=node_id)
        before = random.getstate()
        record = {"pid": os.getpid(), "class": cls.__name__, "method": method,
                  "inputs": dict(inputs)}
        result = None
        try:
            result = await invoke(cls, inputs, method, input_mode=input_mode, node_id=node_id)
            return result
        except Exception as error:
            record.update(error_type=type(error).__name__, error_message=str(error))
            raise
        finally:
            after = random.getstate()
            record["rng_unchanged"] = before == after
            record["rng_before_sha256"] = hashlib.sha256(repr(before).encode()).hexdigest()
            record["rng_after_sha256"] = hashlib.sha256(repr(after).encode()).hexdigest()
            if method == "validate_inputs":
                record["validation_value"] = result
            record["named_rng_refusal"] = (
                record.get("error_type") == "SecureConversionRefusal"
                or (isinstance(result, str) and "host-global Python RNG" in result))
            receipt = Path(os.environ["TMPDIR"]) / "d2-rng-receipts.jsonl"
            with receipt.open("a") as stream:
                stream.write(json.dumps(record, sort_keys=True) + "\n")
            if record["named_rng_refusal"]:
                assert before == after, "guest refusal consumed Python RNG"

    adapter.invoke = audited


if __name__ == "__main__":
    limits.apply()
    install_compat()
    install_seal()
    install_rng_audit()
    asyncio.run(main())
