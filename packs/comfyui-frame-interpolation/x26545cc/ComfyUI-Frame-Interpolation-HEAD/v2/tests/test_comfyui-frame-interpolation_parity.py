"""Tier-1 parity for comfyui-frame-interpolation (pin 26545cc2): pristine vs v2, CPU gate.

    DEPS=<weights dir (fi-models/... + film_net_fp32.ref.safetensors)> run_in_gate.sh \
        <snapshot dir, or the ComfyUI-Frame-Interpolation-HEAD folder> <.../v2/tests> <results> \
        test_comfyui-frame-interpolation_parity.py

Writes /results/parity.json; exits 1 on any failed check. See _fi_harness.py for how pristine
nodes get their weights (verified-equal safetensors, never a download or an unpickle).
"""

import asyncio
import importlib
import json
import platform
import sys
from pathlib import Path

sys.path[:0] = ["/core", "/overlay", "/tests"]

import _fi_harness as H  # noqa: E402
import torch  # noqa: E402
from comfy_secure_nodes import packdb  # noqa: E402
from encode_manifest import build_manifest, serialize  # noqa: E402
from safetensors.torch import load_file  # noqa: E402

EDITED = {
    "__init__.py", "pyproject.toml", "vfi_utils.py", "vfi_models/rife/__init__.py",
    "vfi_models/rife/rife_arch.py", "vfi_models/ifrnet/__init__.py",
    "vfi_models/ifrnet/IFRNet_S_arch.py", "vfi_models/ifrnet/IFRNet_L_arch.py",
    "vfi_models/film/__init__.py", "vfi_models/film/film_arch.py",
}
GUEST_MODULES = [
    "secure_nodes.py", "_fi_weights.py", "_fi_device.py", "vfi_utils.py",
    "vfi_models/rife/__init__.py", "vfi_models/rife/rife_arch.py",
    "vfi_models/ifrnet/__init__.py", "vfi_models/ifrnet/IFRNet_S_arch.py",
    "vfi_models/ifrnet/IFRNet_L_arch.py", "vfi_models/film/__init__.py",
    "vfi_models/film/film_arch.py",
]
DENIED_IMPORTS = ("comfy.", "folder_paths", "nodes", "server", "execution", "yaml", "cv2", "cupy",
                  "taichi", "requests", "torch.hub", "urllib.request", "huggingface_hub")
PREFIX = "comfyui-frame-interpolation/"
NOT_CONVERTED = ("is not yet converted to Secure Nodes V2: its checkpoints ({}) are pickle files "
                 "that have not yet been converted to declared, verified weights")
CUPY = "it runs CUDA kernels through cupy, which a Secure Nodes guest cannot run"
GMFSS_KERNELS = ("GMFSS runs CUDA softsplat kernels through cupy (vfi_models/ops), which a Secure "
                 "Nodes guest cannot run")
