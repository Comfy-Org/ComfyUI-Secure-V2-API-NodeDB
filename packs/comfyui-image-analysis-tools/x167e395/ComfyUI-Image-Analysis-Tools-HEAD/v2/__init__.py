from comfy_api.latest import io

class RGBHistogramRenderer(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('inspect', 'raw')
    ALGORITHM = 'rgb_histogram_renderer'

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='RGB Histogram Renderer', display_name='RGB Histogram Renderer', category='Image Analysis', inputs=[io.Image.Input('image')], outputs=[io.Image.Output('image')])

    @classmethod
    async def execute(cls, **fields):
        from ._execute import execute
        return await execute(cls.ALGORITHM, fields)

class SharpnessFocusScore(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('inspect', 'raw')
    ALGORITHM = 'sharpness_focus_score'

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='Sharpness / Focus Score', display_name='Sharpness/Focus Score', category='Image Analysis', inputs=[io.Image.Input('image'), io.Combo.Input('method', options=['Laplacian', 'Tenengrad', 'Hybrid'], default='Hybrid'), io.Boolean.Input('visualize_edges', default=False)], outputs=[io.Float.Output('sharpness_score'), io.Image.Output('edge_visualization'), io.String.Output('interpretation')])

    @classmethod
    async def execute(cls, **fields):
        from ._execute import execute
        return await execute(cls.ALGORITHM, fields)

class NoiseEstimation(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('inspect', 'raw')
    ALGORITHM = 'noise_estimation_basic'

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='Noise Estimation', display_name='Noise Estimation', category='Image Analysis', inputs=[io.Image.Input('image'), io.Int.Input('block_size', default=32, min=8, max=128, step=8), io.Boolean.Input('visualize_noise_map', default=True)], outputs=[io.Float.Output('noise_score'), io.Image.Output('noise_map')])

    @classmethod
    async def execute(cls, **fields):
        from ._execute import execute
        return await execute(cls.ALGORITHM, fields)

class ContrastAnalysis(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('inspect', 'raw')
    ALGORITHM = 'contrast_analysis'

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='Contrast Analysis', display_name='Contrast Analysis', category='Image Analysis', inputs=[io.Image.Input('image'), io.Combo.Input('method', options=['Global', 'Local', 'Hybrid'], default='Hybrid'), io.Combo.Input('comparison_method', options=['Michelson', 'RMS', 'Weber'], default='RMS'), io.Int.Input('block_size', default=32, min=8, max=128, step=8), io.Boolean.Input('visualize_contrast_map', default=True)], outputs=[io.Float.Output('contrast_score'), io.Image.Output('contrast_map')])

    @classmethod
    async def execute(cls, **fields):
        from ._execute import execute
        return await execute(cls.ALGORITHM, fields)

class EntropyAnalysis(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('inspect', 'raw')
    ALGORITHM = 'entropy_analysis'

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='Entropy Analysis', display_name='Entropy Analysis', category='Image Analysis', inputs=[io.Image.Input('image'), io.Int.Input('block_size', default=32, min=8, max=128, step=8), io.Boolean.Input('visualize_entropy_map', default=True)], outputs=[io.Float.Output('entropy_score'), io.Image.Output('entropy_map'), io.String.Output('interpretation')])

    @classmethod
    async def execute(cls, **fields):
        from ._execute import execute
        return await execute(cls.ALGORITHM, fields)

class BlurDetection(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('inspect', 'raw')
    ALGORITHM = 'blur_detection'

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='Blur Detection', display_name='Blur Detection', category='Image Analysis', inputs=[io.Image.Input('image'), io.Int.Input('block_size', default=32, min=8, max=128, step=8), io.Boolean.Input('visualize_blur_map', default=True)], outputs=[io.Float.Output('blur_score'), io.Image.Output('blur_map'), io.String.Output('interpretation')])

    @classmethod
    async def execute(cls, **fields):
        from ._execute import execute
        return await execute(cls.ALGORITHM, fields)

class EdgeDensityAnalysis(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('inspect', 'raw')
    ALGORITHM = 'edge_density_analysis'

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='Edge Density Analysis', display_name='Edge Density Analysis', category='Image Analysis', inputs=[io.Image.Input('image'), io.Combo.Input('method', options=['Canny', 'Sobel'], default='Canny'), io.Int.Input('block_size', default=32, min=8, max=128, step=8), io.Boolean.Input('visualize_edge_map', default=True)], outputs=[io.Float.Output('edge_density_score'), io.Image.Output('edge_density_map'), io.String.Output('interpretation'), io.Image.Output('edge_preview')])

    @classmethod
    async def execute(cls, **fields):
        from ._execute import execute
        return await execute(cls.ALGORITHM, fields)

