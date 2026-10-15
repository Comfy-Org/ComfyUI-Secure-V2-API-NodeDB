"""Partial-candidate integrity, not a complete-pack or inference certificate."""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode=True
V2=Path(__file__).resolve().parents[1]
PACK=V2.parent
SNAPSHOT=PACK.parent
CORPUS=PACK.parents[3]
BACKEND=Path('/Users/ben/comfy/ComfyUI_secure_nodes/backend')
CORE=Path('/Users/ben/comfy/ComfyUI-secure-nodes')
for path in (CORE,BACKEND):sys.path.insert(0,str(path))
from comfy_secure_nodes import packdb,packpatch
from comfy_secure_nodes.packmanifest import encode_schema
from comfy_secure_nodes.webassets import remote_catalogue_options


def mapping():
    spec=importlib.util.spec_from_file_location('_wan_artifact_data',V2/'__init__.py',
        submodule_search_locations=[str(V2)])
    module=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=module
    spec.loader.exec_module(module)
    return module.NODE_CLASS_MAPPINGS


def test_entire_pinned_snapshot_hashes_and_unchanged_bundled_resources():
    expected=json.loads((V2/'tests/pristine-sha256.json').read_text())
    files={path.relative_to(PACK).as_posix():hashlib.sha256(path.read_bytes()).hexdigest()
        for path in PACK.rglob('*') if path.is_file() and path.relative_to(PACK).parts[0]!='v2'}
    assert expected['upstream_commit']=='088128b224242e110d3906c6750e9a3a348a659b'
    assert len(files)==241 and files==expected['files']
    modified={'__init__.py','pyproject.toml','qwen/qwen.py','wanvideo/modules/tokenizers.py'}
    for relative,digest in files.items():
        if relative not in modified:
            assert hashlib.sha256((V2/relative).read_bytes()).hexdigest()==digest
    assert not list(PACK.rglob('*.pyc')) and not list(PACK.rglob('__pycache__'))


def test_manifest_is_exact_partial_candidate_not_full_release():
    manifest=json.loads((V2/'secure-nodes.json').read_text())
    classes=mapping()
    assert manifest['conversion_progress']=={'complete':False,'intended_upstream_ids':147,
        'candidate_registered_ids':65,'remaining_ids':82,'pack_count_increment':0}
    assert set(classes)==set(manifest['nodes']) and len(classes)==65
    for node_id,cls in classes.items():
        record=manifest['nodes'][node_id]
        assert record['schema']==encode_schema(copy.deepcopy(cls.GET_SCHEMA()))
        assert record['permissions']==list(cls.SDK_PERMISSIONS)
        assert record['sdk_refs']==cls.SDK_REFS
        assert record['module']==cls.__module__.split('.')[-1]
    report=(V2/'SECURE_CONVERSION.md').read_text()
    assert 'secure-conversion-report-v1' in report and 'NOT COMPLETE' in report


def test_production_manifest_proxies_without_importing_legacy_model_modules():
    loaded=packdb.load_pack(SNAPSHOT,mount_name='custom_nodes.jack_wan_manifest_integrity')
    classes=mapping()
    assert set(loaded.node_mappings)==set(classes)
    for node_id,proxy in loaded.node_mappings.items():
        assert proxy.SECURE_NODE_PROXY
        expected=copy.deepcopy(classes[node_id].GET_SCHEMA())
        if node_id=='WanVideoPromptExtenderSelect':
            assert expected.inputs[0].remote.route=='/secure-nodes/models/text_encoders'
            expected.inputs[0].options=remote_catalogue_options(expected.inputs[0].remote.route)
        assert encode_schema(copy.deepcopy(proxy.GET_SCHEMA()))==encode_schema(expected)
        assert proxy.SDK_PERMISSIONS==classes[node_id].SDK_PERMISSIONS
        # Trusted placeholders carry source paths; no guest algorithm executes
        # in the host merely because its manifest is read.
        assert 'NODE_CLASS_MAPPINGS' not in vars(sys.modules[proxy.__module__])
    assert loaded.web_directory is None and not loaded.routes


