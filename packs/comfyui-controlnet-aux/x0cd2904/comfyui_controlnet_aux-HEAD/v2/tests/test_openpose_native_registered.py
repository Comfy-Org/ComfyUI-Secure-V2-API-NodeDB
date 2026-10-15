"""Future genuine trained OpenPose native/registered gate. NOT_RUN in authoring."""
import ast
import asyncio
import contextlib
import hashlib
import importlib
import itertools
import json
import os
from pathlib import Path
import sys
from unittest import mock

import comfy
import comfy.model_management as model_management
import comfy.utils
import execution
import numpy as np
import pytest
import torch
from PIL import Image
from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb
from comfy_secure_nodes.execution import CloudExecutionBackend
from comfy_secure_nodes.transport import sandbox

ROOT = Path(__file__).resolve().parents[1]
PRISTINE = Path(os.environ['AMY_AUX_PRISTINE'])
ID = 'OpenposePreprocessor'
PREFIX = 'src/custom_controlnet_aux/open_pose/'


def file_digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def owning_inputs(positive):
    data = Path(os.environ['AMY_AUX_EXECUTION_RECEIPT']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == os.environ['AMY_AUX_EXECUTION_RECEIPT_SHA256']
    receipt = json.loads(data)
    assert receipt['authorized'] is True and receipt['execution_owner'] == 'chat_f38536805264'
    assert receipt['node_id'] == ID
    for key in ('runtime_profile_sha256', 'capacity_receipt_sha256', 'source_selection_sha256', 'controller_cleanup_plan_sha256'):
        assert type(receipt[key]) is str and len(receipt[key]) == 64
    assert os.environ['COMFY_SECURE_SANDBOX_MODE'] == 'required'
    assert os.environ['COMFY_SECURE_SANDBOX_BACKEND'] == 'gvisor'
    assert sandbox.available() == [sandbox.KIND_GVISOR]
    assert file_digest(ROOT / 'secure-nodes.json') == receipt['manifest_sha256']
    assert file_digest(ROOT / '_openpose/asset-selection.json') == receipt['asset_selection_sha256']
    selected = json.loads((ROOT / '_openpose/asset-selection.json').read_text())
    assert selected['approved'] is positive
    sources = json.loads((ROOT / '_openpose/native-sources.json').read_text())['hashes']
    assert receipt['native_source_hashes'] == sources
    for name, digest in sources.items():
        assert file_digest(PRISTINE / name) == digest
    if positive:
        assert receipt['actual_three_restricted_raw_mappings_qualified'] is True
        assert receipt['native_no_map_location_storage_correspondence'] is True
        assert receipt['native_preimport_context_and_constructor_default_placement_qualified'] is True
        assert str(model_management.get_torch_device()) == selected['device']
        assert file_digest(Path(comfy.utils.__file__)) == selected['published_loader_source_sha256']
    pack = packdb.load_pack(Path(receipt['stable_snapshot_path']),
                           mount_name='custom_nodes.amy_aux_openpose', pack_id=receipt['pack_id'])
    assert set(pack.node_mappings[ID].SDK_PERMISSIONS) == {'raw', 'assets'}
    return receipt, selected, sources, pack


async def dispatch(pack, node_id, values):
    cls = pack.node_mappings[node_id]
    mapped = await execution._async_map_node_over_list('amy-openpose', node_id, cls,
                {k: [v] for k, v in values.items()}, cls.FUNCTION)
    result = (await execution.resolve_map_node_over_list_results(mapped))[0]
    return result.result, result.ui


def same_result(actual, expected):
    outputs, ui = actual
    assert type(outputs) is tuple and len(outputs) == 2
    image, poses = outputs
    ref_image, ref_poses = expected['result']
    assert type(image) is type(ref_image) is torch.Tensor and image.dtype == ref_image.dtype
    assert image.shape == ref_image.shape and torch.equal(image, ref_image)
    assert type(poses) is type(ref_poses) is list and poses == ref_poses
    assert type(ui) is dict and ui == expected['ui']
    assert ui['openpose_json'] == [json.dumps(poses, indent=4)]


def real_native_wrapper(native):
    tree = ast.parse((PRISTINE / 'node_wrappers/openpose.py').read_text())
    cls = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == 'OpenPose_Preprocessor')
    class AcquiredImport(ast.NodeTransformer):
        def visit_ImportFrom(self, node):
            return None
    cls = AcquiredImport().visit(cls)
    annotator = next(x for x in ast.parse((PRISTINE / 'utils.py').read_text()).body
                     if isinstance(x, ast.FunctionDef) and x.name == 'common_annotator_call')
    ns = dict(torch=torch, np=np, comfy=comfy, json=json, model_management=model_management,
              OpenposeDetector=native.OpenposeDetector)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[annotator, cls], type_ignores=[])),
                 str(PRISTINE / 'node_wrappers/openpose.py'), 'exec'), ns)
    return ns['OpenPose_Preprocessor']()


