"""Whole registration, explicit provider identities and exact patch reconstruction."""
import copy,hashlib,json,os,shutil
from pathlib import Path
import pytest
from test_flux import V2,PACK,NEW,OLD,CORE,OVERLAY,SCHEMA
from comfy_secure_nodes import packpatch,packdb
from comfy_secure_nodes.packmanifest import FORMAT,encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
PAIR=PACK.parents[3]/'patches/flux-prompt-generator/x1244eb9/flux-prompt-generator-x1244eb9'

def test_manifest_real_proxy_complete_schema_and_pristine_git_bytes():
    expected={'format':FORMAT,'runtime':manifest_declaration(V2),'nodes':{'FluxPromptGenerator':{
        'module':'_secure_node','class':NEW.__name__,'sdk_refs':False,'permissions':[],
        'methods':{'validate_inputs':False,'fingerprint_inputs':True,'check_lazy_status':False},
        'schema':encode_schema(copy.deepcopy(NEW.GET_SCHEMA()))}},'web_directory':None,'frontend_permissions':[]}
    assert json.loads((V2/'secure-nodes.json').read_bytes())==expected
    proxy=packdb.load_pack(PACK.parent,mount_name='custom_nodes.flux_manifest_probe')
    assert list(proxy.node_mappings)==['FluxPromptGenerator'] and not proxy.routes and proxy.web_directory is None
    assert proxy.node_mappings['FluxPromptGenerator'].INPUT_TYPES()==NEW.INPUT_TYPES()
    assert NEW.RETURN_TYPES==list(OLD.RETURN_TYPES)==['STRING']
    schema=NEW.INPUT_TYPES()['required']
    for name,spec in SCHEMA.items():
        actual=schema[name]
        if isinstance(spec[0],list):
            assert actual[0]=='COMBO' and actual[1]['options']==spec[0]
        else:assert actual[0]==spec[0]
        for key,value in spec[1].items():
            if name=='seed' and key=='default':continue
            assert actual[1][key]==value,(name,key)
    capture=json.loads((V2/'source-provenance.json').read_bytes())
    pristine={str(p.relative_to(PACK)):p for p in PACK.rglob('*') if p.is_file() and not p.is_relative_to(V2)}
    assert len(pristine)==37 and set(pristine)=={r['relative'] for r in capture['source_files']}
    for row in capture['source_files']:
        p=pristine[row['relative']];data=p.read_bytes()
        assert hashlib.sha256(data).hexdigest()==row['sha256'] and p.stat().st_mode&511==row['mode']
        assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==row['git_blob']
    assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))

def test_selected_source_and_owned_declaration_identities():
    profile=json.loads((V2/'runtime-provenance.json').read_bytes())
    roots={'COMFY_CORE_ROOT':CORE,'MANY_FLUX_OVERLAY_ROOT':OVERLAY,'MANY_FLUX_FRONTEND_ROOT':Path(os.environ['MANY_FLUX_FRONTEND_ROOT']).resolve()}
    for row in profile['selected_runtime'].values():
        p=roots[row['root']]/row['relative'];assert p.is_file() and not p.is_symlink()
        assert hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256']
    for name,row in profile['owned_declarations'].items():assert hashlib.sha256((V2/name).read_bytes()).hexdigest()==row['sha256']

def test_plain_zip_two_roundtrips_and_wrong_preimage_refusal(tmp_path):
    metadata,diff=packpatch.generate(PACK.parent)
    assert json.loads(PAIR.with_suffix('.json').read_bytes())==metadata
    assert PAIR.with_suffix('.diff').read_bytes().decode()==diff
    blob=packpatch.bundle(metadata,diff);assert blob==PAIR.with_suffix('.zip').read_bytes()
    for count in range(2):
        fresh=tmp_path/str(count)/'flux-prompt-generator/x1244eb9';fresh.mkdir(parents=True)
        shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
        if count==0:packpatch.apply(fresh,metadata,diff)
        else:packpatch.apply_bundle(fresh,blob)
        packpatch.validate_tree(fresh/PACK.name/'v2',V2)
    bad=tmp_path/'wrong/flux-prompt-generator/x1244eb9';bad.mkdir(parents=True)
    shutil.copytree(PACK,bad/PACK.name,ignore=shutil.ignore_patterns('v2'))
    with (bad/PACK.name/'flux_prompt_generator.py').open('ab') as f:f.write(b'\n# bad preimage')
    with pytest.raises(packpatch.PackPatchError):packpatch.apply(bad,metadata,diff)
    assert not (bad/PACK.name/'v2').exists()
