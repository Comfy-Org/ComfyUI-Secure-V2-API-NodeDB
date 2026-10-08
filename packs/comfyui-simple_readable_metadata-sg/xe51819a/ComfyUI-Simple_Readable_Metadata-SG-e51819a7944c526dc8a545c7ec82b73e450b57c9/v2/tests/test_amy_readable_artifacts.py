"""Exact complete resources/schema/stubs/patches and current collision gates."""
import ast
import asyncio
import base64
import copy
import glob
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import urllib.parse
from types import SimpleNamespace
import pytest
from test_amy_readable_conversion import V2, CORE, BACK, PACK, manifest, EXPECTED
from comfy_secure_nodes import packpatch, packdb, apistubs
OUT=Path('/Users/ben/popbot/raw-chats/outputs')
PAIR=V2.parents[4]/'patches/comfyui-simple_readable_metadata-sg/xe51819a'
STEM='comfyui-simple_readable_metadata-sg-xe51819a'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def test_every_pristine_git_blob_resource_and_no_cache():
    packet=json.loads((OUT/'amy-oct8-readable-metadata-capture.json').read_bytes())
    actual=[p.relative_to(V2.parent).as_posix() for p in V2.parent.rglob('*')
        if p.is_file() and 'v2' not in p.relative_to(V2.parent).parts]
    assert sorted(actual)==sorted(row['path'] for row in packet['pristine']) and len(actual)==19
    for row in packet['pristine']:
        path=V2.parent/row['path'];data=path.read_bytes()
        assert sha(path)==row['sha256'] and len(data)==row['bytes']
        assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==row['git_blob']
        assert oct(path.stat().st_mode&0o777)==row['retained_mode']
    assert (V2/'old versions/ComfyUI-Simple_Readable_Metadata-SG_2.0.2.rar').read_bytes()==(
        V2.parent/'old versions/ComfyUI-Simple_Readable_Metadata-SG_2.0.2.rar').read_bytes()
    assert not list(V2.parent.rglob('__pycache__')) and not list(V2.parent.rglob('*.pyc'))

def test_manifest_proxy_runtime_and_declarations_exact():
    assert json.loads((V2/'secure-nodes.json').read_bytes())==manifest()
    loaded=packdb.load_pack(V2.parent.parent,mount_name='custom_nodes.amy_readable_final_proxy')
    assert set(loaded.node_mappings)==set(EXPECTED) and len(loaded.routes)==0
    assert loaded.web_directory==V2/'web'
    assert loaded.frontend_permissions==frozenset({'clipboard.read','clipboard.write'})
    assert (V2/'comfy-api.pyi').read_text()==apistubs.generate()
    assert (V2/'comfy-api.d.ts').read_bytes()==(OUT/'many-oct8-owned-element-access/comfy-api.d.ts').read_bytes()
    provenance=json.loads((V2/'source-provenance.json').read_bytes())
    for row in provenance['selected_runtime']:
        assert sha(row['path'])==row['sha256']
    for row in provenance['native_selected_payloads']:
        assert sha(row['path'])==row['sha256']

def test_actual_canonical_recursive_extension_listing_and_import_graph():
    source=ast.parse((CORE/'server.py').read_bytes())
    target=next(n for n in ast.walk(source) if isinstance(n,ast.AsyncFunctionDef) and n.name=='get_extensions')
    target.decorator_list=[]
    ns={'glob':glob,'os':os,'self':SimpleNamespace(web_root=''), 'urllib':urllib,
        'nodes':SimpleNamespace(EXTENSION_WEB_DIRS={'amy':str(V2/'web')}),
        'web':SimpleNamespace(json_response=lambda value:value)}
    exec(compile(ast.Module(body=[target],type_ignores=[]),str(CORE/'server.py'),'exec'),ns)
    with tempfile.TemporaryDirectory(prefix='amy-empty-host-web-') as empty:
        ns['self'].web_root=empty
        listed=asyncio.run(ns['get_extensions'](None))
    entries=sorted(p.name for p in (V2/'web').glob('*.js'))
    assert sorted(Path(name).name for name in listed)==entries and len(entries)==5
    helpers=set()
    for path in (V2/'web').iterdir():
        if path.suffix not in ('.js','.mjs'):continue
        for imported in re.findall(r"from\s+['\"]([^'\"]+)['\"]",path.read_text()):
            if imported=='/comfy/api/v2.js':continue
            assert imported.startswith('./')
            resolved=(path.parent/imported).resolve();assert resolved.parent==V2/'web' and resolved.is_file()
            helpers.add(resolved.name)
    assert helpers=={'display-state.mjs','viewer-state.mjs','viewer-profile.mjs'}
    decoded=base64.b64decode((V2/'tests/browser-preview.base64').read_bytes(),validate=False)
    assert decoded==(OUT/'amy-oct8-readable-browser-preview-original.webm').read_bytes()

def test_plain_and_zip_exact_roundtrip_then_tamper_refusal():
    m=json.loads((PAIR/(STEM+'.json')).read_bytes());diff=(PAIR/(STEM+'.diff')).read_bytes().decode('utf-8')
    assert packpatch.generate(V2.parent.parent)==(m,diff)
    artifact=packpatch.bundle(m,diff)
    assert artifact==(OUT/'amy-oct8-readable-metadata-pair.zip').read_bytes()
    for kind in ('plain','zip','tampered'):
        with tempfile.TemporaryDirectory(prefix='amy-readable-test-roundtrip-') as temporary:
            snapshot=Path(temporary)/m['pack']/m['key'];base=snapshot/V2.parent.name
            shutil.copytree(V2.parent,base,ignore=lambda directory,names:['v2'] if Path(directory)==V2.parent else [])
            if kind=='tampered':
                (base/'README.md').write_text('tampered')
                with pytest.raises(packpatch.PackPatchError):packpatch.apply(snapshot,m,diff)
                assert not (base/'v2').exists()
            else:
                if kind=='plain':packpatch.apply(snapshot,m,diff)
                else:packpatch.apply_bundle(snapshot,artifact)
                packpatch.validate_tree(base/'v2',V2);packpatch.validate_bundle(snapshot,artifact)

def test_current_central_normalized_upstream_pin_and_exact_id_negative():
    root=BACK.parent/'pack-db'
    catalogue=json.loads((root/'packs/packs.json').read_bytes())
    def norm(value):return value.rstrip('/').removesuffix('.git').lower()
    target=norm('https://github.com/ShammiG/ComfyUI-Simple_Readable_Metadata-SG')
    assert target not in json.dumps(catalogue).lower()
    assert 'e51819a7944c526dc8a545c7ec82b73e450b57c9' not in json.dumps(catalogue)
    ids={}
    for path in (root/'packs').rglob('secure-nodes.json'):
        nodes=json.loads(path.read_bytes())['nodes']
        for name in EXPECTED:
            if name in nodes:ids.setdefault(name,[]).append(str(path))
    assert ids=={}
    print('READABLE_CURRENT_CENTRAL_NEGATIVE',len(catalogue),'rows',sha(root/'packs/packs.json'))
