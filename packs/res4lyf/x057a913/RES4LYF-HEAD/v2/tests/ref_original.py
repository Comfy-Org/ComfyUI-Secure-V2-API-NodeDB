"""Tier-1 reference run: ORIGINAL RES4LYF ClownsharKSampler_Beta, in-process, on core 6257422b (gate only).

Writes /results/ref/<n>.safetensors (tensors) and /results/ref.json (metadata), read by the V2 run. That run uses
a separate clean core process, because importing RES4LYF patches core globally.
Run: DEPS=<deps-orig> run_in_gate.sh <RES4LYF-HEAD> <parity dir> <out> ref_original.py
"""
import json
import os
import shutil
import sys
import tempfile
import time
import traceback
import types
from pathlib import Path

sys.path.insert(0, "/tests")
CORE = Path(os.environ.get("COMFY_CORE_ROOT", "/core"))
sys.path[:0] = [str(CORE)]
if Path("/deps").is_dir():
    sys.path.append("/deps")

from comfy.cli_args import args  # noqa: E402

args.cpu = True
import torch  # noqa: E402
from safetensors.torch import save_file  # noqa: E402

import folder_paths  # noqa: E402,F401
import server  # noqa: E402
from aiohttp import web  # noqa: E402

server.PromptServer.instance = types.SimpleNamespace(
    routes=web.RouteTableDef(), supports={"custom_nodes_from_web"}, send_sync=lambda *a, **k: None,
    client_id=None, last_node_id=None)

import comfy.model_base as mb  # noqa: E402
import comfy.model_management  # noqa: E402
import comfy.model_patcher as mp  # noqa: E402
import comfy.samplers  # noqa: E402
import comfy.supported_models as sm  # noqa: E402

import cases  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="res4-ref-"))
shutil.copytree("/pack", TMP / "RES4LYF", ignore=shutil.ignore_patterns("v2"))
sys.path.insert(0, str(TMP))
import importlib  # noqa: E402

RES = importlib.import_module("RES4LYF")
SAMPLERS_MOD = importlib.import_module("RES4LYF.beta.samplers")
OUT = Path("/results")
REF = OUT / "ref"
REF.mkdir(parents=True, exist_ok=True)
COUNT = {"n": 0}


def counting(args_):
    COUNT["n"] += 1
    if COUNT.get("interrupt_at") == COUNT["n"]:  # cancellation case: an interrupt surfaces at this evaluation
        raise comfy.model_management.InterruptProcessingException()
    return comfy.samplers.calc_cond_batch(args_["model"], args_["conds"], args_["input"], args_["sigma"],
                                          args_["model_options"])


def cancellation():
    case = next(c for c in cases.case_table() if c["name"] == cases.CANCEL["case"])
    model = model_for(case["model"])
    pos, neg, latent = cases.inputs(mask=case["mask"], batch=case["batch"], zero_latent=case["zero_latent"])
    COUNT["n"] = 0
    COUNT["interrupt_at"] = cases.CANCEL["interrupt_at"]
    try:
        run_node(model, pos, neg, latent, case["widgets"])
        raised = None
    except BaseException as error:  # noqa: BLE001
        raised = type(error).__name__
    finally:
        COUNT["interrupt_at"] = None
    return {"case": case["name"], "interrupt_at": cases.CANCEL["interrupt_at"], "raised": raised,
            "evaluations": COUNT["n"]}


MODELS = {}


def model_for(kind):
    if kind not in MODELS:
        m = cases.tiny_model(mb, mp, sm, kind)
        m.set_model_sampler_calc_cond_batch_function(counting)
        MODELS[kind] = m
    return MODELS[kind]


def run_node(model, pos, neg, latent, widgets, options=None):
    extra = {"options_group": {"options0": options}} if options is not None else {}
    out = SAMPLERS_MOD.ClownsharKSampler_Beta.execute(model=model, positive=pos, negative=neg,
                                                      latent_image=latent, **widgets, **extra)
    return out.result if hasattr(out, "result") else out


def jsonable(value):
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, float):
        return {"float": value.hex()}
    if isinstance(value, torch.Tensor):  # exact: dtype, shape and the bytes
        data = value.detach().cpu().contiguous()
        return {"tensor": str(data.dtype), "shape": list(data.shape),
                "sha256": __import__("hashlib").sha256(data.view(torch.uint8).numpy().tobytes()).hexdigest()}
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return {"type": type(value).__name__}


class _CudaAsCpu:
    """CPU gate adaptation (labelled): ClownOptions_DetailBoost_Beta builds its float64 tables on
    torch.device('cuda') (samplers_extensions.py:292), which a CPU-only gate lacks. While the original options
    nodes run, that module's ``torch`` maps a CUDA device to the CPU; the values do not depend on the device."""

    def __enter__(self):
        import types as _t
        self.module = importlib.import_module("RES4LYF.beta.samplers_extensions")
        self.saved = self.module.torch
        view = _t.ModuleType("torch_cuda_as_cpu")
        view.__getattr__ = lambda name: getattr(torch, name)

        def device(spec=None, *args, **kwargs):
            if isinstance(spec, str) and spec.startswith("cuda"):
                return torch.device("cpu")
            return torch.device(spec, *args, **kwargs)

        view.device = device
        self.module.torch = view
        return self

    def __exit__(self, *exc):
        self.module.torch = self.saved
        return False


def run_option_chain(chain):
    opts = None
    for node_id, widgets in chain:
        cls = RES.NODE_CLASS_MAPPINGS[node_id]
        with _CudaAsCpu():
            opts = getattr(cls(), cls.FUNCTION)(**widgets, options=opts)[0]
    return opts


