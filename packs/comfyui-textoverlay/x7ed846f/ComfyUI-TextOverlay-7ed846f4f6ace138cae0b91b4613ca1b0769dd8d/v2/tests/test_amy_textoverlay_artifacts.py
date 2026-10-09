"""Complete six pristine blobs, exact manifest/proxy/runtime and pair roundtrip."""
import copy,hashlib,json,os,shutil,tomllib
from pathlib import Path
import pytest
from test_amy_textoverlay import V2,PACK,NODE,CORE,BACKEND,FONT,FONT_SHA
from comfy_secure_nodes import packdb,packpatch
from comfy_secure_nodes.packmanifest import FORMAT,encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
SNAPSHOT=PACK.parent;DB=SNAPSHOT.parents[2]
PAIR=DB/'patches/comfyui-textoverlay/x7ed846f/comfyui-textoverlay-x7ed846f'

def test_manifest_real_proxy_full_exact_source_and_no_frontend():
    expected={'format':FORMAT,'runtime':manifest_declaration(V2),'nodes':{
        'Text Overlay':{'module':'_secure_nodes','class':'TextOverlaySecure','sdk_refs':True,'permissions':['inspect','raw','assets'],
          'methods':{'validate_inputs':False,'fingerprint_inputs':False,'check_lazy_status':False},'schema':encode_schema(copy.deepcopy(NODE.GET_SCHEMA()))}},
        'web_directory':None,'frontend_permissions':[]}
    assert json.loads((V2/'secure-nodes.json').read_bytes())==expected
    proxy=packdb.load_pack(SNAPSHOT,mount_name='custom_nodes.amy_textoverlay_proxy')
    assert list(proxy.node_mappings)==['Text Overlay'] and not proxy.routes and proxy.web_directory is None
    assert proxy.node_mappings['Text Overlay'].INPUT_TYPES()==NODE.INPUT_TYPES()
    provenance=json.loads((V2/'source-provenance.json').read_bytes())
    assert provenance['commit']=='7ed846f4f6ace138cae0b91b4613ca1b0769dd8d'
    assert provenance['registry_version']=='1.0.1'
    files={path.relative_to(PACK).as_posix():path for path in PACK.rglob('*') if path.is_file() and not path.is_relative_to(V2)}
    source={row['relative']:row for row in provenance['source_members']}
    assert set(files)==set(source) and len(files)==6
    for name,path in files.items():
        data=path.read_bytes();assert hashlib.sha256(data).hexdigest()==source[name]['sha256']
        assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==source[name]['git_blob']
        assert path.stat().st_mode&0o777==source[name]['git_mode']
    assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))
    assert not list(PACK.rglob('*.ttf')) and not list(PACK.rglob('*.otf'))
    original=tomllib.loads((PACK/'pyproject.toml').read_text())
    converted=tomllib.loads((V2/'pyproject.toml').read_text())
    assert original['project']['version']==converted['project']['version']=='1.0.1'
    assert converted['project']['dependencies']==['torch','numpy','Pillow']

def test_selected_runtime_font_identity_declarations_and_profile_qualification():
    provenance=json.loads((V2/'runtime-provenance.json').read_bytes())
    roots={'COMFY_CORE_ROOT':CORE,'TEXTOVERLAY_OVERLAY_ROOT':BACKEND.parent}
    for row in provenance['selected_runtime'].values():
        path=roots[row['root']]/row['relative'];assert path.is_file() and not path.is_symlink()
        assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256']
    for name,row in provenance['owned_declarations'].items():assert hashlib.sha256((V2/name).read_bytes()).hexdigest()==row['sha256']
    assert hashlib.sha256(FONT.read_bytes()).hexdigest()==FONT_SHA==provenance['test_font']['sha256']
    assert 'not redistributed' in provenance['font_qualification']
    declaration=manifest_declaration(V2)
    assert declaration['python']=={'requires':'>=3.13,<3.14','resolved':'3.13'}
    assert 'profile_sha256' not in (V2/'pyproject.toml').read_text()

def test_plain_and_zip_pair_exact_twice_and_tamper_refusal(tmp_path):
    meta,diff=packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix('.json').read_bytes())==meta
    assert PAIR.with_suffix('.diff').read_bytes().decode()==diff
    blob=packpatch.bundle(meta,diff);assert PAIR.with_suffix('.zip').read_bytes()==blob
    for index in range(2):
        fresh=tmp_path/str(index)/'comfyui-textoverlay/x7ed846f';fresh.mkdir(parents=True)
        shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
        if index==0:packpatch.apply(fresh,meta,diff)
        else:packpatch.apply_bundle(fresh,blob)
        packpatch.validate_tree(fresh/PACK.name/'v2',V2)
    bad=tmp_path/'bad/comfyui-textoverlay/x7ed846f';bad.mkdir(parents=True)
    shutil.copytree(PACK,bad/PACK.name,ignore=shutil.ignore_patterns('v2'))
    with (bad/PACK.name/'nodes.py').open('ab') as output:output.write(b'\n')
    with pytest.raises(packpatch.PackPatchError):packpatch.apply(bad,meta,diff)
    assert not (bad/PACK.name/'v2').exists()
