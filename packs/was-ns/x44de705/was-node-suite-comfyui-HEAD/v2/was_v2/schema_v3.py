"""V3 schemas built from the original's own declarations (Secure Nodes V2).

schemas.json holds, for every NODE_CLASS_MAPPINGS key of WAS_Node_Suite.py, what the original declares:
INPUT_TYPES() as captured from the pinned code with its default configuration, RETURN_TYPES, RETURN_NAMES,
OUTPUT_NODE, CATEGORY, INPUT_IS_LIST and OUTPUT_IS_LIST. Every input becomes the V3 input whose projection
(INPUT_TYPES as the executor and /object_info see it) is the original's tuple: a list type is a COMBO, any other
type is io.Custom(<type>) carrying the original's options unchanged. Two defaults that were absolute host paths
(Cache Node and Write to GIF output_path) are blank here.
"""
import json
import pathlib

from comfy_api.latest import io

ROWS = json.loads(pathlib.Path(__file__).with_name("schemas.json").read_text())["nodes"]

HIDDEN = {
    "PROMPT": io.Hidden.prompt,
    "EXTRA_PNGINFO": io.Hidden.extra_pnginfo,
    "UNIQUE_ID": io.Hidden.unique_id,
    "DYNPROMPT": io.Hidden.dynprompt,
}


def _input(name, spec, optional):
    kind = spec[0]
    options = dict(spec[1]) if len(spec) > 1 and isinstance(spec[1], dict) else {}
    if isinstance(kind, list):
        return io.Combo.Input(name, options=list(kind), optional=optional, extra_dict=options)
    return io.Custom(kind).Input(name, optional=optional, extra_dict=options)


def _output(kind, name, is_list):
    if isinstance(kind, list):
        return io.Combo.Output(display_name=name, options=list(kind), is_output_list=is_list)
    return io.Custom(kind).Output(display_name=name, is_output_list=is_list)


def build_schema(node_id, input_overrides=None):
    row = ROWS[node_id]
    declared = row["input_types"]
    inputs = []
    for group, optional in (("required", False), ("optional", True)):
        for name, spec in (declared.get(group) or {}).items():
            override = (input_overrides or {}).get(name)
            inputs.append(override if override is not None else _input(name, spec, optional))
    hidden = [HIDDEN[value] for value in (declared.get("hidden") or {}).values() if value in HIDDEN]
    return_types = row.get("RETURN_TYPES") or []
    return_names = row.get("RETURN_NAMES")
    output_lists = row.get("OUTPUT_IS_LIST") or [False] * len(return_types)
    outputs = [
        _output(kind, return_names[index] if return_names else None, bool(output_lists[index]))
        for index, kind in enumerate(return_types)
    ]
    return io.Schema(
        node_id=node_id,
        category=row.get("CATEGORY"),
        description=row.get("DESCRIPTION") or "",
        inputs=inputs,
        outputs=outputs,
        hidden=hidden,
        is_output_node=bool(row.get("OUTPUT_NODE")),
        is_input_list=bool(row.get("INPUT_IS_LIST")),
    )
