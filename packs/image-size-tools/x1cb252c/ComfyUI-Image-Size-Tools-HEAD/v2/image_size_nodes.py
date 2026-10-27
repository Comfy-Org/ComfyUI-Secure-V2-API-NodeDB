from comfy_api.latest import ComfyExtension, io
from . import _original

class SD15ResolutionNode(io.ComfyNode):
    '\n    SD 1.5 Resolution Calculator\n    \n    Provides optimal resolution presets for Stable Diffusion 1.5 models.\n    All resolutions are validated to be divisible by 8 (VAE constraint).\n    '
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id='SD15ResolutionNode', display_name='SD 1.5 Resolution', category='Image Size Tool',
            inputs=[
                io.Combo.Input('resolution', options=['512×512 (1:1) - Native', '768×512 (3:2) - Landscape', '512×768 (2:3) - Portrait', '768×576 (4:3) - Standard', '576×768 (3:4) - Standard Portrait', '912×512 (16:9) - Widescreen', '512×912 (9:16) - Mobile', '768×768 (1:1) - Large Square']),
            ],
            outputs=[
                io.Int.Output(display_name='width'),
                io.Int.Output(display_name='height'),
                io.String.Output(display_name='aspect_ratio'),
            ],
        )

    @classmethod
    def execute(cls, resolution) -> io.NodeOutput:
        return io.NodeOutput(*_original.SD15ResolutionNode().get_resolution(resolution))


class SDXLResolutionNode(io.ComfyNode):
    '\n    SDXL Resolution Calculator\n    \n    Provides bucket-trained resolution presets for SDXL models.\n    All resolutions target ~1 megapixel and are divisible by 64.\n    Based on the 43-bucket training system for optimal quality.\n    '
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id='SDXLResolutionNode', display_name='SDXL Resolution', category='Image Size Tool',
            inputs=[
                io.Combo.Input('resolution', options=['1024×1024 (1:1) - Native', '1152×896 (9:7) - Landscape', '896×1152 (7:9) - Portrait', '1344×768 (7:4) - Wide', '768×1344 (4:7) - Tall', '1216×832 (19:13) - Cinema', '832×1216 (13:19) - Tall Cinema', '1280×768 (5:3) - Ultrawide', '768×1280 (3:5) - Ultra Portrait', '1536×640 (12:5) - Banner', '640×1536 (5:12) - Skyscraper', '1600×640 (5:2) - Extreme Wide', '640×1600 (2:5) - Extreme Tall']),
            ],
            outputs=[
                io.Int.Output(display_name='width'),
                io.Int.Output(display_name='height'),
                io.String.Output(display_name='aspect_ratio'),
                io.Int.Output(display_name='total_pixels'),
            ],
        )

    @classmethod
    def execute(cls, resolution) -> io.NodeOutput:
        return io.NodeOutput(*_original.SDXLResolutionNode().get_resolution(resolution))


class FluxResolutionNode(io.ComfyNode):
    '\n    Flux.1 Dev Resolution Calculator\n    \n    Provides practical resolution presets for Flux.1 Dev models.\n    No strict divisibility requirements, focused on hardware compatibility\n    and common use cases from 1024x1024 to 2560x1440.\n    '
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id='FluxResolutionNode', display_name='Flux.1 Dev Resolution', category='Image Size Tool',
            inputs=[
                io.Combo.Input('resolution', options=['1024×1024 (1:1) - Native', '1920×1080 (16:9) - Full HD', '1080×1920 (9:16) - Vertical HD', '1536×640 (12:5) - Ultrawide', '640×1536 (5:12) - Ultra Portrait', '1600×1600 (1:1) - High Detail', '1280×720 (16:9) - HD', '720×1280 (9:16) - Vertical HD', '1366×768 (16:9) - Laptop', '768×1366 (9:16) - Vertical Laptop', '2560×1440 (16:9) - 2K']),
            ],
            outputs=[
                io.Int.Output(display_name='width'),
                io.Int.Output(display_name='height'),
                io.String.Output(display_name='aspect_ratio'),
            ],
        )

    @classmethod
    def execute(cls, resolution) -> io.NodeOutput:
        return io.NodeOutput(*_original.FluxResolutionNode().get_resolution(resolution))


