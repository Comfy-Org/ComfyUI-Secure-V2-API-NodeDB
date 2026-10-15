"""Pinned pure algorithms and real guests; model branches remain untested."""
import ast
import asyncio
import importlib.util
import logging
import os
from pathlib import Path
import shutil
import sys

import cv2
import numpy as np
import pytest
import torch
from PIL import Image

CORE = Path(os.environ.get('COMFY_CORE_ROOT', '/Users/ben/comfy/ComfyUI-secure-nodes'))
OVERLAY = Path('/Users/ben/comfy/ComfyUI_secure_nodes')
sys.path[:0] = [str(CORE), str(OVERLAY / 'backend')]
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes import packdb
import execution

V2 = Path(__file__).resolve().parents[1]
PRISTINE = V2.parent


def load(name, root):
    spec = importlib.util.spec_from_file_location(name, root / '__init__.py', submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return sys.modules[name + '.nodes']


converted = load('_many_aux_helper_test', V2)


def lifted(path, names, namespace):
    tree = ast.parse((PRISTINE / path).read_text())
    selected = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
    assert len(selected) == len(names)
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(PRISTINE / path), 'exec'), namespace)


def reference():
    from enum import Enum
    namespace = dict(cv2=cv2, np=np, torch=torch, Image=Image, Enum=Enum, log=logging.getLogger('aux-reference'),
                     MAX_IMAGEGEN_RESOLUTION=8192, MAX_RESOLUTION=16384)
    import warnings
    namespace['warnings'] = warnings
    lifted('utils.py', ['ResizeMode', 'safe_numpy', 'get_unique_axis0', 'INPUT', 'define_preprocessor_inputs'], namespace)
    namespace['RESIZE_MODES'] = [x.value for x in namespace['ResizeMode']]
    namespace['UPSCALE_METHODS'] = ['INTER_NEAREST', 'INTER_LINEAR', 'INTER_AREA', 'INTER_CUBIC', 'INTER_LANCZOS4']
    lifted('src/custom_controlnet_aux/util.py', ['HWC3', 'safer_memory', 'get_upscale_method', 'pad64', 'resize_image_with_pad', 'common_input_validate', 'make_noise_disk'], namespace)
    lifted('src/custom_controlnet_aux/shuffle/__init__.py', ['ContentShuffleDetector'], namespace)
    # Pure thinning module has no Comfy/global environment dependencies.
    thin = importlib.util.spec_from_file_location('_many_aux_reference_thin', PRISTINE / 'lvminthin.py')
    module = importlib.util.module_from_spec(thin); thin.loader.exec_module(module)
    namespace.update(nake_nms=module.nake_nms, lvmin_thin=module.lvmin_thin)
    lifted('hint_image_enchance.py', ['PixelPerfectResolution', 'HintImageEnchance', 'ImageGenResolutionFromImage', 'ImageGenResolutionFromLatent'], namespace)
    for folder, names in [('canny', ['CannyDetector']), ('binary', ['BinaryDetector']), ('color', ['cv2_resize_shortest_edge', 'apply_color', 'ColorDetector']), ('recolor', ['recolor_luminance', 'recolor_intensity', 'Recolorizer']), ('lineart_standard', ['LineartStandardDetector']), ('scribble', ['ScribbleDetector', 'ScribbleXDog_Detector']), ('pyracanny', ['centered_canny', 'centered_canny_color', 'pyramid_canny_color', 'norm255', 'canny_pyramid', 'PyraCannyDetector'])]:
        lifted(f'src/custom_controlnet_aux/{folder}/__init__.py', names, namespace)
    namespace['recolor_methods'] = {'luminance': namespace['recolor_luminance'], 'intensity': namespace['recolor_intensity']}
    spec = importlib.util.spec_from_file_location('_many_aux_reference_guided', PRISTINE / 'src/custom_controlnet_aux/tile/guided_filter.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    namespace['FastGuidedFilter'] = module.FastGuidedFilter
    lifted('src/custom_controlnet_aux/tile/__init__.py', ['TileDetector', 'apply_gaussian_blur', 'apply_guided_filter', 'TTPlanet_Tile_Detector_GF', 'TTPLanet_Tile_Detector_Simple'], namespace)
    return namespace


old = reference()
IDS = tuple(converted._algorithms.IMPLEMENTED)


def case(name, dtype=torch.float32, channels=3, batch=2):
    image = torch.linspace(0, 1, batch * 17 * 29 * channels, dtype=dtype).reshape(batch, 17, 29, channels)
    if name == 'ControlNetPreprocessorSelector':
        return dict(preprocessor='none')
    if name == 'ControlNetAuxSimpleAddText':
        return dict(image=image, text='Green annotation λ')
    if name == 'ShufflePreprocessor':
        return dict(image=image, resolution=64, seed=23)
    if name == 'TilePreprocessor':
        return dict(image=torch.linspace(0, 1, batch * 64 * 128 * channels, dtype=dtype).reshape(batch, 64, 128, channels), pyrUp_iters=1, resolution=64)
    if name == 'TTPlanet_TileGF_Preprocessor':
        return dict(image=image, scale_factor=2.0, blur_strength=2.0, radius=7, eps=0.01, resolution=64)
    if name == 'TTPlanet_TileSimple_Preprocessor':
        return dict(image=image, scale_factor=2.0, blur_strength=2.0)
    if name == 'ImageGenResolutionFromLatent':
        return dict(latent={'samples': torch.arange(2 * 4 * 3 * 5, dtype=dtype).reshape(2, 4, 3, 5)})
    if name == 'ImageGenResolutionFromImage': return dict(image=image)
    if name == 'PixelPerfectResolution':
        return dict(original_image=image, image_gen_width=64, image_gen_height=96, resize_mode='Resize and Fill')
    if name == 'HintImageEnchance':
        return dict(hint_image=image, image_gen_width=64, image_gen_height=96, resize_mode='Crop and Resize')
    if name == 'InpaintPreprocessor':
        return dict(image=image, mask=torch.linspace(0, 1, batch * 9 * 13, dtype=dtype).reshape(batch, 9, 13), black_pixel_for_xinsir_cn=False)
    if name == 'CannyEdgePreprocessor': return dict(image=image, low_threshold=50, high_threshold=170, resolution=64)
    if name == 'PyraCannyPreprocessor': return dict(image=image, low_threshold=50, high_threshold=170, resolution=64)
    if name == 'Scribble_XDoG_Preprocessor': return dict(image=image, threshold=32, resolution=64)
    if name == 'LineartStandardPreprocessor': return dict(image=image, guassian_sigma=6.0, intensity_threshold=8, resolution=64)
    if name == 'BinaryPreprocessor': return dict(image=image, bin_threshold=100, resolution=64)
    if name in ('ImageLuminanceDetector', 'ImageIntensityDetector'):
        return dict(image=image, gamma_correction=1.3, resolution=64)
    return dict(image=image, resolution=64)


def expected(name, values):
    if name in ('ControlNetPreprocessorSelector', 'ControlNetAuxSimpleAddText'):
        namespace = dict(old, here=PRISTINE,
                         PREPROCESSOR_OPTIONS=converted.SCHEMAS['ControlNetPreprocessorSelector']['inputs']['required']['preprocessor'][0])
        lifted('__init__.py', [name], namespace)
        return getattr(namespace[name](), namespace[name].FUNCTION)(**values)
    if name in ('PixelPerfectResolution', 'HintImageEnchance', 'ImageGenResolutionFromImage', 'ImageGenResolutionFromLatent'):
        return old[name]().execute(**values)
    if name == 'InpaintPreprocessor':
        # Execute the exact pinned method in an independent namespace.
        namespace = dict(torch=torch, INPUT=old['INPUT'])
        lifted('node_wrappers/inpaint.py', ['InpaintPreprocessor'], namespace)
        return namespace[name]().preprocess(**values)
    namespace = dict(old)
    # Original batch function differs only in its host progress notification.
    class Progress:
        def __init__(self, count): pass
        def update(self, step): pass
    from types import SimpleNamespace
    namespace['comfy'] = SimpleNamespace(utils=SimpleNamespace(ProgressBar=Progress))
    lifted('utils.py', ['common_annotator_call'], namespace)
    detector = {'CannyEdgePreprocessor':'CannyDetector', 'BinaryPreprocessor':'BinaryDetector',
                'TilePreprocessor':'TileDetector', 'TTPlanet_TileGF_Preprocessor':'TTPlanet_Tile_Detector_GF',
                'TTPlanet_TileSimple_Preprocessor':'TTPLanet_Tile_Detector_Simple',
                'ColorPreprocessor':'ColorDetector', 'ImageLuminanceDetector':'Recolorizer',
                'ImageIntensityDetector':'Recolorizer', 'LineartStandardPreprocessor':'LineartStandardDetector',
                'ScribblePreprocessor':'ScribbleDetector', 'Scribble_XDoG_Preprocessor':'ScribbleXDog_Detector',
                'PyraCannyPreprocessor':'PyraCannyDetector', 'ShufflePreprocessor':'ContentShuffleDetector'}[name]
    kwargs = {k:v for k,v in values.items() if k != 'image'}
    if name == 'TTPlanet_TileGF_Preprocessor': kwargs.pop('resolution')
    if name == 'Scribble_XDoG_Preprocessor': kwargs['thr_a'] = kwargs.pop('threshold')
    if name in ('ImageLuminanceDetector', 'ImageIntensityDetector'):
        kwargs['mode'] = 'luminance' if name == 'ImageLuminanceDetector' else 'intensity'
    return (namespace['common_annotator_call'](old[detector](), values['image'], **kwargs),)


def compare(actual, desired):
    assert len(actual) == len(desired)
    for a, b in zip(actual, desired):
        if isinstance(b, torch.Tensor):
            assert a.dtype == b.dtype and a.shape == b.shape and torch.equal(a, b)
        else: assert a == b


def test_exact_64_schemas_and_no_eager_ambient_imports():
    assert len(converted.NODE_CLASS_MAPPINGS) == 64
    for node_id, cls in converted.NODE_CLASS_MAPPINGS.items():
        schema = cls.define_schema(); schema.validate()
        assert schema.node_id == node_id
    assert len(IDS) == 20
    with pytest.raises(RuntimeError, match='pending'):
        asyncio.run(converted.NODE_CLASS_MAPPINGS['DWPreprocessor'].execute())


@pytest.mark.parametrize('name', IDS)
@pytest.mark.parametrize('dtype', [torch.float16, torch.float32, torch.float64])
def test_exact_pinned_math(name, dtype):
    values = case(name, dtype)
    compare(asyncio.run(converted.NODE_CLASS_MAPPINGS[name].execute(**values)).result, expected(name, values))


@pytest.mark.parametrize('mode', ['Just Resize', 'Crop and Resize', 'Resize and Fill'])
@pytest.mark.parametrize('channels', [3, 4])
def test_hint_modes_binary_palette_and_alpha(mode, channels):
    image = torch.zeros(2, 31, 47, channels)
    image[:, ::2, :, :3] = 1
    if channels == 4: image[..., 3] = torch.linspace(0, 1, 31).reshape(1, 31, 1)
    values = dict(hint_image=image, image_gen_width=64, image_gen_height=80, resize_mode=mode)
    compare(asyncio.run(converted.NODE_CLASS_MAPPINGS['HintImageEnchance'].execute(**values)).result,
            expected('HintImageEnchance', values))


@pytest.mark.parametrize('name', ['CannyEdgePreprocessor', 'BinaryPreprocessor', 'ColorPreprocessor', 'ImageLuminanceDetector', 'ImageIntensityDetector'])
@pytest.mark.parametrize('channels', [1, 4])
def test_gray_rgba_padding_and_alpha(name, channels):
    values = case(name, channels=channels)
    compare(asyncio.run(converted.NODE_CLASS_MAPPINGS[name].execute(**values)).result, expected(name, values))


def test_tile_preserves_native_zero_dimension_error():
    values = dict(image=torch.zeros(1, 17, 29, 3), pyrUp_iters=1, resolution=64)
    with pytest.raises(cv2.error):
        expected('TilePreprocessor', values)
    with pytest.raises(cv2.error):
        asyncio.run(converted.NODE_CLASS_MAPPINGS['TilePreprocessor'].execute(**values))


def test_annotation_retains_first_image_uint8_and_immutable_bundled_font():
    assert (V2 / 'NotoSans-Regular.ttf').read_bytes() == (PRISTINE / 'NotoSans-Regular.ttf').read_bytes()
    values = dict(image=torch.zeros(3, 80, 160, 3), text='Saved graph\nλ漢字')
    actual = asyncio.run(converted.NODE_CLASS_MAPPINGS['ControlNetAuxSimpleAddText'].execute(**values)).result
    compare(actual, expected('ControlNetAuxSimpleAddText', values))
    assert actual[0].shape == (1, 80, 160, 3) and actual[0].dtype == torch.float32
    assert torch.count_nonzero(actual[0]) > 0
    with pytest.raises(ValueError, match='annotation text'):
        asyncio.run(converted.NODE_CLASS_MAPPINGS['ControlNetAuxSimpleAddText'].execute(image=values['image'], text='x' * 65537))


def test_selector_preserves_catalogue_and_plain_passthrough():
    options = converted.SCHEMAS['ControlNetPreprocessorSelector']['inputs']['required']['preprocessor'][0]
    for text in [*options, 'non-catalogue source passthrough']:
        result = asyncio.run(converted.NODE_CLASS_MAPPINGS['ControlNetPreprocessorSelector'].execute(preprocessor=text)).result
        assert result == expected('ControlNetPreprocessorSelector', dict(preprocessor=text))


@pytest.mark.parametrize('seed', [0, 1, 2 ** 64 - 1, -1])
def test_shuffle_seed_and_render_local_rng_semantics(seed):
    values = case('ShufflePreprocessor') | dict(seed=seed)
    before = np.random.get_state()
    try:
        if seed < 0:
            with pytest.raises(ValueError):
                expected('ShufflePreprocessor', values)
            with pytest.raises(ValueError):
                asyncio.run(converted.NODE_CLASS_MAPPINGS['ShufflePreprocessor'].execute(**values))
            return
        actual = asyncio.run(converted.NODE_CLASS_MAPPINGS['ShufflePreprocessor'].execute(**values)).result
        after = np.random.get_state()
        np.random.set_state(before)
        compare(actual, expected('ShufflePreprocessor', values))
        reference_after = np.random.get_state()
        assert all(np.array_equal(a, b) for a, b in zip(after, reference_after))
    finally:
        np.random.set_state(before)


def test_shuffle_projected_noise_guard_precedes_algorithm(monkeypatch):
    monkeypatch.setitem(converted._algorithms.IMPLEMENTED, 'ShufflePreprocessor', lambda: pytest.fail('algorithm reached'))
    values = case('ShufflePreprocessor') | dict(image=torch.zeros(1, 1, 16000, 3), resolution=512)
    with pytest.raises(ValueError, match='projected shuffle'):
        asyncio.run(converted.NODE_CLASS_MAPPINGS['ShufflePreprocessor'].execute(**values))


@pytest.mark.parametrize('resolution', [64, 512, 768])
def test_guided_tile_preserves_ignored_resolution(resolution):
    values = case('TTPlanet_TileGF_Preprocessor')
    values['resolution'] = resolution
    actual = asyncio.run(converted.NODE_CLASS_MAPPINGS['TTPlanet_TileGF_Preprocessor'].execute(**values)).result
    compare(actual, expected('TTPlanet_TileGF_Preprocessor', values))
    assert actual[0].shape == values['image'].shape


@pytest.mark.parametrize('name,changes', [('TilePreprocessor', {'pyrUp_iters': 33}), ('TTPlanet_TileGF_Preprocessor', {'scale_factor': 1e-8}), ('TTPlanet_TileSimple_Preprocessor', {'blur_strength': 257})])
def test_tile_projected_work_is_denied_before_algorithm(monkeypatch, name, changes):
    values = {**case(name), **changes}
    monkeypatch.setitem(converted._algorithms.IMPLEMENTED, name, lambda: pytest.fail('algorithm reached'))
    with pytest.raises(ValueError, match='bounded compute'):
        asyncio.run(converted.NODE_CLASS_MAPPINGS[name].execute(**values))


@pytest.mark.parametrize('black', [False, True])
def test_inpaint_exact_mask_interpolation_and_batch(black):
    values = case('InpaintPreprocessor') | dict(black_pixel_for_xinsir_cn=black)
    compare(asyncio.run(converted.NODE_CLASS_MAPPINGS['InpaintPreprocessor'].execute(**values)).result,
            expected('InpaintPreprocessor', values))


def test_projected_bounds_precede_algorithm_allocation(monkeypatch):
    def forbidden(*args, **kwargs): raise AssertionError('algorithm ran before bounds')
    monkeypatch.setattr(converted._algorithms.Canny_Edge_Preprocessor, 'execute', forbidden)
    with pytest.raises(ValueError, match='projected'):
        asyncio.run(converted.NODE_CLASS_MAPPINGS['CannyEdgePreprocessor'].execute(image=torch.ones(1, 1, 16384, 3), resolution=512))


def test_all_implemented_real_guest_paths_fresh_roots_and_raw_denial(tmp_path):
    fresh = tmp_path / 'fresh'; shutil.copytree(V2, fresh)
    async def run():
        pids = []
        for root_index, root in enumerate((V2, fresh)):
            package = load('_many_aux_guest_' + str(root_index), root)
            refs = _sdk.InProcessRefResolver()
            session = await GuestSession('many-control-aux', guest_runtime_root=root).start()
            try:
                for name in IDS:
                    cls = package.NODE_CLASS_MAPPINGS[name]; values = case(name)
                    plan = _sdk.ExecutionPlan(prompt_id='aux-helpers', node_id=name, node_type=cls.__name__,
                        node_module=cls.__module__, inputs=await _sdk.wrap_inputs(refs, values),
                        input_mode='values', permissions=('raw',))
                    runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps())
                    result = await session.execute(plan, runtime, capabilities=('raw',))
                    resolved = [await refs.resolve(v) if isinstance(v, _sdk.Ref) else v for v in result.result]
                    compare(resolved, expected(name, values))
                    if name == 'ControlNetPreprocessorSelector':
                        result = await session.execute(plan, runtime, capabilities=())
                        compare(result.result, expected(name, values))
                    else:
                        with pytest.raises(Exception, match='raw'):
                            await session.execute(plan, runtime, capabilities=())
                pids.append(session.last_guest_pid)
                assert pids[-1] != os.getpid()
            finally: await session.kill()
        assert len(set(pids)) == 2
    asyncio.run(run())


def test_all_implemented_production_manifest_outer_outputs():
    loaded = packdb.load_pack(PRISTINE.parent, mount_name='custom_nodes.many_control_aux_outer')
    async def run():
        class Backend:
            session = None
            async def dispatch(self, plan, local_call, runtime):
                if self.session is None:
                    self.session = await GuestSession('many-aux-outer', guest_runtime_root=V2).start()
                plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs, plan.input_types)
                return await self.session.execute(plan, runtime, capabilities=plan.permissions)
        previous = _sdk.providers.execution_backend
        backend = Backend(); _sdk.providers.register_execution_backend(backend)
        try:
            for name in IDS:
                cls = loaded.node_mappings[name]; values = case(name)
                result = await execution._async_map_node_over_list(prompt_id='aux-outer', unique_id=name,
                    obj=cls, input_data_all={k:[v] for k,v in values.items()}, func=cls.FUNCTION, v3_data=None)
                assert len(result) == 1
                compare(result[0].result, expected(name, values))
        finally:
            _sdk.providers.register_execution_backend(previous)
            if backend.session: await backend.session.kill()
    asyncio.run(run())
