"""Exact Nano Banana aspect-ratio and resolution lookup for ComfyUI."""

from typing import Dict, Tuple


class NanoBananaSizeCalculator:
    """Select a documented Nano Banana resolution for an input image."""

    # Source: https://ai.google.dev/gemini-api/docs/image-generation?hl=pl
    _NB1_RESOLUTIONS: Dict[str, Tuple[int, int]] = {
        "1:1": (1024, 1024), "2:3": (832, 1248), "3:2": (1248, 832),
        "3:4": (864, 1184), "4:3": (1184, 864), "4:5": (896, 1152),
        "5:4": (1152, 896), "9:16": (768, 1344), "16:9": (1344, 768),
        "21:9": (1536, 672),
    }
    _PRO_1K_RESOLUTIONS: Dict[str, Tuple[int, int]] = {
        "1:1": (1024, 1024), "2:3": (848, 1264), "3:2": (1264, 848),
        "3:4": (896, 1200), "4:3": (1200, 896), "4:5": (928, 1152),
        "5:4": (1152, 928), "9:16": (768, 1376), "16:9": (1376, 768),
        "21:9": (1584, 672),
    }
    _FLASH_EXTRA_RESOLUTIONS: Dict[str, Tuple[int, int]] = {
        "1:4": (512, 2048), "1:8": (384, 3072), "4:1": (2048, 512),
        "8:1": (3072, 384),
    }
    _PRESETS = (
        "NB 1", "NB 2 (1K)", "NB 2 (2K)", "NB 2 (4K)",
        "Nano Banana 2 Flash (1K)", "Nano Banana 2 Flash (2K)",
        "Nano Banana 2 Flash (4K)",
    )
    _METHODS = ("Clamp (reccomended)", "Dynamic (legacy)", "Static")
    ASPECT_RATIOS = [
        "auto", "1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4",
        "9:16", "16:9", "21:9", "1:4", "1:8", "4:1", "8:1",
    ]
    SUPPORTED_ARS = {
        ratio: int(ratio.split(":")[0]) / int(ratio.split(":")[1])
        for ratio in ASPECT_RATIOS if ratio != "auto"
    }

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "image": ("IMAGE",),
            "preset": (list(cls._PRESETS), {"default": "NB 2 (2K)"}),
            "method": (list(cls._METHODS), {"default": "Clamp (reccomended)"}),
        }, "optional": {
            "aspect_ratio": (list(cls.ASPECT_RATIOS), {"default": "auto"}),
        }}

    RETURN_TYPES = ("INT", "INT", "STRING", "STRING")
    RETURN_NAMES = ("width", "height", "info", "aspect_ratio")
    FUNCTION = "calculate_size"
    CATEGORY = "image/transform"

    @staticmethod
    def _ratio_distance(width: int, height: int, ratio: str) -> float:
        a, b = (int(part) for part in ratio.split(":"))
        left, right = width * b, height * a
        return max(left, right) / min(left, right)

    def _detect_aspect_ratio(self, w: int, h: int, ratios=None) -> str:
        """Find the nearest nominal ratio using symmetric multiplicative distance."""
        choices = tuple(ratios or self.ASPECT_RATIOS[1:])
        return min(choices, key=lambda ratio: self._ratio_distance(w, h, ratio))

    def _detect_gemini_aspect_ratio(self, w: int, h: int, ratios=None) -> str:
        """Compatibility alias for the corrected nominal-ratio lookup."""
        return self._detect_aspect_ratio(w, h, ratios)

    def _resolution_table(self, preset: str) -> Tuple[str, Dict[str, Tuple[int, int]]]:
        if preset == "NB 1":
            return "NB 1", dict(self._NB1_RESOLUTIONS)
        if preset in ("NB 2 (1K)", "NB 2 (2K)", "NB 2 (4K)"):
            scale = {"NB 2 (1K)": 1, "NB 2 (2K)": 2, "NB 2 (4K)": 4}[preset]
            return f"NB 2 ({scale}K) Pro", {r: (w * scale, h * scale) for r, (w, h) in self._PRO_1K_RESOLUTIONS.items()}
        if preset in ("Nano Banana 2 Flash (1K)", "Nano Banana 2 Flash (2K)", "Nano Banana 2 Flash (4K)"):
            scale = {"Nano Banana 2 Flash (1K)": 1, "Nano Banana 2 Flash (2K)": 2, "Nano Banana 2 Flash (4K)": 4}[preset]
            base = dict(self._PRO_1K_RESOLUTIONS)
            base.update(self._FLASH_EXTRA_RESOLUTIONS)
            return f"Nano Banana 2 Flash ({scale}K)", {r: (w * scale, h * scale) for r, (w, h) in base.items()}
        raise ValueError(f"Unknown preset: {preset!r}. Expected one of {list(self._PRESETS)!r}")

    def calculate_size(self, image, preset: str, method: str, aspect_ratio: str = "auto"):
        if method not in self._METHODS:
            raise ValueError(f"Unknown method: {method!r}. Expected one of {list(self._METHODS)!r}")
        if aspect_ratio not in self.ASPECT_RATIOS:
            raise ValueError(f"Unsupported aspect_ratio: {aspect_ratio!r}. Expected one of {list(self.ASPECT_RATIOS)!r}")
        try:
            _, height, width, _ = image.shape
            width, height = int(width), int(height)
        except (AttributeError, TypeError, ValueError):
            raise ValueError("image must expose a four-dimensional shape (batch, height, width, channels)") from None
        if width <= 0 or height <= 0:
            raise ValueError(f"Image dimensions must be positive; got {width}×{height}")
        version_info, resolutions = self._resolution_table(preset)
        available = tuple(resolutions)
        if aspect_ratio == "auto":
            resolved_aspect_ratio = self._detect_aspect_ratio(width, height, available)
        elif aspect_ratio not in resolutions:
            raise ValueError(f"Aspect ratio {aspect_ratio!r} is not supported by preset {preset!r}; choose one of {list(available)!r}")
        else:
            resolved_aspect_ratio = aspect_ratio
        w_out, h_out = resolutions[resolved_aspect_ratio]
        info = f"{version_info} • {w_out}×{h_out} • AR: {resolved_aspect_ratio} • Input: {width}×{height} • Methods are aliases of exact lookup"
        return (w_out, h_out, info, resolved_aspect_ratio)


NODE_CLASS_MAPPINGS = {"NanoBananaSizeCalculator": NanoBananaSizeCalculator}
NODE_DISPLAY_NAME_MAPPINGS = {"NanoBananaSizeCalculator": "Nano Banana Size Calculator"}
