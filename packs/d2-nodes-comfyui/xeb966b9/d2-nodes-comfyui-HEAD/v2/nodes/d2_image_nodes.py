from comfy_api.latest import io, sdk
from ._secure_boundary import SecureConversionRefusal, data_input


class D2_SaveImage(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        tooltip = 'Datetime -- %date:{yyyy/MM/dd/hh/mm/ss}%\nNode param -- %{Node title}.{key}%\nNode param -- %node:{id}.{key}%'
        return io.Schema(node_id='D2 Save Image', display_name='D2 Save Image', category='D2/Image', inputs=[io.Image.Input('images'), io.String.Input('filename_prefix', default='%date:yyyyMMdd-hhmmss%', tooltip=tooltip), io.Boolean.Input('preview_only', default=False), io.Combo.Input('format', options=['png', 'webp', 'jpeg', 'animated_webp']), io.Boolean.Input('lossless', default=True), io.Int.Input('quality', default=80, min=0, max=100), io.Float.Input('fps', default=6.0, min=0.01, max=1000.0, step=0.01), io.Custom('D2_TD2Pipe').Input('d2_pipe', optional=True), io.Custom('D2_BUTTON').Input('popup_image', optional=True)], outputs=[io.Custom('LIST').Output(display_name='filenames')], hidden=[io.Hidden.prompt, io.Hidden.extra_pnginfo], is_output_node=True)

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 Save Image is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 Save Image is not yet converted to Secure Nodes V2: The source returns absolute host paths and relies on an opaque D2 pipe for A1111 metadata; the public output writer does not preserve that complete contract.')


class D2_SaveImageEagle(D2_SaveImage):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        tooltip = 'Datetime -- %date:{yyyy/MM/dd/hh/mm/ss}%\nNode param -- %{Node title}.{key}%\nNode param -- %node:{id}.{key}%'
        return io.Schema(node_id='D2 Save Image Eagle', display_name='D2 Save Image Eagle', category='D2/Image', inputs=[io.Image.Input('images'), io.String.Input('filename_prefix', default='%date:yyyyMMdd-hhmmss%', tooltip=tooltip), io.Boolean.Input('preview_only', default=False), io.Combo.Input('format', options=['png', 'webp', 'jpeg', 'animated_webp']), io.Boolean.Input('lossless', default=True), io.Int.Input('quality', default=80, min=0, max=100), io.Float.Input('fps', default=6.0, min=0.01, max=1000.0, step=0.01), io.String.Input('eagle_folder', default=''), io.String.Input('memo_text', default=''), io.Custom('D2_TD2Pipe').Input('d2_pipe', optional=True), io.Custom('D2_BUTTON').Input('popup_image', optional=True)], outputs=[io.Custom('LIST').Output(display_name='filenames')], hidden=[io.Hidden.prompt, io.Hidden.extra_pnginfo], is_output_node=True)

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 Save Image Eagle is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 Save Image Eagle is not yet converted to Secure Nodes V2: The purpose includes calling the local Eagle HTTP service; the guest has no network capability for it, and filesystem path outputs are host-only.')


class D2_SendFileEagle(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 Send File Eagle', display_name='D2 Send File Eagle', category='D2/Image', inputs=[io.AnyType.Input('file_path'), io.String.Input('eagle_folder', default=''), io.String.Input('memo_text', multiline=True)], outputs=[], is_output_node=True)

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 Send File Eagle is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 Send File Eagle is not yet converted to Secure Nodes V2: The purpose reads an arbitrary host path and calls a local Eagle HTTP service; neither is a public guest operation.')


class D2_PreviewImage(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 Preview Image', display_name='D2 Preview Image', category='D2/Image', inputs=[io.Image.Input('images'), io.Custom('D2_BUTTON').Input('popup_image', optional=True)], outputs=[], hidden=[io.Hidden.prompt, io.Hidden.extra_pnginfo], is_output_node=True)

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 Preview Image is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 Preview Image is not yet converted to Secure Nodes V2: This node is outside the completed backend subset; its original implementation is not imported into the guest.')


class D2_LoadImage(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 Load Image', display_name='D2 Load Image', category='D2/Image', inputs=[io.Combo.Input('image', options=[], upload=io.UploadType.image, remote=io.RemoteOptions(route='/assets/input', refresh_button=True)), io.String.Input('image_path', force_input=True, optional=True), io.Custom('D2_BUTTON').Input('editor', optional=True)], outputs=[io.Image.Output(display_name='IMAGE'), io.Mask.Output(display_name='MASK'), io.Int.Output(display_name='width'), io.Int.Output(display_name='height'), io.String.Output(display_name='positive'), io.String.Output(display_name='negative'), io.String.Output(display_name='filename'), io.String.Output(display_name='filepath'), io.String.Output(display_name='pnginfo')])

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 Load Image is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 Load Image is not yet converted to Secure Nodes V2: The source accepts arbitrary host paths and emits the resolved absolute path as a STRING; public assets are confined logical refs.')


class D2_LoadFolderImages(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 Load Folder Images', display_name='D2 Load Folder Images', category='D2/Image', inputs=[io.String.Input('folder', default=''), io.String.Input('extension', default='*.*'), io.Boolean.Input('include_subfolders', default=False), io.Combo.Input('sort_by', options=['Name', 'Date', 'Random'], default='Name'), io.Combo.Input('order_by', options=['A-Z', 'Z-A'], default='A-Z'), io.Custom('D2_SIMPLE_TEXT').Input('image_count', optional=True), io.Custom('D2_SEED').Input('queue_seed', optional=True), io.Custom('D2_BUTTON').Input('refresh_btn', optional=True)], outputs=[io.Image.Output(display_name='images'), io.Int.Output(display_name='image_count')])

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 Load Folder Images is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 Load Folder Images is not yet converted to Secure Nodes V2: This node is outside the completed backend subset; its original implementation is not imported into the guest.')


class D2_ImageStack(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 Image Stack', display_name='D2 Image Stack', category='D2/Image', inputs=[io.Int.Input('image_count', default=3, min=1, max=50, step=1)], outputs=[io.Image.Output(display_name='images')], accept_all_inputs=True)

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 Image Stack is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 Image Stack is not yet converted to Secure Nodes V2: This node is outside the completed backend subset; its original implementation is not imported into the guest.')


class D2_ImageMaskStack(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 Image Mask Stack', display_name='D2 Image Mask Stack', category='D2/Image', inputs=[io.Int.Input('image_count', default=3, min=1, max=50, step=1)], outputs=[io.Image.Output(display_name='IMAGE'), io.Mask.Output(display_name='MASK')], accept_all_inputs=True)

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 Image Mask Stack is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 Image Mask Stack is not yet converted to Secure Nodes V2: This node is outside the completed backend subset; its original implementation is not imported into the guest.')


class D2_FolderImageQueue(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 Folder Image Queue', display_name='D2 Folder Image Queue', category='D2/Image', inputs=[io.String.Input('folder', default=''), io.String.Input('extension', default='*.*'), io.Boolean.Input('include_subfolders', default=False), io.Int.Input('start_at', default=0, min=0), io.Boolean.Input('auto_queue', default=True), io.Combo.Input('sort_by', options=['Name', 'Date', 'Random'], default='Name'), io.Combo.Input('order_by', options=['A-Z', 'Z-A'], default='A-Z'), io.Custom('D2_SIMPLE_TEXT').Input('image_count', optional=True), io.Custom('D2_SEED').Input('queue_seed', optional=True), io.Custom('D2_PROGRESS_BAR').Input('progress_bar', optional=True), io.Custom('D2_BUTTON').Input('refresh_btn', optional=True)], outputs=[io.String.Output(display_name='image_path'), io.Int.Output(display_name='image_count')], hidden=[io.Hidden.unique_id])

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 Folder Image Queue is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 Folder Image Queue is not yet converted to Secure Nodes V2: The source enumerates arbitrary host folders and retains per-node queue state across executions; no public guest contract for either behavior.')


class D2_EmptyImageAlpha(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 EmptyImage Alpha', display_name='D2 EmptyImage Alpha', category='D2/Image', inputs=[io.Int.Input('width', default=512, min=1, max=16384, step=1), io.Int.Input('height', default=512, min=1, max=16384, step=1), io.Int.Input('batch_size', default=1, min=1, max=4096), io.Int.Input('red', default=0, min=0, max=255, step=1), io.Int.Input('green', default=0, min=0, max=255, step=1), io.Int.Input('blue', default=0, min=0, max=255, step=1), io.Float.Input('alpha', default=1.0, min=0, max=1.0, step=0.001), io.Boolean.Input('output_alpha', default=True, optional=True), io.Custom('D2_COLOR_CANVAS').Input('sample', optional=True)], outputs=[io.Image.Output(display_name='IMAGE')])

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 EmptyImage Alpha is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 EmptyImage Alpha is not yet converted to Secure Nodes V2: This node is outside the completed backend subset; its original implementation is not imported into the guest.')


class D2_GridImage(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 Grid Image', display_name='D2 Grid Image', category='D2/Image', inputs=[io.Image.Input('images'), io.Int.Input('max_columns', default=3), io.Int.Input('grid_gap', default=0), io.Boolean.Input('swap_dimensions', default=False), io.Int.Input('trigger_count', default=1, min=1, step=1), io.String.Input('title_text', optional=True), io.Int.Input('font_size', default=24, optional=True), io.Custom('D2_SIMPLE_TEXT').Input('count', optional=True), io.Custom('D2_BUTTON').Input('reset', optional=True)], outputs=[io.Image.Output(display_name='images')], hidden=[io.Hidden.unique_id])

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 Grid Image is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 Grid Image is not yet converted to Secure Nodes V2: The source retains tensors in per-node process state across executions and requires a frontend reset route; public guests cannot retain those refs across calls.')


class D2_MosaicFilter(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 Mosaic Filter', display_name='D2 Mosaic Filter', category='D2/Image', inputs=[io.Image.Input('images'), io.Int.Input('dot_size', default=20, min=1, max=512), io.Combo.Input('color_mode', options=['average', 'original']), io.Float.Input('opacity', default=1, min=0, max=1), io.Int.Input('brightness', default=0, min=-100, max=100), io.Boolean.Input('invert_color', default=False)], outputs=[io.Image.Output(display_name='IMAGE')])

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 Mosaic Filter is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 Mosaic Filter is not yet converted to Secure Nodes V2: This node is outside the completed backend subset; its original implementation is not imported into the guest.')


class D2_CutByMask(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 Cut By Mask', display_name='D2 Cut By Mask', category='D2/Image', inputs=[io.Image.Input('images'), io.Mask.Input('mask'), io.Combo.Input('cut_type', options=['mask', 'rectangle', 'square_thumb']), io.Combo.Input('output_size', options=['mask_size', 'image_size']), io.Combo.Input('round_to', options=['none', '8px', '16px', '32px', '64px'], optional=True), io.Int.Input('padding', default=0, min=0, max=1000, optional=True), io.Int.Input('min_width', default=0, min=0, max=10000, optional=True), io.Int.Input('min_height', default=0, min=0, max=10000, optional=True), io.Boolean.Input('output_alpha', default=True, optional=True)], outputs=[io.Image.Output(display_name='image'), io.Mask.Output(display_name='mask'), io.Int.Output(display_name='rect')])

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 Cut By Mask is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 Cut By Mask is not yet converted to Secure Nodes V2: This node is outside the completed backend subset; its original implementation is not imported into the guest.')


class D2_PasteByMask(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 Paste By Mask', display_name='D2 Paste By Mask', category='D2/Image', inputs=[io.Image.Input('img_base'), io.Image.Input('img_paste'), io.Combo.Input('paste_mode', options=['mask', 'rect_full', 'rect_position', 'rect_pos_mask']), io.Combo.Input('multi_mode', options=['pair_last', 'pair_only', 'cross']), io.Mask.Input('mask_opt', optional=True), io.Int.Input('rect_opt', force_input=True, optional=True), io.Int.Input('feather', default=0, min=0, max=100, optional=True), io.Combo.Input('feather_type', options=['simple', 'distance'], default='simple', optional=True)], outputs=[io.Image.Output(display_name='image')])

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 Paste By Mask is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 Paste By Mask is not yet converted to Secure Nodes V2: This node is outside the completed backend subset; its original implementation is not imported into the guest.')


class D2_CreatePoint(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 Create Point', display_name='D2 Create Point', category='D2/Image', inputs=[io.Int.Input('marker_count', default=1, min=1, max=16), io.Combo.Input('mode', options=['absolute', 'relative'], default='absolute'), io.Int.Input('width', default=1024, min=8, max=16384, step=8), io.Int.Input('height', default=1024, min=8, max=16384, step=8), io.Combo.Input('image', options=[''], default='', upload=io.UploadType.image, remote=io.RemoteOptions(route='/assets/input', refresh_button=True)), io.Custom('D2_MARKER_CANVAS').Input('canvas', optional=True), io.String.Input('markers', multiline=True, default='[]', optional=True)], outputs=[io.Image.Output(display_name='image'), io.Int.Output(display_name='width'), io.Int.Output(display_name='height'), io.AnyType.Output(display_name='x_1'), io.AnyType.Output(display_name='y_1')])

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 Create Point is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 Create Point is not yet converted to Secure Nodes V2: This node is outside the completed backend subset; its original implementation is not imported into the guest.')


class D2_CreateMasks(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 Create Masks', display_name='D2 Create Masks', category='D2/Image', inputs=[io.Int.Input('mask_count', default=1, min=1, max=16), io.Int.Input('select_mask', default=1, min=1, max=16), io.Int.Input('width', default=1024, min=8, max=16384, step=8), io.Int.Input('height', default=1024, min=8, max=16384, step=8), io.Combo.Input('image', options=[''], default='', upload=io.UploadType.image, remote=io.RemoteOptions(route='/assets/input', refresh_button=True)), io.Custom('D2_MASK_CANVAS').Input('canvas', optional=True), io.String.Input('masks', multiline=True, default='[]', optional=True)], outputs=[io.Image.Output(display_name='image'), io.Int.Output(display_name='width'), io.Int.Output(display_name='height'), io.Mask.Output(display_name='mask_1')])

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 Create Masks is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 Create Masks is not yet converted to Secure Nodes V2: This node is outside the completed backend subset; its original implementation is not imported into the guest.')


class D2_RandomPoint(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 Random Point', display_name='D2 Random Point', category='D2/Image', inputs=[io.Int.Input('width', default=1024, min=8, max=16384, step=8), io.Int.Input('height', default=1024, min=8, max=16384, step=8), io.Float.Input('min_x', default=0.0, min=0.0, max=1.0, step=0.01), io.Float.Input('max_x', default=1.0, min=0.0, max=1.0, step=0.01), io.Float.Input('min_y', default=0.0, min=0.0, max=1.0, step=0.01), io.Float.Input('max_y', default=1.0, min=0.0, max=1.0, step=0.01), io.Combo.Input('mode', options=['absolute', 'relative'], default='absolute'), io.Combo.Input('number_type', options=['int', 'float'], default='int'), io.Int.Input('seed', default=0, min=0, max=18446744073709551615, control_after_generate=True)], outputs=[io.Int.Output(display_name='width'), io.Int.Output(display_name='height'), io.AnyType.Output(display_name='x'), io.AnyType.Output(display_name='y')])

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 Random Point is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 Random Point is not yet converted to Secure Nodes V2: This node is outside the completed backend subset; its original implementation is not imported into the guest.')


class D2_RandomMask(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 Random Mask', display_name='D2 Random Mask', category='D2/Image', inputs=[io.Int.Input('width', default=1024, min=8, max=16384, step=8), io.Int.Input('height', default=1024, min=8, max=16384, step=8), io.Int.Input('min_width', default=512, min=1, max=16384), io.Int.Input('max_width', default=512, min=1, max=16384), io.Int.Input('min_height', default=512, min=1, max=16384), io.Int.Input('max_height', default=512, min=1, max=16384), io.Int.Input('seed', default=0, min=0, max=18446744073709551615, control_after_generate=True)], outputs=[io.Int.Output(display_name='width'), io.Int.Output(display_name='height'), io.Mask.Output(display_name='mask'), io.Int.Output(display_name='mask_x'), io.Int.Output(display_name='mask_y'), io.Int.Output(display_name='mask_w'), io.Int.Output(display_name='mask_h')])

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 Random Mask is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 Random Mask is not yet converted to Secure Nodes V2: This node is outside the completed backend subset; its original implementation is not imported into the guest.')


NODE_CLASS_MAPPINGS = {
    "D2 Create Point": D2_CreatePoint,
    "D2 Create Masks": D2_CreateMasks,
    "D2 Random Point": D2_RandomPoint,
    "D2 Random Mask": D2_RandomMask,
    "D2 Send File Eagle": D2_SendFileEagle,
    "D2 Save Image Eagle": D2_SaveImageEagle,
    "D2 Save Image": D2_SaveImage,
    "D2 Preview Image": D2_PreviewImage,
    "D2 Load Image": D2_LoadImage,
    "D2 Folder Image Queue": D2_FolderImageQueue,
    "D2 EmptyImage Alpha": D2_EmptyImageAlpha,
    "D2 Grid Image": D2_GridImage,
    "D2 Image Stack": D2_ImageStack,
    "D2 Image Mask Stack": D2_ImageMaskStack,
    "D2 Load Folder Images": D2_LoadFolderImages,
    "D2 Mosaic Filter": D2_MosaicFilter,
    "D2 Cut By Mask": D2_CutByMask,
    "D2 Paste By Mask": D2_PasteByMask,
}