class ImageSizeDetectorNode(io.ComfyNode):
    '\n    Image Size Detector\n    \n    Takes an image as input and outputs its dimensions as width and height integers.\n    Useful for determining the size of existing images in your ComfyUI workflow.\n    '
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id='ImageSizeDetectorNode', display_name='Image Size Detector', category='Image Size Tool',
            inputs=[
                io.Image.Input('image'),
            ],
            outputs=[
                io.Int.Output(display_name='width'),
                io.Int.Output(display_name='height'),
            ],
        )

    @classmethod
    async def execute(cls, image) -> io.NodeOutput:
        # The original only reads .shape. Keep its full method unchanged;
        # raw is the existing brokered tensor boundary, explicitly requested.
        return io.NodeOutput(*_original.ImageSizeDetectorNode().detect_size(await image.raw()))


class WAN21ResolutionNode(io.ComfyNode):
    '\n    WAN2.1 Resolution Calculator\n    \n    Provides core video resolution presets for WAN2.1 models.\n    Includes standard 480p and 720p resolutions with option to halve dimensions\n    for lower VRAM usage.\n    '
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id='WAN21ResolutionNode', display_name='WAN2.1 Resolution', category='Image Size Tool',
            inputs=[
                io.Combo.Input('resolution', options=['832×480 (16:9) - 480p Standard', '1280×720 (16:9) - 720p HD', '480×832 (9:16) - 480p Vertical', '720×1280 (9:16) - 720p Vertical']),
                io.Boolean.Input('halve_resolution', default=False),
            ],
            outputs=[
                io.Int.Output(display_name='width'),
                io.Int.Output(display_name='height'),
                io.String.Output(display_name='aspect_ratio'),
                io.Int.Output(display_name='halved_width'),
                io.Int.Output(display_name='halved_height'),
            ],
        )

    @classmethod
    def execute(cls, resolution, halve_resolution) -> io.NodeOutput:
        return io.NodeOutput(*_original.WAN21ResolutionNode().get_resolution(resolution, halve_resolution))


class WAN21AdvancedResolutionNode(io.ComfyNode):
    '\n    WAN2.1 Advanced Resolution Calculator\n    \n    Provides extended video resolution presets for WAN2.1 models.\n    Includes all standard resolutions plus additional aspect ratios and sizes\n    with option to halve dimensions for lower VRAM usage.\n    '
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id='WAN21AdvancedResolutionNode', display_name='WAN2.1 Resolution (Advanced)', category='Image Size Tool',
            inputs=[
                io.Combo.Input('resolution', options=['832×480 (16:9) - 480p Standard', '1280×720 (16:9) - 720p HD', '480×832 (9:16) - 480p Vertical', '720×1280 (9:16) - 720p Vertical', '640×480 (4:3) - Classic 480p', '960×720 (4:3) - Classic 720p', '480×640 (3:4) - Classic Vertical', '720×960 (3:4) - Classic Vertical', '720×720 (1:1) - Square 720p', '480×480 (1:1) - Square 480p', '1024×576 (16:9) - Intermediate', '576×1024 (9:16) - Intermediate Vertical']),
                io.Boolean.Input('halve_resolution', default=False),
            ],
            outputs=[
                io.Int.Output(display_name='width'),
                io.Int.Output(display_name='height'),
                io.String.Output(display_name='aspect_ratio'),
                io.Int.Output(display_name='halved_width'),
                io.Int.Output(display_name='halved_height'),
            ],
        )

    @classmethod
    def execute(cls, resolution, halve_resolution) -> io.NodeOutput:
        return io.NodeOutput(*_original.WAN21AdvancedResolutionNode().get_resolution(resolution, halve_resolution))


NODE_CLASS_MAPPINGS = {
    'SD15ResolutionNode': SD15ResolutionNode,
    'SDXLResolutionNode': SDXLResolutionNode,
    'FluxResolutionNode': FluxResolutionNode,
    'ImageSizeDetectorNode': ImageSizeDetectorNode,
    'WAN21ResolutionNode': WAN21ResolutionNode,
    'WAN21AdvancedResolutionNode': WAN21AdvancedResolutionNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SD15ResolutionNode": "SD 1.5 Resolution",
    "SDXLResolutionNode": "SDXL Resolution", 
    "FluxResolutionNode": "Flux.1 Dev Resolution",
    "ImageSizeDetectorNode": "Image Size Detector",
    "WAN21ResolutionNode": "WAN2.1 Resolution",
    "WAN21AdvancedResolutionNode": "WAN2.1 Resolution (Advanced)",
}


class ImageSizeToolsExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [SD15ResolutionNode, SDXLResolutionNode, FluxResolutionNode, ImageSizeDetectorNode, WAN21ResolutionNode, WAN21AdvancedResolutionNode]


async def comfy_entrypoint() -> ComfyExtension:
    return ImageSizeToolsExtension()
