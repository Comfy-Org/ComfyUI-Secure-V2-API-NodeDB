"""Exact GitV1, schema/proxy, local runtime and plain/ZIP reconstruction."""
import copy,hashlib,json,os,shutil,tomllib
from pathlib import Path
import pytest
from test_amy_all_in_one_style import V2,PACK,OLD,NEW,NATIVE,CONVERTED
from comfy_secure_nodes import packdb,packpatch
from comfy_secure_nodes.packmanifest import FORMAT,encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
SNAPSHOT=PACK.parent;DB=SNAPSHOT.parents[2]
PAIR=DB/'patches/all-in-one-style/xce17ba7/all-in-one-style-xce17ba7'

def test_exact_manifest_proxy_full_source_and_no_authority_frontend():
    expected={'format':FORMAT,'runtime':manifest_declaration(V2),'nodes':{
        'ComfyUIStyler':{'module':'_secure_nodes','class':'ComfyUIStylerSecure','sdk_refs':False,'permissions':[],
          'methods':{'validate_inputs':False,'fingerprint_inputs':False,'check_lazy_status':False},
          'schema':encode_schema(copy.deepcopy(CONVERTED.GET_SCHEMA()))}},
        'web_directory':None,'frontend_permissions':[]}
    assert json.loads((V2/'secure-nodes.json').read_bytes())==expected
    proxy=packdb.load_pack(SNAPSHOT,mount_name='custom_nodes.amy_style_proxy')
    assert list(proxy.node_mappings)==['ComfyUIStyler'] and not proxy.routes and proxy.web_directory is None
    assert proxy.node_mappings['ComfyUIStyler'].INPUT_TYPES()==CONVERTED.INPUT_TYPES()
    provenance=json.loads((V2/'source-provenance.json').read_bytes())
    assert provenance['commit']=='ce17ba7079c99688141e40eed892e14bb92613bb'
    assert '25/26' in provenance['release_match']
    assert tomllib.loads((PACK/'pyproject.toml').read_text())['project']['version']=='1.0.0'
    assert 'version = "1.0.1"' in provenance['publication_metadata_delta']
    files={p.relative_to(PACK).as_posix():p for p in PACK.rglob('*') if p.is_file() and not p.is_relative_to(V2)}
    expected={row['relative']:row for row in provenance['source_members']}
    assert set(files)==set(expected) and len(files)==26
    for name,p in files.items():
        data=p.read_bytes();assert hashlib.sha256(data).hexdigest()==expected[name]['sha256']
        assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==expected[name]['git_blob']
        assert p.stat().st_mode&0o777==int(expected[name]['mode'],8)
    assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))

def test_actual_selected_runtime_and_owned_declarations():
    provenance=json.loads((V2/'runtime-provenance.json').read_bytes())
    roots={'COMFY_CORE_ROOT':Path(os.environ['COMFY_CORE_ROOT']),'STYLE_OVERLAY_ROOT':Path(os.environ['STYLE_BACKEND_ROOT']).parent}
    for row in provenance['selected_runtime'].values():
        p=roots[row['root']]/row['relative'];assert p.is_file() and not p.is_symlink()
        assert hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256']
    for name,row in provenance['owned_declarations'].items():
        assert hashlib.sha256((V2/name).read_bytes()).hexdigest()==row['sha256']
    declaration=manifest_declaration(V2)
    assert declaration['python']=={'requires':'>=3.13,<3.14','resolved':'3.13'}
    assert 'dependencies' not in declaration

def test_exact_plain_and_zip_twice_with_tamper_refusal(tmp_path):
    meta,diff=packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix('.json').read_bytes())==meta
    assert PAIR.with_suffix('.diff').read_bytes().decode()==diff
    blob=packpatch.bundle(meta,diff)
    assert PAIR.with_suffix('.zip').read_bytes()==blob
    for i in range(2):
        fresh=tmp_path/str(i)/'all-in-one-style/xce17ba7';fresh.mkdir(parents=True)
        shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
        if i==0:packpatch.apply(fresh,meta,diff)
        else:packpatch.apply_bundle(fresh,blob)
        packpatch.validate_tree(fresh/PACK.name/'v2',V2)
    bad=tmp_path/'tamper/all-in-one-style/xce17ba7';bad.mkdir(parents=True)
    shutil.copytree(PACK,bad/PACK.name,ignore=shutil.ignore_patterns('v2'))
    with (bad/PACK.name/'data/Aesthetic/Aesthetic.json').open('ab') as f:f.write(b' ')
    with pytest.raises(packpatch.PackPatchError):packpatch.apply(bad,meta,diff)
    assert not (bad/PACK.name/'v2').exists()
