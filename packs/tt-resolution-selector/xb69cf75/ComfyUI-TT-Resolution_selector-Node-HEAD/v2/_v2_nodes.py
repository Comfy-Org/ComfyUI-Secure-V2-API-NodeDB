"""Public V2 schema; preserve the complete original resolution method."""
from comfy_api.latest import io
from .nodes.resolution_selector import TTResolutionSelector as _Original


class TTResolutionSelector(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="TTResolutionSelector", display_name="TT分辨率选择器",
            category="utils",
            inputs=[
                io.Boolean.Input("use_custom_resolution", default=False,
                    label_on="开启自定义", label_off="关闭自定义"),
                io.Combo.Input("resolution", options=[
                        '3072x2048 (横屏)',
                        '2048x3072 (竖屏)',
                        '640x960 (2:3) (竖屏)',
                        '960x640 (3:2) (横屏)',
                        '832x1216 (13:19) (竖屏)',
                        '1216x832 (19:13) (横屏)',
                        '1024x1536 (2:3) (竖屏)',
                        '1536x1024 (3:2) (横屏)',
                        '1280x720 (16:9) (横屏)',
                        '1920x1080 (16:9) (横屏)',
                        '720x1280 (9:16) (竖屏)',
                        '1080x1920 (9:16) (竖屏)',
                        '1344x768 (7:4) (横屏)',
                        '768x1344 (4:7) (竖屏)',
                        '1152x896 (9:7) (横屏)',
                        '896x1152 (7:9) (竖屏)',
                        '480x832 (3:5.2) (竖屏)',
                        '832x480 (5.2:3) (横屏)',
                        '480x854 (9:16) (竖屏)',
                        '854x480 (16:9) (横屏)',
                        '512x512 (1:1) (方形)',
                        '768x768 (1:1) (方形)',
                        '1024x1024 (1:1) (方形)',
                        '512x768 (2:3) (竖屏)',
                        '768x512 (3:2) (横屏)',
                        '512x896 (4:7) (竖屏)',
                        '896x512 (7:4) (横屏)',
                    ],
                    default="1024x1024 (1:1) (方形)"),
                io.Int.Input("custom_width", default=1024, min=64, max=8192, step=1),
                io.Int.Input("custom_height", default=1024, min=64, max=8192, step=1),
            ],
            outputs=[io.Int.Output(display_name="width"), io.Int.Output(display_name="height")],
        )

    @classmethod
    def execute(cls, use_custom_resolution, resolution, custom_width, custom_height):
        return io.NodeOutput(*_Original().get_resolution(
            use_custom_resolution, resolution, custom_width, custom_height))