EXPECTED_REFUSALS = {
    ("GMFSS Fortuna VFI", "GMFSS_fortuna_union"):
        PREFIX + "GMFSS Fortuna VFI is not yet converted to Secure Nodes V2: GMFSS_fortuna_union "
        "needs rife46.pth, which is no longer downloadable upstream (404 on every URL the pack "
        "tries), and " + GMFSS_KERNELS,
    ("GMFSS Fortuna VFI", "GMFSS_fortuna"):
        PREFIX + "GMFSS Fortuna VFI is not yet converted to Secure Nodes V2: " + GMFSS_KERNELS,
    ("AMT VFI", None): PREFIX + "AMT VFI " + NOT_CONVERTED.format("amt-*.pth"),
    ("ATM VFI", None): PREFIX + "ATM VFI " + NOT_CONVERTED.format("atm-vfi-*.pt")
        + ", and it needs the timm package",
    ("CAIN VFI", None): PREFIX + "CAIN VFI " + NOT_CONVERTED.format("pretrained_cain.pth"),
    ("FLAVR VFI", None): PREFIX + "FLAVR VFI " + NOT_CONVERTED.format("FLAVR_*.pth"),
    ("IFUnet VFI", None): PREFIX + "IFUnet VFI " + NOT_CONVERTED.format("IFUNet.pth"),
    ("M2M VFI", None): PREFIX + "M2M VFI " + NOT_CONVERTED.format("M2M.pth") + ", and " + CUPY,
    ("MOMO VFI", None): PREFIX + "MOMO VFI " + NOT_CONVERTED.format("momo-*.pth")
        + ", and it downloads torchvision RAFT weights at run time",
    ("STMFNet VFI", None): PREFIX + "STMFNet VFI " + NOT_CONVERTED.format("stmfnet.pth")
        + ", and " + CUPY,
    ("Sepconv VFI", None): PREFIX + "Sepconv VFI " + NOT_CONVERTED.format("sepconv.pth")
        + ", and " + CUPY,
    ("KSampler Gradually Adding More Denoise (efficient)", None):
        PREFIX + "KSampler Gradually Adding More Denoise (efficient) is not yet converted to "
        "Secure Nodes V2: it runs ComfyUI's sampler step by step inside the node, once per latent "
        "and denoise level, and Secure Nodes V2 has no sampling operation a node can call that way yet",
    ("IFRNet VFI", "IFRNet_S_GoPro.pth"):
        PREFIX + "IFRNet VFI is not yet converted to Secure Nodes V2: the IFRNet_S_GoPro.pth "
        "checkpoint is no longer downloadable upstream (404 on every URL the pack tries). Use "
        "IFRNet_S_Vimeo90K.pth or IFRNet_L_Vimeo90K.pth.",
    ("IFRNet VFI", "IFRNet_L_GoPro.pth"):
        PREFIX + "IFRNet VFI is not yet converted to Secure Nodes V2: the IFRNet_L_GoPro.pth "
        "checkpoint is no longer downloadable upstream (404 on every URL the pack tries). Use "
        "IFRNet_S_Vimeo90K.pth or IFRNet_L_Vimeo90K.pth.",
}
REFUSED_NODES = ["KSampler Gradually Adding More Denoise (efficient)", "GMFSS Fortuna VFI",
                 "IFUnet VFI", "M2M VFI", "Sepconv VFI", "AMT VFI", "STMFNet VFI", "FLAVR VFI",
                 "CAIN VFI", "ATM VFI", "MOMO VFI"]
INFO_FIELDS = ("name", "display_name", "category", "description", "output", "output_is_list",
               "output_name", "output_node", "is_input_list", "input_order",
               "has_intermediate_output")
UNSET_FIELDS = ("deprecated", "experimental", "dev_only", "api_node", "search_aliases",
                "output_tooltips", "essentials_category", "price_badge", "output_matchtypes")

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
    print(("PASS " if ok else "FAIL ") + f"{node} :: {name}" + ("" if ok else f": {str(detail)[:300]}"))
    return ok


# ------------------------------------------------------------------------- /object_info

def v1_node_info(node_class, obj_class):
    """Core's /object_info for a V1 class: server.py:839-884 at ComfyUI 6257422b."""
    info = {"input": obj_class.INPUT_TYPES()}
    info["input_order"] = {key: list(value.keys()) for key, value in obj_class.INPUT_TYPES().items()}
    info["is_input_list"] = getattr(obj_class, "INPUT_IS_LIST", False)
    info["output"] = obj_class.RETURN_TYPES
    info["output_is_list"] = (obj_class.OUTPUT_IS_LIST if hasattr(obj_class, "OUTPUT_IS_LIST")
                              else [False] * len(obj_class.RETURN_TYPES))
    info["output_name"] = (obj_class.RETURN_NAMES if hasattr(obj_class, "RETURN_NAMES")
                           else info["output"])
    info["name"] = node_class
    info["display_name"] = H.V1_DISPLAY.get(node_class, node_class)
    info["description"] = obj_class.DESCRIPTION if hasattr(obj_class, "DESCRIPTION") else ""
    info["category"] = getattr(obj_class, "CATEGORY", "sd")
    info["output_node"] = bool(getattr(obj_class, "OUTPUT_NODE", False) is True)
    info["has_intermediate_output"] = bool(getattr(obj_class, "HAS_INTERMEDIATE_OUTPUT", False) is True)
    if hasattr(obj_class, "OUTPUT_TOOLTIPS"):
        info["output_tooltips"] = obj_class.OUTPUT_TOOLTIPS
    info["search_aliases"] = getattr(obj_class, "SEARCH_ALIASES", [])
    return info


