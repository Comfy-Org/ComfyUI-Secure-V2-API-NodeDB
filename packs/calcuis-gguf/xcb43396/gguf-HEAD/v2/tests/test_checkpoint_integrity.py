"""Artifact integrity never promotes this pending draft to supported/released."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

V2 = Path(__file__).resolve().parents[1]
PACK = V2.parent
sys.dont_write_bytecode = True


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_pristine89_exact_sources_and_no_cache_pollution():
    rows = json.loads((V2 / 'tests/pristine_sha256.json').read_text())
    assert len(rows) == 89 and len({row['path'] for row in rows}) == 89
    assert all(sha(PACK / row['path']) == row['sha256'] for row in rows)
    pristine = [path.relative_to(PACK).as_posix() for path in PACK.rglob('*') if path.is_file() and not path.is_relative_to(V2)]
    assert sorted(pristine) == sorted(row['path'] for row in rows)
    assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc')) and not list(PACK.rglob('.pytest_cache'))


def test_current_approved_contracts_pure_math_license_and_standard_report():
    assert sha(V2 / 'comfy-api.pyi') == '7a445480a536697937a7ee4169bc39a41df32908ba84f5130fbc40eaf42d2f3f'
    assert sha(V2 / 'comfy-api.d.ts') == '2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090'
    assert (V2 / 'LICENSE').read_bytes() == (PACK / 'LICENSE').read_bytes()
    assert (V2 / 'version.json').read_bytes() == (PACK / 'version.json').read_bytes()
    for name in ('const.py', 'lazy.py', 'quant.py', 'quant5.py'):
        assert (V2 / 'gguf_math' / name).read_bytes() == (PACK / 'gguf_connector' / name).read_bytes()
    report = (V2 / 'SECURE_CONVERSION.md').read_text()
    assert report.startswith('<!-- secure-conversion-report-v1 -->') and 'not whole-pack acceptance' in report


def test_draft_manifest_exact_current13_schemas_not_support_certificate():
    from comfy_secure_nodes.packmanifest import encode_schema
    from comfy_secure_nodes.packruntime import manifest_declaration
    spec = importlib.util.spec_from_file_location('moe_gguf_manifest_integrity', V2 / '__init__.py', submodule_search_locations=[str(V2)])
    package = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = package
    spec.loader.exec_module(package)
    manifest = json.loads((V2 / 'secure-nodes.json').read_text())
    assert set(manifest['nodes']) == set(package.NODE_CLASS_MAPPINGS) and len(manifest['nodes']) == 13
    assert manifest['runtime'] == manifest_declaration(V2)
    for node_id, cls in package.NODE_CLASS_MAPPINGS.items():
        row = manifest['nodes'][node_id]
        assert row['module'] == 'nodes' and row['class'] == node_id
        assert row['permissions'] == list(cls.SDK_PERMISSIONS)
        assert row['sdk_refs'] is cls.SDK_REFS
        assert row['schema'] == encode_schema(cls.GET_SCHEMA())


def test_draft_pristine_patch_pair_byte_exact_roundtrip(tmp_path):
    from comfy_secure_nodes import packpatch
    manifest, diff = packpatch.generate(PACK.parent)
    fresh = tmp_path / 'calcuis-gguf' / 'xcb43396'
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns('v2'))
    packpatch.apply(fresh, manifest, diff)
    packpatch.validate_tree(fresh / PACK.name / 'v2', V2)
    pair = PACK.parents[3] / 'patches/calcuis-gguf/xcb43396'
    stored_json = pair / 'calcuis-gguf-xcb43396.json'
    assert stored_json.is_file(), 'owned draft pair must exist; this is not release admission'
    assert json.loads(stored_json.read_text()) == manifest
    assert (pair / 'calcuis-gguf-xcb43396.diff').read_bytes() == diff.encode()
