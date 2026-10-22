"""Future actual trained UniFormer two-alias native/registered gate. NOT_RUN."""
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

import comfy
import comfy.utils
import comfy.model_management as model_management
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
IDS = ('UniFormer-SemSegPreprocessor', 'SemSegPreprocessor')
PREFIX = 'src/custom_controlnet_aux/uniformer/'


def file_digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def owning_inputs(positive):
    data = Path(os.environ['AMY_AUX_EXECUTION_RECEIPT']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == os.environ['AMY_AUX_EXECUTION_RECEIPT_SHA256']
    r = json.loads(data)
    assert r['authorized'] is True and r['execution_owner'] == 'chat_c98a0ab5c4ba'
    assert r['issuer'] == 'chat_f38536805264' and r['node_ids'] == list(IDS)
    for key in ('runtime_profile_sha256', 'capacity_receipt_sha256', 'source_selection_sha256', 'controller_cleanup_plan_sha256'):
        assert type(r[key]) is str and len(r[key]) == 64
    assert os.environ['COMFY_SECURE_SANDBOX_MODE'] == 'required'
    assert os.environ['COMFY_SECURE_SANDBOX_BACKEND'] == 'gvisor'
    assert sandbox.available() == [sandbox.KIND_GVISOR]
    assert file_digest(ROOT / 'secure-nodes.json') == r['manifest_sha256']
    assert file_digest(ROOT / '_uniformer/asset-selection.json') == r['asset_selection_sha256']
    selected = json.loads((ROOT / '_uniformer/asset-selection.json').read_text())
    assert selected['approved'] is positive
    sources = json.loads((ROOT / '_uniformer/native-sources.json').read_text())['hashes']
    assert r['native_source_hashes'] == sources
    for name, sha in sources.items():
        assert file_digest(PRISTINE / name) == sha
    if positive:
        assert r['actual_raw_metadata_and_two_load_storage_correspondence_qualified'] is True
        assert r['actual_npu_mmcv_environment_config_and_global_callback_exclusivity_qualified'] is True
        assert str(model_management.get_torch_device()) == selected['device']
        for key in ('runtime_abi_evidence_sha256', 'preimport_environment_authority_sha256',
                    'config_evaluation_authority_sha256', 'exclusive_global_callback_lifetime_sha256',
                    'device_correspondence_sha256', 'current_invocation_admission_sha256',
                    'restricted_vendor_source_evidence_sha256'):
            assert r[key] == selected[key]
        for module, sha in [('torch.serialization', 'b50f806f9aee71df8c412db95332218deca1ebcb74e694d3e5241da8eefc056c'),
                            ('torch._weights_only_unpickler', 'bc2f0fdcb5657109d066951d58864ec4227c8f65ce4d1f144015062ef097e4b2')]:
            assert file_digest(Path(importlib.import_module(module).__file__)) == sha
        # ComfyUI registers torch safe globals at import (comfy/utils.py), so "none registered" cannot hold.
        # The decode instead proves the checkpoint uses only its pinned, default-allowlisted globals (_restricted_globals.py)
        # on the pinned torch build (review follow-ups M1, L4, L5).
        from torch import _weights_only_unpickler as unpickler
        assert str(torch.__version__) == selected['torch_runtime_version']
        pinned = selected['resource']['pickle_globals']
        assert pinned == sorted(set(pinned)) and all(g in unpickler._get_allowed_globals() for g in pinned)
    pack = packdb.load_pack(Path(r['stable_snapshot_path']),
                           mount_name='custom_nodes.amy_aux_uniformer', pack_id=r['pack_id'])
    for node_id in IDS:
        assert set(pack.node_mappings[node_id].SDK_PERMISSIONS) == {'raw', 'assets', 'models.download'}
    return r, selected, sources, pack


async def dispatch(pack, node_id, values):
    cls = pack.node_mappings[node_id]
    mapped = await execution._async_map_node_over_list('amy-uniformer', node_id, cls,
                {key: [value] for key, value in values.items()}, cls.FUNCTION)
    out = (await execution.resolve_map_node_over_list_results(mapped))[0]
    return out.result, out.ui


def same_result(actual, expected):
    outputs, ui = actual
    assert type(outputs) is type(expected) is tuple and len(outputs) == 1
    image, reference = outputs[0], expected[0]
    assert type(image) is type(reference) is torch.Tensor
    assert image.dtype == reference.dtype and image.shape == reference.shape
    assert torch.equal(image, reference) and not ui


def real_native_wrapper(native):
    tree = ast.parse((PRISTINE / 'node_wrappers/uniformer.py').read_text())
    cls = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == 'Uniformer_SemSegPreprocessor')
    class AcquiredImport(ast.NodeTransformer):
        def visit_ImportFrom(self, node):
            return None
    cls = AcquiredImport().visit(cls)
    annotator = next(x for x in ast.parse((PRISTINE / 'utils.py').read_text()).body
                     if isinstance(x, ast.FunctionDef) and x.name == 'common_annotator_call')
    # Actual native code/dependencies; only original local import binding is
    # relocated. The segmentation algorithm is never replaced by a facade.
    ns = dict(torch=torch, np=np, comfy=comfy, model_management=model_management,
              UniformerSegmentor=native.UniformerSegmentor)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[annotator, cls], type_ignores=[])),
                 str(PRISTINE / 'node_wrappers/uniformer.py'), 'exec'), ns)
    return ns['Uniformer_SemSegPreprocessor']()


