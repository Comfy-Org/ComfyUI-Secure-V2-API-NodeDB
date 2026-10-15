"""Future trained native/registered AnyLine gate; never run by source authoring.

Native source constructors/math are independent of converted implementations.
Only native artifact acquisition is redirected to exact selected local bytes.
No model, morphology, SDK, execution-backend, or guest replacement is used.
"""
import ast
import asyncio
import functools
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import warnings

import cv2
import numpy as np
import pytest
import torch
from PIL import Image
from einops import rearrange
from skimage import morphology
import comfy.model_management as model_management
import comfy.utils
import execution
from comfy.cli_args import args
from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb
from comfy_secure_nodes.execution import CloudExecutionBackend
from comfy_secure_nodes.transport import sandbox

ROOT = Path(__file__).resolve().parents[1]
PRISTINE = Path(os.environ['AMY_AUX_PRISTINE'])
MANIFEST = json.loads((ROOT / 'secure-nodes.json').read_text())
NODE_ID = 'AnyLineArtPreprocessor_aux'


def lift(path, ns, names=None, strip_wrapper_imports=False):
    tree = ast.parse((PRISTINE / path).read_text())
    selected = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))
                and (names is None or n.name in names)]
    assert selected
    if names is not None:
        assert {n.name for n in selected} == set(names)
    if strip_wrapper_imports:
        # Imports are dependency acquisition, not a changed algorithm. Their
        # names below bind the independent original classes and real skimage.
        class Imports(ast.NodeTransformer):
            def visit_Import(self, node): return None
            def visit_ImportFrom(self, node): return None
        selected = [Imports().visit(n) for n in selected]
    module = ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[]))
    exec(compile(module, str(PRISTINE / path), 'exec'), ns)


def native_oracle(artifact_paths):
    declarations = MANIFEST['nodes'][NODE_ID]['required_weights']
    expected = {d['filename']: d for d in declarations}
    def custom_hf_download(repo, filename, subfolder=None):
        name = (subfolder + '/' if subfolder else '') + filename
        declaration = expected[name]
        assert repo == declaration['repo_id']
        p = Path(artifact_paths[name])
        assert hashlib.sha256(p.read_bytes()).hexdigest() == declaration['sha256']
        return str(p)
    ns = dict(torch=torch, nn=torch.nn, F=torch.nn.functional, np=np,
              cv2=cv2, Image=Image, rearrange=rearrange, functools=functools,
              warnings=warnings, morphology=morphology, comfy=comfy,
              model_management=model_management, custom_hf_download=custom_hf_download,
              BDS_MODEL_NAME='bdsqlsz/qinglong_controlnet-lllite',
              HF_MODEL_NAME='lllyasviel/Annotators', norm_layer=torch.nn.InstanceNorm2d,
              UPSCALE_METHODS=['INTER_NEAREST','INTER_LINEAR','INTER_AREA','INTER_CUBIC','INTER_LANCZOS4'])
    lift('src/custom_controlnet_aux/util.py', ns,
         ['HWC3','safe_step','safer_memory','pad64','get_upscale_method',
          'resize_image_with_pad','common_input_validate'])
    # Retain the original scripted activation in the native network oracle.
    lift('src/custom_controlnet_aux/teed/Fsmish.py', ns, ['smish'])
    ns['Fsmish'] = ns['smish']
    lift('src/custom_controlnet_aux/teed/Xsmish.py', ns, ['Smish'])
    lift('src/custom_controlnet_aux/teed/ted.py', ns)
    lift('src/custom_controlnet_aux/teed/__init__.py', ns, ['TEDDetector'])
    lift('src/custom_controlnet_aux/lineart_standard/__init__.py', ns, ['LineartStandardDetector'])
    lift('src/custom_controlnet_aux/lineart/__init__.py', ns)
    lift('src/custom_controlnet_aux/lineart_anime/__init__.py', ns)
    lift('src/custom_controlnet_aux/manga_line/model_torch.py', ns)
    lift('src/custom_controlnet_aux/manga_line/__init__.py', ns, ['LineartMangaDetector'])
    lift('utils.py', ns, ['common_annotator_call'])
    lift('node_wrappers/anyline.py', ns,
         ['get_intensity_mask','combine_layers','AnyLinePreprocessor'],
         strip_wrapper_imports=True)
    return ns['AnyLinePreprocessor']()


def case_image(channels, dtype):
    return torch.linspace(0, 1, 2*24*40*channels, dtype=dtype).reshape(2,24,40,channels)


