"""Trained pinned manga math, managed assets and genuine guest/outer paths."""
import ast
import asyncio
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
import torch
from einops import rearrange
from PIL import Image

V2 = Path(__file__).resolve().parents[1]
PRISTINE = V2.parent
CORE = Path(os.environ.get('COMFY_CORE_ROOT', '/Users/ben/comfy/ComfyUI-secure-nodes'))
sys.path[:0] = [str(CORE), '/Users/ben/comfy/ComfyUI_secure_nodes/backend']
from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb
from comfy_secure_nodes.transport.host import GuestSession
import execution
import folder_paths

NODE = 'Manga2Anime_LineArt_Preprocessor'
WEIGHT = Path('/tmp/many-oct6-controlnet-aux-manga-982e7ed/erika.pth')


def load(name, root):
    spec = importlib.util.spec_from_file_location(name, root / '__init__.py', submodule_search_locations=[str(root)])
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    spec.loader.exec_module(package)
    return sys.modules[name + '.nodes']


converted = load('_many_aux_manga', V2)


def lift(path, names, namespace):
    tree = ast.parse((PRISTINE / path).read_text())
    selected = [node for node in tree.body if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in names]
    assert len(selected) == len(names)
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(PRISTINE / path), 'exec'), namespace)


def reference(image):
    scope = dict(torch=torch, nn=torch.nn, np=np, cv2=cv2, Image=Image,
                 rearrange=rearrange, HF_MODEL_NAME='unused')
    scope['UPSCALE_METHODS'] = ['INTER_NEAREST', 'INTER_LINEAR', 'INTER_AREA', 'INTER_CUBIC', 'INTER_LANCZOS4']
    lift('src/custom_controlnet_aux/util.py', ['HWC3', 'safer_memory', 'pad64', 'get_upscale_method', 'resize_image_with_pad', 'common_input_validate'], scope)
    class Progress:
        def __init__(self, count): pass
        def update(self, step): pass
    scope['comfy'] = SimpleNamespace(utils=SimpleNamespace(ProgressBar=Progress))
    lift('utils.py', ['common_annotator_call'], scope)
    architecture = ast.parse((PRISTINE / 'src/custom_controlnet_aux/manga_line/model_torch.py').read_text())
    lift('src/custom_controlnet_aux/manga_line/model_torch.py', [node.name for node in architecture.body if isinstance(node, ast.ClassDef)], scope)
    lift('src/custom_controlnet_aux/manga_line/__init__.py', ['LineartMangaDetector'], scope)
    state = torch.load(WEIGHT, map_location='cpu', weights_only=True, mmap=False)
    for key in list(state):
        if 'module.' in key:
            state[key.replace('module.', '')] = state[key]
            del state[key]
    network = scope['res_skip']()
    network.load_state_dict(state, strict=True)
    network.eval()
    return scope['common_annotator_call'](scope['LineartMangaDetector'](network), image, resolution=64)


def fields(channels=3, dtype=torch.float32, batch=1):
    return dict(image=torch.linspace(0, 1, batch*24*24*channels, dtype=dtype).reshape(batch, 24, 24, channels), resolution=64)


@pytest.fixture
def catalogue(tmp_path, monkeypatch):
    declaration = converted._manga.WEIGHT
    with WEIGHT.open('rb') as stream:
        assert hashlib.file_digest(stream, 'sha256').hexdigest() == declaration.sha256
    root = tmp_path / 'controlnet'
    target = root / declaration.catalogue_name
    target.parent.mkdir(parents=True)
    shutil.copyfile(WEIGHT, target)
    monkeypatch.setitem(folder_paths.folder_names_and_paths, 'controlnet', ([str(root)], {'.pth'}))
    return target


def test_exact_architecture_detector_ast_and_declared_authority():
    original = ast.parse((PRISTINE / 'src/custom_controlnet_aux/manga_line/model_torch.py').read_text())
    new = ast.parse((V2 / '_manga_network.py').read_text())
    for before in [node for node in original.body if isinstance(node, ast.ClassDef)]:
        after = next(node for node in new.body if isinstance(node, ast.ClassDef) and node.name == before.name)
        assert ast.dump(before, include_attributes=False) == ast.dump(after, include_attributes=False)
    original = ast.parse((PRISTINE / 'src/custom_controlnet_aux/manga_line/__init__.py').read_text())
    detector = next(node for node in original.body if isinstance(node, ast.ClassDef))
    detector.body = [node for node in detector.body if isinstance(node, ast.FunctionDef) and node.name in ('__init__', '__call__')]
    after = next(node for node in new.body if isinstance(node, ast.ClassDef) and node.name == detector.name)
    assert ast.dump(detector, include_attributes=False) == ast.dump(after, include_attributes=False)
    assert converted.NODE_CLASS_MAPPINGS[NODE].SDK_REQUIRED_WEIGHTS == (converted._manga.WEIGHT,)


