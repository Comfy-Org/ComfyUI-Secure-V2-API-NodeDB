"""Actual unchanged f929 encoder build for one existing frontend pack."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser()
    for name in ("backend", "site", "core", "v2", "generator"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    assert hashlib.sha256(args.generator.read_bytes()).hexdigest() == "f929ea628fec11c5cf695a3bee0928866b128050654acc2abf25415c3af9ad2f"
    sys.path[:0] = [str(args.backend), str(args.site), str(args.core)]
    sys.argv = ["resolution-ratio-normal-encoder", "--cpu"]
    import comfy.options
    comfy.options.enable_args_parsing()
    import comfy.cli_args
    from comfy_api.latest import _io
    from comfy_secure_nodes import packmanifest
    assert Path(_io.__file__).resolve().is_relative_to(args.site.resolve())
    assert Path(packmanifest.__file__).resolve().is_relative_to(args.backend.resolve())
    assert Path(comfy.cli_args.__file__).resolve().is_relative_to(args.core.resolve())
    assert comfy.cli_args.args.cpu is True
    spec = importlib.util.spec_from_file_location("_resolution_manifest_f929", args.generator)
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    assert "resolution-and-ratio" not in tool.PROFILES
    tool.PROFILES["resolution-and-ratio"] = {"nodes": 1, "web_directory": "web"}
    normal = tool.build(args.v2.resolve(), "resolution-and-ratio")
    assert set(normal["nodes"]) == {"ResolutionAndRatio"}
    node = normal["nodes"]["ResolutionAndRatio"]
    assert node["sdk_refs"] is False and node["permissions"] == []
    assert node["methods"]["validate_inputs"] is True and isinstance(node["validation_inputs"], dict)
    assert normal["web_directory"] == "web"
    # Only the staged, disposable old manifest is replaced. All encoded schema
    # and validation attributes come from the real selected SDK/tooling.
    (args.v2 / "secure-nodes.json").write_text(json.dumps(normal, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