def verify_resources(selected, receipt):
    paths = {}
    for r in selected['resources']:
        if r['approved'] is not True:
            continue
        key = '/'.join([r['source_repo'], r['source_subfolder'], r['source_filename']])
        path = Path(receipt['native_checkpoint_paths'][key])
        assert path.is_file() and not path.is_symlink()
        assert path.stat().st_size == r['bytes'] and file_digest(path) == r['sha256']
        # Preserve original no-map_location semantics. Only restricted
        # weights_only is supplied; there is no forced CPU oracle fallback.
        raw = torch.load(path, weights_only=True)
        assert isinstance(raw, dict) and list(raw) == r['raw_top_level_keys'] and 'state_dict' not in raw
        proof_path = Path(receipt['restricted_shape_evidence_paths'][key])
        assert file_digest(proof_path) == r['restricted_shape_evidence_sha256']
        proof = json.loads(proof_path.read_text())
        assert proof['actual_inspection'] is True and proof['restricted_weights_only'] is True
        assert proof['asset_sha256'] == r['sha256'] and proof['raw_top_level_keys'] == list(raw)
        assert file_digest(Path(receipt['native_storage_correspondence_paths'][key])) == r['native_storage_correspondence_sha256']
        actual = comfy.utils.load_torch_file(str(path), safe_load=True)
        assert isinstance(actual, dict) and list(actual) == list(raw)
        if r['kind'] == 'face':
            assert not hasattr(raw, '_metadata') and r['raw_metadata_policy'] == 'absent'
        else:
            assert r['raw_metadata_policy'] == 'native-transfer-discards'
        total = 0
        for name, value in raw.items():
            assert type(value) is type(actual[name]) is torch.Tensor
            assert value.device.type == actual[name].device.type == 'cpu'
            assert value.dtype == actual[name].dtype and value.shape == actual[name].shape
            assert torch.equal(value, actual[name])
            total += value.numel() * value.element_size()
        assert total == r['tensor_bytes']
        paths[(r['source_repo'], r['source_subfolder'], r['source_filename'])] = path
    return paths


@contextlib.contextmanager
def pinned_native_acquisition(native, paths):
    real_load = torch.load
    acquired, loaded = [], []
    def download(repo, filename, subfolder=''):
        key = (repo, subfolder, filename)
        acquired.append(key)
        return str(paths[key])
    def restricted_load(path, *args, **kwargs):
        assert not args and Path(path) in paths.values()
        assert 'map_location' not in kwargs
        kwargs['weights_only'] = True
        loaded.append(next(k[2] for k, actual_path in paths.items() if Path(path) == actual_path))
        return real_load(path, **kwargs)
    with mock.patch.object(native, 'custom_hf_download', download), mock.patch.object(torch, 'load', restricted_load):
        yield acquired, loaded


def test_actual_registered_unselected_refusal_and_recovery():
    receipt, selected, sources, pack = owning_inputs(False)
    image = torch.ones(1, 25, 41, 3)
    async def run():
        previous = _sdk.providers.execution_backend
        backend = CloudExecutionBackend()
        _sdk.providers.execution_backend = backend
        try:
            with pytest.raises(Exception, match='three raw checkpoints/runtime/device selection pending'):
                await dispatch(pack, ID, dict(image=image, resolution=64))
            outputs, ui = await dispatch(pack, 'AIO_Preprocessor', dict(image=image, preprocessor='none', resolution=64))
            assert len(outputs) == 1 and torch.equal(outputs[0], image)
        finally:
            try:
                await backend.guests.shutdown()
            finally:
                _sdk.providers.execution_backend = previous
    asyncio.run(run())
    Path(os.environ['AMY_AUX_RESULTS']).write_text(json.dumps(dict(registered_unselected_refusal=True,
        registered_recovery=True, actual_asset_rpc_observation=None, whole_pack_acceptance=False), indent=2) + '\n')


