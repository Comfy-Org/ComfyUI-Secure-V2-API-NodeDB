"""Whole draft census/schema and exact artifacts; not release or inference certification."""
import ast,copy,hashlib,json,shutil,sys
from pathlib import Path
import pytest
from test_ned_comfyroll_cycle_models import NEW,V2,PACK
from comfy_secure_nodes import packpatch,packdb
from comfy_secure_nodes.packmanifest import encode_schema,decode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
MANIFEST=json.loads((V2/'secure-nodes.json').read_text())
CENSUS=json.loads((V2/'intended-node-census.json').read_text())
LOCAL_REVIEW=json.loads((V2/'LOCAL_RELEASE_REVIEW.json').read_text())
@pytest.mark.parametrize('id',sorted(CENSUS))
def test_all_199_exact_ids_module_schema_methods_permission_and_pending_disposition(id):
    cls=NEW.NODE_CLASS_MAPPINGS[id];definition=MANIFEST['nodes'][id]
    assert definition['module']==Path(sys.modules[cls.__module__].__file__).relative_to(V2).with_suffix('').name
    assert definition['class']==cls.__name__ and definition['schema']==encode_schema(copy.deepcopy(cls.GET_SCHEMA()))
    assert definition['sdk_refs']==(cls.SDK_REFS is True) and definition['permissions']==list(cls.SDK_PERMISSIONS)
    assert definition['methods']=={m:m in cls.__dict__ for m in ('validate_inputs','fingerprint_inputs','check_lazy_status')}
    assert CENSUS[id]['status']=='pending' and CENSUS[id]['registered_in_v2'] is True
    assert CENSUS[id]['source_sha256']==hashlib.sha256((PACK/'nodes'/Path(CENSUS[id]['source_path']).name).read_bytes()).hexdigest()
    current=LOCAL_REVIEW['nodes'][id]
    assert current['status']=='supported' and current['deployment_status']=='pending'
    assert current['public_permissions']==definition['permissions']
    assert current['current_source']['sha256']==CENSUS[id]['source_sha256']
    assert current['current_implementation']['sha256']==hashlib.sha256((V2/(definition['module']+'.py')).read_bytes()).hexdigest()
def test_all_199_manifest_proxy_admission_preserves_schema_without_importing_legacy_entrypoint():
    loaded=packdb.load_pack(PACK.parent,mount_name='custom_nodes.ned_comfyroll_artifact_review')
    assert set(loaded.node_mappings)==set(NEW.NODE_CLASS_MAPPINGS)==set(CENSUS)==set(MANIFEST['nodes']) and len(CENSUS)==199
    assert loaded.web_directory is None and loaded.routes==() and not loaded.frontend_permissions
    assert loaded.asset_directories=={'fonts':V2/'fonts'}
    assert MANIFEST['runtime']==manifest_declaration(V2) and MANIFEST['runtime']['python']['resolved']=='3.13'
    for id,cls in loaded.node_mappings.items():
        # The production proxy deliberately hydrates remote options at discovery.
        # Preserve EVERY other field and require exact closed service values, not empty stored options.
        expected=decode_schema(copy.deepcopy(MANIFEST['nodes'][id]['schema']))
        for inp in expected.inputs:
            if getattr(inp,'remote',None) is not None:
                names=packdb.remote_catalogue_options(inp.remote.route)
                if names is not None:
                    static=getattr(inp.remote,'static_options',None)
                    inp.options=names if static is None else list(dict.fromkeys(static+names))
        assert encode_schema(cls.GET_SCHEMA())==encode_schema(expected)
        assert cls.SDK_PERMISSIONS==NEW.NODE_CLASS_MAPPINGS[id].SDK_PERMISSIONS
def test_exact_public_stub_successors_and_no_cache_or_checked_runtime_litter():
    from comfy_secure_nodes import apistubs
    assert (V2/'comfy-api.pyi').read_text()==apistubs.generate()
    assert hashlib.sha256((V2/'comfy-api.pyi').read_bytes()).hexdigest()=='7de9937e919d817f1ae1d5660a99b2fb90737f93946c17207452018730d687d6'
    assert hashlib.sha256((V2/'comfy-api.d.ts').read_bytes()).hexdigest()=='2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090'
    assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))
    assert not list(V2.glob('.venv')) and not list(V2.glob('node_modules'))
def test_active_registration_modules_use_public_sdk_no_ambient_host_imports_private_ref_casts_or_installs():
    modules={Path(sys.modules[cls.__module__].__file__) for cls in NEW.NODE_CLASS_MAPPINGS.values()}
    for p in modules:
        tree=ast.parse(p.read_text())
        for n in ast.walk(tree):
            if isinstance(n,ast.Import):
                assert all(a.name.split('.')[0] not in {'folder_paths','comfy','nodes','server','requests','subprocess','socket','urllib','importlib'} for a in n.names),(p,n.lineno)
            if isinstance(n,ast.ImportFrom):
                assert n.level>0 or (n.module or '').split('.')[0] not in {'folder_paths','comfy','nodes','server','requests','subprocess','socket','urllib','importlib'},(p,n.lineno)
            if isinstance(n,ast.Attribute):assert n.attr not in {'_from_raw','_raw','_resolve_host','system','popen'},(p,n.lineno)
    # Dormant copied legacy sources are archived provenance, not registered secure modules.
    assert all(p.name.startswith('secure_') for p in modules)
def _files(root):return {str(p.relative_to(root)):(p.read_bytes(),p.stat().st_mode&0o777) for p in root.rglob('*') if p.is_file()}
@pytest.mark.parametrize('generation',[0,1])
def test_pristine_to_v2_generated_pair_and_zip_are_byte_exact_in_fresh_reconstruction(tmp_path,generation):
    manifest,diff=packpatch.generate(PACK.parent)
    pair=Path(__file__).resolve().parents[6]/'patches/comfyui-comfyroll-customnodes/xd78b780'
    stored=json.loads((pair/'comfyui-comfyroll-customnodes-xd78b780.json').read_text())
    text=(pair/'comfyui-comfyroll-customnodes-xd78b780.diff').read_text()
    assert stored==manifest and text==diff
    for mode in ['pair','zip']:
        release=tmp_path/mode/'comfyui-comfyroll-customnodes'/'xd78b780'
        shutil.copytree(PACK,release/PACK.name,ignore=shutil.ignore_patterns('v2'))
        if mode=='pair':packpatch.apply(release,stored,text)
        else:packpatch.apply_bundle(release,packpatch.bundle(stored,text))
        assert _files(release/PACK.name/'v2')==_files(V2)
    assert generation in (0,1)
def test_wrong_pristine_refuses_before_v2_materialization(tmp_path):
    manifest,diff=packpatch.generate(PACK.parent)
    release=tmp_path/'comfyui-comfyroll-customnodes'/'xd78b780'
    shutil.copytree(PACK,release/PACK.name,ignore=shutil.ignore_patterns('v2'))
    target=release/PACK.name/'categories.py';target.write_text(target.read_text()+'\n# altered pristine\n')
    with pytest.raises(packpatch.PackPatchError,match='different snapshot'):packpatch.apply(release,manifest,diff)
    assert not (release/PACK.name/'v2').exists()