def plain(value):
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value]
    if isinstance(value, dict):
        return {key: plain(item) for key, item in value.items()}
    return value


def unset(value):
    # Applied ONLY to UNSET_FIELDS (flags and optional lists), where None, missing, False, [] and an
    # all-None list all mean "not set". Never applied to input options or INFO_FIELDS.
    if value is None or value is False or value == [] or value == {}:
        return True
    return isinstance(value, (list, tuple)) and all(item is None for item in value)


def without_output_node_hidden(v1, v2):
    """V3 adds hidden prompt + extra_pnginfo to every output node (_io.py Schema.finalize, 0cd9adec
    :1825-1829). A V1 output node that declares no hidden inputs has none. Core fills them and the
    frontend never shows them; drop exactly that pair, only in that case."""
    hidden = v2["input"].get("hidden")
    if (v2.get("output_node") and "hidden" not in v1["input"] and hidden is not None
            and set(hidden) == {"prompt", "extra_pnginfo"}):
        v2 = dict(v2, input={k: v for k, v in v2["input"].items() if k != "hidden"},
                  input_order={k: v for k, v in v2["input_order"].items() if k != "hidden"})
    return v2


def info_differences(v1, v2):
    v2 = without_output_node_hidden(v1, v2)
    diffs = []
    for field in INFO_FIELDS:
        if plain(v1.get(field)) != plain(v2.get(field)):
            diffs.append((field, plain(v1.get(field)), plain(v2.get(field))))
    for field in UNSET_FIELDS:
        a, b = v1.get(field), v2.get(field)
        if not (unset(a) and unset(b)) and plain(a) != plain(b):
            diffs.append((field, plain(a), plain(b)))
    for section in ("required", "optional", "hidden"):
        a, b = v1["input"].get(section, {}), v2["input"].get(section, {})
        if list(a) != list(b):
            diffs.append((f"input.{section}", list(a), list(b)))
            continue
        for name in a:
            ta, tb = a[name], b[name]
            v1_options = list(ta[0]) if isinstance(ta[0], (list, tuple)) else None
            kind_a = "COMBO" if v1_options is not None else ta[0]
            if kind_a != tb[0]:
                diffs.append((f"input.{section}.{name}.type", kind_a, tb[0]))
            opts_a = dict(ta[1]) if len(ta) > 1 else {}
            opts_b = dict(tb[1]) if len(tb) > 1 else {}
            if v1_options is not None and plain(v1_options) != plain(opts_b.get("options")):
                diffs.append((f"input.{section}.{name}.choices", v1_options, opts_b.get("options")))
            opts_b.pop("options", None)
            # A V3 Combo always serializes its default multiselect=false; V1 omits the key.
            if opts_b.get("multiselect") is False and "multiselect" not in opts_a:
                opts_b.pop("multiselect")
            opts_b = {k: v for k, v in opts_b.items() if v is not None}
            if plain(opts_a) != plain(opts_b):
                diffs.append((f"input.{section}.{name}.options", opts_a, opts_b))
    return diffs


# ------------------------------------------------------------------------- converted nodes

