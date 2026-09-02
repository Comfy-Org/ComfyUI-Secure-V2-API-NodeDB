from __future__ import annotations

import importlib
import pathlib


NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}


def _collect_nodes() -> None:
    for path in sorted(pathlib.Path(__file__).parent.glob("*.py")):
        if path.stem == "__init__" or path.stem.startswith("_"):
            continue
        module = importlib.import_module(f".{path.stem}", __package__)
        classes = getattr(module, "NODE_CLASS_MAPPINGS", {})
        displays = getattr(module, "NODE_DISPLAY_NAME_MAPPINGS", {})
        duplicates = sorted(NODE_CLASS_MAPPINGS.keys() & classes.keys())
        if duplicates:
            raise RuntimeError(
                f"duplicate KJNodes V2 registrations in {path.name}: "
                f"{duplicates}"
            )
        NODE_CLASS_MAPPINGS.update(classes)
        NODE_DISPLAY_NAME_MAPPINGS.update(displays)


_collect_nodes()

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
