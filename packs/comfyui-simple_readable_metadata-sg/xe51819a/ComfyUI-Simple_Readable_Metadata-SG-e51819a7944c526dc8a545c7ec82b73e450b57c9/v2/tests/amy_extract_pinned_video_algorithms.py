"""Mechanical pinned video math; managed IO and budgets are separate."""
import ast
import hashlib
import json
import os
from pathlib import Path

V2 = Path(__file__).resolve().parent.parent
SOURCE = V2.parent / "Simple_Readable_Metadata_VIDEO_SG.py"
data = SOURCE.read_bytes()
tree = ast.parse(data)
original = next(node for node in tree.body if isinstance(node, ast.ClassDef))
skip = {"INPUT_TYPES", "IS_CHANGED", "VALIDATE_INPUTS", "extract_raw_video_metadata"}


class Boundary(ast.NodeTransformer):
    def visit_Call(self, node):
        node = self.generic_visit(node)
        name = ast.unparse(node.func)
        if name == "folder_paths.get_annotated_filepath":
            return ast.parse("self.decode_path", mode="eval").body
        if name == "cv2.VideoCapture":
            return ast.parse("self.open_capture(video_path)", mode="eval").body
        if name == "cv2.cvtColor":
            # Budget admission precedes the retained float conversion/stack.
            node.args[0] = ast.parse("self.selected_frame(frame)", mode="eval").body
        if name == "cv2.resize":
            node.func = ast.parse("self.resize_frame", mode="eval").body
        if name == "os.path.getsize":
            return ast.parse("len(self.source_bytes)", mode="eval").body
        if name == "os.path.basename":
            return ast.parse("posixpath.basename(self.input_label)", mode="eval").body
        return node


functions, records = [], []
for node in original.body:
    if not isinstance(node, ast.FunctionDef) or node.name in skip:
        continue
    before = ast.dump(node, include_attributes=False)
    start, end = node.lineno, node.end_lineno
    Boundary().visit(node)
    after = ast.dump(node, include_attributes=False)
    records.append({"method": node.name, "source_start": start, "source_end": end,
        "normalized_ast_exact": before == after,
        "before_ast_sha256": hashlib.sha256(before.encode()).hexdigest(),
        "after_ast_sha256": hashlib.sha256(after.encode()).hexdigest()})
    functions.append(node)
output = """# Mechanically retained pinned video math. See extraction receipt.
import json
import re
import posixpath
from types import SimpleNamespace
import cv2
import numpy as np
import torch
os = SimpleNamespace(path=posixpath)
""" + ast.unparse(ast.fix_missing_locations(ast.Module(body=[
    ast.ClassDef(name="VideoAlgorithms", bases=[], keywords=[], body=functions, decorator_list=[])
], type_ignores=[]))) + "\n"
(V2 / "video_algorithms.py").write_text(output)
receipt = {"source": str(SOURCE), "source_sha256": hashlib.sha256(data).hexdigest(),
    "target": str(V2 / "video_algorithms.py"), "target_sha256": hashlib.sha256(output.encode()).hexdigest(),
    "methods": records, "allowed_boundary_changes": ["guest-owned decode path",
        "guarded native capture", "selected-frame admission", "managed original basename", "encoded byte length"],
    "runtime_guest_whole_pack_proof": False}
run = os.environ.get("AMY_EXTRACTION_RUN", "initial")
assert run.replace("-", "").isalnum()
with Path(f"/Users/ben/popbot/raw-chats/outputs/amy-oct8-readable-video-algorithm-extraction-{run}.json").open("x") as stream:
    json.dump(receipt, stream, indent=2)
    stream.write("\n")
print(json.dumps({"methods": len(records), "unchanged_method_asts": sum(r["normalized_ast_exact"] for r in records)}))