def compare_runs(node, label, v1_call, v2_call, cases=1):
    r1, r2 = H.outcome(v1_call), H.outcome(v2_call)
    if r1[0] != r2[0]:
        return record(node, label, False, f"pristine {r1[0]} {r1[1] if r1[0] == 'error' else ''} vs v2 "
                      f"{r2[0]} {r2[1] if r2[0] == 'error' else ''}", cases)
    if r1[0] == "error":
        return record(node, label + " (same error)", r1[1] == r2[1], f"{r1[1]} vs {r2[1]}", cases)
    ok, detail = H.same(tuple(r1[1]), tuple(r2[1]))
    return record(node, label, ok, detail, cases)


def main():
    head = H.pack_head()
    v2 = head / "v2"
    H.register_weights()
    environment = {"python": platform.python_version(), "torch": torch.__version__,
                   "pack_head": str(head)}

    # 1. Pristine bytes and untouched copies.
    expected = json.loads((Path("/tests") / "pristine_blobs.json").read_text())
    actual = {p.relative_to(head).as_posix(): p for p in sorted(head.rglob("*"))
              if p.is_file() and not p.relative_to(head).as_posix().startswith("v2/")}
    record("(pack)", "pristine/file-set", set(actual) == set(expected),
           sorted(set(actual) ^ set(expected)), kind="integrity")
    bad = [name for name, path in actual.items() if H.blob_id(path.read_bytes()) != expected.get(name)]
    record("(pack)", "pristine/blob-ids", not bad, bad, cases=len(actual), kind="integrity")
    changed = [name for name, path in actual.items()
               if name not in EDITED and (v2 / name).read_bytes() != path.read_bytes()]
    record("(pack)", "v2/untouched-copies", not changed, changed, cases=len(actual) - len(EDITED),
           kind="integrity")

    # 2. Guest-reachable modules import nothing host-only or network-capable at module level.
    for name in GUEST_MODULES:
        imports = H.module_level_imports(v2 / name)
        denied = [m for m in imports if m and m.startswith(DENIED_IMPORTS)]
        record("(pack)", f"guest-imports/{name}", not denied, denied, kind="integrity")

    # 3. Load both sides.
    V1 = H.pristine_classes()
    v1_utils = sys.modules["vfi_utils"]
    new = H.load_package("fi_v2", v2)
    S = sys.modules["fi_v2.secure_nodes"]
    W = sys.modules["fi_v2._fi_weights"]
    v2_film_arch = importlib.import_module("fi_v2.vfi_models.film.film_arch")
    manifest = json.loads((v2 / "secure-nodes.json").read_bytes())
    # The manifest is serialized with sort_keys=True, so compare it as a set; the mapping order exactly.
    record("(pack)", "ids", list(V1) == list(new.NODE_CLASS_MAPPINGS)
           and set(manifest["nodes"]) == set(V1) and len(V1) == 16,
           [list(V1), list(new.NODE_CLASS_MAPPINGS), sorted(manifest["nodes"])], kind="integrity")
    record("(pack)", "display-mappings", new.NODE_DISPLAY_NAME_MAPPINGS == H.V1_DISPLAY,
           new.NODE_DISPLAY_NAME_MAPPINGS, kind="integrity")
    record("(pack)", "manifest-is-encoder-output",
           serialize(build_manifest(v2, "fi_v2_regen")) == (v2 / "secure-nodes.json").read_text(),
           "secure-nodes.json differs from the encoder", kind="integrity")

    # 4. /object_info for all 16: guest class and host proxy against the original.
    loaded = packdb.load_pack(H.snapshot_dir(), mount_name="custom_nodes.fi_parity_proxy",
                              pack_id=f"{H.SLUG}/{H.KEY}")
    v1_infos = {}
    for node_id, v1_cls in V1.items():
        v1_infos[node_id] = v1_node_info(node_id, v1_cls)
        for side, cls in (("guest-class", new.NODE_CLASS_MAPPINGS[node_id]),
                          ("host-proxy", loaded.node_mappings[node_id])):
            diffs = info_differences(v1_infos[node_id], cls.GET_NODE_INFO_V1())
            record(node_id, f"object-info/{side}", not diffs, diffs,
                   cases=len(INFO_FIELDS) + len(UNSET_FIELDS) + 1, kind="schema")
    record("(pack)", "proxy/display-mappings",
           {k: v for k, v in loaded.display_mappings.items() if v != k} == H.V1_DISPLAY,
           loaded.display_mappings, kind="schema")

    # 5. Converted nodes, pristine vs v2, exact.
    states_v1 = v1_utils.InterpolationStateList
    v1_mods = {kind: sys.modules[f"vfi_models.{kind}"] for kind in ("rife", "ifrnet", "film")}

    def with_states(inputs, states):
        v1_inputs, v2_inputs = dict(inputs), dict(inputs)
        if states is not None:
            v1_inputs["optional_interpolation_states"] = states_v1(
                frame_indices=list(states[0]), is_skip_list=states[1])
            v2_inputs["optional_interpolation_states"] = {
                "frame_indices": list(states[0]), "is_skip_list": states[1]}
        return v1_inputs, v2_inputs

    def run_pair(node, kind, v1_cls, v2_cls, label, inputs, states=None, factory=None):
        v1_inputs, v2_inputs = with_states(inputs, states)

        def v1_call():
            with H.pristine_weights(v1_mods[kind], W, factory):
                return getattr(v1_cls(), v1_cls.FUNCTION)(**v1_inputs)

        return compare_runs(node, label, v1_call,
                            lambda: asyncio.run(H.run_v2(v2_cls, **v2_inputs)))

    rife_frames = H.frames(3, 64, 64, seed=1)
    rife_base = dict(frames=rife_frames, clear_cache_after_n_frames=10, multiplier=2,
                     fast_mode=True, ensemble=True, scale_factor=1.0, dtype="float32",
                     torch_compile=False, batch_size=1)
    for ckpt in ("sudo_rife4_269.662_testV1_scale1.pth", "rife47.pth", "rife49.pth",
                 "rife417.pth", "rife426.pth"):
        run_pair("RIFE VFI", "rife", V1["RIFE VFI"], S.RIFE_VFI, f"{ckpt}/defaults",
                 dict(rife_base, ckpt_name=ckpt))
    variations = [
        ("multiplier=1", dict(multiplier=1), None), ("multiplier=3", dict(multiplier=3), None),
        ("fast_mode=False", dict(fast_mode=False), None), ("ensemble=False", dict(ensemble=False), None),
        ("scale=0.25", dict(scale_factor=0.25), None), ("scale=0.5", dict(scale_factor=0.5), None),
        ("scale=2.0", dict(scale_factor=2.0), None), ("scale=4.0", dict(scale_factor=4.0), None),
        ("dtype=float16", dict(dtype="float16"), None), ("dtype=bfloat16", dict(dtype="bfloat16"), None),
        ("batch_size=2", dict(batch_size=2), None), ("clear_cache=1", dict(clear_cache_after_n_frames=1), None),
        ("multiplier=list[2,3]", dict(multiplier=[2, 3]), None),
        ("states skip [0]", {}, ([0], True)), ("states keep-only [1]", {}, ([1], False)),
    ]
    for label, overrides, states in variations:
        run_pair("RIFE VFI", "rife", V1["RIFE VFI"], S.RIFE_VFI, f"rife49.pth/{label}",
                 dict(rife_base, ckpt_name="rife49.pth", **overrides), states)
    for label, overrides in (("scale=0.5", dict(scale_factor=0.5)), ("multiplier=3", dict(multiplier=3))):
        run_pair("RIFE VFI", "rife", V1["RIFE VFI"], S.RIFE_VFI, f"rife426.pth/{label}",
                 dict(rife_base, ckpt_name="rife426.pth", **overrides))

    ifr_frames = H.frames(3, 64, 64, seed=2)
    ifr_base = dict(frames=ifr_frames, clear_cache_after_n_frames=10, multiplier=2, scale_factor=1.0)
    for ckpt in ("IFRNet_S_Vimeo90K.pth", "IFRNet_L_Vimeo90K.pth"):
        run_pair("IFRNet VFI", "ifrnet", V1["IFRNet VFI"], S.IFRNet_VFI, f"{ckpt}/defaults",
                 dict(ifr_base, ckpt_name=ckpt))
    for label, overrides, states in (
            ("multiplier=3", dict(multiplier=3), None), ("scale=0.5", dict(scale_factor=0.5), None),
            ("scale=2.0", dict(scale_factor=2.0), None), ("scale=0.25", dict(scale_factor=0.25), None),
            ("states skip [1]", {}, ([1], True))):
        run_pair("IFRNet VFI", "ifrnet", V1["IFRNet VFI"], S.IFRNet_VFI,
                 f"IFRNet_S_Vimeo90K.pth/{label}",
                 dict(ifr_base, ckpt_name="IFRNet_S_Vimeo90K.pth", **overrides), states)

    def film_factory(state_dict):
        # Pristine FILM loads a TorchScript archive (not allowed here). Its stand-in is the pack's
        # own Python Interpolator with the same tensors; the reference check below ties it to the
        # TorchScript module's output.
        model = v2_film_arch.Interpolator()
        model.load_state_dict(state_dict)
        return model

    film_frames = H.frames(3, 128, 128, seed=3)
    film_base = dict(ckpt_name="film_net_fp32.pt", frames=film_frames, clear_cache_after_n_frames=10,
                     multiplier=2)
    for label, overrides, states in (("defaults", {}, None), ("multiplier=3", dict(multiplier=3), None),
                                     ("states skip [0]", {}, ([0], True))):
        run_pair("FILM VFI", "film", V1["FILM VFI"], S.FILM_VFI, f"film_net_fp32.pt/{label}",
                 dict(film_base, **overrides), states, factory=film_factory)

    # FILM reference: GERALD ran the pinned TorchScript archive in his isolated converter on these inputs.
    reference = load_file(str(H.FILM_REFERENCE))
    model = film_factory(load_file(str(H.converted_file(W, "film", "film_net_fp32.pt")))).eval()
    # GERALD produced the reference with one intra-op thread (m_360e6935c2). In his container the
    # eager Interpolator equals the TorchScript output bit for bit. Conv reduction order depends on
    # the thread count, so reproduce with one thread here.
    threads = torch.get_num_threads()
    torch.set_num_threads(1)
    try:
        with torch.no_grad():
            produced = model(reference["x0"], reference["x1"], reference["dt"])
    finally:
        torch.set_num_threads(threads)
    exact, detail = H.same(produced, reference["output"])
    max_abs = (produced.double() - reference["output"].double()).abs().max().item()
    film_reference = {"exact": exact, "detail": detail, "max_abs": max_abs,
                      "shape": list(produced.shape), "dtype": str(produced.dtype),
                      "bound": 1e-5, "note": (
                          "Pristine FILM is a TorchScript archive, which this harness may not load. "
                          "The reference output came from GERALD's isolated converter (x86_64, one "
                          "intra-op thread), where eager == TorchScript bit for bit. This check runs "
                          "with one thread and is expected to be exact. The bound (1e-5, far below "
                          "1/255) only tolerates another CPU's float32 kernel differences.")}
    # Pre-declared criterion for this cross-implementation check: same shape/dtype and max abs <= 1e-5.
    record("FILM VFI", "python-interpolator-vs-torchscript-reference(max_abs<=1e-5)",
           produced.shape == reference["output"].shape and produced.dtype == reference["output"].dtype
           and max_abs <= 1e-5, film_reference, kind="reference")

    # Make Interpolation State List: the token carries exactly the pristine object's fields.
    for text, skip in (("1,2,3", True), ("0", False), (" 4, 5 ", True), ("-1,10", True), ("7", True),
                       ("", True), ("a,b", True), ("1,,2", False)):
        def v1_call(text=text, skip=skip):
            (states,) = V1["Make Interpolation State List"]().create_options(
                frame_indices=text, is_skip_list=skip)
            return ({"frame_indices": states.frame_indices, "is_skip_list": states.is_skip_list},)

        compare_runs("Make Interpolation State List", f"{text!r}/{skip}", v1_call,
                     lambda text=text, skip=skip: asyncio.run(H.run_v2(
                         S.MakeInterpolationStateList, frame_indices=text, is_skip_list=skip)))
    token = asyncio.run(H.run_v2(S.MakeInterpolationStateList, frame_indices="1,3", is_skip_list=True))[0]
    (v1_states,) = V1["Make Interpolation State List"]().create_options(frame_indices="1,3", is_skip_list=True)
    rebuilt = S.states_from(token)
    record("Make Interpolation State List", "token-rebuilds-upstream-object",
           [rebuilt.is_frame_skipped(i) for i in range(6)] == [v1_states.is_frame_skipped(i) for i in range(6)]
           and type(rebuilt).__name__ == "InterpolationStateList", token)
    bad_token = H.outcome(lambda: S.states_from({"frame_indices": ["1"], "is_skip_list": True}))
    record("Make Interpolation State List", "malformed-token-refused",
           bad_token[0] == "error" and bad_token[1][0] == "InterpolationStatesError", bad_token)

    # VFI FloatToInt.
    for value in (0, 0.0, 1.5, 2.999, 1000000.5, [1.2, 3.7], (0.5, 2.5)):
        compare_runs("VFI FloatToInt", repr(value),
                     lambda value=value: V1["VFI FloatToInt"]().convert(float=value),
                     lambda value=value: asyncio.run(H.run_v2(S.FloatToInt, float=value)))

    # 6. Refusals: exact text at validation and at execute, for every refused option.
    def refused_inputs(node_id, option):
        if node_id.startswith("KSampler"):
            return {"sampler_name": "euler", "scheduler": "normal"}
        if node_id == "IFRNet VFI":
            # A converted node: execute takes every input, as core passes them.
            return dict(ifr_base, ckpt_name=option)
        return {"ckpt_name": option}

    def validate_inputs_of(node_id, inputs):
        return {k: v for k, v in inputs.items() if k in ("ckpt_name", "sampler_name", "scheduler")}

    for (node_id, option), message in EXPECTED_REFUSALS.items():
        cls = new.NODE_CLASS_MAPPINGS[node_id]
        options = [option] if option else (
            [None] if node_id.startswith("KSampler") else
            v1_infos[node_id]["input"]["required"]["ckpt_name"][0])
        for choice in options:
            inputs = refused_inputs(node_id, choice)
            validated = cls.validate_inputs(**validate_inputs_of(node_id, inputs))
            record(node_id, f"refusal/validate/{choice}", validated == message, validated,
                   kind="refusal")
            raised = H.outcome(lambda: asyncio.run(H.run_v2(cls, **inputs)))
            record(node_id, f"refusal/execute/{choice}",
                   raised == ("error", ("FrameInterpolationRefused", message)), raised, kind="refusal")

    # Core's queue-time view of a saved workflow: a refused node and a refused IFRNet option.
    for node_id, ckpt in (("CAIN VFI", "pretrained_cain.pth"), ("IFRNet VFI", "IFRNet_L_GoPro.pth")):
        previous = H.core_nodes.NODE_CLASS_MAPPINGS.get(node_id)
        H.core_nodes.NODE_CLASS_MAPPINGS[node_id] = new.NODE_CLASS_MAPPINGS[node_id]
        try:
            inputs = {"ckpt_name": ckpt, "frames": ["2", 0], "clear_cache_after_n_frames": 10,
                      "multiplier": 2}
            if node_id == "IFRNet VFI":
                inputs["scale_factor"] = 1.0
            prompt = {"2": {"class_type": "EmptyImage",
                            "inputs": {"width": 64, "height": 64, "batch_size": 3, "color": 0}},
                      "4": {"class_type": node_id, "inputs": inputs}}
            ok, errors, _ = asyncio.run(H.execution.validate_inputs("fi-parity", prompt, "4", {}))
            message = EXPECTED_REFUSALS[(node_id, ckpt if node_id == "IFRNet VFI" else None)]
            record(node_id, "core-validation/refused", ok is False and errors == [{
                "type": "custom_validation_failed", "message": "Custom validation failed for node",
                "details": f"ckpt_name - {message}", "extra_info": {"input_name": "ckpt_name"}}],
                errors, kind="refusal")
        finally:
            if previous is None:
                H.core_nodes.NODE_CLASS_MAPPINGS.pop(node_id, None)
            else:
                H.core_nodes.NODE_CLASS_MAPPINGS[node_id] = previous

    # 7. Negative controls: each perturbation must turn its comparator red.
    controls = {}
    out_v2 = asyncio.run(H.run_v2(S.RIFE_VFI, ckpt_name="rife49.pth", **rife_base))[0]
    with H.pristine_weights(v1_mods["rife"], W):
        out_v1 = V1["RIFE VFI"]().vfi(ckpt_name="rife49.pth", **rife_base)[0]
    perturbed = out_v2.clone()
    perturbed[0, 0, 0, 0] += 1.0 / 1024
    controls["perturbed-rife-output-detected"] = (H.same(out_v1, out_v2)[0]
                                                  and not H.same(out_v1, perturbed)[0])
    original_define = S.RIFE_VFI.__dict__["define_schema"]

    def perturbed_schema(cls):
        schema = original_define.__func__(cls)
        schema.display_name = "RIFE VFI (perturbed)"
        return schema

    S.RIFE_VFI.define_schema = classmethod(perturbed_schema)
    try:
        controls["perturbed-schema-detected"] = bool(
            info_differences(v1_infos["RIFE VFI"], S.RIFE_VFI.GET_NODE_INFO_V1()))
    finally:
        S.RIFE_VFI.define_schema = original_define
    controls["schema-restored"] = not info_differences(v1_infos["RIFE VFI"], S.RIFE_VFI.GET_NODE_INFO_V1())
    saved = S.KSAMPLER_REASON
    S.KSAMPLER_REASON = saved + " (perturbed)"
    try:
        key = ("KSampler Gradually Adding More Denoise (efficient)", None)
        controls["perturbed-refusal-detected"] = (
            new.NODE_CLASS_MAPPINGS[key[0]].validate_inputs("euler", "normal") != EXPECTED_REFUSALS[key])
    finally:
        S.KSAMPLER_REASON = saved
    for name, ok in controls.items():
        record("(pack)", f"negative-control/{name}", ok, kind="control")
    return finish(environment, controls, film_reference)


def finish(environment, controls, film_reference):
    nodes = {}
    for node_id, row in per_node.items():
        if node_id.startswith("("):
            continue
        if row["failed"]:
            verdict = "MISMATCH"
        elif "parity" in row["kinds"] and "refusal" in row["kinds"]:
            verdict = "EXACT (refused options: REFUSED-AS-DESIGNED)"
        elif "parity" in row["kinds"]:
            verdict = "EXACT"
        else:
            verdict = "REFUSED-AS-DESIGNED"
        nodes[node_id] = {"verdict": verdict, "cases": row["cases"], "failed": row["failed"]}
        if node_id == "FILM VFI":
            nodes[node_id]["model_vs_torchscript_reference"] = {
                "exact": film_reference["exact"], "max_abs": film_reference["max_abs"]}
    failed = [c["node"] + " :: " + c["check"] for c in checks if not c["ok"]]
    result = {"pack": H.SLUG, "pin": H.PIN, "nodes": nodes, "negative_control": controls,
              "film_reference": film_reference, "checks": checks, "failed": failed,
              "environment": environment}
    Path("/results/parity.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"nodes": {k: v["verdict"] for k, v in nodes.items()}, "failed": failed}))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
