"""ComfyUI-DepthAnythingV2 v2: weight-loading regression (repair r1).

run_in_gate.sh <pack root ComfyUI-DepthAnythingV2-HEAD (pristine + v2/)> <v2/tests> <results> \
    test_dav2_weight_resolution.py [expect-red]

The defect: the loader passed the logical catalogue name that models.download_huggingface_weights returns straight
to assets.load_state_dict, which takes an AssetRef (resolve the name with assets.resolve first). On the overlay host
the nodes also lacked the capabilities those calls need ("assets"; "models.download" only for declared weights).

1. Behaviour, per guest base (/bases: 0cd9adec and 0b86765f), each in a fresh `python3 -I` process, through the real
   in-process SDK path, called the way Core's execution.py calls an SDK node: an ExecutionPlan from the class's
   SDK_PERMISSIONS and SDK_REQUIRED_WEIGHTS, the providers' ref resolver, ctx and ops, bind_runtime, wrap_inputs,
   execution_backend.dispatch, unwrap_outputs, then the ref table cleared. The run has four steps: the loader node;
   the depth node; the depth node again after the guest's module cache is cleared (as in a new guest process); the
   depth node with its head forced flat (upstream's normalisation gives NaN there; from_value refuses it).
   - The weight is a synthetic SafeTensors file, installed where the host's download_huggingface_weights puts a
     weight (<geometry_estimation root>/huggingface/<repo>/<revision>/<file>). The real install check (SafeTensors
     structure and SHA-256) passes with no network. Only the pack's declaration of that one checkpoint is replaced,
     with the fixture's repository, revision and digest.
   - Checked:
     - the loaded parameters equal the fixture's tensors;
     - the depth image is finite BHWC in [0, 1] at the input's size;
     - the rebuild after a cache miss gives the same bytes, through assets.resolve and assets.load_state_dict only
       (no download).
   - On 0b86765f, the depth node's ImageRef.from_value is absent (minimum base 0cd9adec): designed, recorded.
2. Host contract, with the real overlay code (/overlay):
   - Each SDK call the nodes made in (1) needs the capability that the overlay host's handler requires. The
     transport/host.py handlers _h_models_download_huggingface_weights, _h_assets_resolve and
     _h_assets_load_state_dict are read for their _require(...) calls.
   - Each node's permissions are derived from the committed manifest row, as the host does it (packdb._proxy_class),
     then granted: consent.filter_capabilities, with the deployment allowing and the user granting models.download.
     The granted set must cover those capabilities.
   - The loader row's required_weights must equal the pack's nine declarations.
   - The committed secure-nodes.json must equal the real encoder's output.
expect-red: run against the published (unrepaired) pack. It passes only if (1) fails in the loader at the asset load
on both bases, and (2) finds the loader's missing capabilities and declarations.
Writes /results/regression.json; exits 1 unless the verdict is the expected one.
"""
import ast
import asyncio
import copy
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

sys.dont_write_bytecode = True
PACK = Path("/pack")
V2 = PACK / "v2"
RESULTS = Path("/results")
BASES = {
    "0cd9adec": "/bases/0cd9adec273a703eb3d1c715d83ff1c7d2bb00746330c866c7e3ac644c80ebbb/common-site-packages",
    "0b86765f": "/bases/0b86765f07a7e81a1ef731161472c4af3ceba43b506238eed7fd548dd3bc3727/common-site-packages",
}
HOST = Path("/overlay/comfy_secure_nodes/transport/host.py")
CHECKPOINT = "depth_anything_v2_vits_fp32.safetensors"
FIXTURE_REPO = "jack-regression/dav2-synthetic"
FIXTURE_REVISION = "0123456789abcdef0123456789abcdef01234567"
PACK_NAME = "comfyui-depthanythingv2"
LOADER, DEPTH = "DownloadAndLoadDepthAnythingV2Model", "DepthAnything_V2"
HANDLERS = {
    "models.download_huggingface_weights": "_h_models_download_huggingface_weights",
    "assets.resolve": "_h_assets_resolve",
    "assets.load_state_dict": "_h_assets_load_state_dict",
}


