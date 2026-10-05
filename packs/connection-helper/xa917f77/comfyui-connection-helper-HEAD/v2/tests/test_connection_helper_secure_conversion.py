from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
V2 = Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
PACK_DB = SNAPSHOT.parents[2]
BACKEND = Path("/Users/ben/comfy/ComfyUI_secure_nodes/backend")
CORE = Path("/Users/ben/comfy/ComfyUI-secure-nodes")
COMMIT = "a917f77bd02cde5aa67f427eb81e8356fffbc98e"
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "f2d067f03a2f80f942ba0d5c777daa1148562e44e836b72cb27129b36ba3855f"
PAIR = PACK_DB / "patches/connection-helper/xa917f77/connection-helper-xa917f77"
PRISTINE_FILES = {
    ".github/workflows/publish.yml",
    ".gitignore",
    "LICENSE.txt",
    "README.md",
    "__init__.py",
    "js/connection_helper.js",
    "misc/buttons.jpg",
    "pyproject.toml",
}

for root in (BACKEND, CORE):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from comfy_secure_nodes import packpatch


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _import(name: str, root: Path):
    spec = importlib.util.spec_from_file_location(
        name, root / "__init__.py", submodule_search_locations=[str(root)]
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_actual_loader_census_manifest_contract_and_license_are_exact():
    pristine = _import("connection_helper_pristine", PACK)
    secure = _import("connection_helper_secure", V2)
    assert COMMIT == "a917f77bd02cde5aa67f427eb81e8356fffbc98e"
    assert pristine.NODE_CLASS_MAPPINGS == secure.NODE_CLASS_MAPPINGS == {}
    assert pristine.NODE_DISPLAY_NAME_MAPPINGS == secure.NODE_DISPLAY_NAME_MAPPINGS == {}
    assert pristine.WEB_DIRECTORY == "./js"
    assert secure.WEB_DIRECTORY == "./js"
    assert {
        path.relative_to(PACK).as_posix()
        for path in PACK.rglob("*")
        if path.is_file() and "v2" not in path.relative_to(PACK).parts
    } == PRISTINE_FILES
    manifest = json.loads((V2 / "secure-nodes.json").read_text())
    assert manifest == {
        "format": "comfy-secure-nodes-v1",
        "frontend_permissions": [],
        "nodes": {},
        "runtime": {"python": {"requires": ">=3.13,<3.14", "resolved": "3.13"}},
        "web_directory": "js",
    }
    assert _sha(V2 / "comfy-api.d.ts") == DTS_SHA
    assert _sha(V2 / "comfy-api.pyi") == PYI_SHA
    assert (V2 / "LICENSE.txt").read_bytes() == (PACK / "LICENSE.txt").read_bytes()


def test_frontend_behavior_and_lifecycle_harness():
    result = subprocess.run(
        ["node", str(V2 / "tests/connection_helper_frontend_harness.mjs")],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS" in result.stdout


def test_frontend_typechecks_and_has_no_ambient_authority(tmp_path):
    source = (V2 / "js/connection_helper.js").read_text()
    for forbidden in (
        "../../scripts/app.js",
        "app.graph",
        "LiteGraph",
        "window.",
        "document.",
        "fetch(",
        "PromptServer",
        "onDrawForeground",
        "onMouseDown",
    ):
        assert forbidden not in source
    config = tmp_path / "tsconfig.json"
    config.write_text(
        json.dumps(
            {
                "compilerOptions": {
                    "allowJs": True,
                    "checkJs": True,
                    "noEmit": True,
                    "strict": True,
                    "target": "ES2022",
                    "module": "ESNext",
                    "moduleResolution": "Bundler",
                    "lib": ["ES2022", "DOM"],
                    "ignoreDeprecations": "6.0",
                    "baseUrl": str(V2),
                    "paths": {"/comfy/api/v2.js": ["./comfy-runtime.d.ts"]},
                },
                "files": [
                    str(V2 / "js/connection_helper.js"),
                    str(V2 / "comfy-runtime.d.ts"),
                ],
            }
        )
    )
    result = subprocess.run(
        ["npx", "tsc", "-p", str(config)],
        cwd="/Users/ben/comfy/ComfyUI_frontend",
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_docs_record_the_only_presentation_change_and_no_gap():
    report = (V2 / "SECURE_CONVERSION.md").read_text()
    assert "0 Python nodes, 1 frontend extension, 0 routes" in report
    assert "context submenu" in report
    assert "No operation or authority was dropped" in report.replace("\n", " ")


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_text() == diff_text
    rebuilt = tmp_path / "connection-helper" / SNAPSHOT.name
    rebuilt.parent.mkdir()
    shutil.copytree(SNAPSHOT, rebuilt, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(
        rebuilt,
        json.loads(PAIR.with_suffix(".json").read_text()),
        PAIR.with_suffix(".diff").read_text(),
    )
    packpatch.validate_tree(rebuilt / PACK.name / "v2", V2)


def test_no_cache_artifacts():
    assert not list(PACK.rglob("__pycache__"))
    assert not list(PACK.rglob("*.pyc"))
    assert not list(PACK.rglob(".pytest_cache"))
