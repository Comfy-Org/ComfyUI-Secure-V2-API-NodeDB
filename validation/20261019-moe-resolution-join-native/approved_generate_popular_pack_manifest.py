#!/usr/bin/env python3
"""Generate sealed manifests for converted high-adoption node packs."""
from __future__ import annotations

import argparse
import asyncio
import copy
import importlib.util
import json
import pathlib
import sys
import tomllib


PROFILES = {
    "simple-aspect-ratio": {
        "nodes": 1,
        "node_ids": ("SimpleAspectRatio",),
        "extension_entrypoint": True,
        "git_only_runtime_minor": "3.13",
    },
    "sentence-filter": {
        "nodes": 1,
        "node_ids": ("SentenceFilterNode",),
        "extension_entrypoint": True,
        "git_only_runtime_minor": "3.13",
    },
    "cg-use-everywhere": {"nodes": 7, "web_directory": "js"},
    "custom-scripts": {
        "nodes": 13,
        "web_directory": "web",
        "routes": [
            {"method": "get", "path": "/notes", "module": "_secure_routes",
             "handler": "get_notes", "permissions": ["storage"]},
            {"method": "post", "path": "/notes", "module": "_secure_routes",
             "handler": "save_notes", "permissions": ["storage"]},
            {"method": "get", "path": "/examples", "module": "_secure_routes",
             "handler": "get_examples", "permissions": ["storage"]},
            {"method": "post", "path": "/examples", "module": "_secure_routes",
             "handler": "save_example", "permissions": ["storage"]},
            {"method": "get", "path": "/preview", "module": "_secure_routes",
             "handler": "get_preview", "permissions": ["storage"]},
            {"method": "post", "path": "/preview", "module": "_secure_routes",
             "handler": "save_preview", "permissions": ["storage"]},
            {"method": "get", "path": "/metadata", "module": "_secure_routes",
             "handler": "get_metadata", "permissions": ["assets"]},
        ],
    },
    "crystools": {"nodes": 29, "web_directory": "web"},
    "easy-use": {
        "nodes": 207,
        "web_directory": "web_version/v1",
        "asset_directories": {"easy_wildcards": "wildcards"},
    },
    "efficiency-nodes-comfyui": {"nodes": 40, "web_directory": "js"},
    "videohelpersuite": {"nodes": 40, "web_directory": "web"},
    "impact-pack": {
        "nodes": 197,
        "web_directory": "js",
        "asset_directories": {"impact_wildcards": "wildcards"},
    },
    "impact-subpack": {"nodes": 1},
    "layerstyle": {"nodes": 171, "web_directory": "js"},
    "mxtoolkit": {"nodes": 4, "web_directory": "js"},
    "prompt-reader": {"nodes": 10, "web_directory": "js"},
    "steudio": {"nodes": 10, "web_directory": "js"},
    "ultimate-sd-upscale": {"nodes": 4},
    "whiterabbit": {
        "nodes": 14,
        "dependency_profile_sha256": (
            "79a6f88ddff48f9a0fa7d0d05dbb64807b705425aeae0ee9e8d2b70dd0d31b2f"
        ),
    },
}


