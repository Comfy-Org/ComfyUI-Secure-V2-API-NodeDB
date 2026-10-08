"""Pinned grid oracles, confined assets and real guest/outer verification."""
import ast
import asyncio
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import types
from dataclasses import replace

import numpy as np
from PIL import Image
import pytest
import torch

sys.dont_write_bytecode = True
V2 = Path(__file__).resolve().parents[1]
PACK = V2.parent
DB = PACK.parents[3]
SNAPSHOT = PACK.parent
OVERLAY = Path('/Users/ben/comfy/ComfyUI_secure_nodes')
CORE = Path(os.environ.get('COMFY_CORE_ROOT', '/Users/ben/comfy/ComfyUI-secure-nodes'))
sys.path[:0] = [str(CORE), str(OVERLAY / 'backend')]
from comfy.cli_args import args
args.cpu = True
import execution
import folder_paths
from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb, packpatch
from comfy_secure_nodes import packruntime
from comfy_secure_nodes.packmanifest import encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.execution import CloudExecutionBackend


def load(name, root):
    spec = importlib.util.spec_from_file_location(name, root / '__init__.py', submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


SECURE = load('many_sprite', V2)
NODE = sys.modules[SECURE.ImageGridNode.__module__]
_spec = importlib.util.spec_from_file_location('many_sprite_pristine', PACK / 'node.py')
PRISTINE = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(PRISTINE)


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    root = tmp_path / 'input'
    root.mkdir()
    monkeypatch.setattr(folder_paths, 'get_input_directory', lambda: str(root))
    return root


def fixture_images(root, mode='RGB', extension='png', count=3, size=(3, 2)):
    target = root / 'frames'
    target.mkdir(exist_ok=True)
    for i in range(count):
        h, w = size[1], size[0]
        if mode in ('L', 'P', 'I;16', 'F'):
            dtype = np.uint16 if mode == 'I;16' else np.float32 if mode == 'F' else np.uint8
            values = (np.arange(w * h).reshape(h, w) + i * 30).astype(dtype)
        else:
            channels = {'RGB': 3, 'RGBA': 4, 'LA': 2, 'CMYK': 4}[mode]
            values = (np.arange(w * h * channels).reshape(h, w, channels) + i * 30).astype(np.uint8)
        image = Image.fromarray(values) if mode in ('I;16', 'F') else Image.fromarray(values, mode=mode)
        if mode == 'P':
            image.putpalette([value for i in range(256) for value in (i, 255-i, i//2)])
            image.info['transparency'] = 1
        image.save(target / f'{i:03}.{extension}')
        image.close()
    (target / 'ignored.txt').write_text('not decoded')
    (target / 'nested').mkdir(exist_ok=True)
    return target


def expected(directory, rows, columns):
    source = PRISTINE.ImageGridNode()
    original = source.get_images_from_directory
    source.get_images_from_directory = lambda path: sorted(original(path))
    return source.main(directory, rows, columns)[0]


async def direct(fields, ctx=None):
    refs = _sdk.InProcessRefResolver()
    plan = _sdk.ExecutionPlan(prompt_id='spritesheet-direct', node_id='1', node_type='ImageGridNode', tier='sandbox', inputs=fields)
    runtime_ctx = ctx or _sdk.InProcessCtxProvider().build(plan)
    with _sdk.bind_runtime(refs, runtime_ctx, _sdk.InProcessOps()):
        result = await SECURE.ImageGridNode.execute(**fields)
        return await refs.resolve(result.result[0])


@pytest.mark.parametrize('mode,extension', [('RGB','png'),('RGBA','png'),('L','png'),('LA','png'),('P','png'),('RGB','jpeg'),('RGB','bmp'),('P','gif'),('RGB','tiff'),('I;16','tiff'),('F','tiff'),('CMYK','tiff')])
@pytest.mark.parametrize('rows,columns', [(1,1),(2,2),(1,4),(4,1),(0,2),(2,0)])
def test_exact_native_grid_formats_empty_axes_and_spare_tiles(inputs, mode, extension, rows, columns):
    fixture_images(inputs, mode, extension)
    got = asyncio.run(direct(dict(images_directory='frames', row_count=rows, column_count=columns)))
    want = expected('frames', rows, columns)
    assert got.dtype == want.dtype == torch.float32
    assert got.shape == want.shape
    assert torch.equal(got, want)


def test_exact_grid_method_ast_and_original_mapping_quirk():
    legacy=load('many_sprite_legacy_mapping',PACK)
    assert set(legacy.NODE_CLASS_MAPPINGS)=={'SpriteSheetMaker'}
    assert legacy.NODE_DISPLAY_NAME_MAPPINGS==SECURE.NODE_DISPLAY_NAME_MAPPINGS
    assert not hasattr(legacy,'WEB_DIRECTORY')
    old = ast.parse((PACK / 'node.py').read_text()).body
    original = next(n for n in old if isinstance(n, ast.ClassDef))
    method = next(n for n in original.body if isinstance(n, ast.FunctionDef) and n.name == 'create_image_grid')
    new = ast.parse((V2 / '_grid.py').read_text())
    copied = next(n for n in new.body if isinstance(n, ast.ClassDef)).body[0]
    assert ast.dump(method, include_attributes=False) == ast.dump(copied, include_attributes=False)
    assert set(SECURE.NODE_CLASS_MAPPINGS) == {'SpriteSheetMaker'}
    assert SECURE.NODE_DISPLAY_NAME_MAPPINGS == {'ImageGridNode': 'Image Grid'}
    schema = SECURE.ImageGridNode.GET_SCHEMA()
    assert schema.node_id == 'SpriteSheetMaker' and schema.category == 'ImageGrid'
    assert [x.id for x in schema.inputs] == ['images_directory','row_count','column_count']
    assert schema.outputs[0].id == 'sprite_image'


@pytest.mark.parametrize('case', ['empty','mismatch','corrupt','negative'])
def test_native_errors_and_recovery(inputs, case):
    target = fixture_images(inputs)
    if case == 'empty':
        for p in target.glob('*.png'): p.unlink()
    elif case == 'mismatch':
        Image.new('RGB',(4,2)).save(target/'002.png')
    elif case == 'corrupt':
        (target/'001.png').write_bytes(b'invalid image')
    rows = -1 if case == 'negative' else 2
    with pytest.raises(Exception) as source:
        expected('frames',rows,2)
    with pytest.raises(type(source.value)) as converted:
        asyncio.run(direct(dict(images_directory='frames',row_count=rows,column_count=2)))
    if case in ('empty','mismatch'):
        assert str(converted.value) == str(source.value)
    shutil.rmtree(target)
    fixture_images(inputs)
    assert torch.equal(asyncio.run(direct(dict(images_directory='frames',row_count=2,column_count=2))),expected('frames',2,2))


@pytest.mark.parametrize('name',['../escape','/absolute','frames/../x','frames//x','frames\\x','frames%2fx','frames:x','frames\n'])
def test_path_refusal_before_listing(name):
    class Refusal:
        async def list(self,*a,**kw):raise AssertionError('must refuse before assets')
    with pytest.raises(ValueError,match='directory'):
        asyncio.run(direct(dict(images_directory=name,row_count=2,column_count=2),types.SimpleNamespace(assets=Refusal())))


def test_before_read_and_before_compute_projected_bounds(inputs, monkeypatch):
    assert NODE.ownership_plan([(3,2)]*3,200,2,2)['projected_bytes'] < NODE.MAX_OWNED_BYTES
    for sizes,encoded,rows,columns in [([(8192,8192)],0,2,2), ([(3,2)]*129,0,2,2), ([(3,2)],NODE.MAX_ENCODED_BYTES+1,2,2), ([(3,2)],0,4097,2)]:
        with pytest.raises(ValueError): NODE.ownership_plan(sizes,encoded,rows,columns)
    class TooLarge:
        async def list(self,*a,**kw): return ['frames/x.png']
        async def resolve(self,*a): return 'selected'
        async def size(self,ref): return NODE.MAX_FILE_BYTES+1
        async def read_range(self,*a): raise AssertionError('oversize before read')
    with pytest.raises(ValueError,match='encoded'):
        asyncio.run(direct(dict(images_directory='frames',row_count=2,column_count=2),types.SimpleNamespace(assets=TooLarge())))
    fixture_images(inputs)
    monkeypatch.setattr(Image,'new',lambda *a,**kw: (_ for _ in ()).throw(AssertionError('oversize before canvas')))
    with pytest.raises(ValueError,match='ownership'):
        asyncio.run(direct(dict(images_directory='frames',row_count=4000,column_count=4000)))


@pytest.mark.parametrize('case',['short','growth','resized','exact'])
def test_chunk_tail_and_resize_guards(case):
    class Assets:
        async def read_range(self,ref,offset,count):
            if offset==4:return b'x' if case=='growth' else b''
            return b'ab' if case=='short' else b'abcd'
        async def size(self,ref):return 5 if case=='resized' else 4
    if case=='exact':assert asyncio.run(NODE.bounded_read(Assets(),'ref',4))==b'abcd'
    else:
        with pytest.raises(ValueError,match='changed size'):asyncio.run(NODE.bounded_read(Assets(),'ref',4))


def test_managed_directory_selection_isolation_order_and_ignored_subtrees(inputs):
    target=fixture_images(inputs)
    (target/'nested/hidden.png').write_bytes(b'bad; must not decode')
    outside=inputs.parent/'outside.png';outside.write_bytes(b'private; must not read')
    (target/'escape.png').symlink_to(outside)
    # The source follows OS file order/symlinks; compare supported confined list,
    # removing the deliberately forbidden escape before invoking that oracle.
    (target/'escape.png').unlink()
    want=expected('frames',2,2)
    (target/'escape.png').symlink_to(outside)
    got=asyncio.run(direct(dict(images_directory='frames',row_count=2,column_count=2)))
    assert torch.equal(got,want)
    assert NODE.image_names('frames',['frames/000.PNG','frames/ignored.txt'])==['frames/000.PNG']
    with pytest.raises(ValueError):NODE.image_names('frames',['other/000.png'])


def test_os_enumeration_order_adaptation_is_explicit(inputs):
    fixture_images(inputs)
    source=PRISTINE.ImageGridNode()
    listing=source.get_images_from_directory
    source.get_images_from_directory=lambda path:list(reversed(sorted(listing(path))))
    native_reversed=source.main('frames',1,3)[0]
    managed=asyncio.run(direct(dict(images_directory='frames',row_count=1,column_count=3)))
    assert not torch.equal(managed,native_reversed)
    assert torch.equal(managed,expected('frames',1,3))
    assert torch.equal(managed[:,:,0:3],native_reversed[:,:,6:9])


def test_publication_error_closes_all_images_and_encoded_streams(inputs,monkeypatch):
    fixture_images(inputs)
    closed_images=[]
    original_open=Image.open
    def opened(*a,**kw):
        image=original_open(*a,**kw)
        close=image.close
        def dispose():closed_images.append(image);close()
        image.close=dispose
        return image
    monkeypatch.setattr(Image,'open',opened)
    real_bytes=NODE.bytes_io.BytesIO
    streams=[]
    class Stream(real_bytes):
        def __init__(self,*a,**kw):super().__init__(*a,**kw);streams.append(self)
    monkeypatch.setattr(NODE,'bytes_io',types.SimpleNamespace(BytesIO=Stream))
    async def refused(cls,value):raise RuntimeError('injected publication refusal')
    monkeypatch.setattr(_sdk.ImageRef,'from_value',classmethod(refused))
    with pytest.raises(RuntimeError,match='publication refusal'):
        asyncio.run(direct(dict(images_directory='frames',row_count=2,column_count=2)))
    assert len(closed_images)==3 and len(streams)==3 and all(s.closed for s in streams)


def test_live_proxy_directory_catalogue_and_admission(inputs):
    fixture_images(inputs)
    outside=inputs.parent/'private';outside.mkdir()
    (inputs/'escape').symlink_to(outside,target_is_directory=True)
    record=manifest()['nodes']['SpriteSheetMaker']
    proxy=packdb._proxy_class('custom_nodes.many_sprite_catalogue',V2/'node.py',record)
    choices=proxy.INPUT_TYPES()['required']['images_directory'][1]['options']
    assert choices==['','frames','frames/nested']
    assert proxy.RETURN_TYPES==['IMAGE'] and proxy.RETURN_NAMES==['sprite_image']
    assert proxy.INPUT_TYPES()['required']['row_count'][1]['default']==2
    assert proxy.INPUT_TYPES()['required']['column_count'][1]['default']==2
    shutil.rmtree(inputs/'frames/nested')
    assert proxy.INPUT_TYPES()['required']['images_directory'][1]['options']==['','frames']


def test_two_fresh_required_guests_real_outer_caps_recovery(inputs, tmp_path, monkeypatch):
    fixture_images(inputs,'RGBA')
    monkeypatch.setenv('COMFY_SECURE_SANDBOX_MODE','required')
    async def run():
        previous=_sdk.providers.execution_backend
        pids=set()
        try:
            for generation in range(2):
                root=tmp_path/f'guest-pack-{generation}'
                shutil.copytree(V2,root)
                module=load(f'many_sprite_guest_{generation}',root)
                module.ImageGridNode.GET_SCHEMA()
                session=await GuestSession(f'many-sprite-{generation}',guest_runtime_root=root).start()
                caps=('assets','raw')
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):
                        return await session.execute(plan,runtime,capabilities=caps,tenant='many-sprite-user')
                _sdk.providers.register_execution_backend(Backend())
                async def outer(rows=2,columns=2,directory='frames'):
                    mapped=await execution._async_map_node_over_list('sprite-proof','1',module.ImageGridNode,dict(images_directory=[directory],row_count=[rows],column_count=[columns]),module.ImageGridNode.FUNCTION)
                    return (await execution.resolve_map_node_over_list_results(mapped))[0].result[0]
                try:
                    assert session.sandbox_kind=='seatbelt'
                    for rows,columns in ((2,2),(1,1),(1,4),(4,1),(0,2)):
                        assert torch.equal(await outer(rows,columns),expected('frames',rows,columns))
                    for caps in (('raw',),('assets',)):
                        with pytest.raises(Exception):await outer()
                    caps=('assets','raw')
                    with pytest.raises(Exception):await outer(4000,4000)
                    with pytest.raises(Exception):await outer(directory='../outside')
                    assert torch.equal(await outer(),expected('frames',2,2))
                    pids.add(session.last_guest_pid)
                finally:await session.kill()
        finally:_sdk.providers.register_execution_backend(previous)
        assert len(pids)==2 and os.getpid() not in pids and None not in pids
        print('required fresh SpriteSheetMaker PIDs',sorted(pids))
    asyncio.run(run())


def test_actual_cloud_execution_backend_local_unsealed_path(inputs,monkeypatch):
    fixture_images(inputs,'P')
    monkeypatch.setenv('COMFY_SECURE_SANDBOX_MODE','required')
    monkeypatch.delenv('COMFY_SECURE_REALM_ROOT',raising=False)
    module=load('custom_nodes.many_sprite_cloud',V2)
    module.ImageGridNode.GET_SCHEMA()
    original_resolve=packruntime.resolve_for_tenant
    def selected(spec,tenant):
        # Trusted local test selection, not a sealed dependency/image profile.
        assert spec is None
        resolved=original_resolve(spec,tenant)
        assert resolved.python_executable==Path(sys.executable)
        return replace(resolved,spec=replace(resolved.spec,pack_root=PACK))
    monkeypatch.setattr(packruntime,'resolve_for_tenant',selected)
    async def run():
        prior=_sdk.providers.execution_backend
        backend=CloudExecutionBackend()
        _sdk.providers.register_execution_backend(backend)
        try:
            mapped=await execution._async_map_node_over_list('sprite-cloud-local','1',module.ImageGridNode,dict(images_directory=['frames'],row_count=[2],column_count=[2]),module.ImageGridNode.FUNCTION)
            result=(await execution.resolve_map_node_over_list_results(mapped))[0].result[0]
            assert torch.equal(result,expected('frames',2,2))
            sessions=list(backend.guests._sessions.values())
            assert len(sessions)==1 and sessions[0].sandbox_kind=='seatbelt'
            assert sessions[0].last_guest_pid not in (None,os.getpid())
            print('actual local CloudExecutionBackend PID',sessions[0].last_guest_pid)
        finally:
            _sdk.providers.register_execution_backend(prior)
            await backend.shutdown()
    asyncio.run(run())


def manifest():
    return {'format':'comfy-secure-nodes-v1','runtime':manifest_declaration(V2),'nodes':{
        'SpriteSheetMaker':{'module':'node','class':'ImageGridNode','sdk_refs':True,'permissions':['assets','raw'],
                           'methods':{'validate_inputs':False,'fingerprint_inputs':False,'check_lazy_status':False},
                           'schema':encode_schema(SECURE.ImageGridNode.GET_SCHEMA())}}}


def test_manifest_proxy_and_two_exact_pair_bundle_reconstructions(tmp_path):
    assert json.loads((V2/'secure-nodes.json').read_bytes())==manifest()
    pair=DB/'patches/comfyui-spritesheetmaker/xbd5a4c1/comfyui-spritesheetmaker-xbd5a4c1'
    m,d=packpatch.generate(SNAPSHOT)
    assert json.loads(pair.with_suffix('.json').read_bytes())==m
    assert pair.with_suffix('.diff').read_bytes().decode()==d
    for kind in ('pair','zip'):
        fresh=tmp_path/kind/'comfyui-spritesheetmaker/xbd5a4c1'
        fresh.mkdir(parents=True)
        shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
        if kind=='pair':packpatch.apply(fresh,m,d)
        else:packpatch.apply_bundle(fresh,packpatch.bundle(m,d))
        packpatch.validate_tree(fresh/PACK.name/'v2',V2)
    wrong=tmp_path/'wrong/comfyui-spritesheetmaker/xbd5a4c1'
    wrong.mkdir(parents=True)
    shutil.copytree(PACK,wrong/PACK.name,ignore=shutil.ignore_patterns('v2'))
    (wrong/PACK.name/'node.py').write_text('wrong source')
    with pytest.raises(packpatch.PackPatchError):packpatch.apply(wrong,m,d)
    proxy=packdb.load_pack(SNAPSHOT,mount_name='custom_nodes.many_sprite_proxy',pack_id='comfyui-spritesheetmaker/xbd5a4c1')
    assert set(proxy.node_mappings)=={'SpriteSheetMaker'}
    assert proxy.web_directory is None and not proxy.routes