@contextlib.contextmanager
def pinned_native_acquisition(native, path):
    real_load = torch.load
    acquired, loads = [], []
    def download(repo, filename):
        assert (repo, filename) == ('lllyasviel/Annotators', 'upernet_global_small.pth')
        acquired.append((repo, filename))
        return str(path)
    def restricted_load(filename, *args, **kwargs):
        assert Path(filename) == path and not args
        loads.append(dict(map_location_present='map_location' in kwargs, map_location=kwargs.get('map_location')))
        kwargs['weights_only'] = True
        # Genuine restricted Torch file load; both actual raw objects and
        # native state/metadata processing remain, with no tensor projection.
        return real_load(filename, **kwargs)
    with mock.patch.object(native, 'custom_hf_download', download), mock.patch.object(torch, 'load', restricted_load):
        yield acquired, loads


def test_actual_registered_unselected_refusal_and_recovery():
    r, selected, sources, pack = owning_inputs(False)
    image = torch.ones(1, 25, 41, 3)
    async def run():
        previous = _sdk.providers.execution_backend
        backend = CloudExecutionBackend()
        _sdk.providers.execution_backend = backend
        try:
            for node_id in IDS:
                with pytest.raises(Exception, match='raw checkpoint metadata/config/vendor/device selection pending'):
                    await dispatch(pack, node_id, dict(image=image, resolution=64))
                outputs, ui = await dispatch(pack, 'AIO_Preprocessor', dict(image=image, preprocessor='none', resolution=64))
                assert len(outputs) == 1 and torch.equal(outputs[0], image)
        finally:
            try:
                await backend.guests.shutdown()
            finally:
                _sdk.providers.execution_backend = previous
    asyncio.run(run())
    Path(os.environ['AMY_AUX_RESULTS']).write_text(json.dumps(dict(registered_alias_refusals=2,
        registered_recoveries=2, guest_asset_rpc_observation=None, whole_pack_acceptance=False), indent=2) + '\n')