def _environment(base):
    sys.argv = [sys.argv[0], "--cpu"]
    sys.path[:0] = [BASES[base], "/overlay", "/core"]
    os.chdir(tempfile.mkdtemp(prefix="dav2-cwd-"))
    from comfy.cli_args import args
    args.cpu = True


def _load_pack(alias):
    dst = Path(tempfile.mkdtemp(prefix="dav2-v2-")) / "v2"
    shutil.copytree(V2, dst, ignore=shutil.ignore_patterns("__pycache__", "tests"))
    spec = importlib.util.spec_from_file_location(alias, dst / "__init__.py", submodule_search_locations=[str(dst)])
    package = importlib.util.module_from_spec(spec)
    sys.modules[alias] = package
    spec.loader.exec_module(package)
    return dst, package


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def side(base, out_path):
    """Behaviour on one guest base (see the module docstring, part 1)."""
    _environment(base)
    import torch
    import folder_paths
    from safetensors.torch import save_file
    from comfy_api.latest import _sdk, sdk
    from comfy_execution.utils import CurrentNodeContext

    dst, package = _load_pack("dav2_v2")
    nodes = sys.modules["dav2_v2.nodes"]
    loader, depth = package.NODE_CLASS_MAPPINGS[LOADER], package.NODE_CLASS_MAPPINGS[DEPTH]

    root = Path(tempfile.mkdtemp(prefix="dav2-models-")) / "geometry_estimation"
    folder_paths.add_model_folder_path("geometry_estimation", str(root), is_default=True)

    # The fixture: a complete state dict for the vits architecture, every tensor seeded and well-conditioned. It
    # has to be complete: the vendored layers (manual_cast, like Core's) skip weight initialisation, so any key a
    # checkpoint lacks stays uninitialised memory. The published checkpoints carry every key. Scales:
    #   norm weights and LayerScale gammas: 1 + noise; biases: small noise;
    #   tokens and position embeddings: 0.02 N(0, 1); weights: N(0, 1/fan_in);
    #   the relative head's last bias: 1, so its final ReLU stays above zero.
    # One extra key is added, which strict=False ignores (the published checkpoints carry extra keys too).
    shapes = {key: tuple(value.shape) for key, value in
              nodes.DepthAnythingV2(**nodes.model_config_for(CHECKPOINT)).state_dict().items()}
    generator = torch.Generator().manual_seed(1234)
    fixture = {}
    for key, shape in sorted(shapes.items()):
        noise = torch.randn(shape, generator=generator)
        leaf = key.rsplit(".", 1)[-1]
        if leaf == "gamma" or (leaf == "weight" and "norm" in key):
            value = 1.0 + 0.01 * noise
        elif leaf == "bias":
            value = 0.01 * noise
        elif len(shape) < 2 or leaf in ("pos_embed", "cls_token", "mask_token", "register_tokens"):
            value = 0.02 * noise
        else:
            fan_in = 1
            for size in shape[1:]:
                fan_in *= size
            value = noise / fan_in ** 0.5
        fixture[key] = value.contiguous()
    fixture["depth_head.scratch.output_conv2.2.bias"] = torch.ones(shapes["depth_head.scratch.output_conv2.2.bias"])
    fixture["regression.extra_key"] = torch.zeros(3)
    weight_path = root / "huggingface" / FIXTURE_REPO / FIXTURE_REVISION / CHECKPOINT
    weight_path.parent.mkdir(parents=True)
    save_file(fixture, str(weight_path))
    nodes._WEIGHTS[CHECKPOINT] = sdk.HuggingFaceWeight(
        repo_id=FIXTURE_REPO, filename=CHECKPOINT, folder="geometry_estimation", revision=FIXTURE_REVISION,
        sha256=_sha256(weight_path), on_demand=True)

    # Record which SDK calls a node makes (the provider methods run unchanged).
    calls = []

    def spy(owner, name, label):
        original = getattr(owner, name)

        async def recorded(self, *args, **kwargs):
            calls.append(label)
            return await original(self, *args, **kwargs)
        setattr(owner, name, recorded)
    spy(_sdk._InProcessModels, "download_huggingface_weights", "models.download_huggingface_weights")
    spy(_sdk._InProcessAssets, "resolve", "assets.resolve")
    spy(_sdk._InProcessAssets, "load_state_dict", "assets.load_state_dict")

    async def run(cls, inputs, node_id):
        """Core execution.py's SDK seam (the V3 branch), in-process providers."""
        refs_mode = bool(getattr(cls, "SDK_REFS", False))
        plan = _sdk.ExecutionPlan(
            prompt_id="dav2-regression", node_id=node_id, node_type=cls.__name__, node_module=cls.__module__,
            inputs=inputs, input_mode="refs" if refs_mode else "values", method="execute",
            permissions=tuple(getattr(cls, "SDK_PERMISSIONS", ()) or ()),
            required_weights=tuple(getattr(cls, "SDK_REQUIRED_WEIGHTS", ()) or ()))
        refs = _sdk.providers.ref_resolver_factory()
        scope = _sdk.bind_runtime(refs, _sdk.providers.ctx_provider.build(plan), _sdk.providers.ops_provider)
        if refs_mode:
            inputs = await _sdk.wrap_inputs(refs, inputs)
            plan.inputs = inputs

        async def local_call():
            with CurrentNodeContext("dav2-regression", node_id, 0), scope:
                return await cls.execute(**inputs)
        try:
            result = await _sdk.providers.execution_backend.dispatch(plan, local_call, scope.runtime)
            if isinstance(result, asyncio.Task):
                result = await result
            return await _sdk.unwrap_outputs(refs, result)
        finally:
            refs.clear()

    def pack_frame(error):
        frames = [frame for frame in traceback.extract_tb(error.__traceback__) if frame.filename.startswith(str(dst))]
        if not frames:
            return None
        frame = frames[-1]
        return {"file": os.path.relpath(frame.filename, dst), "line": frame.lineno, "function": frame.name,
                "code": frame.line}

    async def step(name, cls, inputs, node_id, seed):
        torch.manual_seed(seed)
        calls.clear()
        try:
            output = await run(cls, inputs, node_id)
        except Exception as error:  # noqa: BLE001 - recorded, judged by the verdict
            return {"step": name, "node": cls.__name__, "ok": False, "error": [type(error).__name__, str(error)],
                    "where": pack_frame(error), "calls": list(calls)}, None
        return {"step": name, "node": cls.__name__, "ok": True, "calls": list(calls)}, output.result[0]

    def image_summary(value):
        value = value.detach().cpu()
        return {"shape": list(value.shape), "dtype": str(value.dtype), "finite": bool(torch.isfinite(value).all()),
                "min": float(value.min()), "max": float(value.max()),
                "sha256": hashlib.sha256(value.contiguous().numpy().tobytes()).hexdigest()}

    async def scenario():
        steps = []
        record, loaded = await step("loader", loader, {"model": CHECKPOINT, "precision": "auto"}, "1", 7)
        steps.append(record)
        if not record["ok"]:
            return steps
        record["output"] = loaded
        state = nodes._LOADED[(CHECKPOINT, "fp32")].state_dict()
        fixture_keys = [key for key in fixture if key != "regression.extra_key"]
        record["parameters"] = {
            "model_keys": len(state),
            "fixture_keys": len(fixture_keys),
            "equal": sum(1 for key in fixture_keys if torch.equal(state[key], fixture[key])),
            "extra_key_ignored": "regression.extra_key" not in state}
        height, width = 30, 44  # not multiples of 14: the input is resized for the backbone and the output back
        image = (torch.arange(height * width * 3, dtype=torch.float32).reshape(1, height, width, 3)
                 % 97 / 96.0)
        record, first = await step("depth", depth, {"da_model": loaded, "images": image}, "2", 11)
        steps.append(record)
        if record["ok"]:
            record["image"] = image_summary(first)
        nodes._LOADED.clear()  # a new guest process: the module cache is empty, the weight is installed
        record, again = await step("depth-after-cache-miss", depth, {"da_model": loaded, "images": image}, "3", 7)
        steps.append(record)
        if record["ok"]:
            record["image"] = image_summary(again)
        # A flat depth map. Upstream's normalisation (the pack's infer(), its process() body) divides 0 by 0, giving
        # NaN pixels; ImageRef.from_value refuses non-finite pixels.
        model = nodes._LOADED[(CHECKPOINT, "fp32")]
        with torch.no_grad():
            model.depth_head.scratch.output_conv2[2].weight.zero_()
            model.depth_head.scratch.output_conv2[2].bias.fill_(1.0)
            flat = nodes.infer(model, image, torch.float32, False)
        record, _ = await step("depth-flat", depth, {"da_model": loaded, "images": image}, "4", 7)
        record["infer_all_nan"] = bool(torch.isnan(flat).all())
        steps.append(record)
        return steps

    result = {"base": base, "fixture": {"file": os.path.relpath(weight_path, root.parent),
                                        "sha256": _sha256(weight_path), "tensors": len(fixture)},
              "steps": asyncio.run(scenario())}
    Path(out_path).write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    return 0


