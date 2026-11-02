"""comfyui_lora_tag_loader to-50% conversion: tier-1 parity, original vs Secure Nodes V2, in the lane gate.

Run with run_in_gate.sh (network none, read-only): /pack = pristine pack with v2/ inside, /tests = this
folder, /results writable, /bases = guest comfy_api trees, /overlay = comfy_secure_nodes (live overlay).
  python3 test_comfyui_lora_tag_loader_parity.py [generate-manifest]

What is compared, per input text (hand-picked plus seeded fuzz, malformed tags included):
  * the STRING output, byte for byte;
  * the LoRA applications in order: catalogue name, safe_load, strength_model and strength_clip as
    float.hex (so -0.0, inf and nan compare exactly), and which model/clip each one was applied to;
  * whether the MODEL/CLIP outputs are the inputs themselves (no tag applied) or the result of the
    last application;
  * the node's printed lines;
  * an exception, by type and message.
The original runs its own nodes.py with recording fakes for folder_paths, comfy.utils.load_torch_file
and comfy.sd.load_lora_for_models (the host-only modules it imports). v2 runs its own nodes.py on the
real guest SDK (comfy_api 0.37.0 from /bases) with a fake sdk.ctx().assets and MODEL/CLIP refs whose
apply_lora follows the trusted op (comfy_api 0.37.0 _sdk.py _model_apply_lora: number checks, the
[-100, 100] check unless allow_extended_strengths, the zero skip unless skip_zero=False, then
load_torch_file(safe_load=True) and comfy.sd.load_lora_for_models) and records into the same fake.
Core's LoRA math itself is the same function on both sides and is a tier-2 item (TIER2.json).
Also: the schema against INPUT_TYPES/RETURN_*, and v2/secure-nodes.json against the real encoder
(comfy_secure_nodes.packmanifest), serialized json.dumps(indent=2, sort_keys=True) + "\\n".
A negative control perturbs one converted output and must turn the comparison red.
"""
import asyncio
import contextlib
import copy
import glob
import importlib.util
import io as stdio
import json
import math
import os
import random
import sys
import types

PACK = "/pack"
V2 = "/pack/v2"
RESULTS = "/results"
BASE = glob.glob("/bases/0cd9adec*/common-site-packages")[0]
sys.path.insert(0, "/overlay")
sys.path.insert(0, BASE)
sys.dont_write_bytecode = True

from comfy_api.latest import io  # noqa: E402  (guest SDK, comfy_api 0.37.0)

# ---------------------------------------------------------------- the LoRA catalogue fixture
# folder_paths.get_filename_list returns a sorted list; the guest's assets.list("loras") returns
# sorted(name.replace("\\", "/")) of the same list (_sdk.py AssetsDomain.list). On a POSIX host the
# two are equal, which is what this fixture models.
CATALOGUE = sorted([
    "a.safetensors", "ab.safetensors", "abc.pt", "A.safetensors", "a (1).safetensors", "1.safetensors",
    "sub/a.safetensors", "sub/b c.safetensors", "sub/deep/zz.safetensors", "x/y/z.pt", "style_v2-1.0.safetensors",
    "Style.safetensors", "lcm-lora-sdxl.safetensors", "add_detail.safetensors", "my.lora.name.safetensors",
])


class Token:
    """An opaque model/clip value: the input, or the result of applying one LoRA to `parent`."""

    def __init__(self, label, parent=None, step=None):
        self.label, self.parent, self.step = label, parent, step

    def lineage(self):
        out, node = [], self
        while node is not None:
            out.append(node.label if node.step is None else f"step{node.step}")
            node = node.parent
        return tuple(reversed(out))


class Recorder:
    def __init__(self):
        self.calls = []

    def load_lora_for_models(self, model, clip, lora, strength_model, strength_clip, lora_metadata=None):
        step = len(self.calls)
        self.calls.append({
            "lora": lora["lora"], "safe_load": lora["safe_load"],
            "strength_model": float(strength_model).hex(), "strength_clip": float(strength_clip).hex(),
            "model_in": model.lineage(), "clip_in": None if clip is None else clip.lineage(),
        })
        return Token("m", model, step), (None if clip is None else Token("c", clip, step))


