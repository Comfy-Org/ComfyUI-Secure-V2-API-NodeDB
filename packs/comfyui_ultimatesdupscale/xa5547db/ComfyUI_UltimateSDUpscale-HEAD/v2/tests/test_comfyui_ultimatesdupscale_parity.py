"""Tier-1 parity: the original Ultimate SD Upscale pack (V1) vs the V2 port, side by side, CPU only.

Run in the lane gate: run_in_gate.sh <pack root (pristine + v2/)> <this tests dir> <results dir>
test_comfyui_ultimatesdupscale_parity.py

Both sides get the same deterministic stand-ins for the model-owned operations (usdu_fakeops.py): VAE encode/decode,
KSampler/SamplerCustom/guider sampling and the upscale model. Everything else is the pack's own code:
- V1 imports the pristine modules with /core first;
- V2 loads v2/ as a bare namespace package against the guest SDK base, like the production loader.
Per case, the test compares:
- the output IMAGE, exactly (float32 equality);
- the sequence of model-owned calls with their argument and result digests;
- stdout;
- for error cases, the exception type and message.
The comparator negative control must turn red. If the previous V2 (tests/old/_secure_nodes.py, lane-only) is present,
it runs as a second control and is expected to differ, reproducing the live MISMATCH.
"""
from __future__ import annotations

import asyncio
import contextlib
import importlib
import io
import json
import os
import shutil
import subprocess
import sys
import traceback
import types
from pathlib import Path

PACK = Path("/pack")
TESTS = Path(__file__).resolve().parent
RESULTS = Path(os.environ.get("RESULTS", "/results"))
BASE = "/bases/0cd9adec273a703eb3d1c715d83ff1c7d2bb00746330c866c7e3ac644c80ebbb/common-site-packages"


# --------------------------------------------------------------------------------------------------------------------
# Cases
# --------------------------------------------------------------------------------------------------------------------
def _common(**over):
    base = dict(seed=123456789, steps=12, cfg=6.5, sampler_name="dpmpp_2m", scheduler="karras", denoise=0.35,
                mode_type="Linear", tile_width=128, tile_height=128, mask_blur=8, tile_padding=32,
                seam_fix_mode="None", seam_fix_denoise=1.0, seam_fix_width=64, seam_fix_mask_blur=8,
                seam_fix_padding=16, force_uniform_tiles=True, tiled_decode=False, batch_size=1)
    base.update(over)
    return base


