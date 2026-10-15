"""Genuine future trained DensePose native/registered gate; authoring NOT_RUN."""
import ast
import asyncio
import contextlib
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import sys
from unittest import mock

import comfy
import comfy.model_management as model_management
import execution
import numpy as np
import pytest
import torch
import torchvision
from PIL import Image
from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb
from comfy_secure_nodes.execution import CloudExecutionBackend
from comfy_secure_nodes.transport import sandbox

ROOT = Path(__file__).resolve().parents[1]
PRISTINE = Path(os.environ['AMY_AUX_PRISTINE'])
ID = 'DensePosePreprocessor'
PREFIX = 'src/custom_controlnet_aux/densepose/'
REPO = 'LayerNorm/DensePose-TorchScript-with-hint-image'
FILES = ('densepose_r50_fpn_dl.torchscript', 'densepose_r101_fpn_dl.torchscript')


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
    assert r['issuer'] == 'chat_f38536805264' and r['node_id'] == ID
    for key in ('runtime_profile_sha256', 'capacity_receipt_sha256', 'source_selection_sha256',
                'controller_cleanup_plan_sha256', 'actual_operator_abi_evidence_sha256'):
        assert type(r[key]) is str and len(r[key]) == 64
    assert os.environ['COMFY_SECURE_SANDBOX_MODE'] == 'required'
    assert os.environ['COMFY_SECURE_SANDBOX_BACKEND'] == 'gvisor'
    assert sandbox.available() == [sandbox.KIND_GVISOR]
    assert file_digest(ROOT / 'secure-nodes.json') == r['manifest_sha256']
    assert file_digest(ROOT / '_densepose/asset-selection.json') == r['asset_selection_sha256']
    selected = json.loads((ROOT / '_densepose/asset-selection.json').read_text())
    assert selected['approved'] is positive
    sources = json.loads((ROOT / '_densepose/native-sources.json').read_text())['hashes']
    assert r['native_source_hashes'] == sources
    for name, sha in sources.items():
        assert file_digest(PRISTINE / name) == sha
    if positive:
        assert r['actual_executable_code_and_torchvision_nms_approved'] is True
        assert r['actual_cpu_jit_then_native_to_placement_qualified'] is True
        assert str(model_management.get_torch_device()) == selected['device']
        assert selected['runtime_abi_evidence_sha256'] == r['actual_operator_abi_evidence_sha256']
        serialization = importlib.import_module('torch.jit._serialization')
        assert file_digest(Path(serialization.__file__)) == r['actual_jit_serialization_source_sha256']
        assert r['actual_jit_serialization_source_sha256'] == '6193834f0c6f313eb1f9554e8997c480b4781ee27df78cf609141948bc8600f6'
        # Real eager torchvision import must register the actual operator.
        assert hasattr(torch.ops.torchvision, 'nms')
    pack = packdb.load_pack(Path(r['stable_snapshot_path']),
                           mount_name='custom_nodes.amy_aux_densepose', pack_id=r['pack_id'])
    assert set(pack.node_mappings[ID].SDK_PERMISSIONS) == {'raw', 'assets'}
    return r, selected, sources, pack


async def dispatch(pack, node_id, values):
    cls = pack.node_mappings[node_id]
    mapped = await execution._async_map_node_over_list('amy-densepose', node_id, cls,
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
    tree = ast.parse((PRISTINE / 'node_wrappers/densepose.py').read_text())
    cls = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == 'DensePose_Preprocessor')
    class AcquiredImport(ast.NodeTransformer):
        def visit_ImportFrom(self, node):
            return None
    cls = AcquiredImport().visit(cls)
    annotator = next(x for x in ast.parse((PRISTINE / 'utils.py').read_text()).body
                     if isinstance(x, ast.FunctionDef) and x.name == 'common_annotator_call')
    # These are actual pristine bodies and genuine native dependencies; only
    # package-local import binding is relocated. No replacement algorithm.
    ns = dict(torch=torch, np=np, comfy=comfy, model_management=model_management,
              DenseposeDetector=native.DenseposeDetector)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[annotator, cls], type_ignores=[])),
                 str(PRISTINE / 'node_wrappers/densepose.py'), 'exec'), ns)
    return ns['DensePose_Preprocessor']()


def verify_resources(selected, receipt):
    paths = {}
    for row in selected['resources']:
        assert row['approved'] is True and row['executable_code_approved'] is True
        assert row['source_repo'] == REPO and row['source_filename'] in FILES
        filename = row['source_filename']
        path = Path(receipt['native_archive_paths'][filename])
        assert path.is_file() and not path.is_symlink()
        assert path.stat().st_size == row['bytes'] and file_digest(path) == row['sha256']
        for key in ('code_provenance_sha256', 'operator_abi_evidence_sha256', 'sealed_catalogue_evidence_sha256'):
            proof = Path(receipt['resource_evidence_paths'][filename][key])
            assert file_digest(proof) == row[key]
        paths[(REPO, filename)] = path
    assert set(paths) == {(REPO, name) for name in FILES}
    return paths


@contextlib.contextmanager
def pinned_native_acquisition(native, paths):
    real_load = torch.jit.load
    acquired, loaded = [], []
    def download(repo, filename):
        acquired.append((repo, filename))
        return str(paths[(repo, filename)])
    def load(path, *args, **kwargs):
        assert not args and kwargs == {'map_location': 'cpu'}
        assert Path(path) in paths.values()
        loaded.append((str(path), 'cpu'))
        return real_load(path, **kwargs)
    with mock.patch.object(native, 'custom_hf_download', download), mock.patch.object(torch.jit, 'load', load):
        yield acquired, loaded