class ClippingAnalysis(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('inspect', 'raw')
    ALGORITHM = 'clipping_analysis'

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='Clipping Analysis', display_name='Clipping Analysis', category='Image Analysis', inputs=[io.Image.Input('image'), io.Combo.Input('mode', options=['Highlight/Shadow Clipping', 'Saturation Clipping'], default='Highlight/Shadow Clipping'), io.Int.Input('threshold', default=5, min=1, max=50, step=1), io.Boolean.Input('visualize_clipping_map', default=True)], outputs=[io.Float.Output('clipping_score'), io.Image.Output('clipping_map'), io.String.Output('interpretation')])

    @classmethod
    async def execute(cls, **fields):
        from ._execute import execute
        return await execute(cls.ALGORITHM, fields)

class ColorCastDetector(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('inspect', 'raw')
    ALGORITHM = 'color_cast_detector'

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='Color Cast Detector', display_name='Color Cast Detector', category='Image Analysis', inputs=[io.Image.Input('image'), io.Float.Input('tolerance', default=0.05, min=0.01, max=0.5, step=0.01), io.Boolean.Input('visualize_color_bias', default=True), io.Combo.Input('visualization_mode', options=['Channel Difference', 'Neutrality Deviation'], default='Channel Difference')], outputs=[io.Float.Output('cast_score'), io.Image.Output('color_bias_map'), io.String.Output('interpretation')])

    @classmethod
    async def execute(cls, **fields):
        from ._execute import execute
        return await execute(cls.ALGORITHM, fields)

class ColorHarmonyAnalyzer(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('inspect', 'raw')
    ALGORITHM = 'color_harmony_analyzer'

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='Color Harmony Analyzer', display_name='Color Harmony Analyzer', category='Image Analysis', inputs=[io.Image.Input('image'), io.Int.Input('num_clusters', default=3, min=2, max=8), io.Boolean.Input('visualize_harmony', default=True)], outputs=[io.Float.Output('harmony_score'), io.String.Output('harmony_type'), io.Image.Output('hue_wheel_visual')])

    @classmethod
    async def execute(cls, **fields):
        from ._execute import execute
        return await execute(cls.ALGORITHM, fields)

class ColorTemperatureEstimator(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('inspect', 'raw')
    ALGORITHM = 'color_temperature_estimator'

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='Color Temperature Estimator', display_name='Color Temperature Estimator', category='Image Analysis/Color', inputs=[io.Image.Input('image')], outputs=[io.Int.Output('kelvin'), io.String.Output('temperature_label'), io.Image.Output('color_swatch')])

    @classmethod
    async def execute(cls, **fields):
        from ._execute import execute
        return await execute(cls.ALGORITHM, fields)

class DefocusAnalysis(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('inspect', 'raw')
    ALGORITHM = 'defocus_analysis'

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='Defocus Analysis', display_name='Defocus Analysis', category='Image Analysis', inputs=[io.Image.Input('image'), io.Combo.Input('method', options=['FFT Ratio (Sum)', 'FFT Ratio (Mean)', 'Hybrid (Mean+Sum)', 'Edge Width'], default='FFT Ratio (Sum)'), io.Boolean.Input('normalize', default=True), io.Combo.Input('edge_detector', options=['Sobel', 'Canny'], default='Sobel', optional=True)], outputs=[io.Float.Output('defocus_score'), io.String.Output('interpretation'), io.Image.Output('fft_heatmap'), io.Image.Output('high_freq_mask')])

    @classmethod
    async def execute(cls, **fields):
        from ._execute import execute
        return await execute(cls.ALGORITHM, fields)
NODE_CLASS_MAPPINGS = {'RGB Histogram Renderer': RGBHistogramRenderer, 'Sharpness / Focus Score': SharpnessFocusScore, 'Noise Estimation': NoiseEstimation, 'Contrast Analysis': ContrastAnalysis, 'Entropy Analysis': EntropyAnalysis, 'Blur Detection': BlurDetection, 'Edge Density Analysis': EdgeDensityAnalysis, 'Clipping Analysis': ClippingAnalysis, 'Color Cast Detector': ColorCastDetector, 'Color Harmony Analyzer': ColorHarmonyAnalyzer, 'Color Temperature Estimator': ColorTemperatureEstimator, 'Defocus Analysis': DefocusAnalysis}
NODE_DISPLAY_NAME_MAPPINGS = {'RGB Histogram Renderer': 'RGB Histogram Renderer', 'Sharpness / Focus Score': 'Sharpness/Focus Score', 'Noise Estimation': 'Noise Estimation', 'Contrast Analysis': 'Contrast Analysis', 'Entropy Analysis': 'Entropy Analysis', 'Blur Detection': 'Blur Detection', 'Edge Density Analysis': 'Edge Density Analysis', 'Clipping Analysis': 'Clipping Analysis', 'Color Cast Detector': 'Color Cast Detector', 'Color Harmony Analyzer': 'Color Harmony Analyzer', 'Color Temperature Estimator': 'Color Temperature Estimator', 'Defocus Analysis': 'Defocus Analysis'}
WEB_DIRECTORY = './web/js'
