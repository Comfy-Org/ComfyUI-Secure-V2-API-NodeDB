from .nodes.rgb_histogram_renderer import RGBHistogramRenderer
from .nodes.sharpness_focus_score import SharpnessFocusScore
from .nodes.noise_estimation_basic import NoiseEstimation
from .nodes.contrast_analysis import ContrastAnalysis
from .nodes.entropy_analysis import EntropyAnalysis
from .nodes.blur_detection import BlurDetection
from .nodes.edge_density_analysis import EdgeDensityAnalysis
from .nodes.clipping_analysis import ClippingAnalysis
from .nodes.color_cast_detector import ColorCastDetector
from .nodes.color_harmony_analyzer import ColorHarmonyAnalyzer
from .nodes.color_temperature_estimator import ColorTemperatureEstimator
from .nodes.defocus_analysis import DefocusAnalysis

NODE_CLASS_MAPPINGS = {
    "RGB Histogram Renderer": RGBHistogramRenderer,
    "Sharpness / Focus Score": SharpnessFocusScore,
    "Noise Estimation": NoiseEstimation,
    "Contrast Analysis": ContrastAnalysis,
    "Entropy Analysis": EntropyAnalysis,
    "Blur Detection": BlurDetection,
    "Edge Density Analysis": EdgeDensityAnalysis,
    "Clipping Analysis": ClippingAnalysis,
    "Color Cast Detector": ColorCastDetector,
    "Color Harmony Analyzer": ColorHarmonyAnalyzer,
    "Color Temperature Estimator": ColorTemperatureEstimator,
    "Defocus Analysis": DefocusAnalysis
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RGB Histogram Renderer": "RGB Histogram Renderer",
    "Sharpness / Focus Score": "Sharpness/Focus Score",
    "Noise Estimation": "Noise Estimation",
    "Contrast Analysis": "Contrast Analysis",
    "Entropy Analysis": "Entropy Analysis",
    "Blur Detection": "Blur Detection",
    "Edge Density Analysis": "Edge Density Analysis",
    "Clipping Analysis": "Clipping Analysis",
    "Color Cast Detector": "Color Cast Detector",
    "Color Harmony Analyzer": "Color Harmony Analyzer",
    "Color Temperature Estimator": "Color Temperature Estimator",
    "Defocus Analysis": "Defocus Analysis"

}

WEB_DIRECTORY = "./web/js"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
