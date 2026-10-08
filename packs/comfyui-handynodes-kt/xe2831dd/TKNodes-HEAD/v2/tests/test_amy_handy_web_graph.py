"""Actual canonical recursive listing body, active imports, archival disposition."""
import ast
import asyncio
import glob
import hashlib
import json
import os
from pathlib import Path
import re
import types
import urllib.parse
from aiohttp import web

V2 = Path(__file__).resolve().parents[1]
SERVER = Path("/Users/ben/comfy/ComfyUI-secure-nodes/server.py")
ENTRIES = {"TKAudioSpeakerTalkTime..js", "TKLocateSpeakersUsingSilenceBreaks.js",
           "TKVideoUserInputs.js", "TKPhotoUserInputs.js", "TKVideoUserInputsBasic.js",
           "extTKMultiImagePrompt.js", "extTKMultiImageSelect.js"}
HELPERS = {"secureDimensionControl.js", "secureDimensionDefaults.js", "secureImageGrid.js",
           "secureSpeakerState.js", "secureTrackFields.js"}

def test_canonical_recursive_extensions_listing_excludes_archival_logger(tmp_path):
    tree = ast.parse(SERVER.read_bytes())
    function = next(n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef) and n.name == "get_extensions")
    function.decorator_list = []
    env = {"glob": glob, "os": os, "urllib": urllib, "web": web,
           "self": types.SimpleNamespace(web_root=str(tmp_path)),
           "nodes": types.SimpleNamespace(EXTENSION_WEB_DIRS={"handy-proof": str(V2 / "web")})}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(SERVER), "exec"), env)
    response = asyncio.run(env["get_extensions"](None))
    paths = json.loads(response.body)
    assert set(paths) == {"/extensions/handy-proof/" + name for name in ENTRIES | HELPERS}
    assert len(paths) == 12
    assert not any("logger" in item.lower() or "ErrorHandler" in item for item in paths)

def test_all_active_imports_are_confined_independent_of_logger():
    assert {p.name for p in (V2 / "web").rglob("*.js")} == ENTRIES | HELPERS
    pattern = re.compile(r"(?:import\s+.*?\s+from\s+|import\s*)['\"]([^'\"]+)['\"]")
    reached = set()
    def visit(path):
        if path in reached:
            return
        reached.add(path)
        text = path.read_text()
        assert not any(token in text for token in ("LoggerUtils", "ErrorHandler", "localStorage",
                                                   "ResolutionMasterLogger", "window.", "logger.js"))
        for target in pattern.findall(text):
            if target == "/comfy/api/v2.js":
                continue
            assert target.startswith("./")
            next_path = (path.parent / target).resolve()
            assert next_path.is_relative_to(V2 / "web") and next_path.is_file()
            visit(next_path)
    for name in ENTRIES:
        visit(V2 / "web" / name)
    assert {p.name for p in reached} == ENTRIES | HELPERS

def test_inactive_archive_exact_source_and_no_authored_logging_ui():
    for path in ("js/logger.js", "js/config.js", "js/ErrorHandler.js", "js/utils/LoggerUtils.js"):
        assert (V2 / path).read_bytes() == (V2.parent / path).read_bytes()
    assert "export const LOG_LEVEL = 'NONE';" in (V2 / "js/config.js").read_text()
    active = "\n".join(p.read_text() for p in (V2 / "web").glob("*.js"))
    assert "ResolutionMaster_logger_config" not in active
    # Source diagnostics are archived, not a claim to preserve editable durable
    # logging preferences or to create a new settings product.
