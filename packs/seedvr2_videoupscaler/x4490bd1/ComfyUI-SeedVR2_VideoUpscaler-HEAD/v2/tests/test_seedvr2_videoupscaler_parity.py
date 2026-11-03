"""Tier-1 parity for seedvr2_videoupscaler (pin 4490bd1f, v2.5.24): pristine vs v2, CPU gate.

    DEPS=<wheels + checkpoints, see _sv_harness.py> GATE_MEM=8g GATE_CPUS=4 run_in_gate.sh \
        <snapshot dir, or the pack folder> <.../v2/tests> <results> test_seedvr2_videoupscaler_parity.py

Every node runs on both sides with identical inputs. The upscaler runs the full pipeline (VAE
encode, one-step DiT, VAE decode, color correction) on tiny CPU fixtures with the real default
checkpoints. The pristine side reads them from disk; v2 gets the same files' tensors through the
SDK broker. Both sides get the two text embeddings from the declared embedding files: v2 through
the broker, the pristine pack through a swap of only its two torch.load calls. Results are compared
with torch.equal / exact equality.

Fixtures are synthetic. A published snapshot may omit upstream media, example workflows and bundled
model files; the integrity checks accept their absence, and no check reads them except the optional
comparison of the declared embeddings with the pack's own files when those are present.

Writes /results/parity.json; exits 1 on any failed check.
"""

import ast
import asyncio
import gc
import hashlib
import json
import platform
import sys
from pathlib import Path

sys.path[:0] = ["/core", "/overlay", "/tests"]

import _sv_harness as H  # noqa: E402
import torch  # noqa: E402
from comfy_secure_nodes import packdb  # noqa: E402
from encode_manifest import build_manifest, serialize  # noqa: E402

EDITED = {"__init__.py", "pyproject.toml", "src/interfaces/dit_model_loader.py",
          "src/interfaces/vae_model_loader.py", "src/core/model_loader.py", "src/core/generation_utils.py",
          "src/utils/downloads.py"}
GUEST_MODULES = ["secure_seedvr2.py", "_seedvr2_schemas.py", "src/_sn_weights.py", "src/_sn_context.py",
                 "src/interfaces/dit_model_loader.py", "src/interfaces/vae_model_loader.py",
                 "src/core/model_loader.py", "src/core/generation_utils.py", "src/utils/downloads.py"]
# What a published snapshot may omit (pristine and v2 alike): upstream media, example/demo
# workflows and bundled model files.
MEDIA = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".mp4", ".mov", ".webm", ".avi", ".mkv",
         ".wav", ".mp3", ".flac", ".ogg")
MODEL_FILES = (".pt", ".pth", ".ckpt", ".bin", ".safetensors", ".sft", ".gguf", ".onnx")
DENIED = ("comfy.", "comfy_execution", "folder_paths", "nodes", "server", "execution", "urllib.request",
          "requests", "huggingface_hub")
GGUF_REFUSAL = ("seedvr2_videoupscaler: the GGUF checkpoint {name!r} is not available in Secure Nodes "
                "V2 yet. Its reader needs a model file on disk, and a Secure Nodes guest receives "
                "verified tensors, not files. Use a .safetensors model "
                "(e.g. seedvr2_ema_3b_fp8_e4m3fn.safetensors).")
GGUF = ["seedvr2_ema_3b-Q4_K_M.gguf", "seedvr2_ema_3b-Q8_0.gguf", "seedvr2_ema_7b-Q4_K_M.gguf",
        "seedvr2_ema_7b_sharp-Q4_K_M.gguf"]

checks = []
per_node = {}


def record(node, name, ok, detail=None, cases=1, kind="parity"):
    checks.append({"node": node, "check": name, "ok": bool(ok), "cases": cases, "kind": kind,
                   "detail": None if ok else str(detail)[:1500]})
    row = per_node.setdefault(node, {"cases": 0, "failed": [], "kinds": set()})
    row["cases"] += cases
    row["kinds"].add(kind)
    if not ok:
        row["failed"].append(name)
    print(("PASS " if ok else "FAIL ") + f"{node} :: {name}" + ("" if ok else f": {str(detail)[:300]}"),
          flush=True)