@pytest.mark.parametrize('channels,dtype,batch', [(3, torch.float32, 1), (4, torch.float16, 1), (1, torch.float64, 2)])
def test_trained_source_pixel_batch_channel_dtype_parity(catalogue, channels, dtype, batch):
    values = fields(channels, dtype, batch)
    before = values['image'].clone()
    async def run():
        refs = _sdk.InProcessRefResolver()
        plan = _sdk.ExecutionPlan(prompt_id='manga', node_id='1', node_type=NODE)
        with _sdk.bind_runtime(refs, _sdk.InProcessCtxProvider().build(plan), _sdk.InProcessOps()):
            return (await converted.NODE_CLASS_MAPPINGS[NODE].execute(**values)).result[0]
    actual = asyncio.run(run())
    expected = reference(values['image'])
    assert torch.equal(actual, expected) and actual.dtype == expected.dtype == torch.float32
    assert torch.isfinite(actual).all() and torch.equal(values['image'], before)


def test_two_fresh_real_guests_raw_assets_denial_and_manifest_outer(catalogue, tmp_path):
    cases = [fields(), fields(4, torch.float16)]
    expected = [reference(values['image']) for values in cases]
    fresh = tmp_path / 'fresh'
    shutil.copytree(V2, fresh)
    async def run():
        pids = []
        for index, root in enumerate((V2, fresh)):
            nodes = load('_many_manga_guest' + str(index), root)
            session = await GuestSession('many-manga', guest_runtime_root=root).start()
            refs = _sdk.InProcessRefResolver()
            try:
                cls = nodes.NODE_CLASS_MAPPINGS[NODE]
                for values, oracle in zip(cases, expected):
                    plan = _sdk.ExecutionPlan(prompt_id='manga', node_id=NODE, node_type=cls.__name__,
                                              node_module=cls.__module__, inputs=await _sdk.wrap_inputs(refs, values), input_mode='values')
                    runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps())
                    result = await session.execute(plan, runtime, capabilities=cls.SDK_PERMISSIONS)
                    assert torch.equal(await refs.resolve(result.result[0]), oracle)
                    for caps in (('raw',), ('assets',)):
                        with pytest.raises(Exception, match='raw|assets'):
                            await session.execute(plan, runtime, capabilities=caps)
                pids.append(session.last_guest_pid)
            finally:
                await session.kill()
        assert len(set(pids)) == 2 and os.getpid() not in pids
        loaded = packdb.load_pack(PRISTINE.parent, mount_name='custom_nodes.many_manga_outer')
        class Backend:
            session = None
            async def dispatch(self, plan, local_call, runtime):
                if self.session is None:
                    self.session = await GuestSession('many-manga-outer', guest_runtime_root=V2).start()
                plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs, plan.input_types)
                return await self.session.execute(plan, runtime, capabilities=plan.permissions)
        backend = Backend()
        previous = _sdk.providers.execution_backend
        _sdk.providers.execution_backend = backend
        try:
            cls = loaded.node_mappings[NODE]
            for values, oracle in zip(cases, expected):
                result = await execution._async_map_node_over_list('manga-outer', NODE, cls, {k: [v] for k, v in values.items()}, cls.FUNCTION)
                assert isinstance(result[0].result[0], torch.Tensor) and torch.equal(result[0].result[0], oracle)
        finally:
            _sdk.providers.execution_backend = previous
            if backend.session:
                await backend.session.kill()
    asyncio.run(run())


def test_digest_and_256_rounded_projected_guard_before_network(catalogue, monkeypatch):
    monkeypatch.setattr(converted._manga, 'res_skip', lambda: pytest.fail('network constructed before denial'))
    async def run():
        refs = _sdk.InProcessRefResolver()
        plan = _sdk.ExecutionPlan(prompt_id='manga-deny', node_id='1', node_type=NODE)
        with _sdk.bind_runtime(refs, _sdk.InProcessCtxProvider().build(plan), _sdk.InProcessOps()):
            # Native detector rounds257 to512; the estimate must use512.
            values = fields()
            values['resolution'] = 257
            with pytest.raises(ValueError, match='projected'):
                await converted.NODE_CLASS_MAPPINGS[NODE].execute(**values)
            catalogue.write_bytes(b'corrupt')
            with pytest.raises(ValueError, match='digest'):
                await converted.NODE_CLASS_MAPPINGS[NODE].execute(**fields())
    asyncio.run(run())