def load_original(recorder):
    """The pristine nodes.py with its three host modules replaced by recording fakes."""
    folder_paths = types.ModuleType("folder_paths")

    def get_filename_list(folder):
        assert folder == "loras", folder
        return list(CATALOGUE)
    folder_paths.get_filename_list = get_filename_list
    folder_paths.get_full_path = lambda folder, name: "/models/loras/" + name
    comfy = types.ModuleType("comfy")
    comfy.__path__ = []
    comfy_utils = types.ModuleType("comfy.utils")
    comfy_utils.load_torch_file = lambda path, safe_load=False: {"lora": path[len("/models/loras/"):], "safe_load": safe_load}
    comfy_sd = types.ModuleType("comfy.sd")
    comfy_sd.load_lora_for_models = recorder.load_lora_for_models
    comfy.utils, comfy.sd = comfy_utils, comfy_sd
    saved = {k: sys.modules.get(k) for k in ("folder_paths", "comfy", "comfy.utils", "comfy.sd")}
    sys.modules.update({"folder_paths": folder_paths, "comfy": comfy, "comfy.utils": comfy_utils, "comfy.sd": comfy_sd})
    try:
        spec = importlib.util.spec_from_file_location("_lora_tag_original", os.path.join(PACK, "nodes.py"))
        module = importlib.util.module_from_spec(spec)
        with warnings_quiet():
            spec.loader.exec_module(module)
        return module
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


@contextlib.contextmanager
def warnings_quiet():
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        yield


def load_v2():
    spec = importlib.util.spec_from_file_location("_lora_tag_v2", os.path.join(V2, "__init__.py"),
                                                  submodule_search_locations=[V2])
    package = importlib.util.module_from_spec(spec)
    sys.modules["_lora_tag_v2"] = package
    with warnings_quiet():
        spec.loader.exec_module(package)
    return package, sys.modules["_lora_tag_v2.nodes"]


class FakeAssets:
    def __init__(self):
        self.calls = []

    async def list(self, folder, prefix="", recursive=True):
        self.calls.append(("list", folder, prefix, recursive))
        assert folder == "loras" and prefix == "" and recursive is True
        return sorted(name.replace("\\", "/") for name in CATALOGUE)

    async def resolve(self, folder, name):
        self.calls.append(("resolve", folder, name))
        if folder != "loras" or name not in CATALOGUE:
            raise FileNotFoundError(f"{folder}/{name}")
        return {"asset": name}


class FakeRef:
    """A MODEL or CLIP ref. apply_lora follows comfy_api 0.37.0 _sdk.py _model_apply_lora."""

    def __init__(self, token, recorder, kind):
        self.token, self.recorder, self.kind = token, recorder, kind
        self.options = []

    async def apply_lora(self, asset, clip, strength_model, strength_clip, *, skip_zero=True, allow_extended_strengths=False):
        assert self.kind == "MODEL"
        self.recorder_options.append({"skip_zero": skip_zero, "allow_extended_strengths": allow_extended_strengths})
        if type(skip_zero) is not bool or type(allow_extended_strengths) is not bool:
            raise TypeError("options must be booleans")
        strengths = {}
        for name, value in {"strength_model": strength_model, "strength_clip": strength_clip}.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be a number")
            checked = float(value)
            if not allow_extended_strengths and (not math.isfinite(checked) or not -100.0 <= checked <= 100.0):
                raise ValueError(f"{name} must be finite and in [-100, 100]")
            strengths[name] = checked
        if clip is None and strengths["strength_clip"] != 0.0:
            raise ValueError("strength_clip must be zero when clip is None")
        if skip_zero and strengths["strength_model"] == 0.0 and strengths["strength_clip"] == 0.0:
            return self, clip
        state = {"lora": asset["asset"], "safe_load": True}
        model_token, clip_token = self.recorder.load_lora_for_models(
            self.token, None if clip is None else clip.token, state, strengths["strength_model"], strengths["strength_clip"],
            lora_metadata={})
        out_model = FakeRef(model_token, self.recorder, "MODEL")
        out_model.recorder_options = self.recorder_options
        out_clip = None if clip_token is None else FakeRef(clip_token, self.recorder, "CLIP")
        return out_model, out_clip


