"""Exact source, manifest proxy, active resource/stub and pair/ZIP gates."""
import ast
import hashlib
import json
from pathlib import Path
import shutil
import stat
import pytest
import test_amy_handy_v3 as proof
from comfy_secure_nodes import packdb, packmanifest, packpatch

V2 = proof.V2
SOURCE = V2.parent
SNAP = SOURCE.parent
PAIR = SNAP.parents[2]/'patches/comfyui-handynodes-kt/xe2831dd'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def files(root):
    return {p.relative_to(root).as_posix():(digest(p), stat.S_IMODE(p.stat().st_mode))
        for p in root.rglob('*') if p.is_file() and 'v2' not in p.relative_to(root).parts}

def pair():
    return (json.loads((PAIR/'comfyui-handynodes-kt-xe2831dd.json').read_text()),
        (PAIR/'comfyui-handynodes-kt-xe2831dd.diff').read_text())

def test_pristine_full33_and_no_generated_litter():
    provenance = json.loads((V2/'source-provenance.json').read_text())
    assert {p:h for p,(h,_) in files(SOURCE).items()} == provenance['source_hashes']
    assert len(provenance['source_hashes']) == 33
    for root in (SOURCE, V2):
        assert not any(p.name in ('__pycache__','.pytest_cache','.DS_Store') or p.suffix=='.pyc'
            or p.is_symlink() for p in root.rglob('*'))

def test_exact_pristine_registration_census_without_eager_install():
    # Literal init mappings from the pinned source, not mocked eager imports.
    tree = ast.parse((SOURCE/'__init__.py').read_bytes())
    mappings = [item.value for item in tree.body if isinstance(item, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id=='NODE_CLASS_MAPPINGS' for t in item.targets)]
    assert len(mappings)==1 and isinstance(mappings[0],ast.Dict)
    ids = [ast.literal_eval(k) for k in mappings[0].keys]
    assert len(ids)==len(set(ids))==29
    assert set(ids)==set(proof.pack.NODE_CLASS_MAPPINGS)

def test_runtime_and_exact_canonical_stub_origins():
    provenance = json.loads((V2/'source-provenance.json').read_text())
    declaration = json.loads((V2/'secure-nodes.json').read_text())['runtime']
    assert declaration['python']=={'requires':'>=3.13,<3.14','resolved':'3.13'}
    assert 'dependency_profile_sha256' not in declaration
    for name in ('comfy-api.pyi','comfy-api.d.ts'):
        assert digest(V2/name)==provenance['stub_sha256'][name]
        assert (V2/name).read_bytes()==Path(provenance['stub_origins'][name]).read_bytes()

def test_full_manifest_proxy_and_private_route_without_pack_import():
    loaded = packdb.load_pack(SNAP, mount_name='custom_nodes.amy_handy_artifact')
    assert set(loaded.node_mappings)==set(proof.pack.NODE_CLASS_MAPPINGS)
    assert loaded.frontend_permissions==frozenset(('files.upload',))
    assert len(loaded.routes)==1
    declaration = json.loads((V2/'secure-nodes.json').read_text())
    assert declaration['routes']==[{'method':'post','path':'/tk/detect_speakers',
        'module':'_broker','handler':'detect_speakers','permissions':['assets']}]
    for node_id, node in declaration['nodes'].items():
        cls = proof.pack.NODE_CLASS_MAPPINGS[node_id]
        assert node['schema']==packmanifest.encode_schema(cls.GET_SCHEMA())
        assert node['permissions']==list(cls.SDK_PERMISSIONS)
        assert node['sdk_refs'] is (node_id=='TKPrintValueToLog')
        assert node['methods']['fingerprint_inputs']==(node_id in ('TKMultiImagePrompt','TKMultiImageSelect'))

@pytest.mark.parametrize('zip_mode',[False,True])
def test_pair_and_zip_exact_pristine_reconstruction(tmp_path, zip_mode):
    manifest, diff = pair()
    current, current_diff = packpatch.generate(SNAP)
    assert current==manifest and current_diff==diff
    snapshot = tmp_path/'comfyui-handynodes-kt'/'xe2831dd'
    target = snapshot/'TKNodes-HEAD'
    shutil.copytree(SOURCE, target, ignore=shutil.ignore_patterns('v2'))
    if zip_mode:
        packpatch.apply_bundle(snapshot, packpatch.bundle(manifest,diff))
    else:
        packpatch.apply(snapshot, manifest, diff)
    assert files(target/'v2')==files(V2)

def test_wrong_pristine_refused_without_publishing(tmp_path):
    manifest,diff=pair()
    snapshot=tmp_path/'comfyui-handynodes-kt'/'xe2831dd'
    target=snapshot/'TKNodes-HEAD'
    shutil.copytree(SOURCE,target,ignore=shutil.ignore_patterns('v2'))
    (target/'__init__.py').write_bytes(b'wrong source\n')
    before=files(target)
    with pytest.raises(packpatch.PackPatchError):
        packpatch.apply(snapshot,manifest,diff)
    assert files(target)==before

def test_immutable_pcm_resource_exact_and_active_requirements():
    assert (V2/'assets/breather.wav').read_bytes()==(SOURCE/'assets/breather.wav').read_bytes()
    import tomllib
    project=tomllib.loads((V2/'pyproject.toml').read_text())['project']
    assert project['requires-python']=='>=3.13,<3.14'
    assert 'pydub==0.25.1' in project['dependencies']
    assert "audioop-lts==0.2.2; python_version >= '3.13'" in project['dependencies']
    assert not any('sherpa' in x or 'ffmpeg' in x.lower() for x in project['dependencies'])
