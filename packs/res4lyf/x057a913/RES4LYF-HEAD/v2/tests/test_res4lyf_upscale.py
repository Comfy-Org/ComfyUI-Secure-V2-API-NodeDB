"""Tier-1 parity for RES4LYF's LatentUpscaleWithVAE: the ORIGINAL in-process vs V2 in a real guest (gate only).

* Original side: the pristine package imported in this process (labelled import stubs as in test_res4lyf_vae.py).
* V2 side: the node runs in a real guest (GuestSession through _res4_sealed_guest_entry.py, guest import audit on)
  with exactly its declared permissions; decode and encode go to the host's vae.decode_tensor and vae.encode.
* Fixtures: the seeded TAESD and SD-style KL VAEs of test_res4lyf_vae.py, handed to both sides as the same Core VAE.
* Latents: plain ones (the original decodes the samples), and chained ones. A chained latent is what each version's
  sampler outputs: the original's carries state_info with the loop's denoised estimate and its data_prev_ history; the
  V2 one carries the chain marker {"node", "denoised"}. Both decode that estimate, which differs from the samples
  here, so a row also proves which tensor was decoded. (tests/v2_parity.py proves the V2 sampler's carried estimate
  equals the original's state_info['denoised'] bit for bit.)
* Compared: the output samples (dtype, shape, bits), the carried estimate (V2's chain["denoised"] against the
  original's state_info["denoised"]), the chain's node name, and every other key of the input latent (copied).
* LAYOUT_ROUNDING (the class documented for VAEEncodeAdvanced in SECURE_CONVERSION.md): the interpolation is fixed
  to lanczos, whose output is channels-first memory, and the original hands vae.encode that view; V2's pixels cross
  to the host contiguous. A row passes as LAYOUT_ROUNDING only when the original's resized pixels are such a view
  and V2's latents (samples and carried estimate) are bitwise equal to Core's encode of exactly those pixels made
  contiguous. The original's pixels come from its own decode of the tensor it decodes, so this also proves that V2
  decoded and resized the same values.
* Seeds: the original seeds torch's process-wide generator with 42 first (helper_sigma_preview_image_preproc.py:
  653-654); V2 does not. SEED_INDEPENDENT rows seed the host's and the guest's generators with 1234 before the V2 run;
  KNOWN_DIFFERENCE records where each side leaves the host's generator.
* Errors must occur on both sides (BOTH_FAIL); V2-only refusals by name are listed (REFUSED_AS_DESIGNED). A 1-ulp
  change to a V2 latent must compare unequal (negative control).
Writes /results/upscale.json; exit 1 on any difference.
Run: run_in_gate.sh <RES4LYF-HEAD with v2> <v2/tests> <out> test_res4lyf_upscale.py   (DEPS optional)
"""
import asyncio
import importlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import traceback
import types
from pathlib import Path

CORE = Path(os.environ.get("COMFY_CORE_ROOT", "/core"))
sys.path[:0] = [str(CORE), "/overlay"]
if Path("/deps").is_dir():
    sys.path.append("/deps")

from comfy.cli_args import args  # noqa: E402

args.cpu = True
import torch  # noqa: E402

import comfy.sd  # noqa: E402
import comfy.taesd.taesd  # noqa: E402
import folder_paths  # noqa: E402,F401
import server  # noqa: E402
from aiohttp import web  # noqa: E402
from comfy.ldm.models.autoencoder import AutoencodingEngine  # noqa: E402

server.PromptServer.instance = types.SimpleNamespace(
    routes=web.RouteTableDef(), supports={"custom_nodes_from_web"}, send_sync=lambda *a, **k: None,
    client_id=None, last_node_id=None)

from comfy_api.latest import _execution_metadata, _sdk  # noqa: E402
from comfy_execution.graph import DynamicPrompt  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))
import import_stubs  # noqa: E402

STUBBED = import_stubs.install(["matplotlib", "cv2", "pywt", "opensimplex"],  # only those genuinely absent
                               noop_calls=["matplotlib.use"])  # the original calls it at import (see import_stubs)
