"""Tier-1 parity for RES4LYF's VAEEncodeAdvanced: the ORIGINAL in-process vs V2 in a real guest (gate only).

* Original side: the pristine package imported in this process (labelled import stubs as in test_res4lyf_simple.py).
* V2 side: the node runs in a real guest (GuestSession through _res4_sealed_guest_entry.py, with the guest import
  audit on) with exactly its declared permissions. Its VAE encode goes to the host's ``vae.encode``.
* Two synthetic VAE fixtures with seeded weights, built here and handed to both sides as the same Core VAE object:
  TAESD (Core recognises it by key) and an SD-style KL VAE (Core's default AutoencodingEngine), whose encode goes
  through DiagonalGaussianRegularizer.
* Cases: every resize_to_input, method, interpolation, mask channel and latent_type option; inputs present and
  absent; RGBA images; sizes that are not multiples of 8; the zero-size branches that raise NameError upstream.
* The original seeds torch's process-wide generator with 42 before encoding (helper_sigma_preview_image_preproc.py:
  257-258); V2 does not. Two rows cover that:
  - SEED_INDEPENDENT: the host's and the guest's generators are seeded with 1234 before the V2 run, and its latents
    must still equal the original's, for both VAEs;
  - KNOWN_DIFFERENCE (documented in SECURE_CONVERSION.md): after the original runs, the host's generator is at seed
    42; after V2 runs, it is where it was.
* Comparisons are type-strict; tensors (latents, mask) compare by dtype, shape and bits. Errors must occur on both
  sides (BOTH_FAIL). A 1-ulp change to one V2 latent must compare unequal (negative control).
* LAYOUT_ROUNDING (documented in SECURE_CONVERSION.md): Core's comfy.utils.lanczos returns channels-first memory, so
  with interpolation "lanczos" the original hands vae.encode a channels-first view of the resized pixels. A V2 IMAGE
  crosses to the host as a contiguous buffer, and Core's encode rounds its convolutions differently for the two
  layouts. Such a row passes only if every other output is bitwise equal, the original's resized pixels are such a
  view, and V2's latents are bitwise equal to Core's encode of exactly those pixels made contiguous. So the pixels and
  the encode are exact, and the layout alone explains the difference, which the row records.
Writes /results/vae.json; exit 1 on any difference.
Run: run_in_gate.sh <RES4LYF-HEAD with v2> <v2/tests> <out> test_res4lyf_vae.py   (DEPS optional)
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
TMP = Path(tempfile.mkdtemp(prefix="res4-vae-"))
GUARD_LOG = TMP / "import-guard.jsonl"
shutil.copytree(PACK, TMP / "RES4LYF", ignore=shutil.ignore_patterns("v2"))
sys.path.insert(0, str(TMP))
ORIGINAL = importlib.import_module("RES4LYF").NODE_CLASS_MAPPINGS["VAEEncodeAdvanced"]
ORIGINAL_IMAGES = sys.modules["RES4LYF.images"]  # upstream's image_resize, which the original node calls


def import_package(name, root):
    spec = importlib.util.spec_from_file_location(name, root / "__init__.py", submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


SECURE = import_package("res4lyf_secure", V2).NODE_CLASS_MAPPINGS["VAEEncodeAdvanced"]
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
    scope = _execution_metadata.ExecutionMetadataScope("res4-vae", DynamicPrompt({}), None, observe=True)
    scope.__enter__()
    guest = None
    try:
        plan = _sdk.ExecutionPlan(
            prompt_id="res4-vae", node_id="9", node_type=cls.__name__, tier="sandbox", node_module=cls.__module__,
            inputs=dict(inputs), input_mode="refs", method="execute", permissions=permissions, prompt=None,
            extra_pnginfo=None, dynamic_prompt=DynamicPrompt({}), execution_metadata=scope)
        runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps())
        plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
        if seed is None:
            if GUEST["session"] is None:
                GUEST["session"] = await SealedEntryGuestSession("res4-vae", guest_runtime_root=V2).start()
            guest = GUEST["session"]
        else:  # a fresh guest whose global generator was seeded before it served anything
            guest = SealedEntryGuestSession(f"res4-vae-seed-{seed}", guest_runtime_root=V2)
            guest.seed = seed
            await guest.start()
        result = await guest.execute(plan, runtime, capabilities=permissions, tenant="res4-vae")
        if guest.last_guest_pid:
            GUEST["pids"].add(guest.last_guest_pid)
        return tuple([await refs.resolve(v) if isinstance(v, _sdk.Ref) else v for v in (result.result or ())])
    finally:
        scope.__exit__(None, None, None)
        if seed is not None and guest is not None:
            await guest.kill()


def run_original(inputs):
    return tuple(ORIGINAL().main(**{k: (v.clone() if isinstance(v, torch.Tensor) else v) for k, v in inputs.items()}))


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
    """Core's default SD-style KL VAE: comfy/sd.py builds an AutoencodingEngine with DiagonalGaussianRegularizer
    when the state dict has decoder.conv_in.weight and no post_quant_conv."""
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


def image(batch, height, width, channels, seed):
    return torch.rand((batch, height, width, channels), generator=torch.Generator().manual_seed(seed))


TAESD = taesd_vae(101)
KL = kl_vae(102)
IMG_A = image(1, 48, 64, 3, 1)
IMG_B = image(2, 40, 40, 3, 2)
RGBA = image(1, 32, 32, 4, 3)
MASK_RGB = image(1, 50, 30, 3, 4)
MASK_RGBA = image(2, 24, 24, 4, 5)
MASK_1CH = image(1, 24, 24, 1, 6)
LATENT = {"samples": torch.randn((1, 4, 6, 9), generator=torch.Generator().manual_seed(7))}
BASE = {"width": 72, "height": 40, "resize_to_input": "false", "mask_channel": "red", "invert_mask": False,
        "latent_type": "16_channels", "interpolation": "lanczos", "method": "fill / crop"}


def cases():
    """(label, inputs)."""
    out = []

    def add(label, **overrides):
        inputs = dict(BASE)
        inputs.update(overrides)
        out.append((label, {k: v for k, v in inputs.items() if v is not None}))
    for method in ("stretch", "keep proportion", "fill / crop", "pad"):
        for interpolation in ("nearest", "bilinear", "bicubic", "area", "nearest-exact", "lanczos"):
            add(f"taesd:{method}:{interpolation}", method=method, interpolation=interpolation, image_1=IMG_A,
                vae=TAESD)
    for resize in ("false", "image_1", "image_2", "mask", "latent"):
        add(f"taesd:resize_to_input={resize}:all inputs", resize_to_input=resize, image_1=IMG_A, image_2=IMG_B,
            mask=MASK_RGB, latent=LATENT, vae=TAESD)
        add(f"taesd:resize_to_input={resize}:image_2 only", resize_to_input=resize, image_2=IMG_B, vae=TAESD)
    for channel in ("red", "green", "blue", "alpha"):
        for invert in (False, True):
            add(f"mask:{channel}:invert={invert}:rgba", mask=MASK_RGBA, mask_channel=channel, invert_mask=invert)
        add(f"mask:{channel}:rgb", mask=MASK_RGB, mask_channel=channel)
    add("mask:one channel", mask=MASK_1CH)
    for latent_type in ("4_channels", "16_channels"):
        add(f"empty latent only:{latent_type}", latent_type=latent_type)
        add(f"empty latent:{latent_type}:batch from image_2", latent_type=latent_type, image_2=IMG_B, vae=TAESD)
    add("latent passthrough", latent=LATENT)
    add("taesd:rgba image", image_1=RGBA, vae=TAESD, method="stretch")
    add("taesd:not a multiple of 8", image_1=IMG_A, vae=TAESD, width=100, height=60, method="stretch",
        interpolation="bilinear")
    add("taesd:width 0 stretch", image_1=IMG_A, vae=TAESD, width=0, method="stretch", interpolation="area")
    add("taesd:width 0 keep proportion", image_1=IMG_A, vae=TAESD, width=0, method="keep proportion")
    add("taesd:height 0 pad", image_1=IMG_A, vae=TAESD, height=0, method="pad")
    add("width 0 empty latent only", width=0)
    add("no vae with an image", image_1=IMG_A)
    add("kl:stretch:lanczos:both images and mask", image_1=IMG_A, image_2=IMG_B, mask=MASK_RGB, vae=KL,
        method="stretch")
    add("kl:fill / crop:bicubic", image_1=IMG_B, vae=KL, interpolation="bicubic", width=48, height=64)
    add("kl:resize_to_input=latent", image_1=IMG_A, latent=LATENT, vae=KL, resize_to_input="latent",
        method="pad", interpolation="bilinear")
    return out


def layout_check(inputs, expected, actual):
    """The LAYOUT_ROUNDING conditions (see the module docstring); returns (holds, details)."""
    details = {"other_outputs_equal": same(tuple(expected[2:]), tuple(actual[2:]))}
    latents_ok = True
    for index, key in ((0, "image_1"), (1, "image_2")):
        if expected[index] is None and actual[index] is None:
            continue
        resized = ORIGINAL_IMAGES.image_resize(inputs[key].clone(), expected[4], expected[5], inputs["method"],
                                               inputs["interpolation"], "always", 0, False)[:, :, :, :3]
        reference = {"samples": inputs["vae"].encode(resized.contiguous())}
        diff = (expected[index]["samples"].double() - actual[index]["samples"].double()).abs()
        scale = expected[index]["samples"].double().abs().clamp_min(1e-12)
        details[key] = {"original_pixels_contiguous": resized.is_contiguous(),
                        "v2_equals_core_encode_of_original_pixels_contiguous": same(reference, actual[index]),
                        "max_abs_diff": float(diff.max()), "max_rel_diff": float((diff / scale).max()),
                        "elements_differing": int((diff > 0).sum()), "elements": diff.numel()}
        latents_ok = latents_ok and not resized.is_contiguous() and details[key][
            "v2_equals_core_encode_of_original_pixels_contiguous"]
    return details["other_outputs_equal"] and latents_ok, details


async def compare(label, inputs, v2_seed=None):
    try:
        expected, expected_error = run_original(inputs), None
    except Exception as error:  # noqa: BLE001
        expected, expected_error = None, f"{type(error).__name__}: {error}"[:300]
    if v2_seed is not None:
        torch.manual_seed(v2_seed)
    try:
        actual, actual_error = await run_v2(inputs, seed=v2_seed), None
    except Exception as error:  # noqa: BLE001
        actual, actual_error = None, f"{type(error).__name__}: {error}"[:400]
    layout = None
    if expected_error or actual_error:
        verdict = "BOTH_FAIL" if expected_error and actual_error else "MISMATCH"
    elif same(expected, actual):
        verdict = "EXACT"
    else:
        holds, layout = layout_check(inputs, expected, actual)
        verdict = "LAYOUT_ROUNDING" if holds else "MISMATCH"
    encoded = [i for i in (0, 1) if expected is not None and expected[i] is not None]
    return {"case": label, "verdict": verdict, "interpolation": inputs.get("interpolation"),
            "latents_encoded": len(encoded), "layout": layout,
            "expected": show(expected), "actual": show(actual), "expected_error": expected_error,
            "actual_error": actual_error}, expected, actual


async def main():
    rows, perturb = [], None
    for label, inputs in cases():
        row, expected, actual = await compare(label, inputs)
        rows.append(row)
        if row["verdict"] != "EXACT":
            print(row["verdict"], label, row["expected_error"], row["actual_error"], flush=True)
        elif perturb is None and row["latents_encoded"]:
            perturb = (expected, actual)
    # The original seeds the global generator with 42; V2 does not. With both generators elsewhere (1234), the
    # latents must still be equal.
    seed_rows = []
    for name, vae in (("taesd", TAESD), ("kl", KL)):  # bilinear: bitwise-exact pixels in the same layout
        row, _e, _a = await compare(f"{name}:generators seeded 1234 before the V2 run", dict(
            BASE, image_1=IMG_A, image_2=IMG_B, vae=vae, method="stretch", interpolation="bilinear"), v2_seed=1234)
        row["verdict"] = "SEED_INDEPENDENT" if row["verdict"] == "EXACT" else row["verdict"]
        seed_rows.append(row)
    # The documented side effect itself: the host generator after each side's run.
    side_inputs = dict(BASE, image_1=IMG_A, vae=TAESD)
    torch.manual_seed(7)
    run_original(side_inputs)
    after_original = torch.rand(4)
    torch.manual_seed(42)
    at_seed_42 = torch.rand(4)
    torch.manual_seed(7)
    await run_v2(side_inputs)
    after_v2 = torch.rand(4)
    torch.manual_seed(7)
    untouched = torch.rand(4)
    side_effect = {"verdict": "KNOWN_DIFFERENCE",
                   "original_leaves_host_generator_at_seed_42": torch.equal(after_original, at_seed_42),
                   "v2_leaves_host_generator_where_it_was": torch.equal(after_v2, untouched)}
    expected, actual = perturb
    bumped = dict(actual[0])
    bumped["samples"] = actual[0]["samples"].clone()
    flat = bumped["samples"].view(-1)
    flat[0] = torch.nextafter(flat[0], torch.tensor(float("inf"), dtype=flat.dtype))
    ulp_red = not same(expected, (bumped,) + tuple(actual[1:]))
    if GUEST["session"] is not None:
        await GUEST["session"].kill()
    await asyncio.sleep(0.5)
    alive = [pid for pid in GUEST["pids"] if Path(f"/proc/{pid}").exists()]
    totals = {}
    for row in rows + seed_rows:
        totals[row["verdict"]] = totals.get(row["verdict"], 0) + 1
    guard = [json.loads(line) for line in GUARD_LOG.read_text().splitlines()] if GUARD_LOG.exists() else []
    layout_rows = [r for r in rows if r["verdict"] == "LAYOUT_ROUNDING"]
    layout = {"rows": len(layout_rows), "all_lanczos": all(r["interpolation"] == "lanczos" for r in layout_rows),
              "max_abs_diff": max((v["max_abs_diff"] for r in layout_rows for k, v in r["layout"].items()
                                   if k.startswith("image_")), default=0.0),
              "max_rel_diff": max((v["max_rel_diff"] for r in layout_rows for k, v in r["layout"].items()
                                   if k.startswith("image_")), default=0.0),
              "cases": [r["case"] for r in layout_rows]}
    exact_non_lanczos = [r["case"] for r in rows if r["verdict"] == "EXACT" and r["latents_encoded"]]
    doc = {"totals": totals, "cases": len(rows) + len(seed_rows), "layout_rounding": layout,
           "exact_rows_with_encoded_latents": exact_non_lanczos,
           "cases_with_encoded_latents": sum(1 for r in rows + seed_rows if r["latents_encoded"]),
           "seed_independence": seed_rows, "seed_side_effect": side_effect, "negative_control_ulp_red": ulp_red,
           "vae_fixtures": {"taesd": type(TAESD.first_stage_model).__name__,
                            "kl": f"{type(KL.first_stage_model).__name__} + "
                                  f"{type(KL.first_stage_model.regularization).__name__}"},
           "guest_import_audit": {"on": True, "refused_imports": sorted({g["module"] for g in guard}),
                                  "refused_import_events": len(guard)},
           "guest_pids": len(GUEST["pids"]), "alive_after_kill": alive, "stubbed_imports_original_side": STUBBED,
           "rows": rows}
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "vae.json").write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: doc[k] for k in ("totals", "cases", "cases_with_encoded_latents", "layout_rounding",
                                          "seed_side_effect", "negative_control_ulp_red", "vae_fixtures",
                                          "guest_import_audit", "guest_pids", "alive_after_kill")}, indent=1))
    bad = (any(r["verdict"] == "MISMATCH" for r in rows + seed_rows) or alive or not ulp_red
           or not layout["all_lanczos"]
           or not all(r["verdict"] == "SEED_INDEPENDENT" for r in seed_rows)
           or not side_effect["original_leaves_host_generator_at_seed_42"]
           or not side_effect["v2_leaves_host_generator_where_it_was"])
    return 1 if bad else 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except Exception:
        traceback.print_exc()
        sys.exit(2)