def outcome_of(model_in, clip_in, result, recorder, printed, error):
    if error is not None:
        return {"error": [type(error).__name__, str(error)], "calls": recorder.calls, "printed": printed}
    model_out, clip_out, text_out = result
    unwrap = lambda value: value.token if isinstance(value, FakeRef) else value
    model_out, clip_out = unwrap(model_out), unwrap(clip_out)
    return {
        "text": text_out,
        "model": "input" if model_out is model_in else model_out.lineage(),
        "clip": "input" if clip_out is clip_in else clip_out.lineage(),
        "calls": recorder.calls,
        "printed": printed,
    }


def run_original(module, text):
    recorder = Recorder()
    module.comfy.sd.load_lora_for_models = recorder.load_lora_for_models
    model_in, clip_in = Token("model"), Token("clip")
    out, err = stdio.StringIO(), None
    result = None
    try:
        with contextlib.redirect_stdout(out):
            result = module.LoraTagLoader().load_lora(model_in, clip_in, text)
    except Exception as exc:  # compared by type and message
        err = exc
    return outcome_of(model_in, clip_in, result, recorder, out.getvalue().splitlines(), err)


def run_v2(nodes, text, perturb=False):
    recorder = Recorder()
    assets = FakeAssets()
    nodes.sdk = types.SimpleNamespace(ctx=lambda: types.SimpleNamespace(assets=assets))
    model_in, clip_in = Token("model"), Token("clip")
    model_ref, clip_ref = FakeRef(model_in, recorder, "MODEL"), FakeRef(clip_in, recorder, "CLIP")
    model_ref.recorder_options = []
    out, err = stdio.StringIO(), None
    result = None
    try:
        with contextlib.redirect_stdout(out):
            output = asyncio.run(nodes.LoraTagLoader.execute(model=model_ref, clip=clip_ref, text=text))
        result = tuple(output.result)
        if result[0] is model_ref:
            result = (model_in,) + result[1:]
        if result[1] is clip_ref:
            result = (result[0], clip_in, result[2])
        if perturb:
            result = (result[0], result[1], result[2] + " ")
    except Exception as exc:
        err = exc
    outcome = outcome_of(model_in, clip_in, result, recorder, out.getvalue().splitlines(), err)
    return outcome, model_ref.recorder_options, assets.calls


HAND_PICKED = [
    "", " ", "a cat", "no tags at all", "<lora:a:1>", "<lora:a>", "<lora:a:>", "<lora::1>", "<lora:>", "<lora>", "<>",
    "<lora:a:0.5:0.25>", "<lora:a:0.5:>", "<lora:a::0.25>", "<lora:a:1e3>", "<lora:a:-1e3>", "<lora:a:150>", "<lora:a:-101>",
    "<lora:a:inf>", "<lora:a:-inf>", "<lora:a:nan>", "<lora:a:NaN:1>", "<lora:a:1_0>", "<lora:a:_1>", "<lora:a: 0.5>",
    "<lora:a:0.5 >", "<lora:a:abc>", "<lora:a:1:abc>", "<lora:a:1:2:3>", "<lora:a:0>", "<lora:a:0:0>", "<lora:a:-0>",
    "<lora:a:0.>", "<lora:a:.5>", "<lora:a:1.5e-3>", "<lora:a:1E2>", "<lora:a:+1>", "<LORA:a:1>", "<Lora:a:1>",
    "<hypernet:a:1>", "<lyco:a:1>", "<lora:zzz:1>", "<lora:A:1>", "<lora:ab:1>", "<lora:abc:1>", "<lora:a (1):1>",
    "<lora:sub/a:1>", "<lora:sub\\a:1>", "<lora:sub/b c:0.7>", "<lora:b c:0.7>", "<lora:deep:1>", "<lora:x/y:1>", "<lora:z:1>",
    "<lora:style_v2-1.0:0.8>", "<lora:Style:1>", "<lora:style:1>", "<lora:lcm-lora-sdxl:1>", "<lora:my.lora:1>",
    "<lora:1:1>", "<lora:a.safetensors:1>", "<lora:add_detail:0.5:1.5>", "<<lora:a:1>>", "<lora:<a>:1>", "<lora:a:1",
    "lora:a:1>", "<lora:a:1><lora:ab:0.5>", "<lora:a:1> and <lora:a:1>", "x<lora:a:1>y", "<lora:a:\n1>", "<lora:a\n:1>",
    "<lora: a:1>", "<lora :a:1>", "< lora:a:1>", "<lora:a(1):1>", "<lora:é:1>", "<lora:a:1>é", "<lora:a+b:1>",
    "<lora:a,b:1>", "<lora:a;b:1>", "<lora:a'b:1>", "<lora:a:1>\t<lora:ab:2>", "<embedding:x>", "<lora:a:0.5><>",
    "prefix <lora:sub/deep/zz:-0.5:2> suffix", "<lora:sub/deep:1>", "<lora:deep/zz:1>", "<lora:/a:1>", "<lora:..:1>",
    "<lora:a:1:2:>", "<lora:a:9" + "9" * 400 + ">", "<lora:" + "a" * 300 + ":1>", "<" + "lora:a:1" * 20 + ">",
]


