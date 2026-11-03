"""Gate-only independent schema extraction from original class source text.

Only INPUT_TYPES and schema attributes execute. No original package/module
initializer or unselected compute method executes. Dynamic lists are obtained
from real core catalogues and the retained source directories.
"""
import ast
import copy
import json
import os
from pathlib import Path


def normalize(value):
    return json.loads(json.dumps(value))


def schemas(pack, io):
    import comfy.samplers
    import folder_paths
    pack = Path(pack)
    folder_paths.add_model_folder_path("luts", (pack / "luts").as_posix())
    folder_paths.add_model_folder_path("luts", (Path(folder_paths.models_dir) / "luts").as_posix())
    utility = ast.parse((pack / "utils.py").read_text())
    anytype = next(item for item in utility.body if isinstance(item, ast.ClassDef) and item.name == "AnyType")
    environment = {"comfy": comfy, "folder_paths": folder_paths, "os": os,
        "FONTS_DIR": str(pack / "fonts"), "MAX_RESOLUTION": io.MAX_RESOLUTION}
    exec(compile(ast.Module(body=[anytype], type_ignores=[]), str(pack / "utils.py"), "exec"), environment)
    environment["any"] = environment["AnyType"]("*")
    save_attrs = {}
    core = ast.parse(Path("/core/nodes.py").read_text())
    saveimage = next(item for item in core.body if isinstance(item, ast.ClassDef) and item.name == "SaveImage")
    for statement in saveimage.body:
        if isinstance(statement, ast.Assign) and isinstance(statement.targets[0], ast.Name) and statement.targets[0].id in {"RETURN_TYPES", "RETURN_NAMES", "INPUT_IS_LIST", "OUTPUT_IS_LIST", "OUTPUT_NODE"}:
            save_attrs[statement.targets[0].id] = ast.literal_eval(statement.value)
    environment["SaveImageSchema"] = type("SaveImageSchema", (), save_attrs)
    results = {}
    for file in sorted(pack.glob("*.py")):
        tree = ast.parse(file.read_text(encoding="utf-8"))
        classes = {item.name: item for item in tree.body if isinstance(item, ast.ClassDef)}
        display = {}
        mappings = {}
        for statement in tree.body:
            if not isinstance(statement, ast.Assign) or not isinstance(statement.targets[0], ast.Name):
                continue
            target = statement.targets[0].id
            if target.endswith("_CLASS_MAPPINGS") and isinstance(statement.value, ast.Dict):
                mappings.update({ast.literal_eval(key): value.id for key, value in zip(statement.value.keys, statement.value.values, strict=True)})
            elif target.endswith("_NAME_MAPPINGS") and isinstance(statement.value, ast.Dict):
                display.update(ast.literal_eval(statement.value))
        for node_id, class_name in mappings.items():
            source = classes[class_name]
            cloned = copy.deepcopy(source)
            cloned.bases = [ast.Name(id="SaveImageSchema", ctx=ast.Load())] if any(isinstance(base, ast.Name) and base.id == "SaveImage" for base in source.bases) else []
            cloned.decorator_list = []
            cloned.body = [item for item in cloned.body if (isinstance(item, ast.FunctionDef) and item.name == "INPUT_TYPES") or (isinstance(item, ast.Assign) and isinstance(item.targets[0], ast.Name) and item.targets[0].id in {"RETURN_TYPES", "RETURN_NAMES", "FUNCTION", "CATEGORY", "INPUT_IS_LIST", "OUTPUT_IS_LIST", "OUTPUT_NODE", "DESCRIPTION"})]
            module = ast.fix_missing_locations(ast.Module(body=[cloned], type_ignores=[]))
            exec(compile(module, str(file), "exec"), environment)
            klass = environment[class_name]
            inputs = klass.INPUT_TYPES()
            rows = []
            for section in ("required", "optional"):
                for name, specification in inputs.get(section, {}).items():
                    rows.append({"name": name, "type": specification[0], "options": specification[1] if len(specification) > 1 else {}, "extra": list(specification[2:]), "optional": section == "optional"})
            types = getattr(klass, "RETURN_TYPES", ())
            names = getattr(klass, "RETURN_NAMES", types)
            lists = getattr(klass, "OUTPUT_IS_LIST", (False,) * len(types))
            results[node_id] = normalize({"module": file.stem, "class": class_name,
                "method": klass.FUNCTION, "category": klass.CATEGORY,
                "display_name": display[node_id], "description": getattr(klass, "DESCRIPTION", ""),
                "hidden": list(inputs.get("hidden", {}).values()), "inputs": rows,
                "outputs": [{"type": kind, "name": name, "is_list": is_list} for kind, name, is_list in zip(types, names, lists, strict=True)],
                "is_input_list": getattr(klass, "INPUT_IS_LIST", False), "is_output_node": getattr(klass, "OUTPUT_NODE", False)})
    assert len(results) == 85
    return results