CASES = [
    # (case id, node id, image (batch, height, width, seed), node-specific inputs, extra inputs)
    ("basic_model_x2", "UltimateSDUpscale", (1, 136, 200, 1), dict(upscale_by=2.0, model_up=True), _common()),
    ("chess_bandpass_x1_5", "UltimateSDUpscale", (1, 120, 168, 2), dict(upscale_by=1.5, model_up=True),
     _common(mode_type="Chess", seam_fix_mode="Band Pass", seam_fix_width=32, seam_fix_denoise=0.6)),
    ("halftile", "UltimateSDUpscale", (1, 96, 160, 3), dict(upscale_by=2.0, model_up=True),
     _common(seam_fix_mode="Half Tile", seam_fix_mask_blur=4, denoise=0.3)),
    ("halftile_intersections", "UltimateSDUpscale", (1, 96, 128, 4), dict(upscale_by=2.0, model_up=True),
     _common(seam_fix_mode="Half Tile + Intersections", tile_width=96, tile_height=96)),
    ("nonuniform_odd_size", "UltimateSDUpscale", (1, 141, 203, 5), dict(upscale_by=1.25, model_up=True),
     _common(force_uniform_tiles=False, tile_width=96, tile_height=80, tile_padding=16)),
    ("tiled_decode", "UltimateSDUpscale", (1, 96, 96, 6), dict(upscale_by=2.0, model_up=True),
     _common(tiled_decode=True)),
    ("image_batch2", "UltimateSDUpscale", (2, 72, 104, 7), dict(upscale_by=2.0, model_up=True),
     _common(mode_type="Chess", seam_fix_mode="Half Tile")),
    ("tile_batch3_linear", "UltimateSDUpscale", (1, 112, 136, 8), dict(upscale_by=2.0, model_up=True),
     _common(batch_size=3)),
    ("tile_batch2_chess_images2", "UltimateSDUpscale", (2, 64, 96, 9), dict(upscale_by=2.0, model_up=True),
     _common(mode_type="Chess", batch_size=2, seam_fix_mode="Band Pass", seam_fix_width=16)),
    ("model_x3", "UltimateSDUpscale", (1, 48, 64, 10), dict(upscale_by=3.0, model_up=True),
     _common(tile_width=96, tile_height=64, tile_padding=24)),
    ("downscale_0_5", "UltimateSDUpscale", (1, 160, 224, 11), dict(upscale_by=0.5, model_up=True),
     _common(tile_width=64, tile_height=64)),
    ("blur0_pad0_redraw_none_halftile", "UltimateSDUpscale", (1, 96, 96, 12), dict(upscale_by=2.0, model_up=True),
     _common(mask_blur=0, tile_padding=0, mode_type="None", seam_fix_mode="Half Tile", seam_fix_padding=0)),
    ("seed_max", "UltimateSDUpscale", (1, 64, 64, 13), dict(upscale_by=2.0, model_up=True),
     _common(seed=0xffffffffffffffff, denoise=1.0)),
    ("no_upscale", "UltimateSDUpscaleNoUpscale", (1, 136, 200, 14), dict(), _common()),
    ("no_upscale_halftile_int", "UltimateSDUpscaleNoUpscale", (1, 128, 128, 15), dict(),
     _common(seam_fix_mode="Half Tile + Intersections", tile_width=64, tile_height=64)),
    ("custom_lanczos_x1_5", "UltimateSDUpscaleCustomSample", (1, 80, 120, 16), dict(upscale_by=1.5), _common()),
    ("custom_lanczos_x2_batch2", "UltimateSDUpscaleCustomSample", (2, 64, 80, 17), dict(upscale_by=2.0),
     _common(mode_type="Chess")),
    ("custom_sampler_sigmas_model", "UltimateSDUpscaleCustomSample", (1, 80, 120, 18),
     dict(upscale_by=2.0, model_up=True, custom=True), _common()),
    ("custom_sampler_only", "UltimateSDUpscaleCustomSample", (1, 64, 96, 19),
     dict(upscale_by=2.0, custom_sampler_only=True), _common()),
    ("guider", "UltimateSDUpscaleGuider", (1, 96, 120, 20), dict(upscale_by=2.0, model_up=True),
     _common(seam_fix_mode="Band Pass", seam_fix_width=24)),
    ("guider_tile_batch", "UltimateSDUpscaleGuider", (1, 80, 96, 21), dict(upscale_by=2.0, model_up=True),
     _common(batch_size=2)),
    ("error_batch_without_uniform", "UltimateSDUpscale", (1, 64, 64, 22), dict(upscale_by=2.0, model_up=True),
     _common(batch_size=2, force_uniform_tiles=False)),
]

NODE_KEYS = {
    "UltimateSDUpscale": ["seed", "steps", "cfg", "sampler_name", "scheduler", "denoise", "mode_type", "tile_width",
                          "tile_height", "mask_blur", "tile_padding", "seam_fix_mode", "seam_fix_denoise",
                          "seam_fix_width", "seam_fix_mask_blur", "seam_fix_padding", "force_uniform_tiles",
                          "tiled_decode", "batch_size"],
}
GUIDER_DROP = {"steps", "cfg", "sampler_name", "scheduler", "denoise"}


def make_image(batch, height, width, seed):
    import torch
    g = torch.Generator().manual_seed(seed)
    yy = torch.linspace(0, 1, height)[:, None].expand(height, width)
    xx = torch.linspace(0, 1, width)[None, :].expand(height, width)
    base = torch.stack([yy, xx, (yy * xx) ** 0.5], dim=-1)
    noise = torch.rand((batch, height, width, 3), generator=g)
    return (0.55 * base[None] + 0.45 * noise).clamp(0, 1).float().contiguous()