def fuzz_cases(count, seed):
    rng = random.Random(seed)
    names = ["a", "ab", "abc", "A", "sub/a", "sub", "x/y/z", "Style", "style", "lcm", "1", "my.lora", "zz", "", "b c", "a (1)", "é"]
    numbers = ["1", "0", "-1", "0.5", "-0.25", "1e3", "inf", "nan", "1_0", " 2", "abc", "", ".5", "1.", "100.0001", "-100"]
    pieces = ["<", ">", ":", "lora", "LORA", "hypernet", " ", "\n", "\t", ",", "(", ")", "/", "\\", "_", "-", ".", "+", "é", "word"]
    out = []
    for _ in range(count):
        kind = rng.random()
        if kind < 0.6:
            parts = []
            for _ in range(rng.randint(1, 4)):
                tag = "<" + rng.choice(["lora", "lora", "lora", "LORA", "hypernet", "lyco", ""])
                for _ in range(rng.randint(0, 4)):
                    tag += ":" + rng.choice(names + numbers)
                tag += rng.choice([">", ">", ">", "", ">>"])
                parts.append(tag)
                if rng.random() < 0.5:
                    parts.append(rng.choice([" ", ", ", "text ", "\n", ""]))
            out.append("".join(parts))
        else:
            out.append("".join(rng.choice(pieces + names + numbers) for _ in range(rng.randint(0, 30))))
    return out


def compare_schema(original_class, v2_class):
    schema = v2_class.GET_SCHEMA()
    schema.validate()
    legacy = original_class.INPUT_TYPES()["required"]
    checks = {
        "node_id": schema.node_id == "LoraTagLoader",
        "display_name": schema.display_name == "Load LoRA Tag",
        "category": schema.category == original_class.CATEGORY,
        "input_ids": [i.id for i in schema.inputs] == list(legacy),
        "input_types": [i.io_type for i in schema.inputs] == [spec[0] for spec in legacy.values()],
        "text_multiline": schema.inputs[2].multiline is True,
        "inputs_required": all(not i.optional for i in schema.inputs),
        "output_types": [o.io_type for o in schema.outputs] == list(original_class.RETURN_TYPES),
        "output_names": [o.display_name for o in schema.outputs] == list(original_class.RETURN_NAMES),
        "not_output_node": not schema.is_output_node,
        "hidden_none": not schema.hidden,
        "sdk_refs": v2_class.SDK_REFS is True,
        "permissions": v2_class.SDK_PERMISSIONS == ("assets",),
    }
    return checks


def expected_manifest(v2_class):
    from comfy_secure_nodes.packmanifest import FORMAT, encode_schema
    from comfy_secure_nodes.packruntime import manifest_declaration
    row = {
        "class": "LoraTagLoader",
        "methods": {name: name in v2_class.__dict__ for name in ("check_lazy_status", "fingerprint_inputs", "validate_inputs")},
        "module": "nodes",
        "permissions": list(v2_class.SDK_PERMISSIONS),
        "schema": encode_schema(copy.deepcopy(v2_class.GET_SCHEMA())),
        "sdk_refs": True,
    }
    manifest = {"format": FORMAT, "nodes": {"LoraTagLoader": row}, "runtime": manifest_declaration(V2)}
    return json.dumps(manifest, indent=2, sort_keys=True) + "\n"