def test_actual_registered_unselected_refusal_and_recovery():
    receipt, selected, sources, pack = owning_inputs(False)
    image = torch.ones(1, 25, 41, 3)
    async def run():
        previous = _sdk.providers.execution_backend
        backend = CloudExecutionBackend()
        _sdk.providers.execution_backend = backend
        try:
            with pytest.raises(Exception, match='executable archive/runtime/operator/device selection pending'):
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
        registered_recovery=True, guest_asset_rpc_observation=None, whole_pack_acceptance=False), indent=2) + '\n')


def test_future_actual_trained_native_registered_densepose_archives_colormaps_and_errors():
    receipt, selected, sources, pack = owning_inputs(True)
    paths = verify_resources(selected, receipt)
    expected_root = (PRISTINE / PREFIX).resolve()
    assert receipt['native_densepose_module'] == 'custom_controlnet_aux.densepose'
    assert Path(receipt['native_densepose_package_root']).resolve() == expected_root
    native = importlib.import_module(receipt['native_densepose_module'])
    assert Path(native.__file__).resolve().parent == expected_root
    for name, module in list(sys.modules.items()):
        if name == receipt['native_densepose_module'] or name.startswith(receipt['native_densepose_module'] + '.'):
            path = getattr(module, '__file__', None)
            if path and Path(path).suffix == '.py':
                source = PREFIX + str(Path(path).resolve().relative_to(expected_root))
                assert file_digest(Path(path)) == sources[source]
    oracle = real_native_wrapper(native)
    def reference(values):
        filename = values.get('model', FILES[0])
        with pinned_native_acquisition(native, paths) as calls:
            answer = oracle.execute(**values)
        assert calls[0] == [(REPO, filename)]
        assert calls[1] == [(str(paths[(REPO, filename)]), 'cpu')]
        return answer
    def fixture(key, dtype=torch.float32):
        row = receipt['trained_image_fixtures'][key]
        path = Path(row['path']);assert file_digest(path) == row['sha256']
        pixels = np.asarray(Image.open(path).convert('RGB')).copy()
        return torch.from_numpy(pixels.astype(np.float32) / 255).to(dtype).unsqueeze(0)
    # Actual file versus supported BytesIO JIT constructor, CPU->native device
    # and genuine five-output inference. Never replace inference/model values.
    constructor_cases = []
    for filename in FILES:
        with pinned_native_acquisition(native, paths):
            detector = native.DenseposeDetector.from_pretrained(filename=filename).to(selected['device'])
        payload = paths[(REPO, filename)].read_bytes()
        byte_model = torch.jit.load(io.BytesIO(payload), map_location='cpu')
        byte_detector = native.DenseposeDetector(byte_model).to(selected['device'])
        for key, persons in [('people', True), ('no-person', False)]:
            source = (fixture(key)[0].cpu().numpy() * 255).astype(np.uint8)
            prepared, _ = native.resize_image_with_pad(source, 64, 'INTER_CUBIC')
            tensor = torch.from_numpy(prepared).to(selected['device']).permute(2, 0, 1)
            raw = detector.dense_pose_estimation(tensor)
            actual = byte_detector.dense_pose_estimation(tensor)
            assert len(raw) == len(actual) == 5
            assert (len(raw[0]) > 0) is persons
            for left, right in zip(raw, actual):
                assert type(left) is type(right) is torch.Tensor and left.dtype == right.dtype
                assert left.shape == right.shape and torch.equal(left, right)
            for cmap in ('viridis', 'parula'):
                expected = detector(source, detect_resolution=64, output_type='np', cmap=cmap)
                assert np.array_equal(expected, byte_detector(source, detect_resolution=64, output_type='np', cmap=cmap))
                assert np.array_equal(expected, np.asarray(detector(source, detect_resolution=64, output_type='pil', cmap=cmap)))
                if not persons:
                    color = np.array([68, 1, 84] if cmap == 'viridis' else [0, 0, 0], dtype=np.uint8)
                    assert np.all(expected == color)
            constructor_cases.append(dict(filename=filename, fixture=key, cpu_load_then_native_to=True, five_outputs=True))
        del detector, byte_detector, byte_model
    async def run():
        previous = _sdk.providers.execution_backend
        backend = CloudExecutionBackend()
        _sdk.providers.execution_backend = backend
        cases = []
        try:
            for filename in FILES:
                for cmap in ('Viridis (MagicAnimate)', 'Parula (CivitAI)'):
                    for key in ('people', 'no-person'):
                        image = fixture(key).repeat(2, 1, 1, 1);before = image.clone()
                        assert image.shape[1] != image.shape[2]  # real rectangular fixtures
                        values = dict(image=image, model=filename, cmap=cmap, resolution=64)
                        same_result(await dispatch(pack, ID, values), reference(values))
                        assert torch.equal(image, before)
                        cases.append(dict(filename=filename, cmap=cmap, fixture=key, batch=2))
            good = dict(image=fixture('no-person'), resolution=64)
            values = dict(image=fixture('no-person', torch.float16))
            same_result(await dispatch(pack, ID, values), reference(values))
            rgba = torch.cat([fixture('people'), torch.ones_like(fixture('people')[..., :1])], dim=-1).to(torch.float16)
            values = dict(image=rgba, resolution=64)
            same_result(await dispatch(pack, ID, values), reference(values))
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
        actual_native_file_bytesio_constructor_cases=constructor_cases, recoveries=2,
        registered_asset_rpc_order_observation=None, actual_corrupt_archive_or_operator_error_cases=None,
        arbitrary_combo_transport=None, current_generation_or_cold_warm_admission=None,
        whole_pack_acceptance=False), indent=2) + '\n')
