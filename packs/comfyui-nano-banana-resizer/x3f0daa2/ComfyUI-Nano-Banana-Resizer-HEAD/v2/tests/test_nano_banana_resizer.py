import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nano_banana_resizer import NanoBananaSizeCalculator


class FakeImage:
    """Small tensor-shaped stand-in; no torch dependency is needed."""

    def __init__(self, height, width):
        self.shape = (1, height, width, 3)


class NanoBananaResizerTests(unittest.TestCase):
    # Google AI image-generation dimensions. Values are (width, height).
    NB1 = {
        "1:1": (1024, 1024), "2:3": (832, 1248), "3:2": (1248, 832),
        "3:4": (864, 1184), "4:3": (1184, 864), "4:5": (896, 1152),
        "5:4": (1152, 896), "9:16": (768, 1344), "16:9": (1344, 768),
        "21:9": (1536, 672),
    }
    PRO = {
        "1:1": (1024, 1024), "2:3": (848, 1264), "3:2": (1264, 848),
        "3:4": (896, 1200), "4:3": (1200, 896), "4:5": (928, 1152),
        "5:4": (1152, 928), "9:16": (768, 1376), "16:9": (1376, 768),
        "21:9": (1584, 672),
    }
    FLASH = {
        **PRO,
        "1:4": (512, 2048), "1:8": (384, 3072),
        "4:1": (2048, 512), "8:1": (3072, 384),
    }

    METHODS = ("Clamp (reccomended)", "Dynamic (legacy)", "Static")
    PRO_PRESETS = ("NB 2 (1K)", "NB 2 (2K)", "NB 2 (4K)")
    PRO_SCALES = {"NB 2 (1K)": 1, "NB 2 (2K)": 2, "NB 2 (4K)": 4}
    FLASH_PRESETS = (
        "Nano Banana 2 Flash (1K)",
        "Nano Banana 2 Flash (2K)",
        "Nano Banana 2 Flash (4K)",
    )
    FLASH_SCALES = {
        "Nano Banana 2 Flash (1K)": 1,
        "Nano Banana 2 Flash (2K)": 2,
        "Nano Banana 2 Flash (4K)": 4,
    }

    def setUp(self):
        self.calculator = NanoBananaSizeCalculator()

    def calculate(self, width, height, preset, method, aspect_ratio=None):
        kwargs = {} if aspect_ratio is None else {"aspect_ratio": aspect_ratio}
        return self.calculator.calculate_size(
            FakeImage(height, width), preset, method, **kwargs
        )

    def test_regression_3571x4464_maps_to_4k_4x5_for_every_method(self):
        for method in self.METHODS:
            for aspect_ratio in ("auto", "4:5"):
                result = self.calculate(3571, 4464, "NB 2 (4K)", method, aspect_ratio)
                self.assertEqual(result[:2], (3712, 4608), (method, aspect_ratio))
                self.assertEqual(result[3], "4:5", (method, aspect_ratio))

    def test_scaled_nominal_ratios_return_the_same_ratio_bucket(self):
        for preset, scale in self.PRO_SCALES.items():
            for ratio, (width, height) in self.PRO.items():
                for method in self.METHODS:
                    expected = (width * scale, height * scale)
                    for input_scale in (1, 100, 10000):
                        result = self.calculate(
                            width * input_scale, height * input_scale,
                            preset, method, "auto",
                        )
                        self.assertEqual(result[:2], expected, (preset, method, ratio, input_scale))
                        self.assertEqual(result[3], ratio, (preset, method, ratio, input_scale))

    def test_every_official_nb1_dimension_maps_to_itself(self):
        for ratio, expected in self.NB1.items():
            for method in self.METHODS:
                for requested_ratio in ("auto", ratio):
                    result = self.calculate(*expected, "NB 1", method, requested_ratio)
                    self.assertEqual(result[:2], expected, (method, ratio, requested_ratio))
                    self.assertEqual(result[3], ratio, (method, ratio, requested_ratio))

    def test_every_official_pro_dimension_maps_to_itself(self):
        for preset, scale in self.PRO_SCALES.items():
            for ratio, (width, height) in self.PRO.items():
                expected = (width * scale, height * scale)
                for method in self.METHODS:
                    for requested_ratio in ("auto", ratio):
                        result = self.calculate(*expected, preset, method, requested_ratio)
                        self.assertEqual(result[:2], expected, (preset, method, ratio, requested_ratio))
                        self.assertEqual(result[3], ratio, (preset, method, ratio, requested_ratio))

    def test_every_official_flash_dimension_maps_to_itself(self):
        for preset, scale in self.FLASH_SCALES.items():
            for ratio, (width, height) in self.FLASH.items():
                expected = (width * scale, height * scale)
                for method in self.METHODS:
                    for requested_ratio in ("auto", ratio):
                        result = self.calculate(*expected, preset, method, requested_ratio)
                        self.assertEqual(result[:2], expected, (preset, method, ratio, requested_ratio))
                        self.assertEqual(result[3], ratio, (preset, method, ratio, requested_ratio))

    def test_auto_detects_portrait_and_landscape(self):
        for preset in ("NB 1", "NB 2 (2K)", "Nano Banana 2 Flash (2K)"):
            for method in self.METHODS:
                portrait = self.calculate(900, 1200, preset, method, "auto")
                landscape = self.calculate(1200, 900, preset, method, "auto")
                self.assertGreater(portrait[0], 0)
                self.assertGreater(portrait[1], 0)
                self.assertGreater(landscape[0], 0)
                self.assertGreater(landscape[1], 0)
                self.assertLess(portrait[0], portrait[1])
                self.assertGreater(landscape[0], landscape[1])

    def test_node_output_interface_and_widget_choices_are_stable(self):
        self.assertEqual(
            NanoBananaSizeCalculator.RETURN_TYPES,
            ("INT", "INT", "STRING", "STRING"),
        )
        self.assertEqual(
            NanoBananaSizeCalculator.RETURN_NAMES,
            ("width", "height", "info", "aspect_ratio"),
        )
        widgets = NanoBananaSizeCalculator.INPUT_TYPES()["required"]
        self.assertEqual(list(widgets), ["image", "preset", "method"])
        self.assertEqual(widgets["image"], ("IMAGE",))
        self.assertEqual(
            widgets["preset"][0],
            [
                "NB 1",
                "NB 2 (1K)",
                "NB 2 (2K)",
                "NB 2 (4K)",
                "Nano Banana 2 Flash (1K)",
                "Nano Banana 2 Flash (2K)",
                "Nano Banana 2 Flash (4K)",
            ],
        )
        self.assertEqual(
            widgets["method"][0],
            list(self.METHODS),
        )
        self.assertEqual(
            NanoBananaSizeCalculator.INPUT_TYPES()["optional"]["aspect_ratio"][0],
            [
                "auto", "1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4",
                "9:16", "16:9", "21:9", "1:4", "1:8", "4:1", "8:1",
            ],
        )

    def test_extreme_positive_dimensions_remain_valid(self):
        for width, height in ((1, 1), (2, 100000), (100000, 2), (10**9, 10**9)):
            result = self.calculate(width, height, "Nano Banana 2 Flash (4K)", self.METHODS[0])
            self.assertIsInstance(result[0], int)
            self.assertIsInstance(result[1], int)
            self.assertGreater(result[0], 0)
            self.assertGreater(result[1], 0)

    def test_invalid_dimensions_preset_method_and_aspect_ratio_raise_value_error(self):
        cases = (
            (0, 100, "NB 1", self.METHODS[0], "auto"),
            (-1, 100, "NB 1", self.METHODS[0], "auto"),
            (100, 0, "NB 1", self.METHODS[0], "auto"),
            (100, -1, "NB 1", self.METHODS[0], "auto"),
            (100, 100, "missing preset", self.METHODS[0], "auto"),
            (100, 100, "NB 1", "missing method", "auto"),
            (100, 100, "NB 1", self.METHODS[0], "7:11"),
            (100, 100, "NB 1", self.METHODS[0], "1:8"),
            (100, 100, "NB 2 (2K)", self.METHODS[0], "1:8"),
        )
        for width, height, preset, method, ratio in cases:
            with self.subTest(width=width, height=height, preset=preset, method=method, ratio=ratio):
                with self.assertRaises(ValueError):
                    self.calculate(width, height, preset, method, ratio)


if __name__ == "__main__":
    unittest.main()
