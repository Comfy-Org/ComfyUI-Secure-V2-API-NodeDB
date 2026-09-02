from __future__ import annotations
import ast as _remaining_g_ast
import copy as _remaining_g_copy
import json as _remaining_g_json
import math as _remaining_g_math
import pathlib as _remaining_g_pathlib
import numpy as _remaining_g_np
import torch as _remaining_g_torch
from comfy_api.latest import io as _remaining_g_io, sdk as _remaining_g_sdk
from . import _packload as _remaining_g_packload
from ._tensor_utils import common_upscale as _remaining_g_common_upscale
_remaining_g_HDR_FUNCTIONS = None
_remaining_g_IMAGE_TRANSFORM_EXECUTE = None

def _remaining_g_source_tree(relative_path: str):
    path = _remaining_g_pathlib.Path(_remaining_g_packload.ROOT, *relative_path.split('/'))
    source = path.read_text(encoding='utf-8')
    return (path, source, _remaining_g_ast.parse(source, filename=str(path)))

def _remaining_g_hdr_functions():
    global _remaining_g_HDR_FUNCTIONS
    if _remaining_g_HDR_FUNCTIONS is not None:
        return _remaining_g_HDR_FUNCTIONS
    path, _source, tree = _remaining_g_source_tree('nodes/hdr_preview_node.py')
    names = {'_logc3_decompress', '_linear_to_srgb', '_srgb_to_linear'}
    body = []
    found = set()
    for node in tree.body:
        if isinstance(node, _remaining_g_ast.Assign) and all((isinstance(target, _remaining_g_ast.Name) and target.id.startswith('LC_') for target in node.targets)):
            body.append(_remaining_g_copy.deepcopy(node))
        elif isinstance(node, _remaining_g_ast.FunctionDef) and node.name in names:
            body.append(_remaining_g_copy.deepcopy(node))
            found.add(node.name)
    if found != names:
        raise RuntimeError(f'HDR preview helpers changed in {path}; found {sorted(found)}')
    namespace = {'torch': _remaining_g_torch}
    module = _remaining_g_ast.fix_missing_locations(_remaining_g_ast.Module(body=body, type_ignores=[]))
    exec(compile(module, f'<kjnodes.hdr_preview:{path}>', 'exec'), namespace)
    _remaining_g_HDR_FUNCTIONS = (namespace['_logc3_decompress'], namespace['_linear_to_srgb'], namespace['_srgb_to_linear'])
    return _remaining_g_HDR_FUNCTIONS

def _remaining_g_image_transform_execute():
    global _remaining_g_IMAGE_TRANSFORM_EXECUTE
    if _remaining_g_IMAGE_TRANSFORM_EXECUTE is not None:
        return _remaining_g_IMAGE_TRANSFORM_EXECUTE
    path, _source, tree = _remaining_g_source_tree('nodes/image_transform_node.py')
    helpers = {'_upscale_mask', '_resize_single_channel', '_apply_padding'}
    body = []
    found_helpers = set()
    method = None
    for node in tree.body:
        if isinstance(node, _remaining_g_ast.FunctionDef) and node.name in helpers:
            body.append(_remaining_g_copy.deepcopy(node))
            found_helpers.add(node.name)
        if isinstance(node, _remaining_g_ast.ClassDef) and node.name == 'ImageTransformKJ':
            for item in node.body:
                if isinstance(item, _remaining_g_ast.FunctionDef) and item.name == 'execute':
                    method = _remaining_g_copy.deepcopy(item)
    if found_helpers != helpers or method is None:
        raise RuntimeError(f'ImageTransformKJ compute changed in {path}; helpers {sorted(found_helpers)}, execute={method is not None}')
    method.decorator_list = []
    removed = set()
    transformed = []
    discard_assignments = {'temp_dir', 'pil_img', 'preview_filename'}
    for statement in method.body:
        assigned = None
        if isinstance(statement, _remaining_g_ast.Assign) and len(statement.targets) == 1:
            target = statement.targets[0]
            if isinstance(target, _remaining_g_ast.Name):
                assigned = target.id
        if assigned in discard_assignments:
            removed.add(assigned)
            continue
        if assigned == 'preview_ui':
            statement.value = _remaining_g_ast.Dict(keys=[], values=[])
            removed.add('preview_ui')
        if isinstance(statement, _remaining_g_ast.Expr) and isinstance(statement.value, _remaining_g_ast.Call):
            function = statement.value.func
            if isinstance(function, _remaining_g_ast.Attribute) and function.attr == 'save' and isinstance(function.value, _remaining_g_ast.Name) and (function.value.id == 'pil_img'):
                removed.add('pil_img.save')
                continue
        transformed.append(statement)
    expected = discard_assignments | {'preview_ui', 'pil_img.save'}
    if removed != expected:
        raise RuntimeError(f'ImageTransformKJ preview seam changed in {path}; removed {sorted(removed)}, expected {sorted(expected)}')
    method.body = transformed
    body.append(method)
    utility = _remaining_g_packload.load('utility/utility.py')
    namespace = {'io': _remaining_g_io, 'json': _remaining_g_json, 'math': _remaining_g_math, 'np': _remaining_g_np, 'torch': _remaining_g_torch, 'common_upscale': _remaining_g_common_upscale, 'string_to_color': utility.string_to_color, 'normalize_bboxes': utility.normalize_bboxes, 'bbox_to_bounding_box': utility.bbox_to_bounding_box}
    module = _remaining_g_ast.fix_missing_locations(_remaining_g_ast.Module(body=body, type_ignores=[]))
    exec(compile(module, f'<kjnodes.image_transform:{path}>', 'exec'), namespace)
    _remaining_g_IMAGE_TRANSFORM_EXECUTE = namespace['execute']
    return _remaining_g_IMAGE_TRANSFORM_EXECUTE

