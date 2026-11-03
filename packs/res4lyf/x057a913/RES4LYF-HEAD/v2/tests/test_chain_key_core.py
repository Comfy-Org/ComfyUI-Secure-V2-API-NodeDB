"""Core's own LATENT consumers with the V2 chain marker (gate only).

A V2 ClownsharKSampler_Beta output latent carries CHAIN_KEY: {"node": ..., "denoised": <tensor>} where the original's
carries "state_info" (a dict holding the same estimate and more loop state). This test runs every node core registers
(nodes.py and comfy_extras) that takes a LATENT and whose other inputs can be synthesised here (a seeded tiny SD1.5
UNet, a seeded TAESD, small conditioning, images, masks, sigmas and samplers), through core's own execution helpers
(execution.get_input_data and get_output_data, as the executor calls a node). Each node runs three times, with the
LATENT input(s), under torch.inference_mode as the executor runs nodes (execution.py:1053):
  plain     {"samples", ...}
  v2        plain + {CHAIN_KEY: {"node", "denoised"}}
  original  plain + {"state_info": {"denoised", "raw_x", "data_prev_", "end_step", ...}}
Checks per node:
  * the three runs give the same result once the extra key is set aside: every output value bitwise equal (tensors
    by dtype, shape and bits), the same UI data and the same files written, or the same failure in all three;
  * the V2 marker is passed on wherever, and only wherever, the original's state_info is (per output), and unchanged.
Run twice per node with more than one LATENT input: the extra key on every LATENT input, and on the first one only.
Nodes whose inputs cannot be synthesised here are listed (not run).
Writes /results/chain-key-core.json; exits 1 on any difference.
Run: run_in_gate.sh <RES4LYF-HEAD with v2> <v2/tests> <out> test_chain_key_core.py
"""
import asyncio
import json
import os
import sys
import tempfile
import traceback
import types
from pathlib import Path

CORE = Path(os.environ.get("COMFY_CORE_ROOT", "/core"))
for entry in (str(CORE), "/overlay"):
    if entry not in sys.path:
        sys.path.insert(0, entry)
from comfy.cli_args import args  # noqa: E402

args.cpu = True
import torch  # noqa: E402

import comfy.model_base as mb  # noqa: E402
import comfy.model_patcher as mp  # noqa: E402
import comfy.samplers  # noqa: E402
import comfy.sd  # noqa: E402
import comfy.supported_models as sm  # noqa: E402
import comfy.taesd.taesd  # noqa: E402
import folder_paths  # noqa: E402
import server  # noqa: E402
from aiohttp import web  # noqa: E402
from app.node_replace_manager import NodeReplaceManager  # noqa: E402

server.PromptServer.instance = types.SimpleNamespace(
    routes=web.RouteTableDef(), supports={"custom_nodes_from_web"}, send_sync=lambda *a, **k: None,
    client_id=None, last_node_id=None, node_replace_manager=NodeReplaceManager())
folder_paths.set_input_directory(tempfile.mkdtemp(prefix="res4-chain-input-"))
import execution  # noqa: E402
import nodes  # noqa: E402

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))
import cases  # noqa: E402  (the parity fixtures' tiny model)

PACK = Path(os.environ.get("RES4_PACK", "/pack"))
CHAIN_KEY = "res4lyf_v2_chain"
assert (PACK / "v2" / "latent_chain.py").read_text().count(f'CHAIN_KEY = "{CHAIN_KEY}"') == 1
RESULTS = Path(os.environ.get("RES4_RESULTS", "/results"))
INT_VIEW = {torch.float16: torch.int16, torch.bfloat16: torch.int16, torch.float32: torch.int32,
            torch.float64: torch.int64}


def gen(seed):
    return torch.Generator().manual_seed(seed)


def taesd():
    module = comfy.taesd.taesd.TAESD(latent_channels=4)
    g = gen(101)
    with torch.no_grad():
        for p in module.parameters():
            p.copy_(torch.randn(p.shape, generator=g) * 0.05)
    return comfy.sd.VAE(sd={k: v.clone() for k, v in module.state_dict().items()})


MODEL = cases.tiny_model(mb, mp, sm, "EPS")
VAE = taesd()
SAMPLES = torch.randn((1, 4, 8, 8), generator=gen(1)) * 0.5
DENOISED = torch.randn((1, 4, 8, 8), generator=gen(2)) * 0.5
EXTRA = {
    "v2": (CHAIN_KEY, lambda: {"node": "ClownsharKSampler_Beta", "denoised": DENOISED.clone()}),
    "original": ("state_info", lambda: {"denoised": DENOISED.clone(), "raw_x": SAMPLES.clone(),
                                        "data_prev_": torch.zeros((4, 1, 4, 8, 8)), "end_step": 5,
                                        "sampler_mode": "standard", "sigmas": torch.linspace(1.0, 0.0, 7)}),
}