def manifest_text(dst, alias):
    """The real encoder's secure-nodes.json (the same calls as the lane's generate_manifest.py)."""
    from comfy_api.latest import io
    from comfy_secure_nodes import packmanifest
    from comfy_secure_nodes.packruntime import manifest_declaration
    package = sys.modules[alias]

    def overrides(cls, name):
        mine, base = getattr(cls, name, None), getattr(io.ComfyNode, name, None)
        return getattr(mine, "__func__", mine) is not getattr(base, "__func__", base)
    rows = {}
    for node_id, cls in package.NODE_CLASS_MAPPINGS.items():
        module_file = Path(sys.modules[cls.__module__].__file__).resolve()
        row = {
            "module": ".".join(module_file.relative_to(dst.resolve()).with_suffix("").parts),
            "class": cls.__name__,
            "sdk_refs": getattr(cls, "SDK_REFS", False) is True,
            "permissions": list(getattr(cls, "SDK_PERMISSIONS", ()) or ()),
            "methods": {m: overrides(cls, m) for m in ("validate_inputs", "fingerprint_inputs", "check_lazy_status")},
            "schema": packmanifest.encode_schema(copy.deepcopy(cls.GET_SCHEMA())),
        }
        if row["methods"]["validate_inputs"]:
            row["validation_inputs"] = packmanifest.encode_validation_inputs(cls)
        if getattr(cls, "SDK_REQUIRED_WEIGHTS", None):
            row["required_weights"] = packmanifest.encode_required_weights(cls)
        rows[node_id] = row
    manifest = {"format": packmanifest.FORMAT, "nodes": rows, "runtime": manifest_declaration(dst)}
    return json.dumps(manifest, indent=2, sort_keys=True) + "\n"


