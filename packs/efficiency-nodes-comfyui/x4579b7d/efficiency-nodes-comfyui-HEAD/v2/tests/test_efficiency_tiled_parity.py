"""Tier-1 parity for the Tiled Upscaler Script's sampling: the original (V1) against the V2 port, side by side, CPU only.

Run in the lane gate: run_in_gate.sh <pack root (pristine + v2/)> <this tests dir> <results dir>
test_efficiency_tiled_parity.py

Both sides run the same real ComfyUI scheduling code with the same stand-in diffusion step and VAE
(eff_tiled_fakeops.py). Everything else is the pack's own code:
- V1 imports the pristine py/bnk_tiled_samplers.py (and its py/bnk_tiling.py) with /core first, and calls
  TiledKSampler().sample as KSampler (Efficient) does (efficiency_nodes.py:670-673). The pack's AYS scheduler patch is
  applied around it, as inside KSampler (Efficient) (efficiency_nodes.py:478-494).
- V2 loads v2/ as a bare namespace package against the guest SDK base, like the production loader, and calls
  _sample_tiled.
The "post_*" cases cover the whole tile block. V1 runs efficiency_nodes.py:651-673 as written there, with core's real
VAEDecode, VAEDecodeTiled, ImageScaleBy, VAEEncode and VAEEncodeTiled nodes. V2 runs _post_scripts.
Per case, the test compares:
- the output latent, exactly (float32 equality);
- the sequence of diffusion/VAE calls with argument and result digests;
- for error cases, the exception type and message.
Each case has an expected verdict: EXACT, ERROR-PARITY (both raise the same error), or REFUSED-AS-DESIGNED (V1 runs,
V2 raises its named refusal). The comparator negative control must turn red. If the previous V2 module is present
(tests/old/_secure_nodes.py, lane-only), it runs as a second control and must differ.
"""
from __future__ import annotations

import asyncio
import importlib
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
def _case(cid, expect, *, shape=(1, 4, 48, 72), strategy="simple", tile_size=256, steps=2, denoise=0.35,
          seed=20261102, cfg=1.0, sampler_name="euler", scheduler="normal", family="sd1", batch_index=None,
          noise_mask=False, area=False, post=None, refusal=None):
    return dict(cid=cid, expect=expect, shape=shape, strategy=strategy, tile_size=tile_size, steps=steps,
                denoise=denoise, seed=seed, cfg=cfg, sampler_name=sampler_name, scheduler=scheduler, family=family,
                batch_index=batch_index, noise_mask=noise_mask, area=area, post=post, refusal=refusal)


