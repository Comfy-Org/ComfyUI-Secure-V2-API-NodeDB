"""KJNodes V2 entrypoint for standard in-process ComfyUI loading."""

from __future__ import annotations

import copy
import json
import pathlib

from .nodes import NODE_CLASS_MAPPINGS as _API_NODE_CLASS_MAPPINGS


def _bind_source_id(source_id, node_class):
    def define_schema(_cls):
        schema = copy.deepcopy(node_class.define_schema())
        schema.node_id = source_id
        return schema

    return type(
        node_class.__name__,
        (node_class,),
        {
            "__module__": node_class.__module__,
            "define_schema": classmethod(define_schema),
        },
    )


_manifest = json.loads(
    pathlib.Path(__file__).with_name("secure-nodes.json").read_text()
)
_classes_by_name = {
    node_class.__name__: node_class
    for node_class in _API_NODE_CLASS_MAPPINGS.values()
}

NODE_CLASS_MAPPINGS = {
    source_id: _bind_source_id(
        source_id,
        _classes_by_name[definition["class"]],
    )
    for source_id, definition in _manifest["nodes"].items()
}
NODE_DISPLAY_NAME_MAPPINGS = {
    source_id: definition["schema"]["attrs"]["display_name"]
    for source_id, definition in _manifest["nodes"].items()
}

WEB_DIRECTORY = "./web"
STATIC_DIRECTORIES = {"kjweb_async": "./kjweb_async"}

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "STATIC_DIRECTORIES",
    "WEB_DIRECTORY",
]