PACK = Path(os.environ.get("RES4_PACK", "/pack"))
V2 = PACK / "v2"
RESULTS = Path(os.environ.get("RES4_RESULTS", "/results"))
TMP = Path(tempfile.mkdtemp(prefix="res4-upscale-"))
GUARD_LOG = TMP / "import-guard.jsonl"
shutil.copytree(PACK, TMP / "RES4LYF", ignore=shutil.ignore_patterns("v2"))
sys.path.insert(0, str(TMP))
ORIGINAL = importlib.import_module("RES4LYF").NODE_CLASS_MAPPINGS["LatentUpscaleWithVAE"]
ORIGINAL_IMAGES = sys.modules["RES4LYF.images"]  # upstream's image_resize, which the original node calls


def import_package(name, root):
    spec = importlib.util.spec_from_file_location(name, root / "__init__.py", submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


SECURE = import_package("res4lyf_secure", V2).NODE_CLASS_MAPPINGS["LatentUpscaleWithVAE"]
CHAIN_KEY = sys.modules["res4lyf_secure.latent_chain"].CHAIN_KEY
SAMPLER = "ClownsharKSampler_Beta"
GUEST = {"session": None, "pids": set()}


class SealedEntryGuestSession(GuestSession):
    """The production entry order with the guest import audit on (and an optional seed); see the entry's docstring."""

    seed = None

    def _guest_command(self, python):
        return [python, str(TESTS / "_res4_sealed_guest_entry.py")]

    def _adjust_guest_env(self, env):
        super()._adjust_guest_env(env)
        env["RES4_GUARD_ROOT"] = str(self.guest_runtime_root)
        env["RES4_GUARD_LOG"] = str(GUARD_LOG)
        if self.seed is not None:
            env["RES4_GUEST_SEED"] = str(self.seed)


async def run_v2(inputs, seed=None):
    cls = SECURE
    permissions = tuple(cls.SDK_PERMISSIONS)
    refs = _sdk.InProcessRefResolver()
    scope = _execution_metadata.ExecutionMetadataScope("res4-upscale", DynamicPrompt({}), None, observe=True)
    scope.__enter__()
    guest = None
    try:
        plan = _sdk.ExecutionPlan(
            prompt_id="res4-upscale", node_id="9", node_type=cls.__name__, tier="sandbox",
            node_module=cls.__module__, inputs=dict(inputs), input_mode="refs", method="execute",
            permissions=permissions, prompt=None, extra_pnginfo=None, dynamic_prompt=DynamicPrompt({}),
            execution_metadata=scope)
        runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps())
        plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
        if seed is None:
            if GUEST["session"] is None:
                GUEST["session"] = await SealedEntryGuestSession("res4-upscale", guest_runtime_root=V2).start()
            guest = GUEST["session"]
        else:  # a fresh guest whose global generator was seeded before it served anything
            guest = SealedEntryGuestSession(f"res4-upscale-seed-{seed}", guest_runtime_root=V2)
            guest.seed = seed
            await guest.start()
        with torch.inference_mode():  # the host's ops run inside the executor's inference mode (execution.py:1053)
            result = await guest.execute(plan, runtime, capabilities=permissions, tenant="res4-upscale")
        if guest.last_guest_pid:
            GUEST["pids"].add(guest.last_guest_pid)
        return tuple([await refs.resolve(v) if isinstance(v, _sdk.Ref) else v for v in (result.result or ())])
    finally:
        scope.__exit__(None, None, None)
        if seed is not None and guest is not None:
            await guest.kill()


def clone(value):
    if isinstance(value, torch.Tensor):
        return value.clone()
    if isinstance(value, dict):
        return {k: clone(v) for k, v in value.items()}
    return value


def run_original(inputs):
    with torch.inference_mode():  # as core's executor runs every node (execution.py:1053)
        return tuple(ORIGINAL().main(**{k: clone(v) for k, v in inputs.items()}))


INT_VIEW = {torch.float16: torch.int16, torch.bfloat16: torch.int16, torch.float32: torch.int32,
            torch.float64: torch.int64}