def contract(sides_path, out_path):
    """The host contract (see the module docstring, part 2)."""
    work = Path(tempfile.mkdtemp(prefix="dav2-contract-"))
    os.environ["COMFY_SECURE_ALLOW_CAPABILITIES"] = "models.download"
    os.environ["COMFY_SECURE_CONSENT_FILE"] = str(work / "consent.json")
    _environment("0cd9adec")
    from comfy_secure_nodes import consent, packdb, packmanifest

    sides = json.loads(Path(sides_path).read_text())
    dst, package = _load_pack("dav2_contract")
    nodes = sys.modules["dav2_contract.nodes"]

    tree = ast.parse(HOST.read_text())
    host = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name in HANDLERS.values():
            host[node.name] = {
                "requires": sorted({call.args[0].value for call in ast.walk(node)
                                    if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                                    and call.func.attr == "_require" and call.args
                                    and isinstance(call.args[0], ast.Constant)}),
                "checks_declared_weights": any(isinstance(item, ast.Attribute) and item.attr == "_required_weights"
                                               for item in ast.walk(node)),
                "line": node.lineno}
    consent.STORE.record(PACK_NAME, "models.download", True)

    committed = (V2 / "secure-nodes.json").read_text()
    manifest = json.loads(committed)
    rows = {}
    for node_id, row in manifest["nodes"].items():
        source = (V2 / (row["module"].replace(".", "/") + ".py")).resolve()
        proxy = packdb._proxy_class(f"dav2_contract_rows.{row['module']}", source, copy.deepcopy(row))
        granted, refused, pending = consent.filter_capabilities(PACK_NAME, proxy.SDK_PERMISSIONS)
        made = sorted({call for side_record in sides.values() for step in side_record["steps"]
                       if step["node"] == row["class"] for call in step["calls"]})
        needed = sorted({cap for call in made for cap in host[HANDLERS[call]]["requires"]})
        rows[node_id] = {"declared": list(row.get("permissions", [])), "host_permissions": list(proxy.SDK_PERMISSIONS),
                         "granted": sorted(granted), "refused": list(refused), "pending": list(pending),
                         "calls_made": made, "capabilities_needed": needed,
                         "missing": sorted(set(needed) - set(granted)),
                         "required_weights": len(proxy.SDK_REQUIRED_WEIGHTS)}
    identity = lambda item: (item.repo_id, item.filename, item.folder, item.revision, item.sha256)  # noqa: E731
    loader_row = manifest["nodes"].get(LOADER, {})
    declared = {identity(item) for item in packmanifest.decode_required_weights(loader_row.get("required_weights", []))}
    pack_weights = {identity(item) for item in nodes._WEIGHTS.values()}
    regenerated = manifest_text(dst, "dav2_contract")
    result = {
        "host_handlers": {"file": "comfy_secure_nodes/transport/host.py", "sha256": _sha256(HOST), **host},
        "rows": rows,
        "loader_declares_every_pack_weight": declared == pack_weights and len(pack_weights) == 9,
        "loader_declared_weights": len(declared),
        "manifest_equals_real_encoder": regenerated == committed,
        "manifest_sha256": hashlib.sha256(committed.encode()).hexdigest(),
    }
    if not result["manifest_equals_real_encoder"]:
        (RESULTS / "secure-nodes.regenerated.json").write_text(regenerated)
    Path(out_path).write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    return 0