CASES = [
    _case("simple_low_denoise", "EXACT"),
    _case("simple_multistep_karras", "EXACT", shape=(1, 4, 40, 56), steps=6, denoise=0.5, cfg=6.5,
          sampler_name="dpmpp_2m", scheduler="karras", seed=7),
    _case("simple_denoise_1", "EXACT", shape=(1, 4, 32, 40), steps=3, denoise=1.0, seed=11),
    _case("simple_single_tile", "EXACT", shape=(1, 4, 24, 24), steps=4, denoise=0.6, seed=12),
    _case("random", "EXACT", strategy="random", steps=4, denoise=0.5, seed=21),
    _case("random_strict", "EXACT", strategy="random strict", steps=4, denoise=0.5, seed=22),
    _case("random_strict_odd_size", "EXACT", shape=(1, 4, 37, 53), strategy="random strict", steps=3, denoise=0.45,
          seed=23, tile_size=320),
    _case("random_batch2_index", "EXACT", shape=(2, 4, 32, 48), strategy="random", steps=3, denoise=0.5, seed=24,
          batch_index=[3, 1]),
    _case("simple_dpm2_discard_penultimate", "EXACT", steps=5, denoise=0.5, sampler_name="dpm_2", seed=25),
    _case("simple_euler_ancestral_seed_max", "EXACT", steps=3, denoise=0.5, sampler_name="euler_ancestral",
          seed=0xffffffffffffffff),
    _case("simple_sdxl", "EXACT", family="sdxl", steps=4, denoise=0.5, seed=26),
    _case("random_ays_sd1", "EXACT", strategy="random", scheduler="AYS SD1", steps=4, denoise=0.5, seed=27),
    _case("padded", "EXACT", strategy="padded", steps=3, denoise=0.5, seed=32),
    _case("padded_odd_size", "EXACT", shape=(1, 4, 37, 53), strategy="padded", steps=2, denoise=0.4, seed=36,
          tile_size=320),
    # Batch 2 with a boundary tile: the original's mask_at_boundary builds a batch-1 mask and fails.
    _case("padded_batch2_index_error", "ERROR-PARITY", shape=(2, 4, 32, 48), strategy="padded", steps=2, denoise=0.4,
          seed=40, batch_index=[0, 2]),
    _case("padded_flux_family", "EXACT", strategy="padded", family="flux", steps=2, denoise=0.5, seed=37),
    _case("padded_ays_sdxl", "EXACT", strategy="padded", family="sdxl", scheduler="AYS SDXL", steps=3, denoise=0.6,
          seed=38),
    _case("noise_mask_error", "ERROR-PARITY", noise_mask=True, seed=31),
    _case("padded_noise_mask_error", "ERROR-PARITY", strategy="padded", noise_mask=True, seed=39),
    _case("area_cond_refused", "REFUSED-AS-DESIGNED", area=True, seed=33,
          refusal="the original slices spatial conditioning per tile"),
    _case("flux_family_refused", "REFUSED-AS-DESIGNED", family="flux", seed=34, refusal="for flux latents"),
    _case("ays_dpm2_refused", "REFUSED-AS-DESIGNED", scheduler="AYS SD1", sampler_name="dpm_2", steps=3, denoise=0.5,
          seed=35, refusal="drops the schedule's penultimate sigma"),
    _case("post_simple_block", "EXACT", shape=(1, 4, 32, 48), steps=2, denoise=0.35, seed=41,
          post=dict(upscale_by=1.5, vae_decode="true")),
    _case("post_random_upscale2", "EXACT", shape=(1, 4, 24, 32), strategy="random", steps=3, denoise=0.5, seed=42,
          post=dict(upscale_by=2.0, vae_decode="true")),
    _case("post_padded_block", "EXACT", shape=(1, 4, 24, 40), strategy="padded", steps=2, denoise=0.5, seed=44,
          post=dict(upscale_by=1.5, vae_decode="true")),
    _case("post_tiled_vae_error", "ERROR-PARITY", shape=(1, 4, 32, 48), seed=43,
          post=dict(upscale_by=1.5, vae_decode="true (tiled)")),
]


def make_latent(shape, seed):
    import torch
    g = torch.Generator().manual_seed(int(seed) % (1 << 63))
    return (torch.randn(shape, generator=g) * 0.8).contiguous()


def make_cond(value, area=False):
    import torch
    extra = {"area": (16, 24, 8, 16), "strength": 1.0} if area else {}
    return [[torch.full((1, 4, 8), float(value)), {"pooled_output": torch.full((1, 8), float(value) / 2), **extra}]]


def latent_dict(case):
    import torch
    value = {"samples": make_latent(case["shape"], case["seed"])}
    if case["batch_index"] is not None:
        value["batch_index"] = list(case["batch_index"])
    if case["noise_mask"]:
        b, _c, h, w = case["shape"]
        value["noise_mask"] = torch.linspace(0, 1, h * w).reshape(1, 1, h, w).repeat(b, 1, 1, 1)
    return value


# --------------------------------------------------------------------------------------------------------------------
# Children
# --------------------------------------------------------------------------------------------------------------------
def _force_cpu():
    try:
        from comfy.cli_args import args
        args.cpu = True
    except Exception:  # noqa: BLE001
        pass


def _copytree(src: Path, dst: Path, skip_v2: bool):
    if dst.exists():
        shutil.rmtree(dst)
    ignore = shutil.ignore_patterns("__pycache__", *(["v2"] if skip_v2 else []))
    shutil.copytree(src, dst, ignore=ignore)


