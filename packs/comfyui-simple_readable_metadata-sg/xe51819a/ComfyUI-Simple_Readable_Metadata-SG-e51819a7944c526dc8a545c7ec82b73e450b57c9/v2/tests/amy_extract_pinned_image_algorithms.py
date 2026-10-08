"""Mechanical AST extraction; only file IO and canonical-name discovery move.

Run only against this complete assigned pristine sibling. The generated classes
are pack algorithms, not legacy node bootstraps or shared SDK implementations.
"""
import ast
import hashlib
import json
from pathlib import Path

V2 = Path(__file__).resolve().parent.parent
SOURCE = V2.parent
SKIP = {"INPUT_TYPES", "IS_CHANGED", "VALIDATE_INPUTS", "__init__"}


class Boundary(ast.NodeTransformer):
    def visit_Call(self, node):
        node = self.generic_visit(node)
        name = ast.unparse(node.func)
        if name == "folder_paths.get_annotated_filepath":
            return ast.parse("self.input_label", mode="eval").body
        if name == "os.path.getsize":
            return ast.parse("len(self.source_bytes)", mode="eval").body
        if name == "Image.open":
            assert len(node.args) == 1 and ast.unparse(node.args[0]) == "image_path"
            return ast.parse("Image.open(BytesIO(self.source_bytes))", mode="eval").body
        return node

    def visit_Attribute(self, node):
        text = ast.unparse(node)
        if text == "comfy.samplers.KSampler.SAMPLERS":
            return ast.parse("self.sampler_names", mode="eval").body
        if text == "comfy.samplers.KSampler.SCHEDULERS":
            return ast.parse("self.scheduler_names", mode="eval").body
        return self.generic_visit(node)


HEADER = """# Mechanically retained pinned algorithms. See extraction receipt.
import json
import re
import posixpath
from io import BytesIO
from types import SimpleNamespace
import numpy as np
import torch
from PIL import Image, ImageOps
# Pure lexical path operations only: no host filesystem namespace.
os = SimpleNamespace(path=posixpath)
"""
receipt = []
for source_name, class_name, target_name in [
    ("Simple_Readable_Metadata_SG.py", "ImageAlgorithms", "image_algorithms.py"),
    ("Simple_Readable_Metadata_MAX_SG.py", "MaxAlgorithms", "max_algorithms.py"),
]:
    data = (SOURCE / source_name).read_bytes()
    tree = ast.parse(data)
    original = next(node for node in tree.body if isinstance(node, ast.ClassDef))
    functions = [node for node in original.body if isinstance(node, ast.FunctionDef) and node.name not in SKIP]
    records = []
    for node in functions:
        before = ast.dump(node, include_attributes=False)
        start, end = node.lineno, node.end_lineno
        Boundary().visit(node)
        after = ast.dump(node, include_attributes=False)
        records.append({"method": node.name, "source_start": start, "source_end": end,
                        "normalized_ast_exact": before == after,
                        "before_ast_sha256": hashlib.sha256(before.encode()).hexdigest(),
                        "after_ast_sha256": hashlib.sha256(after.encode()).hexdigest()})
    result = ast.Module(body=[ast.ClassDef(name=class_name, bases=[], keywords=[], body=functions, decorator_list=[])], type_ignores=[])
    output = HEADER + ast.unparse(ast.fix_missing_locations(result)) + "\n"
    # Generated mechanical rewrite, never an edit to pristine/corpus inputs.
    (V2 / target_name).write_text(output)
    receipt.append({"source": str(SOURCE / source_name), "source_sha256": hashlib.sha256(data).hexdigest(),
                    "target": str(V2 / target_name), "target_sha256": hashlib.sha256(output.encode()).hexdigest(),
                    "methods": records})
target = Path("/Users/ben/popbot/raw-chats/outputs/amy-oct8-readable-image-algorithm-extraction.json")
with target.open("x") as handle:
    json.dump({"format": "pinned-image-algorithm-extraction-v1", "classes": receipt,
               "allowed_changes": ["managed-label source name", "BytesIO source bytes", "byte length", "public canonical sampling names"],
               "schema_runtime_guest_proof": False, "count_increment": 0}, handle, indent=2)
    handle.write("\n")
print(json.dumps({"receipt": str(target), "classes": len(receipt), "methods": sum(len(item["methods"]) for item in receipt)}))
