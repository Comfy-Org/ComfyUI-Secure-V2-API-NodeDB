from pathlib import Path

import cv2
import numpy as np
import torch


GRID_DIR = Path(__file__).with_name("grids")
TEMPLATE_SIZES = range(5, 21)


class MosaicMask:
    def __init__(self):
        self.templates = []
        for size in TEMPLATE_SIZES:
            path = GRID_DIR / f"pattern{size}x{size}.png"
            template = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            if template is None:
                raise FileNotFoundError(f"Unable to load mosaic template: {path}")
            self.templates.append((size, template))

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "top_n": ("INT", {"default": 1, "min": 1, "max": 10, "step": 1}),
                "kernel_size": ("INT", {"default": 3, "min": 0, "max": 100, "step": 1}),
            },
            "optional": {
                "threshold": ("FLOAT", {"default": 0.3, "min": 0.0, "max": 1.0, "step": 0.01}),
                "min_grid_size": ("INT", {"default": 10, "min": 5, "max": 20, "step": 1}),
                "max_grid_size": ("INT", {"default": 20, "min": 5, "max": 20, "step": 1}),
            },
        }

    RETURN_TYPES = ("MASK",)
    RETURN_NAMES = ("mosaic_mask",)
    FUNCTION = "get_mask"
    CATEGORY = "Mosaic Masking"

    def get_mask(
        self, image, top_n, kernel_size, threshold=0.3, min_grid_size=10, max_grid_size=20
    ):
        images = image.detach().to(device="cpu", dtype=torch.float32).numpy()
        if images.ndim != 4 or images.shape[-1] < 3:
            raise ValueError(
                f"Expected IMAGE with shape [batch, height, width, channels], got {images.shape}"
            )
        if min_grid_size > max_grid_size:
            raise ValueError("min_grid_size cannot exceed max_grid_size")

        images = np.clip(images[..., :3] * 255.0, 0, 255).astype(np.uint8)
        masks = np.stack(
            [
                self.detect_mosaic(
                    image_np, top_n, kernel_size, threshold, min_grid_size, max_grid_size
                )
                for image_np in images
            ]
        )
        return (torch.from_numpy(masks).to(device=image.device, dtype=torch.float32),)

    def detect_mosaic(
        self, image, top_n, kernel_size, threshold, min_grid_size, max_grid_size
    ):
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        gray = cv2.Canny(gray, 10, 20)
        gray = cv2.GaussianBlur(255 - gray, (3, 3), 0)

        height, width = gray.shape
        coverage = np.zeros((height + 1, width + 1), dtype=np.int32)
        for size, template in self.templates:
            if not min_grid_size <= size <= max_grid_size:
                continue
            template_height, template_width = template.shape
            if template_height > height or template_width > width:
                continue

            matches = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
            ys, xs = np.where(matches >= threshold)
            if not len(xs):
                continue

            np.add.at(coverage, (ys, xs), 1)
            np.add.at(coverage, (ys + template_height, xs), -1)
            np.add.at(coverage, (ys, xs + template_width), -1)
            np.add.at(coverage, (ys + template_height, xs + template_width), 1)

        mask = (coverage.cumsum(0).cumsum(1)[:-1, :-1] > 0).astype(np.uint8)
        if kernel_size > 1:
            mask = cv2.dilate(mask, np.ones((kernel_size, kernel_size), np.uint8), iterations=1)
        return self.keep_largest_component(mask, top_n)

    @staticmethod
    def keep_largest_component(mask, top_n=1):
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        component_count = num_labels - 1
        if component_count <= top_n:
            return mask

        areas = stats[1:, cv2.CC_STAT_AREA]
        kept_labels = np.argpartition(areas, -top_n)[-top_n:] + 1
        return np.isin(labels, kept_labels).astype(np.uint8)


NODE_CLASS_MAPPINGS = {
    "MosaicMask": MosaicMask,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MosaicMask": "MosaicMask",
}