def _run_case(run, case):
    import numpy as np
    sys.path.insert(0, str(TESTS))
    import eff_tiled_fakeops as fk
    fk.reset()
    res = {}
    try:
        out = run(case)
        res["output"] = np.ascontiguousarray(out.detach().cpu().numpy())
    except Exception as e:  # noqa: BLE001
        res["error"] = f"{type(e).__name__}: {e}"
        res["traceback"] = traceback.format_exc()[-2500:]
    res["calls"] = [list(c) for c in fk.CALLS]
    res["boundary"] = [repr(b) for b in fk.BOUNDARY]
    return res


def _save(results: dict, out: Path):
    import numpy as np
    arrays = {k: v.pop("output") for k, v in results.items() if "output" in v}
    np.savez(out.with_suffix(".npz"), **arrays)
    out.with_suffix(".json").write_text(json.dumps(results, indent=1, sort_keys=True, default=str))


def child_v1(out: Path):
    sys.argv = [sys.argv[0]]
    dst = Path("/tmp/eff-v1") / "pack"
    _copytree(PACK, dst, skip_v2=True)
    sys.path[:0] = ["/core"]
    os.chdir("/tmp")
    _force_cpu()
    sys.path.insert(0, str(TESTS))
    import comfy.model_patcher
    import comfy.samplers
    import eff_tiled_fakeops as fk
    import nodes
    from comfy_extras.nodes_align_your_steps import AlignYourStepsScheduler
    fk.install_core_fakes()
    comfy.model_patcher.ModelPatcher = fk.FakePatcher
    # The pristine pack modules, imported as a package under a private name (the pack's py/ has no __init__.py).
    pkg = types.ModuleType("eff_py")
    pkg.__path__ = [str(dst / "py")]
    sys.modules["eff_py"] = pkg
    bnk = importlib.import_module("eff_py.bnk_tiled_samplers")

    # efficiency_nodes.py:478-494, as KSampler (Efficient) wraps all of its sampling: AYS/GITS scheduler names.
    original_calculation = comfy.samplers.calculate_sigmas

    def calculate_sigmas(model_sampling, scheduler_name: str, steps):
        if scheduler_name.startswith("AYS"):
            return AlignYourStepsScheduler().get_sigmas(scheduler_name.split(" ")[1], steps, denoise=1.0)[0]
        return original_calculation(model_sampling, scheduler_name, steps)

    comfy.samplers.KSampler.SCHEDULERS = comfy.samplers.KSampler.SCHEDULERS + ["AYS SD1", "AYS SDXL", "AYS SVD", "GITS"]
    comfy.samplers.calculate_sigmas = calculate_sigmas

    def tiled(case, latent):
        model = fk.FakePatcher(fk.FakeBaseModel(case["family"], 0.375))
        return bnk.TiledKSampler().sample(
            model, case["seed"], case["tile_size"], case["tile_size"], case["strategy"], case["steps"], case["cfg"],
            case["sampler_name"], case["scheduler"], make_cond(0.5, case["area"]), make_cond(-0.25), latent,
            denoise=case["denoise"])[0]

    def run(case):
        latent = latent_dict(case)
        post = case["post"]
        if post is None:
            return tiled(case, latent)["samples"]
        # efficiency_nodes.py:651-673 (tile block of KSampler (Efficient)), with vae_decode_latent / vae_encode_image
        # as defined at efficiency_nodes.py:466-470.
        vae = fk.V1Vae()
        vae_decode = post["vae_decode"]
        images = (nodes.VAEDecodeTiled().decode(vae, latent, 320)[0] if "tiled" in vae_decode
                  else nodes.VAEDecode().decode(vae, latent)[0])
        upscaled_image = nodes.ImageScaleBy().upscale(images, "nearest-exact", post["upscale_by"])[0]
        upscaled_latent = (nodes.VAEEncodeTiled().encode(vae, upscaled_image, 320)[0] if "tiled" in vae_decode
                           else nodes.VAEEncode().encode(vae, upscaled_image)[0])
        return tiled(case, upscaled_latent)["samples"]

    results = {case["cid"]: _run_case(run, case) for case in CASES}
    _save(results, out)


