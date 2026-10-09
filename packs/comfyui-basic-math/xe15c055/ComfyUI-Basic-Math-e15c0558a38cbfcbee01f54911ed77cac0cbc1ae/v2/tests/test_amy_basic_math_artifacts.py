"""Portable exact source/census/manifest/capability/plain+ZIP controls."""
import copy,hashlib,json,os,shutil
from pathlib import Path
import pytest
from test_amy_basic_math import V2,PACK,NEW,OLD,IDS
from comfy_secure_nodes import packpatch,packdb
from comfy_secure_nodes.packmanifest import FORMAT,encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
SNAPSHOT=PACK.parent;DB=SNAPSHOT.parents[2]
PAIR=DB/'patches/comfyui-basic-math/xe15c055/comfyui-basic-math-xe15c055'

def test_manifest_all23_proxy_exact_schema_validator_permissions_and_pristine_modes():
    manifest={'format':FORMAT,'runtime':manifest_declaration(V2),'nodes':{
        node_id:{'module':'_secure_nodes','class':cls.__name__,'sdk_refs':False,'permissions':[],
        'methods':{'validate_inputs':True,'fingerprint_inputs':False,'check_lazy_status':False},
        'schema':encode_schema(copy.deepcopy(cls.GET_SCHEMA()))} for node_id,cls in NEW.NODE_CLASS_MAPPINGS.items()},
        'web_directory':None,'frontend_permissions':[]}
    assert json.loads((V2/'secure-nodes.json').read_bytes())==manifest
    proxy=packdb.load_pack(SNAPSHOT,mount_name='custom_nodes.amy_basic_math_proxy')
    assert list(proxy.node_mappings)==IDS and len(IDS)==23
    assert not proxy.routes and proxy.web_directory is None
    for node_id,cls in proxy.node_mappings.items():
        assert cls.INPUT_TYPES()==NEW.NODE_CLASS_MAPPINGS[node_id].INPUT_TYPES()
    source=json.loads((V2/'source-provenance.json').read_bytes())
    assert source['commit']=='e15c0558a38cbfcbee01f54911ed77cac0cbc1ae'
    assert len(source['source_members'])==9
    expected={row['relative']:row for row in source['source_members']}
    files={p.relative_to(PACK).as_posix():p for p in PACK.rglob('*') if p.is_file() and not p.is_relative_to(V2)}
    assert set(files)==set(expected)
    for name,p in files.items():
        assert hashlib.sha256(p.read_bytes()).hexdigest()==expected[name]['sha256']
        assert p.stat().st_mode&0o777==expected[name]['archive_mode']
    assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))

def test_explicit_selected_runtime_and_exact_owned_declarations():
    provenance=json.loads((V2/'runtime-provenance.json').read_bytes())
    roots={'COMFY_CORE_ROOT':Path(os.environ['COMFY_CORE_ROOT']),
        'BASIC_MATH_OVERLAY_ROOT':Path(os.environ['BASIC_MATH_BACKEND_ROOT']).parent}
    for row in provenance['selected_runtime'].values():
        p=roots[row['root']]/row['relative']
        assert p.is_file() and not p.is_symlink()
        assert hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256']
    for name,row in provenance['owned_declarations'].items():
        assert hashlib.sha256((V2/name).read_bytes()).hexdigest()==row['sha256']

def test_plain_zip_rebuild_twice_tamper_refusal_and_expected_resources(tmp_path):
    meta,diff=packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix('.json').read_bytes())==meta
    assert PAIR.with_suffix('.diff').read_bytes().decode()==diff
    blob=packpatch.bundle(meta,diff)
    assert PAIR.with_suffix('.zip').read_bytes()==blob
    for i in range(2):
        fresh=tmp_path/str(i)/'comfyui-basic-math/xe15c055';fresh.mkdir(parents=True)
        shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
        if i==0:packpatch.apply(fresh,meta,diff)
        else:packpatch.apply_bundle(fresh,blob)
        packpatch.validate_tree(fresh/PACK.name/'v2',V2)
    bad=tmp_path/'tamper/comfyui-basic-math/xe15c055';bad.mkdir(parents=True)
    shutil.copytree(PACK,bad/PACK.name,ignore=shutil.ignore_patterns('v2'))
    with (bad/PACK.name/'math_nodes.py').open('ab') as f:f.write(b'\n#tamper')
    with pytest.raises(packpatch.PackPatchError):packpatch.apply(bad,meta,diff)
    assert not (bad/PACK.name/'v2').exists()
