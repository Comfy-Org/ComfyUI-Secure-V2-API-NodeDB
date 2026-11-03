"""Actual Core VAE parity through a guest, including RGBA view strides.

The VAE uses existing Core AutoencoderKL code and seeded synthetic parameters.
No model is downloaded. A test-only delegating recorder logs the input delivered
to Core encode/encode_tiled and asserts that the operation stays in the host.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import signal
import sys
import traceback
from pathlib import Path

sys.path[:0] = ["/core", "/overlay", "/tests"]
import test_d2_parity as parity
import test_d2_guest as guest_test
import _tiny_sd
import torch

RESULTS = Path("/results")
REPORT = {"environment": "gate, B13 sources 38f28c98; core 6257422b; guest base 0cd9adec",
          "fixture": "Core AutoencoderKL with seeded synthetic parameters",
          "cases": [], "failure_count": 0}


class CoreVAERecorder:
    def __init__(self, vae):
        self.vae = vae
        self.calls = []

    def note(self, method, pixels, kwargs):
        self.calls.append({
            "method": method, "host_pid": os.getpid(), "shape": list(pixels.shape),
            "dtype": str(pixels.dtype), "stride": list(pixels.stride()),
            "pixels_sha256": hashlib.sha256(
                pixels.contiguous().reshape(-1).view(torch.uint8).numpy().tobytes()).hexdigest(),
            "kwargs": kwargs,
        })

    def encode(self, pixels):
        self.note("encode", pixels, {})
        return self.vae.encode(pixels)

    def encode_tiled(self, pixels, **kwargs):
        self.note("encode_tiled", pixels, dict(kwargs))
        return self.vae.encode_tiled(pixels, **kwargs)

    def decode(self, samples):
        return self.vae.decode(samples)


async def main():
    RESULTS.mkdir(exist_ok=True)
    new = parity.load_v2()
    old = parity.source_classes(new)["D2 Image Resize"]
    cls = new.NODE_CLASS_MAPPINGS["D2 Image Resize"]
    vae = _tiny_sd.build_vae()
    digest = _tiny_sd.state_dict_digest(vae)
    REPORT["synthetic_state_sha256"] = digest
    session = await guest_test.SelectedGuest("d2-core-vae-0cd9", guest_runtime_root=parity.V2).start()
    print("PLAN: 4 actual Core tiny-VAE guest differential cases, RGB/RGBA x normal/tiled", flush=True)
    try:
        for channels in [3, 4]:
            for tiled in [False, True]:
                original_recorder, guest_recorder = CoreVAERecorder(vae), CoreVAERecorder(vae)
                fields = parity.defaults(cls) | {
                    "image": parity.tensor((1, 32, 40, channels)), "mode": "resize",
                    "resize_width": 40, "resize_height": 32, "round_method": "None",
                    "vae": original_recorder, "use_tiled_vae": tiled,
                }
                before = fields["image"].clone()
                # Comfy's normal execution context enables inference mode;
                # Core's tiled path mutates tensors created under that mode.
                with torch.inference_mode():
                    torch.manual_seed(parity.SEED)
                    expected = parity.source_call(old, fields)
                    torch.manual_seed(parity.SEED)
                    actual = await guest_test.guest_call(
                        session, cls, "D2 Image Resize", fields | {"vae": guest_recorder})
                record = {"channels": channels, "tiled": tiled, "verdict": "EXACT",
                          "original_core_inputs": original_recorder.calls,
                          "guest_core_inputs": guest_recorder.calls}
                try:
                    parity.equal(guest_test.values_output(expected), guest_test.values_output(actual))
                    assert guest_test.ui_output(expected) == guest_test.ui_output(actual)
                    assert len(original_recorder.calls) == len(guest_recorder.calls) == 1
                    assert original_recorder.calls == guest_recorder.calls
                    assert guest_recorder.calls[0]["stride"][-2] == channels
                    assert guest_recorder.calls[0]["shape"][-1] == 3
                    assert guest_recorder.calls[0]["host_pid"] == os.getpid() != session.last_guest_pid
                    parity.equal(before, fields["image"])
                except Exception as error:
                    record.update(verdict="MISMATCH", detail=str(error))
                    REPORT["failure_count"] += 1
                REPORT["cases"].append(record)
                print(f"{record['verdict']} channels={channels} tiled={tiled}", flush=True)
        assert _tiny_sd.state_dict_digest(vae) == digest, "VAE parameters were mutated"
        REPORT["guest_pid"] = session.last_guest_pid
        REPORT["host_pid"] = os.getpid()
        REPORT["guest_import_seal"] = json.loads(
            (Path(session._guest_tmp) / "d2-import-seal.json").read_text())
    finally:
        await session.kill()
    (RESULTS / "core-vae-parity.json").write_text(json.dumps(REPORT, indent=2, sort_keys=True) + "\n")
    assert REPORT["failure_count"] == 0, f"{REPORT['failure_count']} actual Core VAE mismatches"
    print("DONE: 4 actual Core VAE cases EXACT; host-owned input/view strides preserved", flush=True)


if __name__ == "__main__":
    def timed_out(signum, frame):
        raise TimeoutError("finite Core VAE gate budget exceeded: 240 seconds")
    signal.signal(signal.SIGALRM, timed_out)
    signal.alarm(240)
    try:
        asyncio.run(main())
    except BaseException as error:
        RESULTS.mkdir(exist_ok=True)
        (RESULTS / "core-vae-failure.json").write_text(json.dumps({
            "error_type": type(error).__name__, "message": str(error),
            "traceback": traceback.format_exc(), "partial_report": REPORT,
        }, indent=2, sort_keys=True) + "\n")
        raise
    finally:
        signal.alarm(0)