def record(index, name, result, calls, seconds):
    out, den, options = result
    tensors = {"out_samples": out["samples"].contiguous().clone(), "den_samples": den["samples"].contiguous().clone()}
    if "noise_mask" in out:
        tensors["out_noise_mask"] = out["noise_mask"].contiguous().clone()
    if "noise_mask" in den:
        tensors["den_noise_mask"] = den["noise_mask"].contiguous().clone()
    aliasing = ("noise_mask" in out and "noise_mask" in den and out["noise_mask"] is den["noise_mask"])
    save_file(tensors, str(REF / f"{index}.safetensors"))
    return {"index": index, "name": name, "ok": True, "calls": calls, "seconds": round(seconds, 4),
            "noise_mask_shared_between_outputs": aliasing,
            "out_keys": list(out), "den_keys": list(den), "options": jsonable(options),
            "dtypes": {k: str(v.dtype) for k, v in tensors.items()},
            "shapes": {k: list(v.shape) for k, v in tensors.items()}}


def provider_schedules():
    """calculate_sigmas with the scheduler names the original registers globally (RES4LYF __init__.py:24-30)."""
    out = {}
    for kind, name, steps in cases.PROVIDER_CASES:
        model_sampling = model_for(kind).get_model_object("model_sampling")
        key = f"{kind}:{name}:{steps}"
        try:
            sigmas = comfy.samplers.calculate_sigmas(model_sampling, name, steps)
            out[key] = {"ok": True, "dtype": str(sigmas.dtype), "values": [float(v).hex() for v in sigmas.tolist()]}
        except Exception as error:  # noqa: BLE001
            out[key] = {"ok": False, "error": type(error).__name__}
    return out


def queue_verdicts():
    """Core's own validate_inputs on the ORIGINAL node, for each queue case (stub upstream nodes; no weights)."""
    import asyncio
    import execution
    import nodes as core_nodes
    ckpt = TMP / "ckpt"
    ckpt.mkdir()
    (ckpt / "stub.safetensors").write_bytes(b"stub\n")
    folder_paths.folder_names_and_paths["checkpoints"] = ([str(ckpt)], set(folder_paths.supported_pt_extensions))
    core_nodes.NODE_CLASS_MAPPINGS["ClownsharKSampler_Beta"] = SAMPLERS_MOD.ClownsharKSampler_Beta
    rows = []
    for case in cases.queue_cases():
        prompt = {
            "1": {"class_type": "ClownsharKSampler_Beta", "inputs": dict(
                case["widgets"], model=["2", 0], positive=["3", 0], negative=["3", 0], latent_image=["4", 0])},
            "2": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "stub.safetensors"}},
            "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "a", "clip": ["2", 1]}},
            "4": {"class_type": "EmptyLatentImage", "inputs": {"width": 64, "height": 64, "batch_size": 1}},
        }
        ok, errors, _node = asyncio.run(execution.validate_inputs("res4-queue", prompt, "1", {}))
        rows.append({"name": case["name"], "ok": bool(ok),
                     "errors": sorted([e.get("type"), (e.get("extra_info") or {}).get("input_name")] for e in errors)})
    return rows


def main():
    rows = []
    index = 0
    for case in cases.case_table():
        model = model_for(case["model"])
        pos, neg, latent = cases.inputs(mask=case["mask"], batch=case["batch"], zero_latent=case["zero_latent"])
        COUNT["n"] = 0
        t0 = time.perf_counter()
        try:
            result = run_node(model, pos, neg, latent, case["widgets"])
            rows.append(record(index, case["name"], result, COUNT["n"], time.perf_counter() - t0))
        except Exception as error:
            rows.append({"index": index, "name": case["name"], "ok": False,
                         "error": f"{type(error).__name__}: {str(error)[:300]}", "calls": COUNT["n"]})
        index += 1
    for chain in cases.CHAIN:
        model = model_for(chain["model"])
        pos, neg, latent = cases.inputs()
        COUNT["n"] = 0
        t0 = time.perf_counter()
        try:
            up = run_node(model, pos, neg, latent, chain["up"])
            down = run_node(model, pos, neg, up[0], chain["down"])
            row = record(index, chain["name"], down, COUNT["n"], time.perf_counter() - t0)
            row["upstream_keys"] = list(up[0])
            rows.append(row)
        except Exception as error:
            rows.append({"index": index, "name": chain["name"], "ok": False,
                         "error": f"{type(error).__name__}: {str(error)[:300]}"})
        index += 1
    for case in cases.option_cases():
        model = model_for(case["model"])
        pos, neg, latent = cases.inputs()
        COUNT["n"] = 0
        t0 = time.perf_counter()
        try:
            opts = run_option_chain(case["chain"])
            chain_out = jsonable(opts)
            result = run_node(model, pos, neg, latent, case["widgets"], options=opts)
            row = record(index, case["name"], result, COUNT["n"], time.perf_counter() - t0)
            row["option_chain_output"] = chain_out
            rows.append(row)
        except Exception as error:
            rows.append({"index": index, "name": case["name"], "ok": False,
                         "error": f"{type(error).__name__}: {str(error)[:300]}", "calls": COUNT["n"]})
        index += 1
    queue = queue_verdicts()
    doc = {"torch": torch.__version__, "cases": rows, "queue": queue, "provider_schedules": provider_schedules(),
           "cancellation": cancellation()}
    (OUT / "ref.json").write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"cases": len(rows), "ok": sum(1 for r in rows if r["ok"]),
                      "errors": [(r["name"], r["error"]) for r in rows if not r["ok"]],
                      "queue": {r["name"]: (r["ok"], r["errors"]) for r in queue}}, indent=1))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