def _load_v2(module_root: Path, pkg: str):
    sys.path[:0] = [BASE, "/overlay", "/core"]
    os.chdir("/tmp")
    _force_cpu()
    p = types.ModuleType(pkg)
    p.__path__ = [str(module_root)]
    p.__package__ = pkg
    sys.modules[pkg] = p
    return importlib.import_module(f"{pkg}._secure_nodes")


def _v2_runner(port, fk):
    def run(case):
        model = fk.ModelRef(fk.FakePatcher(fk.FakeBaseModel(case["family"], 0.375)))
        positive, negative = fk.CondRef(make_cond(0.5, case["area"])), fk.CondRef(make_cond(-0.25))
        latent = fk.LatentRef(latent_dict(case))
        post = case["post"]
        if post is None:
            result = asyncio.run(port._sample_tiled(
                latent, model=model, positive=positive, negative=negative, seed=case["seed"], steps=case["steps"],
                cfg=case["cfg"], sampler_name=case["sampler_name"], scheduler=case["scheduler"],
                denoise=case["denoise"], tile_size=case["tile_size"], strategy=case["strategy"]))
            return result._value["samples"]
        # The Tiled Upscaler Script node's own SCRIPT entry, as the V2 node emits it.
        script = asyncio.run(port._tile_script(
            post["upscale_by"], case["tile_size"], case["strategy"], case["steps"], case["seed"], case["denoise"],
            False, "none", 1.0, script=None))[0]
        result_latent, image = asyncio.run(port._post_scripts(
            latent, None, model=model, positive=positive, negative=negative, vae=fk.V2Vae(), cfg=case["cfg"],
            sampler_name=case["sampler_name"], scheduler=case["scheduler"], seed=case["seed"],
            vae_decode=post["vae_decode"], script=script))
        assert image is None
        return result_latent._value["samples"]
    return run


def _patch_port(port, fk):
    port.sdk = types.SimpleNamespace(LatentRef=fk.LatentRef, TensorRef=fk.TensorRef, ImageRef=fk.ImageRef,
                                     ctx=lambda: fk.CTX)
    port._ctx = lambda: fk.CTX


def child_v2(out: Path):
    sys.argv = [sys.argv[0]]
    dst = Path("/tmp/eff-v2/v2")
    _copytree(PACK / "v2", dst, skip_v2=False)
    port = _load_v2(dst, "eff_v2")
    sys.path.insert(0, str(TESTS))
    import comfy.samplers  # noqa: F401
    import eff_tiled_fakeops as fk
    fk.install_core_fakes()
    _patch_port(port, fk)
    results = {case["cid"]: _run_case(_v2_runner(port, fk), case) for case in CASES}
    _save(results, out)


def child_old(out: Path):
    """The previous V2 (corpus main) under the same fakes: expected to differ from V1."""
    sys.argv = [sys.argv[0]]
    dst = Path("/tmp/eff-old/v2")
    _copytree(PACK / "v2", dst, skip_v2=False)
    shutil.copyfile(TESTS / "old" / "_secure_nodes.py", dst / "_secure_nodes.py")
    port = _load_v2(dst, "eff_v2_old")
    sys.path.insert(0, str(TESTS))
    import eff_tiled_fakeops as fk
    fk.install_core_fakes()
    _patch_port(port, fk)
    results = {case["cid"]: _run_case(_v2_runner(port, fk), case) for case in CASES}
    _save(results, out)


# --------------------------------------------------------------------------------------------------------------------
# Parent
# --------------------------------------------------------------------------------------------------------------------
def _spawn(kind: str, out: Path):
    proc = subprocess.run([sys.executable, "-I", str(Path(__file__).resolve()), kind, str(out)], capture_output=True,
                          text=True, env=dict(os.environ), timeout=3000)
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
            diffs.append(f"output values: max|d|={float(d.max()):.3g}, differing={int((d > 0).sum())}/{d.size}")
    if a["calls"] != b["calls"]:
        n = next((i for i, (p, q) in enumerate(zip(a["calls"], b["calls"])) if p != q),
                 min(len(a["calls"]), len(b["calls"])))
        diffs.append(f"call sequence differs at #{n} (v1 {len(a['calls'])} calls, v2 {len(b['calls'])}): "
                     f"v1={a['calls'][n] if n < len(a['calls']) else None} "
                     f"v2={b['calls'][n] if n < len(b['calls']) else None}")
    return diffs