def same(a, b):
    if type(a) is not type(b):
        return False
    if isinstance(a, torch.Tensor):
        if a.dtype != b.dtype or a.shape != b.shape or a.device != b.device:
            return False
        if a.dtype in INT_VIEW:
            nan_a, nan_b = torch.isnan(a), torch.isnan(b)
            return torch.equal(nan_a, nan_b) and torch.equal(
                a.contiguous().view(INT_VIEW[a.dtype])[~nan_a], b.contiguous().view(INT_VIEW[b.dtype])[~nan_b])
        return torch.equal(a, b)
    if isinstance(a, float):
        return a.hex() == b.hex()
    if isinstance(a, (list, tuple)):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    return a == b


def show(value):
    if isinstance(value, torch.Tensor):
        flat = value.detach().double().flatten()
        return {"dtype": str(value.dtype), "shape": list(value.shape),
                "sum": float(flat.nansum()) if value.numel() else 0.0}
    if isinstance(value, (list, tuple)):
        return [show(v) for v in value]
    if isinstance(value, dict):
        return {str(k): show(v) for k, v in value.items()}
    return value


# --------------------------------------------------------------------------------------------------------------- #
# Fixtures (synthetic; seeded)
# --------------------------------------------------------------------------------------------------------------- #
def seeded_(module, seed, scale):
    gen = torch.Generator().manual_seed(seed)
    with torch.no_grad():
        for p in module.parameters():
            p.copy_(torch.randn(p.shape, generator=gen) * scale)
    return module


def taesd_vae(seed):
    module = seeded_(comfy.taesd.taesd.TAESD(latent_channels=4), seed, 0.05)
    return comfy.sd.VAE(sd={k: v.clone() for k, v in module.state_dict().items()})


def kl_vae(seed):
    """Core's default SD-style KL VAE (see test_res4lyf_vae.py)."""
    ddconfig = {"double_z": True, "z_channels": 4, "resolution": 256, "in_channels": 3, "out_ch": 3, "ch": 128,
                "ch_mult": [1, 2, 4, 4], "num_res_blocks": 2, "attn_resolutions": [], "dropout": 0.0}
    module = AutoencodingEngine(
        regularizer_config={"target": "comfy.ldm.models.autoencoder.DiagonalGaussianRegularizer"},
        encoder_config={"target": "comfy.ldm.modules.diffusionmodules.model.Encoder", "params": ddconfig},
        decoder_config={"target": "comfy.ldm.modules.diffusionmodules.model.Decoder", "params": ddconfig})
    seeded_(module, seed, 0.02)
    vae = comfy.sd.VAE(sd={k: v.clone() for k, v in module.state_dict().items()})
    assert type(vae.first_stage_model).__name__ == "AutoencodingEngine", type(vae.first_stage_model)
    return vae


def randn(shape, seed, scale=0.5):
    return torch.randn(shape, generator=torch.Generator().manual_seed(seed)) * scale


TAESD = taesd_vae(101)
KL = kl_vae(102)
S1, D1 = randn((1, 4, 8, 8), 11), randn((1, 4, 8, 8), 12)
S2, D2 = randn((2, 4, 6, 10), 13), randn((2, 4, 6, 10), 14)
MASK = torch.zeros((1, 8, 8))
MASK[:, 2:6, 1:7] = 1.0


def chained(samples, denoised, extra=None):
    """The same chained latent as each version's sampler outputs it: (original's, V2's). The original's loop always
    stores its data_prev_ history (4 entries, rk_sampler_beta.py:837-839 and :2255) next to the estimate."""
    state = {"denoised": denoised.clone(), "end_step": 5, "sampler_mode": "standard",
             "data_prev_": randn((4,) + tuple(denoised.shape), 15, 0.3)}
    original = {"samples": samples.clone(), "state_info": state}
    v2 = {"samples": samples.clone(), CHAIN_KEY: {"node": SAMPLER, "denoised": denoised.clone()}}
    for key, value in (extra or {}).items():
        original[key] = clone(value)
        v2[key] = clone(value)
    return original, v2


