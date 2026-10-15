"""Read-only canonical AST capture, later checked against public broker names."""
import ast
import hashlib
import json
from pathlib import Path
source = Path("/Users/ben/comfy/ComfyUI-secure-nodes/comfy/samplers.py")
data = source.read_bytes()
values = {}
for node in ast.parse(data).body:
    if not isinstance(node, ast.Assign) or len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
        continue
    name = node.targets[0].id
    if name == "KSAMPLER_NAMES":
        values[name] = ast.literal_eval(node.value)
    elif name == "SAMPLER_NAMES":
        assert isinstance(node.value, ast.BinOp) and isinstance(node.value.op, ast.Add)
        values[name] = values[node.value.left.id] + ast.literal_eval(node.value.right)
    elif name == "SCHEDULER_HANDLERS":
        values[name] = [ast.literal_eval(key) for key in node.value.keys]
names = {"samplers": values["SAMPLER_NAMES"], "schedulers": values["SCHEDULER_HANDLERS"]}
root = Path(__file__).resolve().parent.parent
receipt = {"canonical_source": str(source), "canonical_sha256": hashlib.sha256(data).hexdigest(),
           "names": names, "policy": "Exact local ordered list; live public sampling_names must match before execution"}
(root / "sampling_names.json").write_text(json.dumps(receipt, indent=2) + "\n")
(root / "sampling_names.py").write_text(
    "# Exact observed local schema names; live public contract is checked at execution.\n"
    + "CANONICAL_SOURCE_SHA256 = " + repr(receipt["canonical_sha256"]) + "\n"
    + "SAMPLERS = " + repr(names["samplers"]) + "\n"
    + "SCHEDULERS = " + repr(names["schedulers"]) + "\n")
print(json.dumps(receipt))