def _remaining_g_preview_entries(payload: dict) -> list[dict]:
    entries = payload.get('images') if isinstance(payload, dict) else None
    if not isinstance(entries, list) or not entries:
        raise RuntimeError('ctx.ui.preview_images returned no image descriptors')
    return entries

class HDRPreviewKJSecure(_remaining_g_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw', 'ui')

    @classmethod
    def define_schema(cls) -> _remaining_g_io.Schema:
        return _remaining_g_io.Schema(node_id='HDRPreviewKJSecure', display_name='🔒 HDR Preview KJ (secure)', category='KJNodes/image', is_output_node=True, is_experimental=True, description='Realtime exposure preview for HDR-compressed images, with the baked sRGB output computed inside a secure guest.', inputs=[_remaining_g_io.Image.Input('image'), _remaining_g_io.Float.Input('exposure', default=0.0, min=-10.0, max=10.0, step=0.01), _remaining_g_io.Float.Input('saturation', default=1.0, min=0.0, max=2.0, step=0.01), _remaining_g_io.Float.Input('fps', default=24.0, min=1.0, max=120.0, step=0.1, optional=True), _remaining_g_io.Combo.Input('input_space', options=['logc3', 'linear', 'srgb'], default='logc3', optional=True)], outputs=[_remaining_g_io.Image.Output(display_name='image')])

    @classmethod
    async def execute(cls, image, exposure=0.0, saturation=1.0, fps=24.0, input_space='logc3') -> _remaining_g_io.NodeOutput:
        logc3_decompress, linear_to_srgb, srgb_to_linear = _remaining_g_hdr_functions()
        pixels = await image.raw()
        batch, height, width, _channels = pixels.shape
        device = pixels.device
        exposure_mul = 2.0 ** exposure
        luma_weights = _remaining_g_torch.tensor([0.2126, 0.7152, 0.0722], device=device)
        bytes_per_frame = height * width * 3 * 4
        chunk_size = max(1, min(batch, int(1000000000 // max(bytes_per_frame * 10, 1))))
        norm_scale = 1.0
        if input_space == 'linear':
            max_value = float(pixels[..., :3].max().item())
            norm_scale = max_value if max_value > 1.0 else 1.0
        preview_chunks = []
        srgb_chunks = []
        for start in range(0, batch, chunk_size):
            end = min(start + chunk_size, batch)
            image_rgb = pixels[start:end, ..., :3].float().to(device, non_blocking=True)
            if input_space == 'linear':
                preview = (image_rgb / norm_scale).clamp(0.0, 1.0)
            else:
                preview = image_rgb.clamp(0.0, 1.0)
            quantized = _remaining_g_torch.floor(preview * 255.0 + 0.5)
            preview_chunks.append(((quantized + 0.25) / 255.0).clamp(0.0, 1.0))
            if input_space == 'logc3':
                hdr = logc3_decompress(image_rgb).clamp(min=0.0)
            elif input_space == 'srgb':
                hdr = srgb_to_linear(image_rgb).clamp(min=0.0)
            else:
                hdr = image_rgb.clamp(min=0.0)
            exposed = hdr * exposure_mul
            luma = (exposed * luma_weights.to(exposed.dtype)).sum(dim=-1, keepdim=True)
            saturated = (luma + (exposed - luma) * saturation).clamp(min=0.0)
            if input_space == 'srgb':
                tonemapped = saturated.clamp(0.0, 1.0)
            else:
                tonemapped = saturated / (1.0 + saturated)
            srgb_chunks.append(linear_to_srgb(tonemapped).cpu())
        preview_ref = await _remaining_g_sdk.ImageRef._from_raw(_remaining_g_torch.cat(preview_chunks, dim=0))
        broker_ui = await _remaining_g_sdk.ctx().ui.preview_images(preview_ref)
        entries = _remaining_g_preview_entries(broker_ui)
        frames = [{'filename': entry['filename'], 'type': entry.get('type', 'temp')} for entry in entries]
        srgb = _remaining_g_torch.cat(srgb_chunks, dim=0)
        output = await _remaining_g_sdk.ImageRef._from_raw(srgb)
        data = {'frames': frames, 'width': int(width), 'height': int(height), 'fps': float(fps), 'input_space': input_space, 'linear_scale': float(norm_scale), 'frame_count': int(batch), 'exposure': float(exposure), 'saturation': float(saturation)}
        return _remaining_g_io.NodeOutput(output, ui={'hdr_preview_data': [data]})

def _remaining_g_padding_inputs():
    return [_remaining_g_io.Int.Input('pad_top', default=0, min=0, max=16384, step=1), _remaining_g_io.Int.Input('pad_bottom', default=0, min=0, max=16384, step=1), _remaining_g_io.Int.Input('pad_left', default=0, min=0, max=16384, step=1), _remaining_g_io.Int.Input('pad_right', default=0, min=0, max=16384, step=1)]

NODE_CLASS_MAPPINGS = {
    'HDRPreviewKJSecure': HDRPreviewKJSecure,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    'HDRPreviewKJSecure': '🔒 HDR Preview KJ (secure)',
}
