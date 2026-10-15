"""Future actual native/registered DWpose+AnimalPose gate; NOT run in authoring.

Positive comparisons remain blocked by the explicit current-realm generation
and ONNX byte-constructor source seams. Receipt fields do not open those seams.
"""
import ast
import asyncio
import contextlib
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
from unittest import mock

import numpy as np
import pytest
import torch
from PIL import Image
import comfy
import comfy.model_management as model_management
import execution
from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb
from comfy_secure_nodes.execution import CloudExecutionBackend
from comfy_secure_nodes.transport import sandbox

ROOT = Path(__file__).resolve().parents[1]
IDS = ('DWPreprocessor', 'AnimalPosePreprocessor')
PRISTINE = Path(os.environ['AMY_AUX_PRISTINE'])


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
    assert receipt['node_ids'] == list(IDS)
    for name in ('source_selection_sha256', 'runtime_profile_sha256', 'capacity_receipt_sha256',
                 'controller_cleanup_plan_sha256', 'source_generation_binding_sha256'):
        assert type(receipt[name]) is str and len(receipt[name]) == 64
    assert os.environ['COMFY_SECURE_SANDBOX_MODE'] == 'required'
    assert os.environ['COMFY_SECURE_SANDBOX_BACKEND'] == 'gvisor'
    assert sandbox.available() == [sandbox.KIND_GVISOR]
    assert file_digest(ROOT / 'secure-nodes.json') == receipt['manifest_sha256']
    selection_path = ROOT / '_dwpose/asset-selection.json'
    assert file_digest(selection_path) == receipt['asset_selection_sha256']
    selected = json.loads(selection_path.read_text())
    sources = json.loads((ROOT / '_dwpose/native-sources.json').read_text())['hashes']
    assert receipt['native_source_hashes'] == sources
    for name, digest in sources.items():
        assert file_digest(PRISTINE / name) == digest
    assert selected['approved'] is positive
    if positive:
        # Source closure and actual trusted generation transport must have
        # happened in a NEW descendant; no false field bypasses this packet's
        # unconditional explicit current-generation refusal.
        assert receipt['managed_current_realm_generation_source_implemented'] is True
        assert receipt['actual_selected_vendor_abi_and_serialized_code_qualified'] is True
        assert receipt['native_cache_and_startup_environment_qualified'] is True
        assert str(model_management.get_torch_device()) == selected['torchscript_device']
        assert receipt['complete_selected_onnx_constructor_contract_qualified'] is True
    pack = packdb.load_pack(Path(receipt['stable_snapshot_path']),
                           mount_name='custom_nodes.amy_aux_dwpose', pack_id=receipt['pack_id'])
    for node_id in IDS:
        assert set(pack.node_mappings[node_id].SDK_PERMISSIONS) == {'raw', 'assets'}
    return receipt, selected, pack


async def dispatch(pack, node_id, values):
    cls = pack.node_mappings[node_id]
    returns = await execution._async_map_node_over_list('amy-dwpose', node_id, cls,
                         {k: [v] for k, v in values.items()}, cls.FUNCTION)
    result = (await execution.resolve_map_node_over_list_results(returns))[0]
    return result.result, result.ui


def same_result(actual, expected):
    outputs, ui = actual
    assert type(outputs) is tuple and len(outputs) == 2
    image, poses = outputs
    expected_image, expected_poses = expected['result']
    assert type(image) is type(expected_image) is torch.Tensor
    assert image.dtype == expected_image.dtype and image.shape == expected_image.shape
    assert torch.equal(image, expected_image)
    assert type(poses) is type(expected_poses) is list and poses == expected_poses
    # Compare raw indent4 JSON and serialized list ordering, not a normalized
    # approximation. Both declared output sockets and actual UI are required.
    assert type(ui) is dict and ui == expected['ui']
    assert ui['openpose_json'] == [json.dumps(poses, indent=4)]


def real_native_wrappers(native):
    original = (PRISTINE / 'node_wrappers/dwpose.py').read_text()
    utils = (PRISTINE / 'utils.py').read_text()
    tree = ast.parse(utils)
    annotator = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == 'common_annotator_call')
    classes = [x for x in ast.parse(original).body if isinstance(x, ast.ClassDef)]
    ns = dict(np=np, torch=torch, comfy=comfy, model_management=model_management, json=json,
              DWPOSE_MODEL_NAME='yzd-v/DWPose', DwposeDetector=native.DwposeDetector,
              AnimalposeDetector=native.AnimalposeDetector)
    # Exact original wrapper classes and actual native common annotator; only
    # dependency import origin changes. No dummy detector/SDK/RPC result.
    exec(compile(ast.Module(body=[annotator, *classes], type_ignores=[]),
                 str(PRISTINE / 'node_wrappers/dwpose.py'), 'exec'), ns)
    return {'DWPreprocessor': ns['DWPose_Preprocessor'](),
            'AnimalPosePreprocessor': ns['AnimalPose_Preprocessor']()}