def test_future_actual_trained_native_registered_openpose_three_models_flags_and_errors():
    receipt, selected, sources, pack = owning_inputs(True)
    paths = verify_resources(selected, receipt)
    expected_root = (PRISTINE / PREFIX).resolve()
    assert receipt['native_openpose_module'] == 'custom_controlnet_aux.open_pose'
    assert Path(receipt['native_openpose_package_root']).resolve() == expected_root
    native = importlib.import_module(receipt['native_openpose_module'])
    assert Path(native.__file__).resolve().parent == expected_root
    for name, module in list(sys.modules.items()):
        if name == receipt['native_openpose_module'] or name.startswith(receipt['native_openpose_module'] + '.'):
            path = getattr(module, '__file__', None)
            if path and Path(path).suffix == '.py':
                source = PREFIX + str(Path(path).resolve().relative_to(expected_root))
                assert file_digest(Path(path)) == sources[source]
    oracle = real_native_wrapper(native)
    def reference(values):
        with pinned_native_acquisition(native, paths) as calls:
            answer = oracle.estimate_pose(**values)
        assert calls[0] == [('lllyasviel/Annotators', '', f) for f in ('body_pose_model.pth', 'hand_pose_model.pth', 'facenet.pth')]
        assert calls[1] == ['body_pose_model.pth', 'hand_pose_model.pth', 'facenet.pth']
        return answer
    def fixture(key, dtype=torch.float32):
        record = receipt['trained_image_fixtures'][key]
        path = Path(record['path']);assert file_digest(path) == record['sha256']
        pixels = np.asarray(Image.open(path).convert('RGB')).copy()
        return torch.from_numpy(pixels.astype(np.float32) / 255).to(dtype).unsqueeze(0)
    async def run():
        previous = _sdk.providers.execution_backend
        backend = CloudExecutionBackend()
        _sdk.providers.execution_backend = backend
        cases = []
        try:
            for key, persons in [('multiple-persons', True), ('no-person', False)]:
                image = fixture(key).repeat(2, 1, 1, 1);before = image.clone()
                values = dict(image=image, resolution=64)
                ref = reference(values)
                assert len(ref['result'][1]) == 2
                assert all((len(frame['people']) >= 2 if persons else len(frame['people']) == 0) for frame in ref['result'][1])
                same_result(await dispatch(pack, ID, values), ref)
                assert torch.equal(image, before)
                cases.append(dict(trained_fixture=key, batch=2))
            image = fixture('multiple-persons')
            for hand, body, face in itertools.product(('enable', 'disable'), repeat=3):
                values = dict(image=image, resolution=64, detect_hand=hand, detect_body=body, detect_face=face,
                              scale_stick_for_xinsr_cn='enable')
                ref = reference(values)
                # Body inference/keypoints are unconditional even if drawing
                # body is disabled. OpenPose does not use DWpose output filter.
                assert len(ref['result'][1][0]['people']) >= 2
                same_result(await dispatch(pack, ID, values), ref)
                if hand == body == face == 'disable':
                    assert torch.count_nonzero(ref['result'][0]) == 0
                cases.append(dict(flags=[hand, body, face], xinsr=True))
            # Default source resolution512 and flag defaults remain genuine.
            values = dict(image=fixture('no-person', torch.float16))
            same_result(await dispatch(pack, ID, values), reference(values))
            cases.append(dict(default_resolution=True, input_dtype='float16'))
            rgba = torch.cat([image, torch.ones_like(image[..., :1])], dim=-1).to(torch.float16)
            values = dict(image=rgba, resolution=64)
            same_result(await dispatch(pack, ID, values), reference(values))
            cases.append(dict(input='RGBA-float16'))
            good = dict(image=fixture('no-person'), resolution=64)
            bad = dict(good, image=torch.ones(1, 25, 41, 2))
            with pytest.raises(AssertionError):reference(bad)
            with pytest.raises(Exception):await dispatch(pack, ID, bad)
            same_result(await dispatch(pack, ID, good), reference(good))
            with pytest.raises(Exception, match='workspace|projected|bounded'):
                await dispatch(pack, ID, dict(good, resolution=16384))
            same_result(await dispatch(pack, ID, good), reference(good))
            return cases
        finally:
            try:
                await backend.guests.shutdown()
            finally:
                _sdk.providers.execution_backend = previous
    cases = asyncio.run(run())
    Path(os.environ['AMY_AUX_RESULTS']).write_text(json.dumps(dict(native_registered_cases=cases,
        recoveries=2, native_three_load_order_even_disabled=True, registered_three_load_call_observation=None,
        exact_image_pose_keypoint_and_indent4_ui=True, actual_constructor_missing_key_errors=None,
        detector_pil_image_json_error_and_hand_and_face=None, actual_alternate_controlnet_subfolder=None,
        cold_warm_cache_or_device_portability=None, whole_pack_acceptance=False), indent=2) + '\n')
