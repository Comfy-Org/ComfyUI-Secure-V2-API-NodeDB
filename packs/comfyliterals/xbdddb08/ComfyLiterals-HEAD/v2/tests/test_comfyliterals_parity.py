"""Tier-1 parity for ComfyLiterals: the original and v2 side by side in the gate container.

    run_in_gate.sh <pack root (pristine + v2/) or a snapshot dir holding it> <.../v2/tests> <results dir> \
        test_comfyliterals_parity.py

Writes /results/parity.json. Every node is a pure value node, so each case compares the outputs exactly (type,
float.hex for floats) or the raised exception (type and message), plus console output and the node interface.
"""
import contextlib
import importlib.util
import io as _stdio
import json
import math
import sys
from pathlib import Path

sys.path[:0] = ["/core", "/overlay"]
from comfy.cli_args import args as _cli_args  # noqa: E402

_cli_args.cpu = True
import folder_paths  # noqa: E402,F401  (the original imports it)


def pack_root(root=Path("/pack")):
    if (root / "v2").is_dir():
        return root
    heads = [d for d in sorted(root.iterdir()) if d.is_dir() and not d.name.startswith(".")]
    if len(heads) != 1:
        raise SystemExit(f"/pack must hold exactly one pack folder: {heads}")
    return heads[0]


PACK = pack_root()
V2 = PACK / "v2"
RESULTS = Path("/results")


