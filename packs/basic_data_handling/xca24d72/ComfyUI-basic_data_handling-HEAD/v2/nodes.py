"""Secure bindings for the pinned Basic Data Handling node surface."""
from __future__ import annotations

import inspect
import os
from typing import Any

from . import legacy
from ._secure_runtime import (
    SCHEMAS,
    bind_node,
    materialize,
    sdk,
    unsupported,
)


_PATH_PREFIX = "Basic data handling: Path"

_PURE_PATH_CLASSES = {
    "PathBasename",
    "PathCommonPrefix",
    "PathDirname",
    "PathGetExtension",
    "PathSetExtension",
    "PathIsAbsolute",
    "PathJoin",
    "PathNormalize",
    "PathSplit",
    "PathSplitExt",
}

_REJECTED_PATH_CLASSES = {
    "PathAbspath",
    "PathExists",
    "PathExpandVars",
    "PathGetCwd",
    "PathGetSize",
    "PathGlob",
    "PathInputDir",
    "PathIsDir",
    "PathIsFile",
    "PathListDir",
    "PathLoadImageRGB",
    "PathLoadImageRGBA",
    "PathLoadMaskFromAlpha",
    "PathLoadMaskFromGreyscale",
    "PathLoadStringFile",
    "PathOutputDir",
    "PathRelative",
    "PathSaveImageRGB",
    "PathSaveImageRGBA",
    "PathSaveStringFile",
}

_RAW_TYPES = {"*", "IMAGE", "MASK", "LIST", "DICT", "SET", "BYTES"}


def _permissions(node_id: str) -> tuple[str, ...]:
    definition = SCHEMAS[node_id]["schema"]
    types = {
        item.get("io_type")
        for item in (*definition["inputs"], *definition["outputs"])
    }
    return ("raw",) if types & _RAW_TYPES else ()


def _legacy_handler(node_id: str, legacy_class: type):
    method_name = SCHEMAS[node_id]["method"]

    async def execute(**kwargs: Any):
        converted = {
            name: await materialize(value)
            for name, value in kwargs.items()
        }
        result = getattr(legacy_class(), method_name)(**converted)
        return await result if inspect.isawaitable(result) else result

    return execute


def _legacy_lazy(legacy_class: type):
    method = getattr(legacy_class(), "check_lazy_status")

    async def check(**kwargs: Any):
        converted = {
            name: await materialize(value)
            for name, value in kwargs.items()
        }
        return method(**converted)

    return check


def _legacy_fingerprint(legacy_class: type):
    method = getattr(legacy_class, "IS_CHANGED")

    async def fingerprint(**kwargs: Any):
        converted = {
            name: await materialize(value)
            for name, value in kwargs.items()
        }
        return method(**converted)

    return fingerprint


async def _always_valid(**_kwargs: Any) -> bool:
    return True


async def _continue_flow(value: Any, select: bool = True, message: str = ""):
    if select:
        return (value,)
    return (await sdk.ctx().graph.block(message or None),)


async def _flow_select(value: Any, select: bool = True):
    block = await sdk.ctx().graph.block()
    return (value, block) if select else (block, value)


async def _path_basename(path: str):
    return (os.path.basename(path),)


async def _path_common_prefix(path1: str, path2: str = ""):
    return (os.path.commonprefix([path for path in (path1, path2) if path]),)


async def _path_dirname(path: str):
    return (os.path.dirname(path),)


async def _path_get_extension(path: str):
    return (os.path.splitext(path)[1],)


async def _path_set_extension(path: str, extension: str):
    if extension and not extension.startswith("."):
        extension = "." + extension
    root, _old = os.path.splitext(path)
    return (root + extension,)


async def _path_is_absolute(path: str):
    return (os.path.isabs(path),)


async def _path_join(path1: str, path2: str = ""):
    return (str(os.path.join(*[path for path in (path1, path2) if path])),)


async def _path_normalize(path: str):
    return (os.path.normpath(path),)


async def _path_split(path: str):
    return os.path.split(path)


async def _path_split_ext(path: str):
    return os.path.splitext(path)


_PATH_HANDLERS = {
    "PathBasename": _path_basename,
    "PathCommonPrefix": _path_common_prefix,
    "PathDirname": _path_dirname,
    "PathGetExtension": _path_get_extension,
    "PathSetExtension": _path_set_extension,
    "PathIsAbsolute": _path_is_absolute,
    "PathJoin": _path_join,
    "PathNormalize": _path_normalize,
    "PathSplit": _path_split,
    "PathSplitExt": _path_split_ext,
}


_CONTROL_HANDLERS = {
    "Basic data handling: ContinueFlow": _continue_flow,
    "Basic data handling: FlowSelect": _flow_select,
}


NODE_CLASS_MAPPINGS: dict[str, type] = {}
NODE_DISPLAY_NAME_MAPPINGS = {
    node_id: definition["schema"]["attrs"]["display_name"]
    for node_id, definition in SCHEMAS.items()
}

for node_id, definition in SCHEMAS.items():
    class_name = definition["class"]
    if class_name in _PURE_PATH_CLASSES:
        handler = _PATH_HANDLERS[class_name]
        node_class = bind_node(node_id, handler, module=__name__)
    elif class_name in _REJECTED_PATH_CLASSES:
        handler = unsupported(
            node_id,
            "arbitrary host paths, environment disclosure, or ambient "
            "filesystem reads and writes are not permitted",
        )
        node_class = bind_node(node_id, handler, module=__name__)
    else:
        legacy_class = legacy.NODE_CLASS_MAPPINGS[node_id]
        handler = _CONTROL_HANDLERS.get(
            node_id, _legacy_handler(node_id, legacy_class)
        )
        lazy = (
            _legacy_lazy(legacy_class)
            if definition["methods"]["check_lazy_status"] else None
        )
        fingerprint = (
            _legacy_fingerprint(legacy_class)
            if definition["methods"]["fingerprint_inputs"] else None
        )
        validator = (
            _always_valid
            if definition["methods"]["validate_inputs"] else None
        )
        permissions = _permissions(node_id)
        if node_id in _CONTROL_HANDLERS:
            permissions = tuple(sorted(set(permissions) | {"graph.block"}))
        node_class = bind_node(
            node_id,
            handler,
            permissions=permissions,
            check_lazy_status=lazy,
            fingerprint_inputs=fingerprint,
            validate_inputs=validator,
            module=__name__,
        )
    NODE_CLASS_MAPPINGS[node_id] = node_class


SUPPORTED_NODE_IDS = tuple(
    node_id for node_id, definition in SCHEMAS.items()
    if definition["class"] not in _REJECTED_PATH_CLASSES
)
REJECTED_NODE_IDS = tuple(
    node_id for node_id, definition in SCHEMAS.items()
    if definition["class"] in _REJECTED_PATH_CLASSES
)


__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "REJECTED_NODE_IDS",
    "SUPPORTED_NODE_IDS",
]