def verify_native_resources(selected, receipt):
    resources = {}
    for r in selected['resources']:
        if r['approved'] is not True:
            continue
        key = r['source_repo'] + '/' + r['source_filename']
        path = Path(receipt['native_asset_paths'][key])
        assert path.is_file() and not path.is_symlink()
        assert path.stat().st_size == r['bytes'] and file_digest(path) == r['sha256']
        assert r['serialized_code_provenance_sha256'] in receipt['approved_serialized_code_provenance_hashes']
        resources[(r['source_repo'], r['source_filename'])] = path
    assert resources
    return resources


@contextlib.contextmanager
def pinned_native_acquisition(native, resources):
    def resolved(repo, filename):
        if filename is None:
            # Native Animal acquisition path's None filename TypeError,
            # before download. DW skips None detector acquisition entirely.
            Path('native-reference-shape').joinpath(filename)
        return str(resources[(repo, filename)])
    with mock.patch.object(native, 'custom_hf_download', resolved):
        yield


def test_genuine_registered_unselected_refusal_then_same_guest_recovery():
    receipt, selected, pack = owning_inputs(False)
    image = torch.linspace(0, 1, 25 * 41 * 3).reshape(1, 25, 41, 3)
    async def run():
        previous = _sdk.providers.execution_backend
        backend = CloudExecutionBackend()
        _sdk.providers.execution_backend = backend
        try:
            for node_id in IDS:
                with pytest.raises(Exception, match='resources/runtime remain unselected'):
                    await dispatch(pack, node_id, dict(image=image, resolution=64))
                result, ui = await dispatch(pack, 'AIO_Preprocessor',
                             dict(image=image, resolution=64, preprocessor='none'))
                assert len(result) == 1 and torch.equal(result[0], image)
            return dict(unselected_registered_refusals=2, registered_recoveries=2,
                        asset_or_engine_calls_expected=0, actual_asset_call_observation=None)
        finally:
            try:
                await backend.guests.shutdown()
            finally:
                _sdk.providers.execution_backend = previous
    result = asyncio.run(run())
    Path(os.environ['AMY_AUX_RESULTS']).write_text(json.dumps(dict(result,
        phase='actual-unselected-refusal', whole_pack_acceptance=False), indent=2) + '\n')


