"""Repair r3 (B12 asset guard): the TTL latent upscalers refuse by name, and the City96 path still runs.

Run in the lane gate: run_in_gate.sh <pack root (pristine + v2/)> <this tests dir> <results dir>
test_efficiency_ttl_refusal.py

V2 is loaded as a bare namespace package against the guest SDK base 0cd9adec, as the production loader does. It runs
inside a real in-process SDK runtime from that base (InProcessCtxProvider and InProcessRefResolver over ComfyUI core
6257422b), so assets.resolve and assets.load_state_dict are the SDK's own. Only models.download_huggingface_weights is
replaced: a recorder returns the catalogue name the host would install, and nothing goes to the network. A synthetic
City96 weight file (SafeTensors, seeded) sits at that name in the latent_upscale_models folder.

Cases:
- TTL (both versions) through _hires_script: the named refusal, with no weight request;
- TTL through _resize_latent_raw: the named refusal, with no load_state_dict call;
- a TTL choice with upscale_type "pixel" or "both", or with zero iterations: no refusal (the choice is unused);
- City96 through _hires_script: exactly the declared City96 weight is requested (repo, file, folder, revision, sha256);
- City96 through _resize_latent_raw (assets.resolve, assets.load_state_dict): the latent equals the original
  py/city96_latent_upscaler.py Upscaler applied to the same weights (exact float32);
- the manifest declares no .pt weight for HighRes-Fix Script: its required_weights are exactly the six City96
  SafeTensors files the module declares (repo, file, folder, revision, sha256).
A tampered expected latent must turn the City96 comparison red. Writes /results/ttl-refusal.json; exit 0 when all
cases hold.
"""
import ast
import asyncio
import dataclasses
import importlib
import json
import os
from pathlib import Path
import shutil
import sys
import types

PACK = Path("/pack")
RESULTS = Path(os.environ.get("RESULTS", "/results"))
BASE = "/bases/0cd9adec273a703eb3d1c715d83ff1c7d2bb00746330c866c7e3ac644c80ebbb/common-site-packages"
WORK = Path("/tmp/eff-ttl")
REFUSAL = "HighRes-Fix Script is not available in this secure build with the latent upscaler"


def _load_v2():
    sys.argv = [sys.argv[0], "--cpu"]
    sys.path[:0] = [BASE, "/overlay", "/core"]
    os.chdir("/tmp")
    try:
        from comfy.cli_args import args
        args.cpu = True
    except Exception:  # noqa: BLE001
        pass
    dst = WORK / "v2"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(PACK / "v2", dst, ignore=shutil.ignore_patterns("__pycache__"))
    package = types.ModuleType("eff_v2")
    package.__path__ = [str(dst)]
    package.__package__ = "eff_v2"
    sys.modules["eff_v2"] = package
    return importlib.import_module("eff_v2._secure_nodes")


def _original_upscaler_class():
    """The original's City96 Upscaler class (py/city96_latent_upscaler.py), executed from its own source. The module's
    hf_hub_download import is not needed for the class, so only the class is taken."""
    import torch
    source = (PACK / "py" / "city96_latent_upscaler.py").read_text()
    tree = ast.parse(source)
    node = next(item for item in tree.body if isinstance(item, ast.ClassDef) and item.name == "Upscaler")
    namespace = {"torch": torch, "nn": torch.nn}
    exec(compile(ast.Module(body=[node], type_ignores=[]), "city96_latent_upscaler.py", "exec"), namespace)
    return namespace["Upscaler"]


class WeightRecorder:
    """models.download_huggingface_weights without the network: records the request, returns the catalogue name."""

    def __init__(self):
        self.calls = []

    async def download_huggingface_weights(self, repo_id, filename, folder, revision=None, sha256=None):
        self.calls.append({"repo_id": repo_id, "filename": filename, "folder": folder, "revision": revision,
                           "sha256": sha256})
        return f"huggingface/{repo_id}/{revision}/{filename}"


def _hires_kwargs(**overrides):
    values = dict(upscale_type="latent", hires_ckpt_name="(use same)", latent_upscaler="ttl_nn.SDXL",
                  pixel_upscaler="", upscale_by=1.5, use_same_seed=True, seed=7, hires_steps=4, denoise=0.5,
                  iterations=1, use_controlnet=False, control_net_name="None", strength=1.0, preprocessor="none",
                  preprocessor_imgs=False)
    values.update(overrides)
    return values


async def run_cases(port, sdk_module, recorder, loads):
    import torch
    rows = {}

    async def expect_refusal(name, coroutine, method):
        before_requests, before_loads = len(recorder.calls), len(loads)
        try:
            await coroutine
            rows[name] = {"ok": False, "why": "no refusal"}
        except RuntimeError as error:
            message = str(error)
            ok = (message.startswith(REFUSAL) and repr(method) in message
                  and len(recorder.calls) == before_requests and len(loads) == before_loads)
            rows[name] = {"ok": ok, "error": message[:300], "weight_requests": len(recorder.calls) - before_requests,
                          "state_loads": len(loads) - before_loads}

    for method in ("ttl_nn.SD 1.x", "ttl_nn.SDXL"):
        await expect_refusal(f"hires-script-refuses-{method}", port._hires_script(**_hires_kwargs(latent_upscaler=method)),
                             method)
    latent = await sdk_module.LatentRef.from_value({"samples": torch.zeros(1, 4, 8, 8)})
    await expect_refusal("resize-latent-refuses-ttl", port._resize_latent_raw(latent, 1.5, "ttl_nn.SDXL", "unused"),
                         "ttl_nn.SDXL")

    for name, overrides in (("ttl-unused-pixel", dict(upscale_type="pixel")),
                            ("ttl-unused-both", dict(upscale_type="both")),
                            ("ttl-unused-zero-iterations", dict(iterations=0))):
        before = len(recorder.calls)
        output = (await port._hires_script(**_hires_kwargs(**overrides)))[0]
        rows[name] = {"ok": len(recorder.calls) == before and output["hiresfix"]["latent_weight"] is None,
                      "latent_upscaler": output["hiresfix"]["latent_upscaler"]}

    # City96: the declared weight is requested, then the resize runs through assets.resolve + assets.load_state_dict
    before = len(recorder.calls)
    output = (await port._hires_script(**_hires_kwargs(latent_upscaler="city96.v1", upscale_by=1.5)))[0]
    requested = recorder.calls[before:]
    declared = port._CITY96_WEIGHTS[("v1", "1.5")]
    expected_request = {"repo_id": declared.repo_id, "filename": declared.filename, "folder": declared.folder,
                        "revision": declared.revision, "sha256": declared.sha256}
    weight_name = output["hiresfix"]["latent_weight"]
    rows["hires-script-city96-requests-declared-weight"] = {
        "ok": requested == [expected_request] and weight_name == f"huggingface/{declared.repo_id}/"
                                                                 f"{declared.revision}/{declared.filename}",
        "requested": requested, "latent_weight": weight_name}
    return rows, weight_name