def cases():
    """(label, original inputs, V2 inputs, expect)."""
    out = []

    def add(label, latent_original, latent_v2, vae, width, height, expect="compare"):
        base = {"vae": vae, "width": width, "height": height}
        out.append((label, dict(base, latent=latent_original), dict(base, latent=latent_v2), expect))

    for name, vae in (("taesd", TAESD), ("kl", KL)):
        for width, height in ((64, 64), (96, 80), (40, 32), (72, 56)):
            add(f"{name}:plain:{width}x{height}", {"samples": S1.clone()}, {"samples": S1.clone()}, vae, width,
                height)
            o, v = chained(S1, D1)
            add(f"{name}:chained:{width}x{height}", o, v, vae, width, height)
        o, v = chained(S2, D2)
        add(f"{name}:chained:batch2:88x48", o, v, vae, 88, 48)
        add(f"{name}:plain:batch2:88x48", {"samples": S2.clone()}, {"samples": S2.clone()}, vae, 88, 48)
    o, v = chained(S1, D1, extra={"noise_mask": MASK, "batch_index": [3]})
    add("taesd:chained:noise_mask+batch_index", o, v, TAESD, 80, 64)
    add("taesd:plain:noise_mask", {"samples": S1.clone(), "noise_mask": MASK.clone()},
        {"samples": S1.clone(), "noise_mask": MASK.clone()}, TAESD, 64, 48)
    o, v = chained(S1.half(), D1)
    add("taesd:chained:float16 samples", o, v, TAESD, 64, 64)
    add("kl:plain:bfloat16 samples", {"samples": S1.bfloat16()}, {"samples": S1.bfloat16()}, KL, 48, 64)
    # A sampler whose loop ran no step and had no incoming state: no denoised estimate, and the original fails
    # reading it (KeyError)
    add("taesd:chained:no denoised", {"samples": S1.clone(), "state_info": {"model_call_counts": [0, 0, 0]}},
        {"samples": S1.clone(), CHAIN_KEY: {"node": SAMPLER}}, TAESD, 64, 64)
    # V2-only inputs refused by name: an unconverted sampler's state_info, and an earlier version's string marker
    add("v2:state_info refused", {"samples": S1.clone()}, chained(S1, D1)[0], TAESD, 64, 64, expect="refused_v2")
    add("v2:string marker refused", {"samples": S1.clone()}, {"samples": S1.clone(), CHAIN_KEY: SAMPLER}, TAESD,
        64, 64, expect="refused_v2")
    return out


def decoded_source(latent):
    state = latent.get("state_info")
    return state["denoised"] if isinstance(state, dict) else latent["samples"]


def layout_check(inputs, expected, actual):
    """The LAYOUT_ROUNDING conditions (see the module docstring); returns (holds, details)."""
    vae, latent = inputs["vae"], inputs["latent"]
    with torch.inference_mode():
        images = vae.decode(decoded_source(latent))
        if len(images.shape) == 5:
            images = images.reshape(-1, images.shape[-3], images.shape[-2], images.shape[-1])
        resized = ORIGINAL_IMAGES.image_resize(images, inputs["width"], inputs["height"], "stretch", "lanczos",
                                               "always", 0, False)[:, :, :, :3]
        reference = vae.encode(resized.contiguous())
    out_e, out_a = expected[0], actual[0]
    details = {"original_pixels_contiguous": resized.is_contiguous(),
               "v2_samples_equal_core_encode_of_original_pixels_contiguous":
                   same(reference.to(latent["samples"]), out_a["samples"])}
    if isinstance(out_e.get("state_info"), dict):
        details["v2_carried_equals_core_encode_of_original_pixels_contiguous"] = same(
            reference, out_a[CHAIN_KEY]["denoised"])
    diff = (out_e["samples"].double() - out_a["samples"].double()).abs()
    details.update(max_abs_diff=float(diff.max()), elements_differing=int((diff > 0).sum()),
                   elements=diff.numel())
    holds = (not resized.is_contiguous()
             and all(v for k, v in details.items() if k.startswith("v2_")))
    return holds, details