def cond_tensor(value):
    import torch
    return torch.full((1, 4, 8), float(value))


# --------------------------------------------------------------------------------------------------------------------
# Children
# --------------------------------------------------------------------------------------------------------------------
def _force_cpu():
    try:
        from comfy.cli_args import args
        args.cpu = True
    except Exception:  # noqa: BLE001
        pass


class _Anything:
    def __getattr__(self, name):
        return _Anything()

    def __call__(self, *a, **k):
        if len(a) == 1 and callable(a[0]) and not k:
            return a[0]
        return _Anything()


def _copytree(src: Path, dst: Path, skip_v2: bool):
    if dst.exists():
        shutil.rmtree(dst)
    ignore = shutil.ignore_patterns("__pycache__", *(["v2"] if skip_v2 else []))
    shutil.copytree(src, dst, ignore=ignore)


def _run_case(run, case):
    """run(case) -> output tensor; returns a result dict with stdout, calls and the output or error."""
    import numpy as np
    sys.path.insert(0, str(TESTS))
    import usdu_fakeops as fk
    fk.reset()
    buf = io.StringIO()
    res = {}
    try:
        with contextlib.redirect_stdout(buf):
            out = run(case)
        res["output"] = np.ascontiguousarray(out.detach().cpu().numpy())
    except Exception as e:  # noqa: BLE001
        res["error"] = f"{type(e).__name__}: {e}"
        res["traceback"] = traceback.format_exc()[-2500:]
    res["stdout"] = buf.getvalue()
    res["calls"] = [list(c) for c in fk.CALLS]
    res["boundary"] = [repr(b) for b in fk.BOUNDARY]
    res["progress"] = list(fk.PROGRESS)
    res["released"] = len(fk.RELEASED)
    return res


def _save(results: dict, out: Path):
    import numpy as np
    arrays = {k: v.pop("output") for k, v in results.items() if "output" in v}
    np.savez(out.with_suffix(".npz"), **arrays)
    out.with_suffix(".json").write_text(json.dumps(results, indent=1, sort_keys=True, default=str))


