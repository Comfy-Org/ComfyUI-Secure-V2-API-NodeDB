"""Actual registration, selected profile and exact source-pair acceptance."""
import copy,hashlib,importlib.metadata,json,os,shutil
from pathlib import Path
import pytest
from test_post_processing import V2,PACK,NEW,OLD,IDS,CORE,OVERLAY,FONT,FONT_BYTES
from comfy_secure_nodes import packpatch,packdb
from comfy_secure_nodes.packmanifest import FORMAT,encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
SNAPSHOT=PACK.parent
PAIR=SNAPSHOT.parents[2]/'patches/comfyui-post-processing-nodes/xb265f36/comfyui-post-processing-nodes-xb265f36'

def test_complete_manifest_actual_proxy_all23_schema_permissions_and_source_bytes():
    expected={'format':FORMAT,'runtime':manifest_declaration(V2),'nodes':{
        name:{'module':'_secure_nodes','class':cls.__name__,'sdk_refs':True,'permissions':list(cls.SDK_PERMISSIONS),
              'methods':{'validate_inputs':False,'fingerprint_inputs':False,'check_lazy_status':False},
              'schema':encode_schema(copy.deepcopy(cls.GET_SCHEMA()))} for name,cls in NEW.NODE_CLASS_MAPPINGS.items()},
        'web_directory':None,'frontend_permissions':[]}
    assert json.loads((V2/'secure-nodes.json').read_bytes())==expected
    proxy=packdb.load_pack(SNAPSHOT,mount_name='custom_nodes.post_processing_manifest_probe')
    assert len(proxy.node_mappings)==23 and list(proxy.node_mappings)==IDS
    assert not proxy.routes and proxy.web_directory is None
    for name,cls in proxy.node_mappings.items():
        assert cls.INPUT_TYPES()==NEW.NODE_CLASS_MAPPINGS[name].INPUT_TYPES()
    capture=json.loads((V2/'source-provenance.json').read_bytes())
    assert capture['pin']=='b265f36ef5988154bee2aa808d8abe8a2a197847'
    source={p.relative_to(PACK).as_posix():p for p in PACK.rglob('*') if p.is_file() and not p.is_relative_to(V2)}
    assert len(source)==36 and set(source)=={r['relative'] for r in capture['source_files']}
    for row in capture['source_files']:
        p=source[row['relative']];data=p.read_bytes()
        assert hashlib.sha256(data).hexdigest()==row['sha256'] and p.stat().st_mode&511==row['mode']
        assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==row['git_blob']
    assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))

def test_explicit_runtime_profile_font_identity_declarations_and_all_selected_sources():
    profile=json.loads((V2/'runtime-provenance.json').read_bytes())
    roots={'COMFY_CORE_ROOT':CORE,'MANY_POST_OVERLAY_ROOT':OVERLAY,
           'MANY_POST_FRONTEND_ROOT':Path(os.environ['MANY_POST_FRONTEND_ROOT']).resolve()}
    for row in profile['selected_runtime'].values():
        p=roots[row['root']]/row['relative']
        assert p.is_file() and not p.is_symlink()
        assert hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256']
    for name,row in profile['owned_declarations'].items():
        assert hashlib.sha256((V2/name).read_bytes()).hexdigest()==row['sha256']
    development=profile['development_profile']
    for name,version in development['distributions'].items():assert importlib.metadata.version(name)==version
    assert hashlib.sha256(FONT_BYTES).hexdigest()==development['arial_fixture']['sha256']
    assert len(FONT_BYTES)==development['arial_fixture']['bytes']

def test_plain_and_zip_pair_rebuild_twice_and_wrong_pristine_refusal(tmp_path):
    metadata,diff=packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix('.json').read_bytes())==metadata
    assert PAIR.with_suffix('.diff').read_bytes().decode()==diff
    blob=packpatch.bundle(metadata,diff)
    assert PAIR.with_suffix('.zip').read_bytes()==blob
    for count in range(2):
        fresh=tmp_path/str(count)/'comfyui-post-processing-nodes/xb265f36';fresh.mkdir(parents=True)
        shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
        if count==0:packpatch.apply(fresh,metadata,diff)
        else:packpatch.apply_bundle(fresh,blob)
        packpatch.validate_tree(fresh/PACK.name/'v2',V2)
    bad=tmp_path/'tamper/comfyui-post-processing-nodes/xb265f36';bad.mkdir(parents=True)
    shutil.copytree(PACK,bad/PACK.name,ignore=shutil.ignore_patterns('v2'))
    with (bad/PACK.name/'post_processing_nodes.py').open('ab') as f:f.write(b'\n# wrong preimage')
    with pytest.raises(packpatch.PackPatchError):packpatch.apply(bad,metadata,diff)
    assert not (bad/PACK.name/'v2').exists()