def conditioning(seed):
    return [[torch.randn((1, 8, 32), generator=gen(seed)), {}]]


def synth(type_, opts):
    """A value for one input, or raise LookupError when this test cannot make one."""
    opts = opts or {}
    if isinstance(type_, (list, tuple)):
        if not type_:
            raise LookupError("empty combo")
        return opts.get("default", type_[0]) if opts.get("default") in type_ else type_[0]
    if type_ == "COMBO":
        options = opts.get("options") or []
        if not options:
            raise LookupError("empty combo")
        return opts.get("default") if opts.get("default") in options else options[0]
    if type_ == "INT":
        value = opts.get("default", 1)
        return max(int(opts.get("min", value)), min(int(opts.get("max", value)), int(value)))
    if type_ == "FLOAT":
        value = opts.get("default", 1.0)
        return float(max(opts.get("min", value), min(opts.get("max", value), value)))
    if type_ == "BOOLEAN":
        return bool(opts.get("default", False))
    if type_ == "STRING":
        return str(opts.get("default", ""))
    if type_ == "MODEL":
        return MODEL
    if type_ == "VAE":
        return VAE
    if type_ == "CONDITIONING":
        return conditioning(3)
    if type_ == "IMAGE":
        return torch.rand((1, 64, 64, 3), generator=gen(4))
    if type_ == "MASK":
        return torch.rand((1, 64, 64), generator=gen(5))
    if type_ == "SIGMAS":
        return comfy.samplers.calculate_sigmas(MODEL.get_model_object("model_sampling"), "normal", 4)
    if type_ == "SAMPLER":
        return comfy.samplers.sampler_object("euler")
    if type_ == "NOISE":
        from comfy_extras.nodes_custom_sampler import Noise_RandomNoise
        return Noise_RandomNoise(7)
    if type_ == "GUIDER":
        guider = comfy.samplers.CFGGuider(MODEL)
        guider.set_conds(conditioning(3), conditioning(6))
        guider.set_cfg(2.0)
        return guider
    raise LookupError(f"no synthetic {type_}")


def latent(variant):
    value = {"samples": SAMPLES.clone()}
    if variant != "plain":
        key, make = EXTRA[variant]
        value[key] = make()
    return value


def same(a, b):
    if type(a) is not type(b):
        return False
    if isinstance(a, torch.Tensor):
        if a.dtype != b.dtype or a.shape != b.shape or a.device != b.device:
            return False
        if a.is_floating_point() and a.dtype in INT_VIEW:
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
    if isinstance(a, (str, int, bool, bytes)) or a is None:
        return a == b
    return True  # live objects (models, samplers): compared by type only


def strip(value, key):
    """value without the extra key in any LATENT-like dict; returns (stripped, list of carried values found)."""
    found = []

    def walk(v):
        if isinstance(v, dict):
            if key in v and "samples" in v:
                found.append(v[key])
            return {k: walk(x) for k, x in v.items() if not (k == key and "samples" in v)}
        if isinstance(v, (list, tuple)):
            items = [walk(x) for x in v]
            return tuple(items) if isinstance(v, tuple) else items
        return v
    return walk(value), found


def latent_inputs(class_def):
    types_ = class_def.INPUT_TYPES()
    names = []
    for section in ("required", "optional"):
        for name, spec in (types_.get(section) or {}).items():
            type_ = spec[0] if isinstance(spec, (list, tuple)) else spec
            if type_ == "LATENT":
                names.append(name)
    return names


def build_inputs(class_def, latents, variant):
    types_ = class_def.INPUT_TYPES()
    inputs = {}
    for section in ("required", "optional"):
        for name, spec in (types_.get(section) or {}).items():
            spec = list(spec) if isinstance(spec, (list, tuple)) else [spec]
            type_, opts = spec[0], (spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {})
            if type_ == "LATENT":
                inputs[name] = latent(variant if name in latents else "plain")
                continue
            try:
                inputs[name] = synth(type_, opts)
            except LookupError:
                if section == "required":
                    raise
    return inputs