def verdict(sides, contract_result, expect_red):
    steps = {base: {step["step"]: step for step in record["steps"]} for base, record in sides.items()}
    if expect_red:
        loader_fails_at_load = all(
            not by["loader"]["ok"] and (by["loader"]["where"] or {}).get("function") == "_build"
            and by["loader"]["calls"] == ["models.download_huggingface_weights", "assets.load_state_dict"]
            for by in steps.values())
        contract_red = (bool(contract_result["rows"][LOADER]["missing"])
                        and not contract_result["loader_declares_every_pack_weight"])
        return {"expected": "red", "loader_fails_at_the_asset_load": loader_fails_at_load,
                "contract_finds_missing_capabilities": contract_red,
                "status": "RED_AS_EXPECTED" if loader_fails_at_load and contract_red else "NOT_RED"}
    checks = {}
    for base, by in steps.items():
        loader = by["loader"]
        checks[f"{base}: loader ok, through download, resolve and load_state_dict"] = (
            loader["ok"] and loader["calls"] == ["models.download_huggingface_weights", "assets.resolve",
                                                  "assets.load_state_dict"]
            and loader.get("output") == {"model": CHECKPOINT, "dtype": "fp32", "is_metric": False})
        parameters = loader.get("parameters", {})
        checks[f"{base}: every model tensor loaded from the fixture, extra key ignored"] = (
            parameters.get("fixture_keys", 0) > 0 and parameters.get("model_keys") == parameters.get("fixture_keys")
            and parameters.get("equal") == parameters.get("fixture_keys")
            and parameters.get("extra_key_ignored") is True)
        first, again = by.get("depth", {}), by.get("depth-after-cache-miss", {})
        if base == "0cd9adec":
            image = first.get("image", {})
            checks[f"{base}: depth image finite BHWC [0, 1] at the input size"] = (
                first.get("ok") and first["calls"] == [] and image.get("shape") == [1, 30, 44, 3]
                and image.get("dtype") == "torch.float32" and image.get("finite")
                and image.get("min") == 0.0 and image.get("max") == 1.0)
            checks[f"{base}: rebuild after a cache miss: same bytes, resolve + load only"] = (
                again.get("ok") and again["calls"] == ["assets.resolve", "assets.load_state_dict"]
                and again.get("image", {}).get("sha256") == image.get("sha256"))
            flat = by.get("depth-flat", {})
            checks[f"{base}: flat depth: upstream arithmetic gives NaN, the node refuses non-finite pixels"] = (
                flat.get("infer_all_nan") is True and not flat.get("ok")
                and flat.get("error") == ["ValueError", "IMAGE pixels must be finite"])
        else:
            checks[f"{base}: depth node needs ImageRef.from_value (minimum base 0cd9adec)"] = all(
                not record.get("ok") and record["error"][0] == "AttributeError" and "from_value" in record["error"][1]
                for record in (first, again))
    for node_id, row in contract_result["rows"].items():
        checks[f"contract: {node_id} granted everything its calls need"] = not row["missing"]
    checks["contract: the loader declares the nine pack weights"] = contract_result["loader_declares_every_pack_weight"]
    checks["contract: manifest equals the real encoder"] = contract_result["manifest_equals_real_encoder"]
    return {"expected": "green", "checks": checks, "status": "PASS" if all(checks.values()) else "FAIL"}