def mapped(expected, actual):
    """Compare the parts that must be bitwise equal outside the encode: every copied key, the node name, and which
    tensor each side carries. Returns (ok, details)."""
    out_e, out_a = expected[0], actual[0]
    details = {}
    plain_e = {k: v for k, v in out_e.items() if k not in ("samples", "state_info")}
    plain_a = {k: v for k, v in out_a.items() if k not in ("samples", CHAIN_KEY)}
    details["other_keys_equal"] = same(plain_e, plain_a)
    has_state = isinstance(out_e.get("state_info"), dict)
    details["carries_iff_original_does"] = has_state == (CHAIN_KEY in out_a)
    if has_state:
        chain = out_a[CHAIN_KEY]
        details["chain_node_kept"] = chain.get("node") == SAMPLER
        details["chain_keys"] = sorted(chain) == ["denoised", "node"]
        details["carried_dtype_shape"] = (chain["denoised"].dtype == out_e["state_info"]["denoised"].dtype
                                          and chain["denoised"].shape == out_e["state_info"]["denoised"].shape)
    details["samples_dtype_shape"] = (out_e["samples"].dtype == out_a["samples"].dtype
                                      and out_e["samples"].shape == out_a["samples"].shape)
    return all(v for k, v in details.items()), details


def exact(expected, actual):
    out_e, out_a = expected[0], actual[0]
    ok = same(out_e["samples"], out_a["samples"])
    if isinstance(out_e.get("state_info"), dict):
        ok = ok and same(out_e["state_info"]["denoised"], out_a[CHAIN_KEY]["denoised"])
    return ok


async def compare(label, inputs_original, inputs_v2, expect, v2_seed=None):
    try:
        expected, expected_error = run_original(inputs_original), None
    except Exception as error:  # noqa: BLE001
        expected, expected_error = None, f"{type(error).__name__}: {error}"[:300]
    if v2_seed is not None:
        torch.manual_seed(v2_seed)
    try:
        actual, actual_error = await run_v2(inputs_v2, seed=v2_seed), None
    except Exception as error:  # noqa: BLE001
        actual, actual_error = None, f"{type(error).__name__}: {error}"[:400]
    layout, structure = None, None
    if expect == "refused_v2":
        named = actual_error is not None and "RES4LYF/LatentUpscaleWithVAE" in actual_error
        verdict = "REFUSED_AS_DESIGNED" if named else "MISMATCH"
    elif expected_error or actual_error:
        verdict = "BOTH_FAIL" if expected_error and actual_error else "MISMATCH"
        if verdict == "BOTH_FAIL" and expected_error.split(":")[0] not in actual_error:
            verdict = "MISMATCH"  # the same failure: the original's exception type, as the guest reports it
    else:
        ok, structure = mapped(expected, actual)
        if not ok:
            verdict = "MISMATCH"
        elif exact(expected, actual):
            verdict = "EXACT"
        else:
            holds, layout = layout_check(inputs_original, expected, actual)
            verdict = "LAYOUT_ROUNDING" if holds else "MISMATCH"
    return {"case": label, "verdict": verdict, "expect": expect, "layout": layout, "structure": structure,
            "expected": show(expected), "actual": show(actual), "expected_error": expected_error,
            "actual_error": actual_error}, expected, actual