async def run(node_id, class_def, latents, variant):
    out_dir = Path(tempfile.mkdtemp(prefix="res4-chain-out-"))
    folder_paths.set_output_directory(str(out_dir))
    folder_paths.set_temp_directory(str(out_dir / "temp"))
    inputs = build_inputs(class_def, latents, variant)
    torch.manual_seed(0)
    try:
        input_data_all, _missing, v3_data = execution.get_input_data(inputs, class_def, "1")
        obj = class_def()
        with torch.inference_mode():  # as core's executor runs every node (execution.py:1053)
            output, ui, _sub, pending = await execution.get_output_data("res4-chain", "1", obj, input_data_all,
                                                                         v3_data=v3_data)
        if pending:
            raise RuntimeError("pending task")
        files = {str(p.relative_to(out_dir)): p.read_bytes() for p in sorted(out_dir.rglob("*")) if p.is_file()}
        return {"ok": True, "output": output, "ui": ui, "files": files}
    except Exception as error:  # noqa: BLE001
        return {"ok": False, "error": f"{type(error).__name__}: {str(error)[:200]}"}


async def node_row(node_id, class_def):
    names = latent_inputs(class_def)
    try:
        build_inputs(class_def, names, "plain")
    except LookupError as error:
        return {"node": node_id, "verdict": "NOT_SYNTHESISABLE", "why": str(error)}
    except Exception as error:  # noqa: BLE001
        return {"node": node_id, "verdict": "NOT_SYNTHESISABLE", "why": f"{type(error).__name__}: {error}"[:200]}
    placements = [("all", names)] + ([("first", names[:1])] if len(names) > 1 else [])
    row = {"node": node_id, "latent_inputs": names, "placements": {}}
    verdicts = []
    for placement, latents in placements:
        runs = {variant: await run(node_id, class_def, latents, variant) for variant in ("plain", "v2", "original")}
        detail = {"ok": {v: r["ok"] for v, r in runs.items()}}
        if not any(r["ok"] for r in runs.values()):
            same_failure = len({r["error"] for r in runs.values()}) == 1
            detail["error"] = runs["plain"]["error"]
            verdict = "FAIL_IDENTICAL" if same_failure else "DIFFER"
            if not same_failure:
                detail["errors"] = {v: r["error"] for v, r in runs.items()}
        elif not all(r["ok"] for r in runs.values()):
            verdict = "DIFFER"
            detail["errors"] = {v: r.get("error") for v, r in runs.items()}
        else:
            base = runs["plain"]
            carried, equal = {}, {}
            for variant in ("v2", "original"):
                key = EXTRA[variant][0]
                stripped, found = strip(runs[variant]["output"], key)
                ui_stripped, _ = strip(runs[variant]["ui"], key)
                equal[variant] = (same(stripped, base["output"]) and same(ui_stripped, base["ui"])
                                  and runs[variant]["files"] == base["files"])
                carried[variant] = {"count": len(found), "positions": [
                    i for i, values in enumerate(runs[variant]["output"] or [])
                    if strip(values, key)[1]]}
                if variant == "v2":
                    reference = EXTRA["v2"][1]()
                    carried[variant]["unchanged"] = all(same(f, reference) for f in found)
            detail.update(outputs_equal_without_the_key=equal, carried=carried)
            same_pattern = carried["v2"]["positions"] == carried["original"]["positions"] and \
                carried["v2"]["count"] == carried["original"]["count"]
            ok = all(equal.values()) and same_pattern and carried["v2"].get("unchanged", True)
            verdict = ("IDENTICAL_PASSED_ON" if carried["v2"]["count"] else "IDENTICAL_DROPPED") if ok else "DIFFER"
        detail["verdict"] = verdict
        row["placements"][placement] = detail
        verdicts.append(verdict)
    row["verdict"] = "DIFFER" if "DIFFER" in verdicts else verdicts[0]
    return row


async def main():
    failed_extras = list(await nodes.init_builtin_extra_nodes() or [])
    rows = []
    for node_id, class_def in sorted(nodes.NODE_CLASS_MAPPINGS.items()):
        try:
            if not latent_inputs(class_def):
                continue
        except Exception:  # noqa: BLE001
            continue
        row = await node_row(node_id, class_def)
        rows.append(row)
        print(row["verdict"], node_id, row.get("why", ""), flush=True)
    totals = {}
    for row in rows:
        totals[row["verdict"]] = totals.get(row["verdict"], 0) + 1
    doc = {"totals": totals, "nodes_with_latent_inputs": len(rows),
           "ran_successfully": sorted(r["node"] for r in rows if r["verdict"].startswith("IDENTICAL")),
           "differ": sorted(r["node"] for r in rows if r["verdict"] == "DIFFER"),
           "core_modules_failed": failed_extras, "rows": rows}
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "chain-key-core.json").write_text(json.dumps(doc, indent=1, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: doc[k] for k in ("totals", "nodes_with_latent_inputs", "differ", "core_modules_failed")},
                     indent=1))
    return 1 if doc["differ"] or failed_extras else 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except Exception:
        traceback.print_exc()
        sys.exit(2)
