"""rgthree-comfy to-50% repair R1: tier-1 parity runner for the 9 corpus-used frontend-only types.

Runs inside the lane gate (run_in_gate.sh): /pack is the pristine pack with v2/ inside it, /tests is
this directory, /results is writable, and /deps supplies the test tools (DEPS.json):
  /deps/node/bin/node                                   Node v25.9.0 linux-x64 (nodejs.org, sha256-checked)
  /deps/lib/libatomic.so.1                              needed by that Node build; not in the gate image
  /deps/host-frontend/src/platform/nodeApi/resolution.ts  host frontend 1.53.4 resolution system, unmodified
Two runs: the normal one, then a negative control that perturbs one converted output (the Fast
Muter's off mode). The negative run must turn red. Writes /results/parity.json, the two receipts
and run.log. Never imports or executes pack Python; the pack JS runs only inside this container.
"""
import json
import os
import subprocess
import sys

NODE = "/deps/node/bin/node"
TESTS = "/tests"
WEB = "/pack/v2/web"
PRISTINE_WEB = "/pack/web"
RESOLUTION = "/deps/host-frontend/src/platform/nodeApi/resolution.ts"
USED = [
    "Fast Actions Button (rgthree)", "Fast Bypasser (rgthree)", "Fast Muter (rgthree)", "Label (rgthree)",
    "Mute / Bypass Relay (rgthree)", "Mute / Bypass Repeater (rgthree)", "Node Collector (rgthree)",
    "Random Unmuter (rgthree)", "Reroute (rgthree)",
]


def run(mode):
    out = f"/tmp/receipt-{mode}.json"
    argv = [NODE, "--experimental-vm-modules", "--no-warnings", "--import", f"{TESTS}/host_model/hooks.mjs",
            f"{TESTS}/frontend_used_types.test.mjs", WEB, PRISTINE_WEB, RESOLUTION, out]
    if mode == "negative":
        argv.append("negative")
    env = dict(os.environ, LD_LIBRARY_PATH="/deps/lib", HOME="/tmp")
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=600, env=env, cwd="/tmp")
    if not os.path.exists(out):
        with open(f"/results/run-{mode}-crash.log", "w", encoding="utf-8") as handle:
            handle.write("$ " + " ".join(argv) + "\n" + f"exit {proc.returncode}" + "\n" + proc.stdout + "\n" + proc.stderr + "\n")
        raise SystemExit(f"{mode} run wrote no receipt (exit {proc.returncode}); see run-{mode}-crash.log")
    with open(out, encoding="utf-8") as handle:
        receipt = json.load(handle)
    return argv, proc, receipt


def main():
    log = []
    runs = {}
    for mode in ("normal", "negative"):
        argv, proc, receipt = run(mode)
        runs[mode] = receipt
        log += [f"== {mode}", "$ " + " ".join(argv), f"exit {proc.returncode}", proc.stdout.rstrip(), proc.stderr.rstrip(), ""]
        with open(f"/results/frontend_receipt_{mode}.json", "w", encoding="utf-8") as handle:
            json.dump(receipt, handle, indent=1)
            handle.write("\n")
    normal, negative = runs["normal"], runs["negative"]
    with open("/results/run.log", "w", encoding="utf-8") as handle:
        handle.write("\n".join(log) + "\n")
    if normal["status"] == "CRASH":
        print(json.dumps({"status": "CRASH", "failed": normal["failed"], "uncaught": normal.get("uncaught")}, indent=1))
        return 2
    nodes = {}
    for node in USED:
        row = normal["per_type"][node]
        nodes[node] = {"verdict": "EXACT" if row["cases"] and not row["failed"] else "MISMATCH",
                       "cases": row["cases"], "failed": row["failed"]}
    negative_red = negative["status"] == "FAIL" and any(
        "Fast Muter (rgthree)" in name and name.startswith("M modes") for name in negative["failed"])
    parity = {
        "pack": "rgthree-comfy",
        "scope": "9 corpus-used frontend-only types; host-fake frontend unit tests (no browser, no host)",
        "node": normal["node"],
        "status": normal["status"],
        "cases": normal["cases"],
        "nodes": nodes,
        "prompt_deviations": normal["prompt_deviations"],
        "negative_control": {"perturbation": "muter.js modeOff 'never' -> 'bypass'", "turned_red": negative_red,
                             "failed": negative["failed"]},
        "inputs_sha256": normal["inputs_sha256"],
    }
    with open("/results/parity.json", "w", encoding="utf-8") as handle:
        json.dump(parity, handle, indent=1, sort_keys=True)
        handle.write("\n")
    with open("/results/run.log", "w", encoding="utf-8") as handle:
        handle.write("\n".join(log) + "\n")
    print(json.dumps({"status": parity["status"], "verdicts": {k: v["verdict"] for k, v in nodes.items()},
                      "deviations": parity["prompt_deviations"], "negative_turned_red": negative_red}, indent=1))
    return 0 if negative_red else 3


if __name__ == "__main__":
    sys.exit(main())