def child_v1(out: Path):
    sys.argv = [sys.argv[0]]
    dst = Path("/tmp/usdu-v1") / "pack"
    _copytree(PACK, dst, skip_v2=True)
    sys.path[:0] = [str(dst), "/core"]
    os.chdir("/tmp")
    _force_cpu()
    try:
        import server  # noqa: F401
        if getattr(server.PromptServer, "instance", None) is None:
            server.PromptServer.instance = _Anything()
    except Exception:  # noqa: BLE001
        m = types.ModuleType("server")
        m.PromptServer = type("PromptServer", (), {"instance": _Anything()})
        sys.modules["server"] = m
    notes = []
    # Modules the original imports but whose objects this test replaces anyway; stub only if absent in the image.
    for name, attrs in (("comfy_extras.nodes_upscale_model", ("ImageUpscaleWithModel",)),
                        ("torchvision.transforms", ("GaussianBlur",))):
        try:
            importlib.import_module(name)
        except Exception as e:  # noqa: BLE001
            stub = types.ModuleType(name)
            for a in attrs:
                setattr(stub, a, type(a, (), {}))
            sys.modules[name] = stub
            notes.append(f"stubbed {name}: {e!r}"[:200])
    sys.path.insert(0, str(TESTS))
    import usdu_fakeops as fk
    import usdu_nodes  # noqa: E402  (the pristine node module; pulls in usdu_patch, modules.*, the USDU script)
    import modules.processing as processing
    import modules.upscaler as upscaler
    processing.common_ksampler = fk.v1_common_ksampler
    processing.SamplerCustom = fk.V1SamplerCustom
    processing.VAEEncode = fk.V1VAEEncode
    processing.VAEDecode = fk.V1VAEDecode
    processing.VAEDecodeTiled = fk.V1VAEDecodeTiled
    processing.sample_with_guider = fk.v1_sample_with_guider
    upscaler.ImageUpscaleWithModel = fk.V1ImageUpscaleWithModel

    def run(case):
        cid, node, (b, h, w, s), special, extra = case
        image = make_image(b, h, w, s)
        kw = dict(extra)
        cls = usdu_nodes.NODE_CLASS_MAPPINGS[node]
        if node == "UltimateSDUpscaleGuider":
            for k in GUIDER_DROP:
                kw.pop(k)
            kw.update(image=image, guider=fk.V1Guider(0.25), sampler=fk.V1Tagged(0.5), sigmas=fk.V1Tagged(0.125),
                      vae=object(), upscale_by=special["upscale_by"], upscale_model=fk.V1Tagged(0.75))
            return cls().upscale(**kw)[0]
        kw.update(model=fk.V1Model(0.375), positive=fk.v1_cond(cond_tensor(0.5)),
                  negative=fk.v1_cond(cond_tensor(-0.25)), vae=object())
        if node == "UltimateSDUpscaleNoUpscale":
            kw.update(upscaled_image=image)
            return cls().upscale(**kw)[0]
        kw.update(image=image, upscale_by=special["upscale_by"])
        if node == "UltimateSDUpscale":
            kw.update(upscale_model=fk.V1Tagged(0.75))
            return cls().upscale(**kw)[0]
        # CustomSample
        if special.get("model_up"):
            kw.update(upscale_model=fk.V1Tagged(0.75))
        if special.get("custom"):
            kw.update(custom_sampler=fk.V1Tagged(0.5), custom_sigmas=fk.V1Tagged(0.125))
        if special.get("custom_sampler_only"):
            kw.update(custom_sampler=fk.V1Tagged(0.5))
        return cls().upscale(**kw)[0]

    results = {case[0]: _run_case(run, case) for case in CASES}
    results["_notes"] = {"notes": notes, "calls": [], "stdout": ""}
    _save(results, out)


def _load_v2(module_root: Path, pkg: str, extra_files: dict | None = None):
    sys.path[:0] = [BASE, "/overlay", "/core"]
    os.chdir("/tmp")
    _force_cpu()
    p = types.ModuleType(pkg)
    p.__path__ = [str(module_root)]
    p.__package__ = pkg
    sys.modules[pkg] = p
    return importlib.import_module(f"{pkg}._secure_nodes")


def _v2_runner(port, fk, style: str):
    def run(case):
        cid, node, (b, h, w, s), special, extra = case
        image = fk.Ref("IMAGE", make_image(b, h, w, s))
        kw = dict(extra)
        handler = {"UltimateSDUpscale": "_upscale", "UltimateSDUpscaleNoUpscale": "_no_upscale",
                   "UltimateSDUpscaleCustomSample": "_custom", "UltimateSDUpscaleGuider": "_guider"}[node]
        if node == "UltimateSDUpscaleGuider":
            for k in GUIDER_DROP:
                kw.pop(k)
            kw.update(image=image, guider=fk.V2Guider(0.25), sampler=fk.Ref("SAMPLER", tag=0.5),
                      sigmas=fk.Ref("SIGMAS", tag=0.125), vae=fk.V2Vae(), upscale_by=special["upscale_by"],
                      upscale_model=fk.V2UpscaleModel(0.75))
        else:
            kw.update(model=fk.V2Model(0.375), positive=fk.V2Cond(cond_tensor(0.5)),
                      negative=fk.V2Cond(cond_tensor(-0.25)), vae=fk.V2Vae())
            if node == "UltimateSDUpscaleNoUpscale":
                kw.update(upscaled_image=image)
            else:
                kw.update(image=image, upscale_by=special["upscale_by"])
                if node == "UltimateSDUpscale" or special.get("model_up"):
                    kw.update(upscale_model=fk.V2UpscaleModel(0.75))
                if special.get("custom"):
                    kw.update(custom_sampler=fk.Ref("SAMPLER", tag=0.5), custom_sigmas=fk.Ref("SIGMAS", tag=0.125))
                if special.get("custom_sampler_only"):
                    kw.update(custom_sampler=fk.Ref("SAMPLER", tag=0.5))
        result = asyncio.run(getattr(port, handler)(**kw))
        ref = result[0]
        return ref.value
    return run