def main(argv):
    if argv[:1] == ["side"]:
        return side(argv[1], argv[2])
    if argv[:1] == ["contract"]:
        return contract(argv[1], argv[2])
    expect_red = argv[:1] == ["expect-red"]
    work = Path(tempfile.mkdtemp(prefix="dav2-regression-"))
    sides, logs = {}, {}
    for base in BASES:
        out = work / f"side-{base}.json"
        proc = subprocess.run([sys.executable, "-I", __file__, "side", base, str(out)], capture_output=True, text=True)
        logs[base] = {"rc": proc.returncode, "stderr_tail": proc.stderr[-3000:]}
        if proc.returncode != 0 or not out.exists():
            print(proc.stdout[-2000:], proc.stderr[-6000:])
            raise SystemExit(f"side {base} failed (rc {proc.returncode})")
        sides[base] = json.loads(out.read_text())
    (work / "sides.json").write_text(json.dumps(sides))
    out = work / "contract.json"
    proc = subprocess.run([sys.executable, "-I", __file__, "contract", str(work / "sides.json"), str(out)],
                          capture_output=True, text=True)
    logs["contract"] = {"rc": proc.returncode, "stderr_tail": proc.stderr[-3000:]}
    if proc.returncode != 0 or not out.exists():
        print(proc.stdout[-2000:], proc.stderr[-6000:])
        raise SystemExit(f"contract failed (rc {proc.returncode})")
    contract_result = json.loads(out.read_text())
    result = {"pack": PACK_NAME, "test": "test_dav2_weight_resolution.py",
              "test_sha256": _sha256(__file__), "nodes_py_sha256": _sha256(V2 / "nodes.py"),
              "verdict": verdict(sides, contract_result, expect_red),
              "sides": sides, "contract": contract_result, "logs": logs}
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "regression.json").write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    print(json.dumps(result["verdict"], indent=1))
    return 0 if result["verdict"]["status"] in ("PASS", "RED_AS_EXPECTED") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
