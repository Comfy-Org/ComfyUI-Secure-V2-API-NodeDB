"""The pack registers no node id that ComfyUI Core already owns (gate test).

    run_in_gate.sh <pack root (pristine + v2/)> <tests dir holding this file> <results dir> test_no_core_id_clash.py

Core's own loader skips a custom node whose id is already a Core id (nodes.load_custom_node: `if name not in ignore`,
with ignore = the base node names taken after the extra and API nodes load). So on V1 such an id is always served by
Core. Secure Nodes stage composition is first-owner-wins and refuses the whole pack on a duplicate. This test loads
Core's node set the way Core does at startup (nodes.py, comfy_extras, API nodes) and checks that the pack's manifest
declares none of its ids. Writes /results/core_id_clash.json; exits 1 on a clash.
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path[:0] = ["/core"]
from comfy.cli_args import args as _cli_args  # noqa: E402

_cli_args.cpu = True
import nodes  # noqa: E402


def pack_root(root=Path("/pack")):
    if (root / "v2").is_dir():
        return root
    heads = [d for d in sorted(root.iterdir()) if d.is_dir() and not d.name.startswith(".")]
    if len(heads) != 1:
        raise SystemExit(f"/pack must hold exactly one pack folder: {heads}")
    return heads[0]


def core_ids():
    # The same order Core uses before loading custom nodes: built-ins, then extras and API nodes.
    try:
        result = nodes.init_extra_nodes(init_custom_nodes=False, init_api_nodes=True)
        if asyncio.iscoroutine(result):
            asyncio.run(result)
    except Exception as error:  # some extras need write access to /core; the ids that loaded still count
        print(f"note: init_extra_nodes raised {type(error).__name__}: {error}")
    return set(nodes.NODE_CLASS_MAPPINGS)


def main():
    out = Path("/results")
    out.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((pack_root() / "v2" / "secure-nodes.json").read_text())
    ids = set(manifest["nodes"])
    core = core_ids()
    clashes = sorted(ids & core)
    control = "KSampler" in core  # negative control: a known Core id must be in the loaded set
    report = {"pack_ids": len(ids), "core_ids": len(core), "clashes": clashes, "control_core_has_KSampler": control,
              "passed": not clashes and control}
    (out / "core_id_clash.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
