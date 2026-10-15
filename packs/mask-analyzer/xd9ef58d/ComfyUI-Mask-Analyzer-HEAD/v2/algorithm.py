import numpy as np
import torch

try:
    import cv2
except ImportError:
    cv2 = None


class MaskAnalyze:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mask": ("MASK",),
                "threshold": ("FLOAT", {
                    "default": 0.5,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.01
                }),
                "min_component_area": ("INT", {
                    "default": 40,
                    "min": 1,
                    "max": 100000,
                    "step": 1
                }),
                "small_component_area": ("INT", {
                    "default": 300,
                    "min": 1,
                    "max": 100000,
                    "step": 1
                }),
                "direct_max_components": ("INT", {
                    "default": 4,
                    "min": 1,
                    "max": 1000,
                    "step": 1
                }),
                "overlay_min_components": ("INT", {
                    "default": 9,
                    "min": 1,
                    "max": 1000,
                    "step": 1
                }),
                "wide_aspect_overlay": ("FLOAT", {
                    "default": 3.2,
                    "min": 1.0,
                    "max": 20.0,
                    "step": 0.1
                }),
                "small_ratio_overlay": ("FLOAT", {
                    "default": 0.45,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.01
                }),
            }
        }

    RETURN_TYPES = ("INT", "INT", "FLOAT", "FLOAT", "FLOAT", "STRING", "BOOLEAN")
    RETURN_NAMES = (
        "component_count",
        "small_component_count",
        "small_component_ratio",
        "aspect_ratio",
        "complexity_score",
        "strategy",
        "use_overlay_mode",
    )
    FUNCTION = "analyze"
    CATEGORY = "Mask Tools"

    def _prepare_mask(self, mask_tensor, threshold):
        if isinstance(mask_tensor, torch.Tensor):
            mask_np = mask_tensor.detach().cpu().numpy()
        else:
            mask_np = np.array(mask_tensor)

        if mask_np.ndim == 3:
            mask_np = mask_np[0]

        binary = (mask_np >= threshold).astype(np.uint8)
        return binary

    def _fallback_components_numpy(self, binary):
        h, w = binary.shape
        visited = np.zeros_like(binary, dtype=np.uint8)
        areas = []

        neighbors = [
            (-1, -1), (-1, 0), (-1, 1),
            (0, -1),           (0, 1),
            (1, -1),  (1, 0),  (1, 1),
        ]

        for y in range(h):
            for x in range(w):
                if binary[y, x] == 1 and visited[y, x] == 0:
                    stack = [(y, x)]
                    visited[y, x] = 1
                    area = 0

                    while stack:
                        cy, cx = stack.pop()
                        area += 1
                        for dy, dx in neighbors:
                            ny, nx = cy + dy, cx + dx
                            if 0 <= ny < h and 0 <= nx < w:
                                if binary[ny, nx] == 1 and visited[ny, nx] == 0:
                                    visited[ny, nx] = 1
                                    stack.append((ny, nx))

                    areas.append(area)

        return areas

    def analyze(
        self,
        mask,
        threshold,
        min_component_area,
        small_component_area,
        direct_max_components,
        overlay_min_components,
        wide_aspect_overlay,
        small_ratio_overlay,
    ):
        binary = self._prepare_mask(mask, threshold)

        ys, xs = np.where(binary > 0)
        if len(xs) == 0 or len(ys) == 0:
            return (0, 0, 0.0, 0.0, 0.0, "direct", False)

        x_min, x_max = xs.min(), xs.max()
        y_min, y_max = ys.min(), ys.max()
        bbox_w = max(1, int(x_max - x_min + 1))
        bbox_h = max(1, int(y_max - y_min + 1))
        aspect_ratio = float(bbox_w / bbox_h)

        if cv2 is not None:
            num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)

            component_areas = []
            for label_id in range(1, num_labels):
                area = int(stats[label_id, cv2.CC_STAT_AREA])
                if area >= min_component_area:
                    component_areas.append(area)
        else:
            all_areas = self._fallback_components_numpy(binary)
            component_areas = [int(a) for a in all_areas if a >= min_component_area]

        component_count = len(component_areas)
        small_component_count = sum(1 for a in component_areas if a <= small_component_area)
        small_component_ratio = (
            float(small_component_count / component_count) if component_count > 0 else 0.0
        )

        score = 0.0
        score += min(component_count * 6.0, 36.0)
        score += min(small_component_ratio * 35.0, 35.0)

        if aspect_ratio > 1.8:
            score += min((aspect_ratio - 1.8) * 10.0, 20.0)

        if component_count >= overlay_min_components:
            score += 10.0

        complexity_score = float(min(score, 100.0))

        if (
            component_count >= overlay_min_components
            or aspect_ratio >= wide_aspect_overlay
            or small_component_ratio >= small_ratio_overlay
        ):
            strategy = "overlay"
            use_overlay_mode = True
        elif component_count <= direct_max_components and small_component_ratio < 0.25:
            strategy = "direct"
            use_overlay_mode = False
        else:
            strategy = "simplified"
            use_overlay_mode = False

        return (
            int(component_count),
            int(small_component_count),
            float(small_component_ratio),
            float(aspect_ratio),
            float(complexity_score),
            strategy,
            bool(use_overlay_mode),
        )


class MaskStrategySwitch:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "strategy": ("STRING", {"default": "direct"}),
                "direct_value": ("INT", {"default": 0, "min": -999999, "max": 999999, "step": 1}),
                "simplified_value": ("INT", {"default": 1, "min": -999999, "max": 999999, "step": 1}),
                "overlay_value": ("INT", {"default": 2, "min": -999999, "max": 999999, "step": 1}),
            }
        }

    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("selected_value",)
    FUNCTION = "pick"
    CATEGORY = "Mask Tools"

    def pick(self, strategy, direct_value, simplified_value, overlay_value):
        value = direct_value
        mode = str(strategy).strip().lower()

        if mode == "overlay":
            value = overlay_value
        elif mode == "simplified":
            value = simplified_value
        else:
            value = direct_value

        return (int(value),)


NODE_CLASS_MAPPINGS = {
    "MaskAnalyze": MaskAnalyze,
    "MaskStrategySwitch": MaskStrategySwitch,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MaskAnalyze": "Mask Analyze",
    "MaskStrategySwitch": "Mask Strategy Switch",
}