def child_v2(out: Path):
    sys.argv = [sys.argv[0]]
    dst = Path("/tmp/usdu-v2/v2")
    _copytree(PACK / "v2", dst, skip_v2=False)
    port = _load_v2(dst, "usdu_v2")
    sys.path.insert(0, str(TESTS))
    import usdu_fakeops as fk
    port._image_ref = fk.image_ref
    port._ctx = lambda: fk.CTX
    run = _v2_runner(port, fk, "port")
    results = {case[0]: _run_case(run, case) for case in CASES}
    _save(results, out)


def child_old(out: Path):
    """The previous V2 (corpus main) under the same fakes: expected to differ from V1."""
    sys.argv = [sys.argv[0]]
    dst = Path("/tmp/usdu-old/v2")
    _copytree(PACK / "v2", dst, skip_v2=False)
    shutil.copyfile(TESTS / "old" / "_secure_nodes.py", dst / "_secure_nodes.py")
    sys.path.insert(0, str(TESTS))
    import usdu_fakeops as fk
    port = _load_v2(dst, "usdu_v2_old")

    class _OldImageRef:
        @staticmethod
        async def _from_raw(value):
            return await fk.image_ref(value)

    port.sdk = types.SimpleNamespace(ImageRef=_OldImageRef, ctx=lambda: fk.CTX)
    run = _v2_runner(port, fk, "old")
    results = {case[0]: _run_case(run, case) for case in CASES if case[0] in (
        "basic_model_x2", "halftile", "no_upscale", "custom_lanczos_x1_5")}
    _save(results, out)


# --------------------------------------------------------------------------------------------------------------------
# Parent
# --------------------------------------------------------------------------------------------------------------------
def _spawn(kind: str, out: Path):
    env = dict(os.environ)
    proc = subprocess.run([sys.executable, "-I", str(Path(__file__).resolve()), kind, str(out)], capture_output=True,
                          text=True, env=env, timeout=3000)
    (RESULTS / f"{kind}.stderr.txt").write_text(proc.stderr[-200000:])
    (RESULTS / f"{kind}.stdout.txt").write_text(proc.stdout[-200000:])
    if proc.returncode != 0:
        raise RuntimeError(f"{kind} child failed rc={proc.returncode}: {proc.stderr[-3000:]}")
    import numpy as np
    meta = json.loads(out.with_suffix(".json").read_text())
    with np.load(out.with_suffix(".npz"), allow_pickle=False) as z:
        for k in z.files:
            meta[k]["output"] = z[k]
    return meta