def test_future_trained_native_registered_choices_batch_json_errors_and_cache():
    receipt, selected, pack = owning_inputs(True)
    resources = verify_native_resources(selected, receipt)
    native_name = 'custom_controlnet_aux.dwpose'
    assert receipt['native_dwpose_module'] == native_name
    expected_root = (PRISTINE / 'src/custom_controlnet_aux/dwpose').resolve()
    assert Path(receipt['native_dwpose_package_root']).resolve() == expected_root
    native = importlib.import_module(native_name)
    assert Path(native.__file__).resolve().parent == expected_root
    sources = json.loads((ROOT / '_dwpose/native-sources.json').read_text())['hashes']
    for name, module in list(sys.modules.items()):
        if name == native_name or name.startswith(native_name + '.'):
            path = getattr(module, '__file__', None)
            if path and Path(path).suffix == '.py':
                key = 'src/custom_controlnet_aux/dwpose/' + str(Path(path).resolve().relative_to(expected_root))
                assert file_digest(Path(path)) == sources[key]
    oracles = real_native_wrappers(native)
    schema = json.loads((ROOT / '_schemas.json').read_text())
    def defaults(node_id):
        answer = {}
        for fields in schema[node_id]['inputs'].values():
            for key, spec in fields.items():
                if key != 'image':
                    answer[key] = spec[1]['default'] if len(spec) > 1 and 'default' in spec[1] else spec[0][0]
        return answer
    def expected(node_id, values):
        with pinned_native_acquisition(native, resources):
            return oracles[node_id].estimate_pose(**values)
    async def run():
        previous = _sdk.providers.execution_backend
        backend = CloudExecutionBackend()
        _sdk.providers.execution_backend = backend
        cases = []
        try:
            # Schema defaults differ from direct Python method defaults.
            for node_id in IDS:
                for default_kind, parameters in [('schema', defaults(node_id)), ('direct', {})]:
                    image = torch.linspace(0, 1, 2 * 25 * 41 * 3).reshape(2, 25, 41, 3)
                    before = image.clone()
                    values = dict(image=image, **parameters)
                    same_result(await dispatch(pack, node_id, values), expected(node_id, values))
                    assert torch.equal(image, before)
                    cases.append(dict(node_id=node_id, defaults=default_kind, batch=2))
            # Genuine retained, owner-bound multi-person/multi-animal frames,
            # not a fabricated detector response or a synthetic empty image.
            for node_id in IDS:
                fixture = receipt['trained_image_fixtures'][node_id]
                path = Path(fixture['path'])
                assert file_digest(path) == fixture['sha256']
                pixels = np.asarray(Image.open(path).convert('RGB')).copy()
                image = torch.from_numpy(pixels.astype(np.float32) / 255).unsqueeze(0).repeat(2, 1, 1, 1)
                values = dict(image=image, resolution=64, **receipt['torchscript_recovery_choices'][node_id])
                reference = expected(node_id, values)
                assert len(reference['result'][1]) == 2
                kind = 'people' if node_id == 'DWPreprocessor' else 'animals'
                assert all(len(frame[kind]) >= 2 for frame in reference['result'][1])
                same_result(await dispatch(pack, node_id, values), reference)
                cases.append(dict(node_id=node_id, trained_fixture_sha256=fixture['sha256'], multi_subject_batch=2))
            # Owner must select every exact native repo/format combination.
            # None Animal is tested as an ERROR, never a supported inference.
            choices = receipt['qualified_native_choices']
            assert choices and {c['node_id'] for c in choices} == set(IDS)
            coverage = {node_id: {'bbox': set(), 'pose': set()} for node_id in IDS}
            for choice in choices:
                node_id = choice['node_id']
                image = torch.linspace(0, 1, 41 * 25 * 3).reshape(1, 41, 25, 3)
                values = dict(image=image, resolution=64, bbox_detector=choice['bbox_detector'],
                              pose_estimator=choice['pose_estimator'])
                same_result(await dispatch(pack, node_id, values), expected(node_id, values))
                coverage[node_id]['bbox'].add(choice['bbox_detector'])
                coverage[node_id]['pose'].add(choice['pose_estimator'])
                cases.append(dict(node_id=node_id, bbox=choice['bbox_detector'], pose=choice['pose_estimator']))
            for node_id in IDS:
                specs = schema[node_id]['inputs']['optional']
                assert coverage[node_id]['bbox'] == set(specs['bbox_detector'][0]) - ({'None'} if node_id == 'AnimalPosePreprocessor' else set())
                assert coverage[node_id]['pose'] == set(specs['pose_estimator'][0])
            # All8 body/hand/face filter choices + source xinsr stick scaling.
            for body in ('enable', 'disable'):
                for hand in ('enable', 'disable'):
                    for face in ('enable', 'disable'):
                        image = torch.ones(1, 25, 41, 3)
                        values = dict(image=image, resolution=64, **receipt['dwpose_torchscript_choice'],
                                      detect_body=body, detect_hand=hand, detect_face=face,
                                      scale_stick_for_xinsr_cn='enable')
                        same_result(await dispatch(pack, 'DWPreprocessor', values), expected('DWPreprocessor', values))
                        cases.append(dict(flags=[body, hand, face], xinsr=True))
            recoveries = 0
            for node_id in IDS:
                good = dict(image=torch.ones(1, 25, 41, 3), resolution=64,
                            **receipt['torchscript_recovery_choices'][node_id])
                invalid = dict(good, image=torch.ones(1, 25, 41, 2))
                with pytest.raises(AssertionError):
                    expected(node_id, invalid)
                with pytest.raises(Exception):
                    await dispatch(pack, node_id, invalid)
                same_result(await dispatch(pack, node_id, good), expected(node_id, good));recoveries += 1
                with pytest.raises(Exception, match='projected|bounded|workspace'):
                    await dispatch(pack, node_id, dict(good, resolution=16384))
                same_result(await dispatch(pack, node_id, good), expected(node_id, good));recoveries += 1
                # Real repeated same selection enters original cache branch;
                # no replacement or invented correctness for its filename bug.
                same_result(await dispatch(pack, node_id, good), expected(node_id, good))
            animal = dict(image=torch.ones(1, 25, 41, 3), resolution=64,
                          bbox_detector='None', pose_estimator='rtmpose-m_ap10k_256_bs5.torchscript.pt')
            with pytest.raises(TypeError):expected('AnimalPosePreprocessor', animal)
            with pytest.raises(Exception):await dispatch(pack, 'AnimalPosePreprocessor', animal)
            good = dict(image=animal['image'], resolution=64, **receipt['torchscript_recovery_choices']['AnimalPosePreprocessor'])
            same_result(await dispatch(pack, 'AnimalPosePreprocessor', good), expected('AnimalPosePreprocessor', good));recoveries += 1
            return cases, recoveries
        finally:
            try:
                await backend.guests.shutdown()
            finally:
                _sdk.providers.execution_backend = previous
    cases, recoveries = asyncio.run(run())
    Path(os.environ['AMY_AUX_RESULTS']).write_text(json.dumps(dict(native_registered_cases=cases,
        recoveries=recoveries, exact_image_pose_json_and_indent4_ui=True, cache_alias_typo_source_preserved=True,
        cache_object_alias_correspondence=None, actual_engine_exception_bug_cases=None,
        cross_realm_current_generation_proof=None, caller_device_portability=None,
        cache_cold_warm_acceptance=None, whole_pack_acceptance=False), indent=2) + '\n')
