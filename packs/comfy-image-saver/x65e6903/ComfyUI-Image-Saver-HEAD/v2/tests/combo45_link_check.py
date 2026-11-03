"""Selector-output link check: LABELLED EVIDENCE, not tier-1 parity.

Does core's own prompt validation accept links from the V2 selector outputs into stock inputs?
  * "Sampler Selector" / "Scheduler Selector" -> KSampler.sampler_name / KSampler.scheduler
  * "Checkpoint Selector" -> CheckpointLoaderSimple.ckpt_name
The original giriss selectors return their choice LIST as the output type, which core accepts on overlap
(comfy_execution/validation.py). Run it on two cores through run_in_gate.sh:
  default core (6257422b)                      -> results/combo45-default/combo45-links.json
  GATE_CORE=<ComfyUI checkout at 45c05a86>     -> results/combo45-45c05a86/combo45-links.json
The V2 classes are the HOST PROXIES that packdb builds from v2/secure-nodes.json, as in production.
"""
import asyncio
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

CORE = Path(os.environ.get("COMFY_CORE_ROOT", "/core"))
PACK = Path(os.environ.get("CIS_PACK", "/pack"))
RESULTS = Path(os.environ.get("CIS_RESULTS", "/results"))
# /deps (when mounted) goes FIRST: for the 45c05a86 run it carries the comfy-kitchen version that core pins
# (requirements.txt:25, 0.2.40), which must shadow the gate image's older copy.
sys.path[:0] = (["/deps"] if Path("/deps").is_dir() else []) + [str(CORE), "/overlay"]

from comfy.cli_args import args  # noqa: E402

args.cpu = True
import folder_paths  # noqa: E402
import nodes as core_nodes  # noqa: E402
import execution  # noqa: E402
from comfy_execution.validation import validate_node_input  # noqa: E402


def core_commit():
    git = CORE / ".git"
    try:
        head = (git / "HEAD").read_text().strip()
        if head.startswith("ref: "):
            ref = head[5:]
            path = git / ref
            if path.is_file():
                return path.read_text().strip()
            for line in (git / "packed-refs").read_text().splitlines():
                if line.endswith(" " + ref):
                    return line.split()[0]
        return head
    except Exception as error:  # noqa: BLE001
        return f"unknown ({type(error).__name__})"


def proxies():
    """Host proxy classes from the committed manifest, exactly as the runtime registers them."""
    from comfy_secure_nodes import packdb
    tmp = Path(tempfile.mkdtemp(prefix="combo45-snap-"))
    snap = tmp / "comfy-image-saver" / "x65e6903"
    shutil.copytree(PACK, snap / PACK.name)
    loaded = packdb.load_pack(snap, mount_name="custom_nodes.combo45_check")
    return dict(loaded.node_mappings), "packdb host proxies from v2/secure-nodes.json"


def guest_classes():
    v2 = PACK / "v2"
    spec = importlib.util.spec_from_file_location("combo45_v2", v2 / "__init__.py", submodule_search_locations=[str(v2)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return dict(module.NODE_CLASS_MAPPINGS), "guest classes (packdb proxies unavailable on this core)"


def main():
    import importlib.metadata as metadata
    import comfy_kitchen
    report = {"core_path": str(CORE), "core_commit": core_commit(),
              "core_io_sha256": hashlib.sha256((CORE / "comfy_api/latest/_io.py").read_bytes()).hexdigest(),
              "comfy_kitchen": {"file": comfy_kitchen.__file__, "version": metadata.version("comfy-kitchen")}}
    ckpt = Path(tempfile.mkdtemp(prefix="combo45-ckpt-"))
    (ckpt / "model_a.safetensors").write_bytes(b"x")
    folder_paths.folder_names_and_paths["checkpoints"] = ([str(ckpt)], set(folder_paths.supported_pt_extensions))
    try:
        classes, source = proxies()
    except Exception:  # noqa: BLE001
        report["proxy_error"] = traceback.format_exc()[-1500:]
        classes, source = guest_classes()
    report["classes"] = source
    ksampler = core_nodes.NODE_CLASS_MAPPINGS["KSampler"].INPUT_TYPES()["required"]
    loader = core_nodes.NODE_CLASS_MAPPINGS["CheckpointLoaderSimple"].INPUT_TYPES()["required"]
    targets = {"Sampler Selector": ksampler["sampler_name"][0], "Scheduler Selector": ksampler["scheduler"][0],
               "Checkpoint Selector": loader["ckpt_name"][0]}
    direct = {}
    for node_id, target in targets.items():
        received = classes[node_id].RETURN_TYPES[0]
        direct[node_id] = {
            "return_type": received if not isinstance(received, list) else {"list_len": len(received), "head": received[:3]},
            "object_info_output": (lambda o: o if not isinstance(o, list) else [
                x if not isinstance(x, list) else {"list_len": len(x)} for x in o])(classes[node_id].GET_NODE_INFO_V1()["output"]),
            "validate_node_input": validate_node_input(received, target),
        }
    report["direct"] = direct
    saved = {k: core_nodes.NODE_CLASS_MAPPINGS.get(k) for k in targets}
    core_nodes.NODE_CLASS_MAPPINGS.update({k: classes[k] for k in targets})
    try:
        stock = {
            "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "model_a.safetensors"}},
            "5": {"class_type": "CLIPTextEncode", "inputs": {"text": "a", "clip": ["4", 1]}},
            "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "b", "clip": ["4", 1]}},
            "7": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512, "batch_size": 1}},
            "8": {"class_type": "KSampler", "inputs": {
                "model": ["4", 0], "positive": ["5", 0], "negative": ["6", 0], "latent_image": ["7", 0],
                "seed": 1, "steps": 1, "cfg": 7.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0}},
        }
        prompts = {}
        a = json.loads(json.dumps(stock))
        a["1"] = {"class_type": "Sampler Selector", "inputs": {"sampler_name": "euler"}}
        a["2"] = {"class_type": "Scheduler Selector", "inputs": {"scheduler": "karras"}}
        a["8"]["inputs"].update(sampler_name=["1", 0], scheduler=["2", 0])
        prompts["A selectors -> KSampler"] = (a, "8")
        b = json.loads(json.dumps(stock))
        b["3"] = {"class_type": "Checkpoint Selector", "inputs": {"ckpt_name": "model_a.safetensors"}}
        b["4"]["inputs"]["ckpt_name"] = ["3", 0]
        prompts["B checkpoint selector -> CheckpointLoaderSimple"] = (b, "4")
        prompts["control stock prompt"] = (stock, "8")
        full = {}
        for label, (prompt, output) in prompts.items():
            ok, errors, node_id = asyncio.run(execution.validate_inputs("combo45", prompt, output, {}))
            full[label] = {"ok": ok, "errors": [{"type": e.get("type"), "details": e.get("details")} for e in errors]}
        report["core_validate_inputs"] = full
    finally:
        for k, v in saved.items():
            if v is None:
                core_nodes.NODE_CLASS_MAPPINGS.pop(k, None)
            else:
                core_nodes.NODE_CLASS_MAPPINGS[k] = v
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "combo45-links.json").write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps(report, indent=1, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