def _compare(a: dict, b: dict) -> list[str]:
    import numpy as np
    diffs = []
    if ("error" in a) != ("error" in b):
        diffs.append(f"error presence: v1={a.get('error')!r} v2={b.get('error')!r}")
    elif "error" in a:
        if a["error"] != b["error"]:
            diffs.append(f"error text: v1={a['error']!r} v2={b['error']!r}")
    else:
        x, y = a["output"], b["output"]
        if x.shape != y.shape or x.dtype != y.dtype:
            diffs.append(f"output shape/dtype: v1={x.shape}/{x.dtype} v2={y.shape}/{y.dtype}")
        elif not np.array_equal(x, y):
            d = np.abs(x.astype(np.float64) - y.astype(np.float64))
            mse = float((d * 255) ** 2 .mean()) if False else float(((d * 255) ** 2).mean())
            psnr = float("inf") if mse == 0 else 10 * np.log10(255.0 ** 2 / mse)
            diffs.append(f"output values: max|d|*255={float(d.max()) * 255:.3f}, differing={int((d > 0).sum())}"
                         f"/{d.size}, psnr={psnr:.2f} dB")
    if a["calls"] != b["calls"]:
        n = next((i for i, (p, q) in enumerate(zip(a["calls"], b["calls"])) if p != q),
                 min(len(a["calls"]), len(b["calls"])))
        diffs.append(f"model-call sequence differs at #{n} (v1 {len(a['calls'])} calls, v2 {len(b['calls'])}): "
                     f"v1={a['calls'][n] if n < len(a['calls']) else None} "
                     f"v2={b['calls'][n] if n < len(b['calls']) else None}")
    if a["stdout"] != b["stdout"]:
        diffs.append(f"stdout differs: v1={a['stdout'][-300:]!r} v2={b['stdout'][-300:]!r}")
    return diffs


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    tmp = Path("/tmp/usdu-parity")
    tmp.mkdir(parents=True, exist_ok=True)
    v1 = _spawn("child_v1", tmp / "v1")
    v2 = _spawn("child_v2", tmp / "v2")
    report = {"cases": {}, "exact": 0, "failed": 0, "checks": 0}
    for case in CASES:
        cid = case[0]
        a, b = v1[cid], v2[cid]
        diffs = _compare(a, b)
        verdict = "EXACT" if not diffs else "MISMATCH"
        if not diffs and "error" in a:
            verdict = "ERROR-PARITY"
        report["cases"][cid] = {
            "node": case[1], "verdict": verdict, "diffs": diffs,
            "v1_error": a.get("error"), "v2_error": b.get("error"),
            "v1_traceback": a.get("traceback"), "v2_traceback": b.get("traceback"),
            "model_calls": len(a["calls"]), "output_shape": list(a["output"].shape) if "output" in a else None,
            "v2_progress_last": b["progress"][-1] if b["progress"] else None, "v2_refs_released": b["released"],
            "v2_boundary_sample": b["boundary"][:3],
        }
        report["checks"] += 4
        report["exact" if not diffs else "failed"] += 1
    # Negative control 1: the comparator must see a one-level change in one value.
    import numpy as np
    ref = v2["basic_model_x2"]
    flipped = dict(ref, output=ref["output"].copy())
    flipped["output"].flat[12345 % flipped["output"].size] += 1.0 / 255
    report["negative_control_comparator"] = {"diffs": _compare(v1["basic_model_x2"], flipped)}
    report["negative_control_comparator"]["red"] = bool(report["negative_control_comparator"]["diffs"])
    # Negative control 2 (lane-only): the previous V2 under the same fakes.
    if (TESTS / "old" / "_secure_nodes.py").is_file():
        old = _spawn("child_old", tmp / "old")
        report["previous_v2_control"] = {cid: {"diffs": _compare(v1[cid], old[cid]), "error": old[cid].get("error")}
                                         for cid in old}
        report["previous_v2_control_red"] = all(bool(x["diffs"]) for x in report["previous_v2_control"].values())
    report["notes"] = v1.get("_notes", {}).get("notes")
    report["ok"] = report["failed"] == 0 and report["negative_control_comparator"]["red"]
    (RESULTS / "parity.json").write_text(json.dumps(report, indent=1, sort_keys=True, default=str))
    print(json.dumps({k: report[k] for k in ("ok", "exact", "failed", "checks")}))
    for cid, r in report["cases"].items():
        print(f"{r['verdict']:13s} {cid:36s} {r['node']:30s} calls={r['model_calls']} {r['diffs'][:1]}")
    print("negative control (comparator) red:", report["negative_control_comparator"]["red"])
    if "previous_v2_control" in report:
        for cid, r in report["previous_v2_control"].items():
            print(f"previous V2 {cid}: {r['diffs'][:1] or 'NO DIFF'} {r['error'] or ''}")
    sys.exit(0 if report["ok"] else 1)


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] in ("child_v1", "child_v2", "child_old"):
        globals()[sys.argv[1]](Path(sys.argv[2]))
    else:
        main()
