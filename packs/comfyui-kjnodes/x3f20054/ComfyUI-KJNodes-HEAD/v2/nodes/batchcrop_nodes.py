from __future__ import annotations
from comfy_api.latest import io as _batchcrop_io, sdk as _batchcrop_sdk
from . import _packload as _batchcrop_packload
_batchcrop_MOD = None

def _batchcrop_mod():
    global _batchcrop_MOD
    if _batchcrop_MOD is None:
        _batchcrop_MOD = _batchcrop_packload.load('nodes/batchcrop_nodes.py')
    return _batchcrop_MOD
_batchcrop_Bbox = _batchcrop_io.Custom('BBOX,BOUNDING_BOX')
_batchcrop_BboxOut = _batchcrop_io.Custom('BBOX')

class BboxVisualizeSecure(_batchcrop_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _batchcrop_io.Schema:
        return _batchcrop_io.Schema(node_id='BboxVisualizeSecure', display_name='🔒 Bbox Visualize (secure)', category='KJNodes/masking', description='Visualizes the specified bbox on the image.', inputs=[_batchcrop_io.Image.Input('images'), _batchcrop_Bbox.Input('bboxes'), _batchcrop_io.Int.Input('line_width', default=1, min=1, max=10, step=1), _batchcrop_io.Combo.Input('bbox_format', options=['xywh', 'xyxy'], default='xywh')], outputs=[_batchcrop_io.Image.Output(display_name='images')])

    @classmethod
    async def execute(cls, images, bboxes, line_width, bbox_format) -> _batchcrop_io.NodeOutput:
        pixels = await images.raw()
        out = _batchcrop_mod().BboxVisualize().visualizebbox(bboxes, pixels, line_width, bbox_format)
        return _batchcrop_io.NodeOutput(await _batchcrop_sdk.ImageRef._from_raw(out[0]))

class SplitBboxesSecure(_batchcrop_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _batchcrop_io.Schema:
        return _batchcrop_io.Schema(node_id='SplitBboxesSecure', display_name='🔒 Split Bboxes (secure)', category='KJNodes/masking', description='Splits a batch of bboxes and returns one at index.', inputs=[_batchcrop_Bbox.Input('bboxes'), _batchcrop_io.Int.Input('index', default=0, min=0, max=99999999, step=1)], outputs=[_batchcrop_BboxOut.Output(display_name='bboxes_a'), _batchcrop_BboxOut.Output(display_name='bboxes_b')])

    @classmethod
    async def execute(cls, bboxes, index) -> _batchcrop_io.NodeOutput:
        out = _batchcrop_mod().SplitBboxes().splitbbox(bboxes, index)
        return _batchcrop_io.NodeOutput(out[0], out[1])
from comfy_api.latest import io as _batchcrop_more_io, sdk as _batchcrop_more_sdk
from . import _packload as _batchcrop_more_packload
_batchcrop_more_MOD = None

def _batchcrop_more_mod():
    global _batchcrop_more_MOD
    if _batchcrop_more_MOD is None:
        _batchcrop_more_MOD = _batchcrop_more_packload.load('nodes/batchcrop_nodes.py')
    return _batchcrop_more_MOD
_batchcrop_more_Bbox = _batchcrop_more_io.Custom('BBOX,BOUNDING_BOX')
_batchcrop_more_Indexes = _batchcrop_more_io.Custom('INDEXES')

class BatchCropFromMaskSecure(_batchcrop_more_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _batchcrop_more_io.Schema:
        return _batchcrop_more_io.Schema(node_id='BatchCropFromMaskSecure', display_name='🔒 Batch Crop From Mask (secure)', category='KJNodes/masking', inputs=[_batchcrop_more_io.Image.Input('original_images'), _batchcrop_more_io.Mask.Input('masks'), _batchcrop_more_io.Float.Input('crop_size_mult', default=1.0, min=0.0, max=10.0, step=0.001), _batchcrop_more_io.Float.Input('bbox_smooth_alpha', default=0.5, min=0.0, max=1.0, step=0.01)], outputs=[_batchcrop_more_io.Image.Output(display_name='original_images'), _batchcrop_more_io.Image.Output(display_name='cropped_images'), _batchcrop_more_io.BBOX.Output(display_name='bboxes'), _batchcrop_more_io.Int.Output(display_name='width'), _batchcrop_more_io.Int.Output(display_name='height')])

    @classmethod
    async def execute(cls, original_images, masks, crop_size_mult, bbox_smooth_alpha) -> _batchcrop_more_io.NodeOutput:
        images = await original_images.raw()
        out = _batchcrop_more_mod().BatchCropFromMask().crop(await masks.raw(), images, crop_size_mult, bbox_smooth_alpha)
        return _batchcrop_more_io.NodeOutput(await _batchcrop_more_sdk.ImageRef._from_raw(out[0]), await _batchcrop_more_sdk.ImageRef._from_raw(out[1]), out[2], out[3], out[4])

class BatchCropFromMaskAdvancedSecure(_batchcrop_more_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _batchcrop_more_io.Schema:
        return _batchcrop_more_io.Schema(node_id='BatchCropFromMaskAdvancedSecure', display_name='🔒 Batch Crop From Mask Advanced (secure)', category='KJNodes/masking', inputs=[_batchcrop_more_io.Image.Input('original_images'), _batchcrop_more_io.Mask.Input('masks'), _batchcrop_more_io.Float.Input('crop_size_mult', default=1.0, min=0.0, max=10.0, step=0.01), _batchcrop_more_io.Float.Input('bbox_smooth_alpha', default=0.5, min=0.0, max=1.0, step=0.01)], outputs=[_batchcrop_more_io.Image.Output(display_name='original_images'), _batchcrop_more_io.Image.Output(display_name='cropped_images'), _batchcrop_more_io.Mask.Output(display_name='cropped_masks'), _batchcrop_more_io.Image.Output(display_name='combined_crop_image'), _batchcrop_more_io.Mask.Output(display_name='combined_crop_masks'), _batchcrop_more_io.BBOX.Output(display_name='bboxes'), _batchcrop_more_io.BBOX.Output(display_name='combined_bounding_box'), _batchcrop_more_io.Int.Output(display_name='bbox_width'), _batchcrop_more_io.Int.Output(display_name='bbox_height')])

    @classmethod
    async def execute(cls, original_images, masks, crop_size_mult, bbox_smooth_alpha) -> _batchcrop_more_io.NodeOutput:
        images = await original_images.raw()
        out = _batchcrop_more_mod().BatchCropFromMaskAdvanced().crop(await masks.raw(), images, crop_size_mult, bbox_smooth_alpha)
        return _batchcrop_more_io.NodeOutput(await _batchcrop_more_sdk.ImageRef._from_raw(out[0]), await _batchcrop_more_sdk.ImageRef._from_raw(out[1]), await _batchcrop_more_sdk.MaskRef._from_raw(out[2]), await _batchcrop_more_sdk.ImageRef._from_raw(out[3]), await _batchcrop_more_sdk.MaskRef._from_raw(out[4]), out[5], out[6], out[7], out[8])

class BatchUncropSecure(_batchcrop_more_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _batchcrop_more_io.Schema:
        return _batchcrop_more_io.Schema(node_id='BatchUncropSecure', display_name='🔒 Batch Uncrop (secure)', category='KJNodes/masking', inputs=[_batchcrop_more_io.Image.Input('original_images'), _batchcrop_more_io.Image.Input('cropped_images'), _batchcrop_more_Bbox.Input('bboxes'), _batchcrop_more_io.Float.Input('border_blending', default=0.25, min=0.0, max=1.0, step=0.01), _batchcrop_more_io.Float.Input('crop_rescale', default=1.0, min=0.0, max=10.0, step=0.01), _batchcrop_more_io.Boolean.Input('border_top', default=True), _batchcrop_more_io.Boolean.Input('border_bottom', default=True), _batchcrop_more_io.Boolean.Input('border_left', default=True), _batchcrop_more_io.Boolean.Input('border_right', default=True)], outputs=[_batchcrop_more_io.Image.Output(display_name='IMAGE')])

    @classmethod
    async def execute(cls, original_images, cropped_images, bboxes, border_blending, crop_rescale, border_top, border_bottom, border_left, border_right) -> _batchcrop_more_io.NodeOutput:
        out = _batchcrop_more_mod().BatchUncrop().uncrop(await original_images.raw(), await cropped_images.raw(), bboxes, border_blending, crop_rescale, border_top, border_bottom, border_left, border_right)
        return _batchcrop_more_io.NodeOutput(await _batchcrop_more_sdk.ImageRef._from_raw(out[0]))

class BatchUncropAdvancedSecure(_batchcrop_more_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _batchcrop_more_io.Schema:
        return _batchcrop_more_io.Schema(node_id='BatchUncropAdvancedSecure', display_name='🔒 Batch Uncrop Advanced (secure)', category='KJNodes/masking', inputs=[_batchcrop_more_io.Image.Input('original_images'), _batchcrop_more_io.Image.Input('cropped_images'), _batchcrop_more_io.Mask.Input('cropped_masks'), _batchcrop_more_io.Mask.Input('combined_crop_mask'), _batchcrop_more_Bbox.Input('bboxes'), _batchcrop_more_io.Float.Input('border_blending', default=0.25, min=0.0, max=1.0, step=0.01), _batchcrop_more_io.Float.Input('crop_rescale', default=1.0, min=0.0, max=10.0, step=0.01), _batchcrop_more_io.Boolean.Input('use_combined_mask', default=False), _batchcrop_more_io.Boolean.Input('use_square_mask', default=True), _batchcrop_more_Bbox.Input('combined_bounding_box', optional=True)], outputs=[_batchcrop_more_io.Image.Output(display_name='IMAGE')])

    @classmethod
    async def execute(cls, original_images, cropped_images, cropped_masks, combined_crop_mask, bboxes, border_blending, crop_rescale, use_combined_mask, use_square_mask, combined_bounding_box=None) -> _batchcrop_more_io.NodeOutput:
        out = _batchcrop_more_mod().BatchUncropAdvanced().uncrop(await original_images.raw(), await cropped_images.raw(), await cropped_masks.raw(), await combined_crop_mask.raw(), bboxes, border_blending, crop_rescale, use_combined_mask, use_square_mask, combined_bounding_box)
        return _batchcrop_more_io.NodeOutput(await _batchcrop_more_sdk.ImageRef._from_raw(out[0]))

class BboxToIntSecure(_batchcrop_more_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _batchcrop_more_io.Schema:
        return _batchcrop_more_io.Schema(node_id='BboxToIntSecure', display_name='🔒 Bbox To Int (secure)', category='KJNodes/masking', description='Returns selected index from bounding box list as integers.', inputs=[_batchcrop_more_Bbox.Input('bboxes'), _batchcrop_more_io.Int.Input('index', default=0, min=0, max=99999999, step=1)], outputs=[_batchcrop_more_io.Int.Output(display_name='x_min'), _batchcrop_more_io.Int.Output(display_name='y_min'), _batchcrop_more_io.Int.Output(display_name='width'), _batchcrop_more_io.Int.Output(display_name='height'), _batchcrop_more_io.Int.Output(display_name='center_x'), _batchcrop_more_io.Int.Output(display_name='center_y')])

    @classmethod
    async def execute(cls, bboxes, index) -> _batchcrop_more_io.NodeOutput:
        return _batchcrop_more_io.NodeOutput(*_batchcrop_more_mod().BboxToInt().bboxtoint(bboxes, index))

class FilterZeroMasksAndCorrespondingImagesSecure(_batchcrop_more_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _batchcrop_more_io.Schema:
        return _batchcrop_more_io.Schema(node_id='FilterZeroMasksAndCorrespondingImagesSecure', display_name='🔒 FilterZeroMasksAndCorrespondingImages (secure)', category='KJNodes/masking', description='Filter out all the empty (i.e. all zero) mask in masks  \nAlso filter out all the corresponding images in original_images by indexes if provide  \n  \noriginal_images (optional): If provided, need have same length as masks.', inputs=[_batchcrop_more_io.Mask.Input('masks'), _batchcrop_more_io.Image.Input('original_images', optional=True)], outputs=[_batchcrop_more_io.Mask.Output(display_name='non_zero_masks_out'), _batchcrop_more_io.Image.Output(display_name='non_zero_mask_images_out'), _batchcrop_more_io.Image.Output(display_name='zero_mask_images_out'), _batchcrop_more_Indexes.Output(display_name='zero_mask_images_out_indexes')])

    @classmethod
    async def execute(cls, masks, original_images=None) -> _batchcrop_more_io.NodeOutput:
        images = None if original_images is None else await original_images.raw()
        out = _batchcrop_more_mod().FilterZeroMasksAndCorrespondingImages().filter(await masks.raw(), images)
        return _batchcrop_more_io.NodeOutput(await _batchcrop_more_sdk.MaskRef._from_raw(out[0]), None if out[1] is None else await _batchcrop_more_sdk.ImageRef._from_raw(out[1]), None if out[2] is None else await _batchcrop_more_sdk.ImageRef._from_raw(out[2]), out[3])

class InsertImageBatchByIndexesSecure(_batchcrop_more_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> _batchcrop_more_io.Schema:
        return _batchcrop_more_io.Schema(node_id='InsertImageBatchByIndexesSecure', display_name='🔒 Insert Image Batch By Indexes (secure)', category='KJNodes/image', description='This node is designed to be use with node FilterZeroMasksAndCorrespondingImages\nIt inserts the images_to_insert into images according to insert_indexes\n\nReturns:\n    images_after_insert: updated original images with origonal sequence order', inputs=[_batchcrop_more_io.Image.Input('images'), _batchcrop_more_io.Image.Input('images_to_insert'), _batchcrop_more_Indexes.Input('insert_indexes')], outputs=[_batchcrop_more_io.Image.Output(display_name='images_after_insert')])

    @classmethod
    async def execute(cls, images, images_to_insert, insert_indexes) -> _batchcrop_more_io.NodeOutput:
        out = _batchcrop_more_mod().InsertImageBatchByIndexes().insert(await images.raw(), await images_to_insert.raw(), insert_indexes)
        return _batchcrop_more_io.NodeOutput(await _batchcrop_more_sdk.ImageRef._from_raw(out[0]))

NODE_CLASS_MAPPINGS = {
    'BboxVisualizeSecure': BboxVisualizeSecure,
    'SplitBboxesSecure': SplitBboxesSecure,
    'BatchCropFromMaskSecure': BatchCropFromMaskSecure,
    'BatchCropFromMaskAdvancedSecure': BatchCropFromMaskAdvancedSecure,
    'BatchUncropSecure': BatchUncropSecure,
    'BatchUncropAdvancedSecure': BatchUncropAdvancedSecure,
    'BboxToIntSecure': BboxToIntSecure,
    'FilterZeroMasksAndCorrespondingImagesSecure': FilterZeroMasksAndCorrespondingImagesSecure,
    'InsertImageBatchByIndexesSecure': InsertImageBatchByIndexesSecure,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    'BboxVisualizeSecure': '🔒 Bbox Visualize (secure)',
    'SplitBboxesSecure': '🔒 Split Bboxes (secure)',
    'BatchCropFromMaskSecure': '🔒 Batch Crop From Mask (secure)',
    'BatchCropFromMaskAdvancedSecure': '🔒 Batch Crop From Mask Advanced (secure)',
    'BatchUncropSecure': '🔒 Batch Uncrop (secure)',
    'BatchUncropAdvancedSecure': '🔒 Batch Uncrop Advanced (secure)',
    'BboxToIntSecure': '🔒 Bbox To Int (secure)',
    'FilterZeroMasksAndCorrespondingImagesSecure': '🔒 FilterZeroMasksAndCorrespondingImages (secure)',
    'InsertImageBatchByIndexesSecure': '🔒 Insert Image Batch By Indexes (secure)',
}
