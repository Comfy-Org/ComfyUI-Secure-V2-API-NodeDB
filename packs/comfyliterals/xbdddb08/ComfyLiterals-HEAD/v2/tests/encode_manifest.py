"""Regenerate v2/secure-nodes.json with the real encoder, inside the gate.

    run_in_gate.sh <snapshot dir holding ComfyLiterals-HEAD> \
        <.../v2/tests> <results dir> encode_manifest.py

Writes /results/secure-nodes.json. Rows come only from
comfy_secure_nodes.packmanifest (encode_schema, encode_validation_inputs,
encode_required_weights) and packruntime.manifest_declaration.
Serialization: json.dumps(indent=2, sort_keys=True) + "\\n".
"""

import copy
import importlib.util
import json
import sys
from pathlib import Path

sys.path[:0] = ["/core", "/overlay"]

from comfy_api.latest import io  # noqa: E402
from comfy_secure_nodes.packmanifest import (  # noqa: E402
    FORMAT,
    encode_required_weights,
    encode_schema,
    encode_validation_inputs,
)
from comfy_secure_nodes.packruntime import manifest_declaration  # noqa: E402

METHODS = ("check_lazy_status", "fingerprint_inputs", "validate_inputs")


def pack_head(root: Path = Path("/pack")) -> Path:
    if (root / "v2").is_dir():
        return root
    heads = [d for d in sorted(root.iterdir())
             if d.is_dir() and not d.name.startswith(".")]
    if len(heads) != 1:
        raise SystemExit(f"/pack must hold exactly one pack folder: {heads}")
    return heads[0]


def load_package(name: str, folder: Path):
    spec = importlib.util.spec_from_file_location(
        name, folder / "__init__.py", submodule_search_locations=[str(folder)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def overrides(cls, name: str) -> bool:
    return getattr(cls, name).__func__ is not getattr(io.ComfyNode, name).__func__


def build_manifest(v2: Path, package_name: str = "literals_v2_manifest") -> dict:
    package = load_package(package_name, v2)
    nodes = {}
    for node_id, cls in package.NODE_CLASS_MAPPINGS.items():
        prefix = package.__name__ + "."
        if not cls.__module__.startswith(prefix):
            raise SystemExit(f"{node_id}: class defined outside v2: {cls.__module__}")
        methods = {name: overrides(cls, name) for name in METHODS}
        row = {
            "class": cls.__name__,
            "methods": methods,
            "module": cls.__module__[len(prefix):],
            "permissions": list(cls.SDK_PERMISSIONS),
            "schema": encode_schema(copy.deepcopy(cls.GET_SCHEMA())),
            "sdk_refs": cls.SDK_REFS is True,
        }
        if methods["validate_inputs"]:
            row["validation_inputs"] = encode_validation_inputs(cls)
        weights = encode_required_weights(cls)
        if weights:
            row["required_weights"] = weights
        nodes[node_id] = row
    return {"format": FORMAT, "nodes": nodes, "runtime": manifest_declaration(v2)}


def serialize(manifest: dict) -> str:
    return json.dumps(manifest, indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    v2 = pack_head() / "v2"
    text = serialize(build_manifest(v2))
    Path("/results/secure-nodes.json").write_text(text)
    print(f"wrote /results/secure-nodes.json ({len(text)} bytes)")