def main(argv):
    package, v2_nodes = load_v2()
    manifest_text = expected_manifest(v2_nodes.LoraTagLoader)
    if argv[:1] == ["generate-manifest"]:
        with open(os.path.join(RESULTS, "secure-nodes.json"), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(manifest_text)
        print("wrote /results/secure-nodes.json")
        return 0
    original = load_original(Recorder())
    cases = HAND_PICKED + fuzz_cases(4000, seed=20261102)
    mismatches, options_seen, applied, refused = [], set(), 0, 0
    for index, text in enumerate(cases):
        want = run_original(original, text)
        got, options, asset_calls = run_v2(v2_nodes, text)
        options_seen.update(json.dumps(o, sort_keys=True) for o in options)
        applied += len(want.get("calls", []))
        refused += "error" in want
        if want != got:
            mismatches.append({"index": index, "text": text, "original": want, "v2": got})
    # Negative control: one converted output perturbed must be caught by the same comparison.
    probe = "<lora:a:0.5> red"
    negative_red = run_original(original, probe) != run_v2(v2_nodes, probe, perturb=True)[0]
    # Counterfactual (evidence for the two apply_lora options): the same cases with the op's
    # defaults (skip_zero=True, allow_extended_strengths=False) forced on every call.
    real_apply = FakeRef.apply_lora

    async def defaults_only(self, asset, clip, strength_model, strength_clip, **_options):
        return await real_apply(self, asset, clip, strength_model, strength_clip)
    FakeRef.apply_lora = defaults_only
    try:
        counterfactual = sum(run_original(original, text) != run_v2(v2_nodes, text)[0] for text in cases)
    finally:
        FakeRef.apply_lora = real_apply
    schema = compare_schema(original.LoraTagLoader, v2_nodes.LoraTagLoader)
    with open(os.path.join(V2, "secure-nodes.json"), encoding="utf-8") as handle:
        manifest_equal = handle.read() == manifest_text
    entry = {"comfy_entrypoint": callable(getattr(package, "comfy_entrypoint", None)),
             "mapping_keys": sorted(package.NODE_CLASS_MAPPINGS) == sorted(original.NODE_CLASS_MAPPINGS) == ["LoraTagLoader"],
             "display_names": package.NODE_DISPLAY_NAME_MAPPINGS == original.NODE_DISPLAY_NAME_MAPPINGS}
    ok = not mismatches and all(schema.values()) and manifest_equal and all(entry.values())
    parity = {
        "pack": "comfyui_lora_tag_loader",
        "nodes": {"LoraTagLoader": {"verdict": "EXACT" if ok else "MISMATCH", "cases": len(cases),
                                    "lora_applications_compared": applied, "original_errors_compared": refused,
                                    "mismatches": len(mismatches)}},
        "v2_apply_lora_options_used": sorted(options_seen),
        "counterfactual_with_default_apply_lora_options": {"cases_that_would_differ": counterfactual},
        "schema": schema,
        "manifest_equals_real_encoder": manifest_equal,
        "entry": entry,
        "negative_control": {"perturbation": "STRING output + ' ' for one case", "turned_red": negative_red},
        "guest_sdk_base": BASE,
    }
    with open(os.path.join(RESULTS, "parity.json"), "w", encoding="utf-8") as handle:
        json.dump(parity, handle, indent=1, sort_keys=True)
        handle.write("\n")
    with open(os.path.join(RESULTS, "mismatches.json"), "w", encoding="utf-8") as handle:
        json.dump(mismatches[:50], handle, indent=1, sort_keys=True, default=repr)
        handle.write("\n")
    print(json.dumps({k: parity[k] for k in ("nodes", "manifest_equals_real_encoder", "negative_control", "v2_apply_lora_options_used",
                                             "counterfactual_with_default_apply_lora_options")}, indent=1))
    return 0 if ok and negative_red else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