def main():
    import torch
    from safetensors.torch import load_file, save_file

    port = _load_v2()
    from comfy_api.latest import _sdk
    import comfy_api
    import folder_paths

    # the synthetic City96 v1 x1.5 weights, in the folder the host installs declared weights into
    original_upscaler = _original_upscaler_class()
    torch.manual_seed(20261103)
    reference = original_upscaler(1.5)
    declared = port._CITY96_WEIGHTS[("v1", "1.5")]
    models_dir = WORK / "latent_upscale_models"
    weight_path = models_dir / "huggingface" / declared.repo_id / declared.revision / declared.filename
    weight_path.parent.mkdir(parents=True, exist_ok=True)
    save_file({key: value.contiguous() for key, value in reference.state_dict().items()}, str(weight_path))
    folder_paths.folder_names_and_paths["latent_upscale_models"] = ([str(models_dir)], {".safetensors"})

    plan = _sdk.ExecutionPlan(prompt_id="ttl-refusal", node_id="1", node_type="HighRes-Fix Script",
                              permissions=("assets",), node_module="eff_v2._secure_nodes")
    recorder = WeightRecorder()
    ctx = dataclasses.replace(_sdk.InProcessCtxProvider().build(plan), models=recorder)
    loads = []
    real_load = ctx.assets.load_state_dict

    async def counted_load(*args, **kwargs):
        loads.append(1)
        return await real_load(*args, **kwargs)
    ctx.assets.load_state_dict = counted_load

    async def run():
        with _sdk.bind_runtime(_sdk.InProcessRefResolver(), ctx):
            rows, weight_name = await run_cases(port, _sdk, recorder, loads)
            generator = torch.Generator().manual_seed(11)
            samples = torch.randn(1, 4, 12, 16, generator=generator)
            latent = await _sdk.LatentRef.from_value({"samples": samples.clone()})
            before = len(loads)
            resized = await (await port._resize_latent_raw(latent, 1.5, "city96.v1", weight_name)).value()
            return rows, samples, resized["samples"], len(loads) - before

    rows, samples, v2_samples, state_loads = asyncio.run(run())
    original = original_upscaler(1.5)
    original.load_state_dict(load_file(str(weight_path)))
    expected = original(samples)
    exact = (v2_samples.shape == expected.shape and v2_samples.dtype == expected.dtype
             and torch.equal(v2_samples, expected.detach()))
    tampered = expected.detach().clone()
    tampered.view(-1)[0] += 1e-3
    rows["city96-resize-equals-original"] = {"ok": exact and state_loads == 1, "shape": list(v2_samples.shape),
                                             "state_loads": state_loads}
    rows["negative-control-turns-red"] = {"ok": not torch.equal(v2_samples, tampered)}

    manifest = json.loads((PACK / "v2" / "secure-nodes.json").read_text())
    weights = manifest["nodes"]["HighRes-Fix Script"].get("required_weights", [])
    fields = ("repo_id", "filename", "folder", "revision", "sha256")
    declared_rows = sorted(tuple(getattr(weight, field) for field in fields)
                           for weight in port._CITY96_WEIGHTS.values())
    manifest_rows = sorted(tuple(row.get(field) for field in fields) for row in weights)
    rows["manifest-declares-city96-only"] = {
        "ok": (len(weights) == 6 and manifest_rows == declared_rows
               and all(row["filename"].endswith(".safetensors") for row in weights)),
        "filenames": sorted(row["filename"] for row in weights)}

    import hashlib
    sdk_file = Path(_sdk.__file__)
    report = {"sdk_base": str(sdk_file), "sdk_sha256": hashlib.sha256(sdk_file.read_bytes()).hexdigest(),
              "sdk_from_base_0cd9adec": str(sdk_file).startswith(BASE), "comfy_api_paths": list(comfy_api.__path__),
              "core": "/core (ComfyUI 6257422b)", "assets": f"{type(ctx.assets).__module__}.{type(ctx.assets).__name__}",
              "cases": rows, "all_ok": all(row["ok"] for row in rows.values())}
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "ttl-refusal.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"all_ok": report["all_ok"], "sdk_base": report["sdk_base"], "sdk_sha256": report["sdk_sha256"],
                      "assets": report["assets"], "cases": {name: row["ok"] for name, row in rows.items()}}, indent=1))
    sys.exit(0 if report["all_ok"] and report["sdk_from_base_0cd9adec"] else 1)


if __name__ == "__main__":
    main()