def load(name, folder):
    spec = importlib.util.spec_from_file_location(name, folder / "__init__.py",
                                                  submodule_search_locations=[str(folder)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ORIGINAL = load("literals_original", PACK)   # its symlink_web_dir finds no web/extensions root and only prints
CONVERTED = load("literals_v2", V2)


def norm(value):
    if isinstance(value, bool):
        return ["bool", value]
    if isinstance(value, int):
        return ["int", value]
    if isinstance(value, float):
        return ["float", value.hex()]
    if isinstance(value, str):
        return ["str", value]
    if isinstance(value, (list, tuple)):
        return [type(value).__name__, [norm(v) for v in value]]
    return ["other", repr(value)]


def outcome(fn):
    out = _stdio.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            result = fn()
        return {"ok": norm(result), "stdout": out.getvalue()}
    except Exception as e:  # noqa: BLE001
        return {"error": [type(e).__name__, str(e)], "stdout": out.getvalue()}


def run_original(node_id, kwargs):
    cls = ORIGINAL.NODE_CLASS_MAPPINGS[node_id]
    return outcome(lambda: tuple(getattr(cls(), cls.FUNCTION)(**kwargs)))


def run_converted(node_id, kwargs):
    cls = CONVERTED.NODE_CLASS_MAPPINGS[node_id]
    return outcome(lambda: tuple(cls.execute(**kwargs).args))


CHECKS = []


def check(node, case, ok, detail=None):
    CHECKS.append({"node": node, "case": case, "ok": bool(ok), "detail": detail})


def compare(node, case, kwargs, stdout_must_match=True):
    a, b = run_original(node, kwargs), run_converted(node, kwargs)
    same = a.get("ok") == b.get("ok") and a.get("error") == b.get("error")
    if stdout_must_match:
        same = same and a["stdout"] == b["stdout"]
    check(node, case, same, {"original": a, "v2": b})


NUMBERS = ["0", "42", "-7", " 12 ", "+5", "1e3", "3.5", "-0", "0x10", "1_000", "abc", "", " ", "inf", "-inf", "nan",
           "NaN", "1e400", "٣", "１２", "9" * 40, "1.0", ".5", "5.", "-1.5e-3", "\t8\n"]


def value_cases():
    for s in NUMBERS:
        compare("Int", f"int({s!r})", {"Number": s})
        compare("Float", f"float({s!r})", {"Number": s})
    for s in ["", "a", "multi\nline\n", "  spaced  ", "unicode ✓ ünï", "x" * 5000]:
        compare("String", f"string({s[:12]!r})", {"String": s})
        compare("KepStringLiteral", f"kep({s[:12]!r})", {"String": s})
    for s in ["", "\n", "a", "a\nb", "a\n\nb\n", "\n\nx.safetensors\ny.ckpt\n\n", "  \n  ", "sub/dir/m.safetensors"]:
        compare("Checkpoint", f"ckpt({s!r})", {"literal": s})
        compare("Lora", f"lora({s!r})", {"literal": s})


def operation_cases():
    values = {"Int": [0, 1, -3, 7, 2 ** 40], "Float": [0.0, 1.5, -2.25, 1e-9, float("inf"), float("nan")]}
    for at in ("Int", "Float"):
        for bt in ("Int", "Float"):
            for op in ("A+B", "A-B", "A*B", "A/B"):
                for av in values[at]:
                    for bv in values[bt]:
                        kwargs = {"A Type": at, "B Type": bt, "Operation": op,
                                  f"A - {at}": av, f"B - {bt}": bv}
                        compare("Operation", f"{at}{op}{bt}({av!r},{bv!r})", kwargs)
    # error paths: the selected input is not connected
    compare("Operation", "missing-A", {"A Type": "Int", "B Type": "Int", "Operation": "A+B", "B - Int": 1})
    compare("Operation", "missing-B", {"A Type": "Float", "B Type": "Float", "Operation": "A*B", "A - Float": 1.0})
    compare("Operation", "wrong-type-connected", {"A Type": "Int", "B Type": "Int", "Operation": "A-B",
                                                  "A - Float": 1.0, "B - Int": 2})


def interface_cases():
    for node_id in ORIGINAL.NODE_CLASS_MAPPINGS:
        a, b = ORIGINAL.NODE_CLASS_MAPPINGS[node_id], CONVERTED.NODE_CLASS_MAPPINGS[node_id]
        ia, ib = a.INPUT_TYPES(), b.INPUT_TYPES()
        for section in ("required", "optional"):
            sa, sb = ia.get(section, {}), ib.get(section, {})
            check(node_id, f"inputs.{section}.names", list(sa) == list(sb), [list(sa), list(sb)])
            for name in sa:
                ta = sa[name][0]
                ta = "COMBO" if isinstance(ta, list) else str(ta)
                oa = dict(sa[name][1]) if len(sa[name]) > 1 else {}
                if isinstance(sa[name][0], list):
                    oa["options"] = list(sa[name][0])
                tb, ob = str(sb[name][0]), (dict(sb[name][1]) if len(sb[name]) > 1 else {})
                check(node_id, f"inputs.{section}.{name}.type", ta == tb, [ta, tb])
                diff = {k: (oa[k], ob.get(k, "<absent>")) for k in oa if ob.get(k, "<absent>") != oa[k]}
                check(node_id, f"inputs.{section}.{name}.options", not diff, diff)
        check(node_id, "RETURN_TYPES", [str(t) for t in a.RETURN_TYPES] == [str(t) for t in b.RETURN_TYPES],
              [list(map(str, a.RETURN_TYPES)), list(map(str, b.RETURN_TYPES))])
        names_a = list(getattr(a, "RETURN_NAMES", None) or [str(t) for t in a.RETURN_TYPES])
        check(node_id, "RETURN_NAMES", names_a == list(b.RETURN_NAMES), [names_a, list(b.RETURN_NAMES)])
        lists_a = list(getattr(a, "OUTPUT_IS_LIST", None) or [False] * len(a.RETURN_TYPES))
        check(node_id, "OUTPUT_IS_LIST", lists_a == list(b.OUTPUT_IS_LIST), [lists_a, list(b.OUTPUT_IS_LIST)])
        check(node_id, "CATEGORY", a.CATEGORY == b.CATEGORY, [a.CATEGORY, b.CATEGORY])
        shown_a = ORIGINAL.NODE_DISPLAY_NAME_MAPPINGS.get(node_id, node_id)
        check(node_id, "display_name", shown_a == b.GET_SCHEMA().display_name, [shown_a, b.GET_SCHEMA().display_name])


def negative_control():
    cls = CONVERTED.NODE_CLASS_MAPPINGS["Float"]
    saved = cls.execute
    cls.execute = classmethod(lambda c, Number: CONVERTED.nodes.io.NodeOutput(float(Number) + 1e-12))
    try:
        a, b = run_original("Float", {"Number": "1.5"}), run_converted("Float", {"Number": "1.5"})
        return {"perturbed-float-detected": a["ok"] != b["ok"]}
    finally:
        cls.execute = saved


def main():
    value_cases()
    operation_cases()
    interface_cases()
    control = negative_control()
    nodes = {}
    for node in ORIGINAL.NODE_CLASS_MAPPINGS:
        mine = [c for c in CHECKS if c["node"] == node]
        failed = [c for c in mine if not c["ok"]]
        nodes[node] = {"verdict": "EXACT" if not failed else "MISMATCH", "cases": len(mine), "failed": failed[:8]}
    for node in ("Checkpoint", "Lora"):
        nodes[node]["known_differences"] = ["the text box of a NEW node is not pre-filled with the host's file names"]
    nodes["Operation"]["known_differences"] = ["the frontend extension that hides the unused A/B input is not served"]
    result = {"pack": "comfyliterals", "nodes": nodes, "negative_control": {**control, "turned_red": all(control.values())}}
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "parity.json").write_text(json.dumps(result, indent=1, sort_keys=True, default=str))
    print(json.dumps({n: (v["verdict"], v["cases"]) for n, v in nodes.items()}), json.dumps(result["negative_control"]))
    bad = any(v["verdict"] != "EXACT" for v in nodes.values()) or not result["negative_control"]["turned_red"]
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