def test_only_safe_converted_modules_are_entrypoint_reachable():
    modules=['__init__.py','secure_scalar_nodes.py','secure_tensor_nodes.py','secure_ref_nodes.py','secure_frame_nodes.py','secure_passthrough_nodes.py','secure_pose_nodes.py','secure_schedule_nodes.py','secure_silence_nodes.py','secure_ati_visual_nodes.py','secure_recam_camera_nodes.py','secure_fun_camera_nodes.py','secure_nlf_raster_nodes.py','MTV/draw_pose.py','secure_landmark_nodes.py','secure_gaussian_nodes.py','secure_portrait_payload_nodes.py','secure_recam_raster_nodes.py','secure_unianimate_input_nodes.py','secure_wanmove_raster_nodes.py','secure_arcface_raster_nodes.py','secure_noise_algorithms.py','secure_vision_algorithms.py']
    modules.append('secure_sampler_settings_nodes.py')
    modules.extend(['secure_prompt_extender_settings_nodes.py','qwen/system_prompt.py'])
    # Unregistered staged math still receives the same import/ambient audit.
    modules.append('secure_mocha_algorithms.py')
    modules.append('secure_qwenvl_nodes.py')
    modules.append('secure_bindweave_nodes.py')
    for name in modules:
        tree=ast.parse((V2/name).read_text())
        imports=[item for item in ast.walk(tree) if isinstance(item,(ast.Import,ast.ImportFrom))]
        allowed={'secure_scalar_nodes','secure_tensor_nodes','secure_ref_nodes','secure_frame_nodes','secure_passthrough_nodes','secure_pose_nodes','secure_schedule_nodes','secure_silence_nodes','secure_ati_visual_nodes','secure_recam_camera_nodes','secure_fun_camera_nodes','secure_nlf_raster_nodes','MTV.draw_pose','PIL','torchvision','secure_landmark_nodes','secure_gaussian_nodes','secure_portrait_payload_nodes','secure_recam_raster_nodes','secure_unianimate_input_nodes','secure_wanmove_raster_nodes','secure_arcface_raster_nodes','io','matplotlib','matplotlib.figure','matplotlib.backends.backend_agg','mpl_toolkits.mplot3d.art3d','torchvision.transforms','torchvision.transforms.functional','secure_noise_algorithms','comfy_api.latest','logging','torch','torch.nn.functional','math','numpy','einops','cv2','pathlib','hashlib','safetensors.torch','json','typing'}
        allowed.add('secure_sampler_settings_nodes')
        allowed.update({'secure_prompt_extender_settings_nodes','qwen.system_prompt'})
        allowed.add('secure_qwenvl_nodes')
        allowed.add('secure_bindweave_nodes')
        for item in imports:
            names=[item.module] if isinstance(item,ast.ImportFrom) else [entry.name for entry in item.names]
            assert set(names)<=allowed
        assert not any(isinstance(item,ast.Call) and isinstance(item.func,ast.Name)
            and item.func.id in ('eval','exec','open','compile','__import__') for item in ast.walk(tree))
    # Other bundled upstream algorithms still await conversion, not a bridge.
    assert 'nodes_model_loading' not in (V2/'__init__.py').read_text()


def test_candidate_exact_patch_pair_and_pristine_roundtrip(tmp_path):
    manifest,diff=packpatch.generate(SNAPSHOT)
    stem='comfyui-wanvideowrapper-x088128b'
    pair=CORPUS/'patches/comfyui-wanvideowrapper/x088128b'
    assert json.loads((pair/(stem+'.json')).read_text())==manifest
    assert (pair/(stem+'.diff')).read_text()==diff
    fresh=tmp_path/'comfyui-wanvideowrapper/x088128b'
    destination=fresh/PACK.name
    shutil.copytree(PACK,destination,ignore=shutil.ignore_patterns('v2'))
    packpatch.apply(fresh,manifest,diff)
    packpatch.validate_tree(destination/'v2',V2)
    assert json.loads((destination/'v2/secure-nodes.json').read_text())['conversion_progress']['complete'] is False