async def main():
    rows, perturb = [], None
    for label, inputs_original, inputs_v2, expect in cases():
        row, expected, actual = await compare(label, inputs_original, inputs_v2, expect)
        rows.append(row)
        print(row["verdict"], label, row["expected_error"] or "", row["actual_error"] or "", flush=True)
        if perturb is None and row["verdict"] in ("EXACT", "LAYOUT_ROUNDING") and expect == "compare":
            perturb = (inputs_original, expected, actual)
    # The original seeds the global generator with 42; V2 does not. With both generators elsewhere (1234), the
    # results must still pass.
    seed_rows = []
    for name, vae in (("taesd", TAESD), ("kl", KL)):
        o, v = chained(S1, D1)
        base = {"vae": vae, "width": 72, "height": 56}
        row, _e, _a = await compare(f"{name}:chained:generators seeded 1234 before the V2 run", dict(base, latent=o),
                                    dict(base, latent=v), "compare", v2_seed=1234)
        row["verdict"] = "SEED_INDEPENDENT" if row["verdict"] in ("EXACT", "LAYOUT_ROUNDING") else row["verdict"]
        seed_rows.append(row)
    side_o, side_v = chained(S1, D1)
    side_base = {"vae": TAESD, "width": 64, "height": 64}
    torch.manual_seed(7)
    run_original(dict(side_base, latent=side_o))
    after_original = torch.rand(4)
    torch.manual_seed(42)
    at_seed_42 = torch.rand(4)
    torch.manual_seed(7)
    await run_v2(dict(side_base, latent=side_v))
    after_v2 = torch.rand(4)
    torch.manual_seed(7)
    untouched = torch.rand(4)
    side_effect = {"verdict": "KNOWN_DIFFERENCE",
                   "original_leaves_host_generator_at_seed_42": torch.equal(after_original, at_seed_42),
                   "v2_leaves_host_generator_where_it_was": torch.equal(after_v2, untouched)}
    # negative control: one ulp on V2's samples must fail both the exact and the layout comparison
    inputs_original, expected, actual = perturb
    bumped = dict(actual[0])
    bumped["samples"] = actual[0]["samples"].clone()
    flat = bumped["samples"].view(-1)
    flat[0] = torch.nextafter(flat[0], torch.tensor(float("inf"), dtype=flat.dtype))
    ulp_red = not exact(expected, (bumped,)) and not layout_check(inputs_original, expected, (bumped,))[0]
    if GUEST["session"] is not None:
        await GUEST["session"].kill()
    await asyncio.sleep(0.5)
    alive = [pid for pid in GUEST["pids"] if Path(f"/proc/{pid}").exists()]
    totals = {}
    for row in rows + seed_rows:
        totals[row["verdict"]] = totals.get(row["verdict"], 0) + 1
    guard = [json.loads(line) for line in GUARD_LOG.read_text().splitlines()] if GUARD_LOG.exists() else []
    layout_rows = [r for r in rows + seed_rows if r["layout"]]
    doc = {"totals": totals, "cases": len(rows) + len(seed_rows),
           "layout_rounding": {"rows": len(layout_rows),
                               "max_abs_diff": max((r["layout"]["max_abs_diff"] for r in layout_rows), default=0.0),
                               "all_original_pixels_channels_first_views": all(
                                   not r["layout"]["original_pixels_contiguous"] for r in layout_rows)},
           "chained_rows_decoding_the_carried_estimate": sum(
               1 for r in rows if ":chained:" in r["case"] and r["verdict"] in ("EXACT", "LAYOUT_ROUNDING")),
           "seed_independence": seed_rows, "seed_side_effect": side_effect, "negative_control_ulp_red": ulp_red,
           "vae_fixtures": {"taesd": type(TAESD.first_stage_model).__name__,
                            "kl": f"{type(KL.first_stage_model).__name__} + "
                                  f"{type(KL.first_stage_model.regularization).__name__}"},
           "guest_import_audit": {"on": True, "refused_imports": sorted({g["module"] for g in guard}),
                                  "refused_import_events": len(guard)},
           "guest_pids": len(GUEST["pids"]), "alive_after_kill": alive, "stubbed_imports_original_side": STUBBED,
           "rows": rows}
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "upscale.json").write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: doc[k] for k in ("totals", "cases", "layout_rounding",
                                          "chained_rows_decoding_the_carried_estimate", "seed_side_effect",
                                          "negative_control_ulp_red", "vae_fixtures", "guest_import_audit",
                                          "guest_pids", "alive_after_kill")}, indent=1))
    bad = (any(r["verdict"] == "MISMATCH" for r in rows + seed_rows) or alive or not ulp_red
           or not all(r["verdict"] == "SEED_INDEPENDENT" for r in seed_rows)
           or not side_effect["original_leaves_host_generator_at_seed_42"]
           or not side_effect["v2_leaves_host_generator_where_it_was"]
           or guard)
    return 1 if bad else 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except Exception:
        traceback.print_exc()
        sys.exit(2)
