"""Tier-1 parity: the original XTNodes prompt nodes (V1) vs the V2 nodes, side by side, CPU only.

    run_in_gate.sh <pack root (pristine + v2/)> <v2/tests> <results dir> test_easycivitai_parity.py

V1 is civitaiNodes/prompt_concatenate.py from the pristine copy (a pure-Python module). V2 is v2/ loaded as a bare
namespace package against the guest SDK base, as the production loader does. For every case the test compares the
returned result, the UI text, and the type and message of any exception, exactly. It also compares the node
interfaces. A perturbed result must turn the comparator red. Writes /results/parity.json.
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import os
import random
import shutil
import sys
import types
from pathlib import Path

PACK = Path(os.environ.get("XT_PACK", "/pack"))
RESULTS = Path(os.environ.get("XT_RESULTS", "/results"))
BASE = "/bases/0cd9adec273a703eb3d1c715d83ff1c7d2bb00746330c866c7e3ac644c80ebbb/common-site-packages"

POOL = [
    "", " ", "a, b, c", "a,b,,c", "  x  ,  y ", "cat\ndog\rbird", "tab\tsep", "full，width，comma", "\f\v",
    "under_score, under score", "dup, dup, DUP!, d-u-p", "1girl, solo, (masterpiece:1.2), 1girl", "a, a , a",
    "日本語, テスト, 日本語", "emoji 😀, 😀 emoji", "a_b c_d, a b c d", "Hello, World!, hello world",
    "  leading, trailing  ", ",,,", "x" * 300, "mixed\t_tabs_\nand_newlines", "(a:1.1), [b], {c|d}",
    123, 4.5, 0, -7, True, False, None,
    ["a", "b"], ["x", ["y", "z"]], [], ["", "a"], [["deep", ["deeper"]], "top"], ["a, b", "b, c"],
    [1, 2], ["ok", 3],
]
STYLES = ["keep", "space", "underscore"]


def load_v1():
    dst = Path("/tmp/xt-v1")
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(PACK / "civitaiNodes", dst / "civitaiNodes", ignore=shutil.ignore_patterns("__pycache__"))
    spec = importlib.util.spec_from_file_location("xt_v1_prompt", dst / "civitaiNodes" / "prompt_concatenate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_v2():
    sys.path[:0] = [BASE, "/core"]
    dst = Path("/tmp/xt-v2/v2")
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(PACK / "v2", dst, ignore=shutil.ignore_patterns("__pycache__"))
    pkg = types.ModuleType("xt_v2")
    pkg.__path__ = [str(dst)]
    pkg.__package__ = "xt_v2"
    sys.modules["xt_v2"] = pkg
    return importlib.import_module("xt_v2.xt_prompt_nodes")


def outcome(fn):
    try:
        value = fn()
    except Exception as e:  # noqa: BLE001
        return {"error": [type(e).__name__, str(e)]}
    return value


def v1_call(v1, node, kwargs):
    cls = {"XTNodesPromptConcatenate": v1.PromptConcatenate, "XTNodesCleanPrompt": v1.CleanPrompt}[node]
    method = "_concatenate_prompt" if node == "XTNodesPromptConcatenate" else "_clean_prompt"

    def run():
        r = getattr(cls(), method)(**kwargs)
        return {"result": list(r["result"]), "ui": r["ui"]}
    return outcome(run)


def v2_call(v2, node, kwargs):
    cls = v2.NODE_CLASS_MAPPINGS[node]

    def run():
        out = cls.execute(**kwargs)
        return {"result": list(out.args), "ui": out.ui}
    return outcome(run)


def cases():
    rng = random.Random(20261103)
    out = []
    for style in STYLES:
        for dedup in (True, False):
            for value in POOL:
                out.append(("XTNodesCleanPrompt", dict(remove_duplicates=dedup, whitespace_style=style, prompt=value)))
            out.append(("XTNodesCleanPrompt", dict(remove_duplicates=dedup, whitespace_style=style)))
            out.append(("XTNodesPromptConcatenate", dict(remove_duplicates=dedup, whitespace_style=style)))
            for _ in range(60):
                kw = dict(remove_duplicates=dedup, whitespace_style=style)
                for name in "ABCDE":
                    if rng.random() < 0.55:
                        kw[f"prompt_{name}"] = rng.choice(POOL)
                out.append(("XTNodesPromptConcatenate", kw))
    return out


def interface(v1, v2):
    """V1 INPUT_TYPES / RETURN_* / CATEGORY against the V2 schema."""
    diffs = []
    for node, v1cls in (("XTNodesPromptConcatenate", v1.PromptConcatenate), ("XTNodesCleanPrompt", v1.CleanPrompt)):
        schema = v2.NODE_CLASS_MAPPINGS[node].GET_SCHEMA()
        it = v1cls.INPUT_TYPES()
        v1_inputs = {**{k: ("required", v) for k, v in it["required"].items()},
                     **{k: ("optional", v) for k, v in it.get("optional", {}).items()}}
        v2_inputs = {i.id: i for i in schema.inputs}
        if list(v1_inputs) != list(v2_inputs):
            diffs.append(f"{node}: input order/ids {list(v1_inputs)} != {list(v2_inputs)}")
        for name, (section, spec) in v1_inputs.items():
            i = v2_inputs.get(name)
            if i is None:
                continue
            if (section == "optional") != bool(getattr(i, "optional", False)):
                diffs.append(f"{node}.{name}: optional {section} vs {getattr(i, 'optional', False)}")
            t = spec[0]
            opts = spec[1] if len(spec) > 1 else {}
            if isinstance(t, list):
                if list(getattr(i, "options", [])) != t:
                    diffs.append(f"{node}.{name}: options {t} vs {getattr(i, 'options', None)}")
            elif str(t) != i.get_io_type():
                diffs.append(f"{node}.{name}: type {t!r} vs {i.get_io_type()!r}")
            if "default" in opts and getattr(i, "default", None) != opts["default"]:
                diffs.append(f"{node}.{name}: default {opts['default']!r} vs {getattr(i, 'default', None)!r}")
        if [o.get_io_type() for o in schema.outputs] != list(v1cls.RETURN_TYPES):
            diffs.append(f"{node}: RETURN_TYPES")
        if [o.display_name for o in schema.outputs] != list(v1cls.RETURN_NAMES):
            diffs.append(f"{node}: RETURN_NAMES {[o.display_name for o in schema.outputs]} vs {v1cls.RETURN_NAMES}")
        if schema.category != v1cls.CATEGORY:
            diffs.append(f"{node}: CATEGORY")
        if schema.display_name != v1.NODE_DISPLAY_NAME_MAPPINGS[node]:
            diffs.append(f"{node}: display name")
        if bool(schema.is_output_node) != bool(getattr(v1cls, "OUTPUT_NODE", False)):
            diffs.append(f"{node}: output node")
    return diffs


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    v1 = load_v1()
    v2 = load_v2()
    report = {"cases": 0, "exact": 0, "mismatch": [], "error_parity": 0, "by_node": {}}
    first = None
    for node, kwargs in cases():
        a, b = v1_call(v1, node, kwargs), v2_call(v2, node, kwargs)
        report["cases"] += 1
        report["by_node"][node] = report["by_node"].get(node, 0) + 1
        if a == b:
            report["exact"] += 1
            if "error" in a:
                report["error_parity"] += 1
            if first is None and "result" in a and a["result"][0]:
                first = (node, kwargs, a)
        else:
            report["mismatch"].append({"node": node, "kwargs": repr(kwargs)[:300], "v1": repr(a)[:300],
                                       "v2": repr(b)[:300]})
    report["interface_diffs"] = interface(v1, v2)
    node, kwargs, a = first
    tampered = {"result": [a["result"][0] + " "], "ui": a["ui"]}
    report["negative_control"] = {"case": repr(kwargs)[:200], "turned_red": tampered != v2_call(v2, node, kwargs)}
    report["verdict"] = ("PASS" if not report["mismatch"] and not report["interface_diffs"]
                         and report["negative_control"]["turned_red"] else "FAIL")
    (RESULTS / "parity.json").write_text(json.dumps(report, indent=1, ensure_ascii=False))
    print(json.dumps({k: report[k] for k in ("verdict", "cases", "exact", "error_parity", "by_node")}))
    for m in report["mismatch"][:5]:
        print("MISMATCH", m)
    for d in report["interface_diffs"]:
        print("INTERFACE", d)
    sys.exit(0 if report["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