def test_future_actual_trained_native_registered_uniformer_two_loads_aliases_palette_and_errors():
    r, selected, sources, pack = owning_inputs(True)
    row = selected['resource'];path = Path(r['native_checkpoint_path'])
    assert path.is_file() and not path.is_symlink()
    assert path.stat().st_size == row['bytes'] and file_digest(path) == row['sha256']
    for field in ('raw_container_evidence_sha256', 'saved_storage_correspondence_sha256'):
        assert file_digest(Path(r['resource_evidence_paths'][field])) == row[field]
    first = torch.load(path, map_location='cpu', weights_only=True)
    second = torch.load(path, weights_only=True)
    assert type(first) is type(second) and list(first) == list(second) == row['raw_top_level_keys']
    assert list(first['state_dict']) == list(second['state_dict']) == row['state_keys']
    assert first['meta'] == second['meta']
    for key in first['state_dict']:
        a, b = first['state_dict'][key], second['state_dict'][key]
        assert type(a) is type(b) is torch.Tensor and a.device.type == b.device.type == 'cpu'
        assert a.dtype == b.dtype and a.shape == b.shape and torch.equal(a, b)
    assert hasattr(first['state_dict'], '_metadata') == hasattr(second['state_dict'], '_metadata')
    if hasattr(first['state_dict'], '_metadata'):
        assert first['state_dict']._metadata == second['state_dict']._metadata
    # Apply only original environment effects, under the supplied authority,
    # BEFORE native config/MMCV imports. No environment isolation is claimed.
    os.environ['NPU_DEVICE_COUNT'] = '0'
    os.environ['MMCV_WITH_OPS'] = '0'
    assert r['native_uniformer_module'] == 'custom_controlnet_aux.uniformer'
    expected_root = (PRISTINE / PREFIX).resolve()
    assert Path(r['native_uniformer_package_root']).resolve() == expected_root
    native = importlib.import_module(r['native_uniformer_module'])
    assert Path(native.__file__).resolve().parent == expected_root
    for name, module in list(sys.modules.items()):
        if name.startswith(('custom_controlnet_aux.uniformer', 'custom_mmpkg')):
            file = getattr(module, '__file__', None)
            if file and Path(file).suffix == '.py':
                original = str(Path(file).resolve().relative_to(PRISTINE))
                assert file_digest(Path(file)) == sources[original]
    oracle = real_native_wrapper(native)
    def reference(values):
        before = torch.nn.functional.adaptive_avg_pool2d
        with pinned_native_acquisition(native, path) as calls:
            answer = oracle.semantic_segmentate(**values)
        assert calls[0] == [('lllyasviel/Annotators', 'upernet_global_small.pth')]
        assert calls[1] == [dict(map_location_present=True, map_location='cpu'),
                            dict(map_location_present=False, map_location=None)]
        assert torch.nn.functional.adaptive_avg_pool2d is before
        return answer
    def fixture(dtype=torch.float32):
        record = r['trained_image_fixture'];image_path = Path(record['path'])
        assert file_digest(image_path) == record['sha256']
        pixels = np.asarray(Image.open(image_path).convert('RGB')).copy()
        assert pixels.shape[0] != pixels.shape[1]
        return torch.from_numpy(pixels.astype(np.float32) / 255).to(dtype).unsqueeze(0)
    with pinned_native_acquisition(native, path) as calls:
        detector = native.UniformerSegmentor.from_pretrained().to(selected['device'])
    assert calls[1] == [dict(map_location_present=True, map_location='cpu'), dict(map_location_present=False, map_location=None)]
    assert detector.model.CLASSES == first['meta']['CLASSES']
    assert detector.model.PALETTE == first['meta']['PALETTE']
    source = (fixture()[0].cpu().numpy() * 255).astype(np.uint8)
    before = torch.nn.functional.adaptive_avg_pool2d
    pixels = detector(source, detect_resolution=64, output_type='np')
    assert torch.nn.functional.adaptive_avg_pool2d is before
    assert np.array_equal(pixels, np.asarray(detector(source, detect_resolution=64, output_type='pil')))
    assert len(native.get_palette('ade')) == 150
    # Actual model/config/type failure, with native error unchanged.
    with pytest.raises(TypeError, match='config must be a filename or Config object'):
        native.init_segmentor(123, checkpoint=None, device='cpu')
    if selected['device'] == 'mps':
        assert r['actual_mps_runtime_and_exclusive_process_global_lifetime_qualified'] is True
        # Real malformed ndarray pipeline must fail inside _inference while
        # its actual finally restores the process-global callback.
        with pytest.raises(Exception):
            detector._inference(np.zeros((9, 13, 2), dtype=np.uint8))
        assert torch.nn.functional.adaptive_avg_pool2d is before
    del detector
    async def run():
        previous = _sdk.providers.execution_backend
        backend = CloudExecutionBackend()
        _sdk.providers.execution_backend = backend
        cases = []
        try:
            for node_id in IDS:
                for values in [dict(image=fixture().repeat(2, 1, 1, 1), resolution=64),
                               dict(image=fixture(torch.float16)),
                               dict(image=torch.cat([fixture(), torch.ones_like(fixture()[..., :1])], dim=-1).to(torch.float16), resolution=64)]:
                    image = values['image'];snapshot = image.clone()
                    same_result(await dispatch(pack, node_id, values), reference(values))
                    assert torch.equal(image, snapshot)
                    cases.append(dict(node_id=node_id, batch=image.shape[0], channels=image.shape[-1],
                                      dtype=str(image.dtype), default512='resolution' not in values))
                good = dict(image=fixture(), resolution=64)
                bad = dict(good, image=torch.ones(1, 25, 41, 2))
                with pytest.raises(AssertionError):reference(bad)
                with pytest.raises(Exception):await dispatch(pack, node_id, bad)
                same_result(await dispatch(pack, node_id, good), reference(good))
                with pytest.raises(Exception, match='workspace|projected|bounded'):
                    await dispatch(pack, node_id, dict(good, resolution=16384))
                same_result(await dispatch(pack, node_id, good), reference(good))
            return cases
        finally:
            try:
                await backend.guests.shutdown()
            finally:
                _sdk.providers.execution_backend = previous
    cases = asyncio.run(run())
    Path(os.environ['AMY_AUX_RESULTS']).write_text(json.dumps(dict(native_registered_cases=cases, recoveries=4,
        native_first_cpu_then_second_no_map_load_order=True, raw_classes_palette_preserved=True,
        mps_actual_branch_restoration=selected['device']=='mps', actual_mps_fallback_triggered=None,
        registered_two_raw_load_order_observation=None, registered_model_metadata_readback=None,
        actual_raw_container_corruption_and_missing_key_cases=None, current_generation_device_cold_warm=None,
        whole_pack_acceptance=False), indent=2) + '\n')