def test_actual_native_registered_four_modes_errors_and_refusal_recovery():
    # This receipt is issued only by the actual qualified runtime owner.
    receipt_bytes = Path(os.environ['AMY_AUX_EXECUTION_RECEIPT']).read_bytes()
    assert hashlib.sha256(receipt_bytes).hexdigest() == os.environ['AMY_AUX_EXECUTION_RECEIPT_SHA256']
    receipt = json.loads(receipt_bytes)
    assert receipt['authorized'] is True and receipt['execution_owner'] == 'chat_f38536805264'
    assert receipt['node_id'] == NODE_ID
    assert receipt['manifest_sha256'] == hashlib.sha256((ROOT/'secure-nodes.json').read_bytes()).hexdigest()
    for field in ('runtime_profile_sha256','capacity_receipt_sha256','source_selection_sha256'):
        assert len(receipt[field]) == 64
    assert args.cpu is True and model_management.get_torch_device().type == 'cpu'
    assert os.environ['COMFY_SECURE_SANDBOX_MODE'] == 'required'
    assert os.environ['COMFY_SECURE_SANDBOX_BACKEND'] == 'gvisor'
    assert sandbox.available() == [sandbox.KIND_GVISOR]
    artifacts = receipt['native_artifact_paths']
    assert set(artifacts) == {d['filename'] for d in MANIFEST['nodes'][NODE_ID]['required_weights']}
    oracle = native_oracle(artifacts)
    pack = packdb.load_pack(Path(receipt['stable_snapshot_path']),
                            mount_name='custom_nodes.amy_aux_anyline', pack_id=receipt['pack_id'])
    cls = pack.node_mappings[NODE_ID]
    assert set(cls.SDK_PERMISSIONS) == {'raw','assets','models.download'}
    cases = [
        dict(merge_with_lineart='lineart_standard', resolution=64, channels=3, dtype=torch.float32),
        dict(merge_with_lineart='lineart_standard', resolution=64, channels=1, dtype=torch.float16,
             lineart_lower_bound=.8, lineart_upper_bound=.2, object_min_size=1, object_connectivity=3),
        dict(merge_with_lineart='lineart_realisitic', resolution=64, channels=4, dtype=torch.float64),
        dict(merge_with_lineart='lineart_anime', resolution=64, channels=3, dtype=torch.float32),
        dict(merge_with_lineart='manga_line', resolution=256, channels=3, dtype=torch.float32),
    ]
    async def dispatch(values):
        mapped = await execution._async_map_node_over_list('amy-aux', NODE_ID, cls,
            {k:[v] for k,v in values.items()}, cls.FUNCTION)
        return (await execution.resolve_map_node_over_list_results(mapped))[0].result[0]
    async def run():
        previous = _sdk.providers.execution_backend
        backend = CloudExecutionBackend()
        _sdk.providers.execution_backend = backend
        passed = []
        try:
            for description in cases:
                values = dict(description)
                image = case_image(values.pop('channels'), values.pop('dtype'))
                values['image'] = image
                before = image.clone()
                expected = oracle.get_anyline(**values)[0]
                actual = await dispatch(values)
                assert type(actual) is type(expected) is torch.Tensor
                assert actual.dtype == expected.dtype and actual.shape == expected.shape
                assert torch.equal(actual, expected) and torch.equal(image, before)
                passed.append(description['merge_with_lineart'])
            # At resolution64, native manga rounds to256 while MTEED remains64:
            # preserve the resulting source composition error rather than resize.
            broken = dict(image=case_image(3, torch.float32), resolution=64,
                          merge_with_lineart='manga_line')
            with pytest.raises(ValueError): oracle.get_anyline(**broken)
            with pytest.raises(Exception): await dispatch(broken)
            recovery = dict(image=case_image(3, torch.float32), resolution=64,
                            merge_with_lineart='lineart_standard')
            assert torch.equal(await dispatch(recovery), oracle.get_anyline(**recovery)[0])
            with pytest.raises(Exception, match='projected|workspace|bounded'):
                await dispatch(dict(recovery, resolution=16384))
            assert torch.equal(await dispatch(recovery), oracle.get_anyline(**recovery)[0])
            return passed
        finally:
            try:
                await backend.guests.shutdown()
            finally:
                _sdk.providers.execution_backend = previous
    passed = asyncio.run(run())
    Path(os.environ['AMY_AUX_RESULTS']).write_text(json.dumps({
        'node_id': NODE_ID, 'manifest_sha256': receipt['manifest_sha256'],
        'native_registered_modes': passed, 'native_shape_error': True,
        'workload_refusal': True, 'recoveries': 2,
        'whole_pack_acceptance': False}, indent=2) + '\n')