def _load(v2_root: pathlib.Path, profile: str):
    mount_name = f"_secure_{profile.replace('-', '_')}_manifest"
    package = sys.modules.get(mount_name)
    if package is not None:
        if pathlib.Path(package.__path__[0]).resolve() != v2_root:
            raise ValueError(f"{mount_name} is already mounted elsewhere")
        return package
    spec = importlib.util.spec_from_file_location(
        mount_name,
        v2_root / "__init__.py",
        submodule_search_locations=[str(v2_root)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not create a package spec for {v2_root}")
    package = importlib.util.module_from_spec(spec)
    sys.modules[mount_name] = package
    spec.loader.exec_module(package)
    return package


def build(v2_root: pathlib.Path, profile: str) -> dict:
    from comfy_secure_nodes.packmanifest import (
        FORMAT,
        encode_required_weights,
        encode_schema,
    )
    from comfy_secure_nodes.packruntime import manifest_declaration

    settings = PROFILES[profile]
    pack = _load(v2_root, profile)
    if settings.get("extension_entrypoint"):
        from comfy_api.latest import ComfyExtension

        async def extension_nodes():
            extension = await pack.comfy_entrypoint()
            if not isinstance(extension, ComfyExtension):
                raise TypeError(f"{profile} did not return a ComfyExtension")
            return await extension.get_node_list()

        registered = asyncio.run(extension_nodes())
        mapped = list(pack.NODE_CLASS_MAPPINGS.values())
        if len(registered) != len(mapped) or set(registered) != set(mapped):
            raise ValueError(f"{profile} extension and mapping registrations differ")
        if set(pack.NODE_CLASS_MAPPINGS) != set(settings["node_ids"]):
            raise ValueError(f"{profile} does not expose its original node ids")
    nodes = {}
    for node_id, node_class in sorted(pack.NODE_CLASS_MAPPINGS.items()):
        module = sys.modules[node_class.__module__]
        module_file = pathlib.Path(module.__file__).resolve()
        relative = module_file.relative_to(v2_root)
        relative = (
            relative.parent if relative.name == "__init__.py"
            else relative.with_suffix("")
        )
        schema = copy.deepcopy(node_class.GET_SCHEMA())
        if schema.node_id != node_id:
            raise ValueError(
                f"mapping {node_id!r} owns schema {schema.node_id!r}"
            )
        required_weights = encode_required_weights(node_class)
        permissions = list(getattr(node_class, "SDK_PERMISSIONS", ()) or ())
        if required_weights and "models.download" not in permissions:
            permissions.append("models.download")
        definition = {
            "module": ".".join(relative.parts),
            "class": node_class.__name__,
            "sdk_refs": getattr(node_class, "SDK_REFS", False) is True,
            "permissions": permissions,
            "methods": {
                method: method in node_class.__dict__
                for method in (
                    "validate_inputs",
                    "fingerprint_inputs",
                    "check_lazy_status",
                )
            },
            "schema": encode_schema(schema),
        }
        if definition["methods"]["validate_inputs"]:
            # Older admitted backends support these scalar nodes but do not
            # expose signature encoding. Require it only for nodes that use it.
            from comfy_secure_nodes.packmanifest import encode_validation_inputs

            definition["validation_inputs"] = encode_validation_inputs(node_class)
        if required_weights:
            definition["required_weights"] = required_weights
        nodes[node_id] = definition
    if len(nodes) != settings["nodes"]:
        raise ValueError(
            f"{profile} manifest coverage is {len(nodes)}/{settings['nodes']}"
        )
    manifest = {
        "format": FORMAT,
        "runtime": manifest_declaration(
            v2_root,
            dependency_profile_sha256=settings.get(
                "dependency_profile_sha256"),
        ),
        "nodes": nodes,
    }
    if settings.get("web_directory"):
        manifest["web_directory"] = settings["web_directory"]
    if settings.get("asset_directories"):
        manifest["asset_directories"] = settings["asset_directories"]
    if settings.get("routes"):
        manifest["routes"] = copy.deepcopy(settings["routes"])
    return manifest


def _stage_runtime_declaration(v2_root: pathlib.Path, profile: str,
                               source: pathlib.Path) -> None:
    """Stage confirmed converter runtime metadata into an isolated writable copy.

    Git-only upstreams need no invented project name, version or publisher.
    Canonical packruntime validation is retained for the selected minor range.
    """
    from comfy_secure_nodes.packruntime import manifest_declaration

    minor = PROFILES[profile].get("git_only_runtime_minor")
    if minor is None:
        raise ValueError("external runtime metadata is only for the Git-only scalar profiles")
    source = source.resolve()
    if source.name != "pyproject.toml" or not source.is_file():
        raise ValueError("runtime metadata must be an existing pyproject.toml")
    data = source.read_bytes()
    parsed = tomllib.loads(data.decode("utf-8"))
    if set(parsed) != {"project"} or set(parsed["project"]) != {"requires-python"}:
        raise ValueError("converter runtime metadata must contain only project.requires-python")
    declaration = manifest_declaration(source.parent)
    if declaration["python"]["resolved"] != minor:
        raise ValueError(f"{profile} requires the confirmed Python {minor} profile")
    destination = v2_root / "pyproject.toml"
    if destination.exists():
        if not destination.is_file() or destination.read_bytes() != data:
            raise ValueError("refusing to override an existing pack runtime declaration")
        return
    # Explicit CLI option: the caller supplies an isolated writable staging
    # copy, never the original/frozen source packet. No file is overwritten.
    with destination.open("xb") as stream:
        stream.write(data)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", choices=tuple(PROFILES))
    parser.add_argument("v2_root", type=pathlib.Path)
    parser.add_argument("output", type=pathlib.Path)
    parser.add_argument(
        "--runtime-pyproject", type=pathlib.Path,
        help="stage confirmed runtime-only metadata in an isolated writable scalar-pack copy",
    )
    args = parser.parse_args(argv)
    if args.runtime_pyproject is not None:
        _stage_runtime_declaration(args.v2_root.resolve(), args.profile,
                                   args.runtime_pyproject)
    manifest = build(args.v2_root.resolve(), args.profile)
    args.output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