def blob_id(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def omittable(name: str) -> bool:
    lower = name.lower()
    return (lower.endswith(MEDIA + MODEL_FILES)
            or (lower.startswith("example_workflows/") and lower.endswith(".json")))


def module_level_imports(path: Path):
    tree = ast.parse(path.read_bytes())
    out = []
    for item in tree.body:
        if isinstance(item, ast.Import):
            out += [alias.name for alias in item.names]
        elif isinstance(item, ast.ImportFrom) and item.level == 0:
            out.append(item.module)
    return out


def info_without_module(info):
    info = dict(info)
    info.pop("python_module", None)
    return info


def compare(node, label, pristine_call, v2_call, cases=1):
    r1, r2 = H.outcome(pristine_call), H.outcome(v2_call)
    if r1[0] != r2[0]:
        return record(node, label, False, f"pristine {r1} vs v2 {r2}"[:1200], cases)
    if r1[0] == "error":
        return record(node, label + " (same error)", r1[1] == r2[1], f"{r1[1]} vs {r2[1]}", cases)
    ok, detail = H.same(tuple(r1[1]), tuple(r2[1]))
    return record(node, label, ok, detail, cases)


def main():
    head = H.pack_head()
    v2 = head / "v2"
    H.setup_weights()
    environment = {"python": platform.python_version(), "torch": torch.__version__,
                   "threads": torch.get_num_threads(), "pack_head": str(head)}

    # 1. Integrity. Files the mirror policy omits may be absent, from pristine and v2 alike.
    expected = json.loads((Path("/tests") / "pristine_blobs.json").read_text())
    actual = {p.relative_to(head).as_posix(): p for p in sorted(head.rglob("*"))
              if p.is_file() and not p.relative_to(head).as_posix().startswith("v2/")}
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    environment["omitted_from_snapshot"] = missing
    record("(pack)", "pristine/file-set", not extra and all(omittable(n) for n in missing),
           {"extra": extra, "missing": [n for n in missing if not omittable(n)]}, kind="integrity")
    bad = [n for n, p in actual.items() if blob_id(p.read_bytes()) != expected.get(n)]
    record("(pack)", "pristine/blob-ids", not bad, bad, cases=len(actual), kind="integrity")
    changed = [n for n in sorted(expected) if n not in EDITED and (
        (n in actual) != (v2 / n).is_file()
        or (n in actual and (v2 / n).read_bytes() != actual[n].read_bytes()))]
    record("(pack)", "v2/untouched-copies", not changed, changed, cases=len(expected) - len(EDITED),
           kind="integrity")
    for name in GUEST_MODULES:
        denied = [m for m in module_level_imports(v2 / name) if m and m.startswith(DENIED)]
        record("(pack)", f"guest-imports/{name}", not denied, denied, kind="integrity")
    generation = (v2 / "src/core/generation_utils.py").read_text()
    record("(pack)", "v2/embeddings-not-read-from-pack",
           all(f"brokered_tensor('{n}')" in generation and f"'{n}'), weights_only" not in generation
               for n in ("pos_emb.pt", "neg_emb.pt")),
           "v2 generation_utils still reads the pack's embedding files", kind="integrity")

    # 2. Load both sides. The pristine __init__ runs here, in the container.
    pristine = H.load_package("seedvr2_pristine", head)
    P = sys.modules["seedvr2_pristine.src.interfaces"]
    new = H.load_package("seedvr2_v2", v2)
    S = sys.modules["seedvr2_v2.secure_seedvr2"]
    pristine_ids = [cls.define_schema.__self__.__name__ for cls in (
        P.SeedVR2VideoUpscaler, P.SeedVR2LoadDiTModel, P.SeedVR2LoadVAEModel, P.SeedVR2TorchCompileSettings)]
    manifest = json.loads((v2 / "secure-nodes.json").read_bytes())
    record("(pack)", "ids", pristine_ids == list(new.NODE_CLASS_MAPPINGS)
           and set(manifest["nodes"]) == set(pristine_ids),
           [pristine_ids, list(new.NODE_CLASS_MAPPINGS), sorted(manifest["nodes"])], kind="integrity")
    record("(pack)", "manifest-is-encoder-output",
           serialize(build_manifest(v2, "sv_v2_regen")) == (v2 / "secure-nodes.json").read_text(),
           "secure-nodes.json differs from the encoder", kind="integrity")
    del pristine

    # 2b. The text embeddings: the declared files (sha256, one tensor each) feed both sides.
    weights = sys.modules["seedvr2_v2.src._sn_weights"]
    try:
        declared = H.declared_embeddings(weights)
        record("(pack)", "embeddings/declared-files", True, kind="integrity", cases=len(declared))
    except (OSError, ValueError, KeyError) as error:
        record("(pack)", "embeddings/declared-files", False, error, kind="integrity")
        return finish(environment, {})
    present = [n for n in weights.EMBEDDINGS if (head / n).is_file()]
    if present:
        # Only when the snapshot still has them: the pack's own files, read with the pack's own call.
        diffs = {n: H.same(torch.load(head / n, weights_only=True), declared[n]) for n in present}
        record("(pack)", "embeddings/declared-equal-pack-files", all(ok for ok, _ in diffs.values()),
               {n: d for n, (ok, d) in diffs.items() if not ok}, cases=len(present), kind="integrity")
    else:
        print("INFO embeddings/declared-equal-pack-files: not run, the snapshot omits the pack's files",
              flush=True)
    H.pristine_embeddings("seedvr2_pristine", declared)

    # 3. /object_info: pristine on a one-GPU host vs guest class vs host proxy (full dicts).
    loaded = packdb.load_pack(H.snapshot_dir(), mount_name="custom_nodes.sv_parity_proxy",
                              pack_id=f"{H.SLUG}/{H.KEY}")
    for node_id in pristine_ids:
        with H.simulated_gpu_host("seedvr2_pristine"):
            reference = info_without_module(getattr(P, node_id).GET_NODE_INFO_V1())
        for side, cls in (("guest-class", new.NODE_CLASS_MAPPINGS[node_id]),
                          ("host-proxy", loaded.node_mappings[node_id])):
            got = info_without_module(cls.GET_NODE_INFO_V1())
            ok, detail = H.same(reference, got)
            record(node_id, f"object-info/{side}", ok, detail, cases=len(reference), kind="schema")

    # 4. Config nodes: identical dicts (node id included) and identical errors.
    compile_cases = [
        dict(backend="inductor", mode="default", fullgraph=False, dynamic=False,
             dynamo_cache_size_limit=64, dynamo_recompile_limit=128),
        dict(backend="cudagraphs", mode="max-autotune-no-cudagraphs", fullgraph=True, dynamic=True,
             dynamo_cache_size_limit=0, dynamo_recompile_limit=1024),
    ]
    compile_args = None
    for index, inputs in enumerate(compile_cases):
        compare("SeedVR2TorchCompileSettings", f"case{index}",
                lambda inputs=inputs: H.run_pristine(P.SeedVR2TorchCompileSettings, **inputs),
                lambda inputs=inputs: asyncio.run(H.run_v2(S.SeedVR2TorchCompileSettings, **inputs)))
        compile_args = H.run_pristine(P.SeedVR2TorchCompileSettings, **inputs)[0]
    dit_cases = [
        dict(model=H.DIT, device="cpu"),
        dict(model="seedvr2_ema_7b_fp16.safetensors", device="cuda:0", offload_device="cpu",
             cache_model=True, blocks_to_swap=16, swap_io_components=True,
             attention_mode="flash_attn_2", torch_compile_args=compile_args),
        dict(model=H.DIT, device="cpu", offload_device="none", cache_model=True),
        dict(model="seedvr2_ema_3b-Q4_K_M.gguf", device="cpu"),
    ]
    for index, inputs in enumerate(dit_cases):
        compare("SeedVR2LoadDiTModel", f"case{index}",
                lambda inputs=inputs: H.run_pristine(P.SeedVR2LoadDiTModel, node_id="31", **inputs),
                lambda inputs=inputs: asyncio.run(H.run_v2(S.SeedVR2LoadDiTModel, node_id="31", **inputs)))
    vae_cases = [
        dict(model=H.VAE, device="cpu"),
        dict(model=H.VAE, device="cuda:0", offload_device="cpu", cache_model=True, encode_tiled=True,
             encode_tile_size=768, encode_tile_overlap=64, decode_tiled=True, decode_tile_size=512,
             decode_tile_overlap=32, tile_debug="encode", torch_compile_args=compile_args),
        dict(model=H.VAE, device="cpu", cache_model=True),
    ]
    for index, inputs in enumerate(vae_cases):
        compare("SeedVR2LoadVAEModel", f"case{index}",
                lambda inputs=inputs: H.run_pristine(P.SeedVR2LoadVAEModel, node_id="32", **inputs),
                lambda inputs=inputs: asyncio.run(H.run_v2(S.SeedVR2LoadVAEModel, node_id="32", **inputs)))

    # 5. GGUF options: refused by name at queue time; other names keep the menu check.
    for name in GGUF:
        got = S.SeedVR2LoadDiTModel.validate_inputs(model=name)
        record("SeedVR2LoadDiTModel", f"refusal/validate/{name}", got == GGUF_REFUSAL.format(name=name),
               got, kind="refusal")
    record("SeedVR2LoadDiTModel", "validate/known-safetensors", S.SeedVR2LoadDiTModel.validate_inputs(
        model=H.DIT) is True, None, kind="refusal")
    unknown = S.SeedVR2LoadDiTModel.validate_inputs(model="other.safetensors")
    record("SeedVR2LoadDiTModel", "validate/unknown-name",
           isinstance(unknown, str) and unknown.startswith("Value not in list: model: 'other.safetensors'"),
           unknown, kind="refusal")

    # 6. The upscaler: full pipeline, pristine vs v2, tiny CPU fixtures, real default checkpoints.
    dit_cfg = H.run_pristine(P.SeedVR2LoadDiTModel, node_id="41", model=H.DIT, device="cpu")[0]
    vae_cfg = H.run_pristine(P.SeedVR2LoadVAEModel, node_id="42", model=H.VAE, device="cpu")[0]
    rgb = H.frames(1, 32, 32, 3, seed=5)
    upscale_cases = [
        ("lab", dict(image=rgb, color_correction="lab")),
        ("wavelet", dict(image=rgb, color_correction="wavelet")),
        ("adain", dict(image=rgb, color_correction="adain")),
        ("none", dict(image=rgb, color_correction="none")),
        ("rgba", dict(image=H.frames(1, 32, 32, 4, seed=6), color_correction="lab")),
        ("5 frames batch 5", dict(image=H.frames(5, 32, 32, 3, seed=8), batch_size=5, color_correction="lab")),
        ("noise seed 7", dict(image=rgb, seed=7, input_noise_scale=0.3, latent_noise_scale=0.2,
                              color_correction="lab")),
        ("3 frames uniform batch, prepend 2, max_resolution 48, tensor offload cpu",
         dict(image=H.frames(3, 32, 32, 3, seed=9), batch_size=5, uniform_batch_size=True,
              prepend_frames=2, max_resolution=48, offload_device="cpu", color_correction="wavelet")),
    ]
    first_v2_output = None
    first_pristine_output = None
    for label, overrides in upscale_cases:
        inputs = dict(dit=dit_cfg, vae=vae_cfg, seed=42, resolution=64, batch_size=1)
        inputs.update(overrides)
        r1 = H.outcome(lambda: H.run_pristine(P.SeedVR2VideoUpscaler, node_id="43", **inputs))
        r2 = H.outcome(lambda: asyncio.run(H.run_v2(S.SeedVR2VideoUpscaler, node_id="43", **inputs)))
        if r1[0] == r2[0] == "ok":
            ok, detail = H.same(tuple(r1[1]), tuple(r2[1]))
            if first_v2_output is None:
                first_pristine_output, first_v2_output = r1[1][0], r2[1][0]
        else:
            ok, detail = (r1 == r2), f"pristine {r1} vs v2 {r2}"[:1200]
        record("SeedVR2VideoUpscaler", f"upscale/{label}", ok, detail)
        gc.collect()
    gguf_cfg = dict(dit_cfg, model="seedvr2_ema_3b-Q8_0.gguf")
    refused = H.outcome(lambda: asyncio.run(H.run_v2(
        S.SeedVR2VideoUpscaler, node_id="44", image=rgb, dit=gguf_cfg, vae=vae_cfg, seed=42,
        resolution=64, batch_size=1)))
    record("SeedVR2VideoUpscaler", "refusal/execute/gguf",
           refused == ("error", ("WeightsNotBrokered", GGUF_REFUSAL.format(name="seedvr2_ema_3b-Q8_0.gguf"))),
           refused, kind="refusal")

    # 7. Negative controls.
    controls = {}
    if first_v2_output is not None:
        perturbed = first_v2_output.clone()
        perturbed[0, 0, 0, 0] += 1.0 / 1024
        controls["perturbed-output-detected"] = (H.same(first_pristine_output, first_v2_output)[0]
                                                 and not H.same(first_pristine_output, perturbed)[0])
        # The brokered embeddings really drive v2: halve one and the first case's output must change.
        saved_embeddings = weights.load_embeddings

        async def halved_embeddings():
            tensors = await saved_embeddings()
            tensors["pos_emb.pt"] = tensors["pos_emb.pt"] * 0.5
            return tensors

        weights.load_embeddings = halved_embeddings
        try:
            inputs = dict(dit=dit_cfg, vae=vae_cfg, seed=42, resolution=64, batch_size=1, image=rgb,
                          color_correction="lab")
            got = H.outcome(lambda: asyncio.run(H.run_v2(S.SeedVR2VideoUpscaler, node_id="45", **inputs)))
            controls["perturbed-embedding-detected"] = (
                got[0] == "ok" and not H.same(first_pristine_output, got[1][0])[0])
        finally:
            weights.load_embeddings = saved_embeddings
    original = S.SeedVR2LoadDiTModel.__dict__["define_schema"]

    def perturbed_schema(cls):
        schema = original.__func__(cls)
        schema.display_name = "SeedVR2 (Down)Load DiT Model (perturbed)"
        return schema

    S.SeedVR2LoadDiTModel.define_schema = classmethod(perturbed_schema)
    try:
        with H.simulated_gpu_host("seedvr2_pristine"):
            reference = info_without_module(P.SeedVR2LoadDiTModel.GET_NODE_INFO_V1())
        controls["perturbed-schema-detected"] = not H.same(
            reference, info_without_module(S.SeedVR2LoadDiTModel.GET_NODE_INFO_V1()))[0]
    finally:
        S.SeedVR2LoadDiTModel.define_schema = original
    saved = weights.gguf_refusal
    weights.gguf_refusal = lambda name: saved(name) + " (perturbed)"
    try:
        controls["perturbed-refusal-detected"] = (
            S.SeedVR2LoadDiTModel.validate_inputs(model=GGUF[0]) != GGUF_REFUSAL.format(name=GGUF[0]))
    finally:
        weights.gguf_refusal = saved
    for name, ok in controls.items():
        record("(pack)", f"negative-control/{name}", ok, kind="control")
    return finish(environment, controls)


def finish(environment, controls):
    nodes = {}
    for node_id, row in per_node.items():
        if node_id.startswith("("):
            continue
        if row["failed"]:
            verdict = "MISMATCH"
        elif "parity" in row["kinds"] and "refusal" in row["kinds"]:
            verdict = "EXACT (GGUF options: REFUSED-AS-DESIGNED)"
        elif "parity" in row["kinds"]:
            verdict = "EXACT"
        else:
            verdict = "REFUSED-AS-DESIGNED"
        nodes[node_id] = {"verdict": verdict, "cases": row["cases"], "failed": row["failed"]}
    failed = [c["node"] + " :: " + c["check"] for c in checks if not c["ok"]]
    result = {"pack": H.SLUG, "pin": H.PIN, "nodes": nodes, "negative_control": controls,
              "checks": checks, "failed": failed, "environment": environment}
    Path("/results/parity.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"nodes": {k: v["verdict"] for k, v in nodes.items()}, "failed": failed}))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