def _verdict(case, a, b):
    diffs = _compare(a, b)
    if case["expect"] == "REFUSED-AS-DESIGNED":
        ok = ("error" not in a and "error" in b and b["error"].startswith("RuntimeError: Tiled Upscaler Script is not "
                                                                         "available in this secure build")
              and case["refusal"] in b["error"])
        return ("REFUSED-AS-DESIGNED" if ok else "UNEXPECTED"), diffs
    if diffs:
        return "MISMATCH", diffs
    return ("ERROR-PARITY" if "error" in a else "EXACT"), diffs


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    tmp = Path("/tmp/eff-tiled-parity")
    tmp.mkdir(parents=True, exist_ok=True)
    v1 = _spawn("child_v1", tmp / "v1")
    v2 = _spawn("child_v2", tmp / "v2")
    report = {"cases": {}, "met": 0, "failed": 0}
    for case in CASES:
        cid = case["cid"]
        a, b = v1[cid], v2[cid]
        verdict, diffs = _verdict(case, a, b)
        met = verdict == case["expect"]
        report["cases"][cid] = {
            "expect": case["expect"], "verdict": verdict, "met": met, "diffs": diffs,
            "v1_error": a.get("error"), "v2_error": b.get("error"),
            "v1_traceback": a.get("traceback"), "v2_traceback": b.get("traceback"),
            "calls": len(a["calls"]), "output_shape": list(a["output"].shape) if "output" in a else None,
            "v2_boundary_sample": b["boundary"][:4],
        }
        report["met" if met else "failed"] += 1
    # Negative control 1: the comparator must see a change of one value by one float32 ulp.
    import numpy as np
    ref = v2["simple_low_denoise"]
    flipped = dict(ref, output=ref["output"].copy())
    flat = flipped["output"].reshape(-1)
    flat[12345 % flat.size] = np.nextafter(flat[12345 % flat.size], np.float32(np.inf))
    report["negative_control_comparator"] = {"diffs": _compare(v1["simple_low_denoise"], flipped)}
    report["negative_control_comparator"]["red"] = bool(report["negative_control_comparator"]["diffs"])
    # Negative control 2 (lane-only): the previous V2 under the same fakes.
    if (TESTS / "old" / "_secure_nodes.py").is_file():
        old = _spawn("child_old", tmp / "old")
        report["previous_v2_control"] = {cid: {"diffs": _compare(v1[cid], old[cid]), "error": old[cid].get("error")}
                                         for cid in old}
        report["previous_v2_control_red"] = all(bool(x["diffs"]) for x in report["previous_v2_control"].values())
    report["ok"] = report["failed"] == 0 and report["negative_control_comparator"]["red"]
    (RESULTS / "tiled-parity.json").write_text(json.dumps(report, indent=1, sort_keys=True, default=str))
    print(json.dumps({k: report[k] for k in ("ok", "met", "failed")}))
    for cid, r in report["cases"].items():
        print(f"{r['verdict']:20s} expect={r['expect']:20s} {cid:34s} calls={r['calls']} "
              f"{(r['diffs'][:1] or [r['v2_error'] or ''])[0][:160]}")
    print("negative control (comparator) red:", report["negative_control_comparator"]["red"])
    if "previous_v2_control" in report:
        for cid, r in report["previous_v2_control"].items():
            print(f"previous V2 {cid:34s} {(r['diffs'][:1] or ['NO DIFF'])[0][:150]}")
    sys.exit(0 if report["ok"] else 1)


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] in ("child_v1", "child_v2", "child_old"):
        globals()[sys.argv[1]](Path(sys.argv[2]))
    else:
        main()
