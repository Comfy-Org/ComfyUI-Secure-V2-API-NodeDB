"""Secure, behavior-preserving implementations of Steudio's ten nodes.

The tile and utility algorithms remain pack code.  Host-owned images cross as
typed references; only the nodes that manipulate pixels request the bounded
``raw`` tier.  The legacy arbitrary-directory loader is deliberately narrowed
to logical subdirectories of ComfyUI's managed input folder.
"""
from __future__ import annotations

import math
from pathlib import PurePosixPath
from typing import Any

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFilter

from comfy_api.latest import io, sdk


OVERLAP_DICT = {
    "None": 0,
    "1/64 Tile": 0.015625,
    "1/32 Tile": 0.03125,
    "1/16 Tile": 0.0625,
    "1/8 Tile": 0.125,
    "1/4 Tile": 0.25,
    "1/2 Tile": 0.5,
}
TILE_ORDER_DICT = {"linear": 0, "spiral": 1}
SCALING_METHODS = (
    "nearest-exact", "bilinear", "area", "bicubic", "lanczos",
)
RATIO = {
    "1:1 ◻": (1, 1),
    "5:4 ▭": (5, 4),
    "4:3 ▭": (4, 3),
    "3:2 ▭": (3, 2),
    "16:9 ▭": (16, 9),
    "2:1 ▭": (2, 1),
    "21:9 ▭": (21, 9),
    "32:9 ▭": (32, 9),
    "": (1, 1),
    "4:5 ▯": (4, 5),
    "3:4 ▯": (3, 4),
    "2:3 ▯": (2, 3),
    "9:16 ▯": (9, 16),
    "1:2 ▯": (1, 2),
    "9:21 ▯": (9, 21),
    "9:32 ▯": (9, 32),
}
SAMPLERS = (
    "euler", "euler_cfg_pp", "euler_ancestral",
    "euler_ancestral_cfg_pp", "heun", "heunpp2", "exp_heun_2_x0",
    "exp_heun_2_x0_sde", "dpm_2", "dpm_2_ancestral", "lms",
    "dpm_fast", "dpm_adaptive", "dpmpp_2s_ancestral",
    "dpmpp_2s_ancestral_cfg_pp", "dpmpp_sde", "dpmpp_sde_gpu",
    "dpmpp_2m", "dpmpp_2m_cfg_pp", "dpmpp_2m_sde",
    "dpmpp_2m_sde_gpu", "dpmpp_2m_sde_heun",
    "dpmpp_2m_sde_heun_gpu", "dpmpp_3m_sde", "dpmpp_3m_sde_gpu",
    "ddpm", "lcm", "ipndm", "ipndm_v", "deis", "res_multistep",
    "res_multistep_cfg_pp", "res_multistep_ancestral",
    "res_multistep_ancestral_cfg_pp", "gradient_estimation",
    "gradient_estimation_cfg_pp", "er_sde", "seeds_2", "seeds_3",
    "sa_solver", "sa_solver_pece", "ddim", "uni_pc", "uni_pc_bh2",
)
SCHEDULERS = (
    "simple", "sgm_uniform", "karras", "exponential", "ddim_uniform",
    "beta", "normal", "linear_quadratic", "kl_optimal",
)
DAC_DATA = io.Custom("DAC_DATA")
UI = io.Custom("UI")
_MAX_TILES = 4096
_MAX_SEQUENCE = 100_000
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


async def _image_value(image: sdk.ImageRef) -> torch.Tensor:
    value = await image.raw()
    if not isinstance(value, torch.Tensor) or value.ndim != 4:
        raise TypeError("Steudio expects an IMAGE in BHWC tensor form")
    if value.shape[0] < 1 or value.shape[-1] < 1:
        raise ValueError("Steudio received an empty IMAGE")
    return value


async def _image_output(value: torch.Tensor) -> sdk.ImageRef:
    if not isinstance(value, torch.Tensor) or value.ndim != 4:
        raise TypeError("Steudio produced an invalid IMAGE tensor")
    return await sdk.ImageRef._from_raw(value)


def _common_upscale(
    samples: torch.Tensor, width: int, height: int, method: str,
) -> torch.Tensor:
    """Exact crop-disabled subset of pinned ``comfy.utils.common_upscale``."""
    if method == "lanczos":
        values = samples.squeeze(1) if samples.shape[1] == 1 else samples.movedim(1, -1)
        images = [
            Image.fromarray(
                np.clip(255.0 * item.cpu().numpy(), 0, 255).astype(np.uint8)
            )
            for item in values
        ]
        arrays = []
        for image in images:
            image = image.resize((width, height), resample=Image.Resampling.LANCZOS)
            array = np.array(image).astype(np.float32) / 255.0
            tensor = torch.from_numpy(array)
            arrays.append(tensor.movedim(-1, 0) if array.ndim == 3 else tensor)
        return torch.stack(arrays).to(values.device, values.dtype)
    return torch.nn.functional.interpolate(
        samples, size=(height, width), mode=method,
    )


def calculate_overlap(tile_size: int, overlap_fraction: float) -> int:
    return int(overlap_fraction * tile_size)


def create_tile_coordinates(
    image_width: int,
    image_height: int,
    tile_width: int,
    tile_height: int,
    overlap_x: int,
    overlap_y: int,
    grid_x: int,
    grid_y: int,
    tile_order: int,
) -> tuple[list[tuple[int, int]], list[list[str]]]:
    if min(tile_width, tile_height, grid_x, grid_y) < 1:
        raise ValueError("tile dimensions and grid dimensions must be positive")
    if tile_width <= overlap_x or tile_height <= overlap_y:
        raise ValueError("tile overlap must be smaller than the tile")
    if grid_x * grid_y > _MAX_TILES:
        raise ValueError(f"Steudio is limited to {_MAX_TILES} tiles")

    tiles: list[tuple[int, int]] = []
    matrix = [["" for _ in range(grid_x)] for _ in range(grid_y)]
    for row in range(grid_y):
        y = row * (tile_height - overlap_y)
        if row == grid_y - 1:
            y = image_height - tile_height
        for col in range(grid_x):
            x = col * (tile_width - overlap_x)
            if col == grid_x - 1:
                x = image_width - tile_width
            tiles.append((x, y))

    if tile_order == 1:
        spiral_tiles: list[tuple[int, int]] = []
        visited: set[tuple[int, int]] = set()
        x, y = grid_x // 2, grid_y // 2
        dx, dy = 1, 0
        layer = 1
        while len(spiral_tiles) < len(tiles):
            for _ in range(2):
                for _ in range(layer):
                    if (
                        0 <= x < grid_x and 0 <= y < grid_y
                        and (x, y) not in visited
                    ):
                        index = y * grid_x + x
                        if index < len(tiles):
                            spiral_tiles.append(tiles[index])
                            visited.add((x, y))
                    x += dx
                    y += dy
                dx, dy = -dy, dx
            layer += 1
        spiral_tiles.reverse()
        tiles = spiral_tiles

    for index, (x, y) in enumerate(tiles):
        row = y // (tile_height - overlap_y)
        col = x // (tile_width - overlap_x)
        matrix[row][col] = f"{index + 1} ({x},{y})"
    return tiles, matrix


class DivideAndConquerAlgorithm(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Divide and Conquer Algorithm",
            display_name="Divide and Conquer Algorithm",
            category="Steudio/Divide and Conquer",
            description=(
                "\nCalculate the best dimensions and optionally upscale an image\n"
                "while maintaining minimum tile overlap and scale factor "
                "constraints.\nSteudio\n"
            ),
            is_output_node=True,
            inputs=[
                io.Image.Input("image"),
                io.Int.Input("tile_width", default=1024),
                io.Int.Input("tile_height", default=1024),
                io.Combo.Input(
                    "min_overlap", options=list(OVERLAP_DICT),
                    default="1/32 Tile",
                ),
                io.Float.Input(
                    "min_scale_factor", default=3.0, min=1.0, max=8.0,
                ),
                io.Combo.Input(
                    "tile_order", options=list(TILE_ORDER_DICT),
                    default="spiral",
                ),
                io.Combo.Input(
                    "scaling_method", options=SCALING_METHODS,
                    default="lanczos",
                ),
                io.UpscaleModel.Input("upscale_model", optional=True),
                io.Boolean.Input(
                    "use_upscale_with_model", default=True, optional=True,
                ),
            ],
            outputs=[
                io.Image.Output("IMAGE"),
                DAC_DATA.Output("dac_data"),
                io.String.Output("ui"),
            ],
        )

    @classmethod
    async def execute(
        cls,
        image: sdk.ImageRef,
        tile_width: int,
        tile_height: int,
        min_overlap: str,
        min_scale_factor: float,
        tile_order: str,
        scaling_method: str,
        upscale_model: sdk.UpscaleModelRef | None = None,
        use_upscale_with_model: bool = True,
    ) -> io.NodeOutput:
        if (
            isinstance(tile_width, bool) or isinstance(tile_height, bool)
            or not isinstance(tile_width, int) or not isinstance(tile_height, int)
            or tile_width < 1 or tile_height < 1
        ):
            raise ValueError("tile dimensions must be positive integers")
        if tile_width > 16384 or tile_height > 16384:
            raise ValueError("tile dimensions exceed the 16384 pixel limit")
        if min_overlap not in OVERLAP_DICT:
            raise ValueError(f"unknown overlap setting {min_overlap!r}")
        if tile_order not in TILE_ORDER_DICT:
            raise ValueError(f"unknown tile order {tile_order!r}")
        if scaling_method not in SCALING_METHODS:
            raise ValueError(f"unknown scaling method {scaling_method!r}")

        source = await _image_value(image)
        _batch, height, width, _channels = source.shape
        overlap = OVERLAP_DICT[min_overlap]
        order = TILE_ORDER_DICT[tile_order]
        overlap_x = calculate_overlap(tile_width, overlap)
        overlap_y = calculate_overlap(tile_height, overlap)
        min_scale_factor = max(float(min_scale_factor), 1.0)

        if width <= height:
            multiply_factor = math.ceil(min_scale_factor * width / tile_width)
            while True:
                upscaled_width = tile_width * multiply_factor
                grid_x = math.ceil(upscaled_width / tile_width)
                upscaled_width = tile_width * grid_x - overlap_x * (grid_x - 1)
                upscale_ratio = upscaled_width / width
                if upscale_ratio >= min_scale_factor:
                    break
                multiply_factor += 1
            upscaled_height = int(height * upscale_ratio)
            grid_y = math.ceil(
                (upscaled_height - overlap_y) / (tile_height - overlap_y)
            )
            if grid_y > 1:
                overlap_y = round(
                    (tile_height * grid_y - upscaled_height) / (grid_y - 1)
                )
        else:
            multiply_factor = math.ceil(min_scale_factor * height / tile_height)
            while True:
                upscaled_height = tile_height * multiply_factor
                grid_y = math.ceil(upscaled_height / tile_height)
                upscaled_height = tile_height * grid_y - overlap_y * (grid_y - 1)
                upscale_ratio = upscaled_height / height
                if upscale_ratio >= min_scale_factor:
                    break
                multiply_factor += 1
            upscaled_width = int(width * upscale_ratio)
            grid_x = math.ceil(
                (upscaled_width - overlap_x) / (tile_width - overlap_x)
            )
            if grid_x > 1:
                overlap_x = round(
                    (tile_width * grid_x - upscaled_width) / (grid_x - 1)
                )

        if grid_x * grid_y > _MAX_TILES:
            raise ValueError(f"Steudio is limited to {_MAX_TILES} tiles")
        dac_data = {
            "upscaled_width": upscaled_width,
            "upscaled_height": upscaled_height,
            "tile_width": tile_width,
            "tile_height": tile_height,
            "overlap_x": overlap_x,
            "overlap_y": overlap_y,
            "grid_x": grid_x,
            "grid_y": grid_y,
            "tile_order": order,
        }

        if use_upscale_with_model and upscale_model is not None:
            model_image = await upscale_model.upscale(image, tile_size=512)
            samples = (await _image_value(model_image)).movedim(-1, 1)
        else:
            samples = source.movedim(-1, 1)
        upscaled = _common_upscale(
            samples, upscaled_width, upscaled_height, scaling_method,
        ).movedim(1, -1)

        original_image = f"{width}x{height}"
        upscaled_image_size = f"{upscaled_width}x{upscaled_height}"
        grid_n_xy = f"{grid_x}x{grid_y}"
        algo_ui = (
            "Divide and Conquer Algorithm:\n"
            f"Original Image Size: {original_image}\n"
            f"Upscaled Image Size: {upscaled_image_size}\n"
            f"Grid: {grid_n_xy} ({grid_x * grid_y} tiles)\n"
            f"Overlap_x: {overlap_x} pixels\n"
            f"Overlap_y: {overlap_y} pixels\n"
            f"Effective_upscale: {round(upscaled_width / width, 2)}"
        )
        return io.NodeOutput(await _image_output(upscaled), dac_data, algo_ui)


class DivideImageAndSelectTile(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Divide Image and Select Tile",
            display_name="Divide Image and Select Tile",
            category="Steudio/Divide and Conquer",
            description="\ntile 0 = All tiles\ntile # = Tile #\n",
            inputs=[
                io.Image.Input("image"),
                DAC_DATA.Input("dac_data"),
                io.Int.Input("tile", default=0, min=0, step=1),
            ],
            outputs=[
                io.Image.Output("TILE(S)", is_output_list=True),
                UI.Output("ui"),
            ],
        )

    @classmethod
    async def execute(
        cls, image: sdk.ImageRef, dac_data: dict[str, Any], tile: int,
    ) -> io.NodeOutput:
        value = await _image_value(image)
        image_height, image_width = value.shape[1:3]
        tile_width = int(dac_data["tile_width"])
        tile_height = int(dac_data["tile_height"])
        coordinates, matrix = create_tile_coordinates(
            image_width,
            image_height,
            tile_width,
            tile_height,
            int(dac_data["overlap_x"]),
            int(dac_data["overlap_y"]),
            int(dac_data["grid_x"]),
            int(dac_data["grid_y"]),
            int(dac_data["tile_order"]),
        )
        image_tiles = [
            value[:, y:y + tile_height, x:x + tile_width, :]
            for x, y in coordinates
        ]
        if not image_tiles:
            raise ValueError("Divide Image and Select Tile produced no tiles")
        if tile == 0:
            selected = torch.cat(image_tiles, dim=0)
        else:
            if not 1 <= int(tile) <= len(image_tiles):
                raise IndexError(
                    f"tile {tile} is outside the 1..{len(image_tiles)} range"
                )
            selected = image_tiles[int(tile) - 1]
        outputs = [
            await _image_output(item.unsqueeze(0)) for item in selected
        ]
        matrix_ui = "Divide and Conquer Matrix:\n" + "\n".join(
            " ".join(row) for row in matrix
        )
        return io.NodeOutput(outputs, matrix_ui)


def _tile_mask(
    tile_width: int,
    tile_height: int,
    x: int,
    y: int,
    upscaled_width: int,
    upscaled_height: int,
    overlap_x: int,
    overlap_y: int,
) -> Image.Image:
    f_overlap_x = overlap_x // 4
    f_overlap_y = overlap_y // 4
    mask = Image.new("L", (tile_width, tile_height), 0)
    draw = ImageDraw.Draw(mask)
    if x == 0 and y == 0 and upscaled_height != tile_height and upscaled_width != tile_width:
        draw.rectangle([x, y, tile_width - f_overlap_x, tile_height - f_overlap_y], fill=255)
    elif x == upscaled_width - tile_width and y == 0 and upscaled_height != tile_height and upscaled_width != tile_width:
        draw.rectangle([f_overlap_x, y, tile_width, tile_height - f_overlap_y], fill=255)
    elif x == 0 and y == upscaled_height - tile_height and upscaled_height != tile_height and upscaled_width != tile_width:
        draw.rectangle([x, f_overlap_y, tile_width - f_overlap_x, tile_height], fill=255)
    elif x == upscaled_width - tile_width and y == upscaled_height - tile_height and upscaled_height != tile_height and upscaled_width != tile_width:
        draw.rectangle([f_overlap_x, f_overlap_y, tile_width, tile_height], fill=255)
    elif x == 0 and y == 0 and upscaled_height == tile_height:
        draw.rectangle([x, y, tile_width - f_overlap_x, tile_height], fill=255)
    elif x == upscaled_width - tile_width and y == 0 and upscaled_height == tile_height:
        draw.rectangle([f_overlap_x, y, tile_width, tile_height], fill=255)
    elif x == 0 and y == 0 and upscaled_width == tile_width:
        draw.rectangle([x, y, tile_width, tile_height - f_overlap_y], fill=255)
    elif x == 0 and y == upscaled_height - tile_height and upscaled_width == tile_width:
        draw.rectangle([x, f_overlap_y, tile_width, tile_height], fill=255)
    elif x not in (0, upscaled_width - tile_width) and y == 0 and upscaled_height != tile_height and upscaled_width != tile_width:
        draw.rectangle([f_overlap_x, y, tile_width - f_overlap_x, tile_height - f_overlap_y], fill=255)
    elif x not in (0, upscaled_width - tile_width) and y == upscaled_height - tile_height and upscaled_height != tile_height and upscaled_width != tile_width:
        draw.rectangle([f_overlap_x, f_overlap_y, tile_width - f_overlap_x, tile_height], fill=255)
    elif x == 0 and y not in (0, upscaled_height - tile_height) and upscaled_height != tile_height and upscaled_width != tile_width:
        draw.rectangle([x, f_overlap_y, tile_width - f_overlap_x, tile_height - f_overlap_y], fill=255)
    elif x == upscaled_width - tile_width and y not in (0, upscaled_height - tile_height) and upscaled_height != tile_height and upscaled_width != tile_width:
        draw.rectangle([f_overlap_x, f_overlap_y, tile_width, tile_height - f_overlap_y], fill=255)
    elif x not in (0, upscaled_width - tile_width) and y == 0 and upscaled_height == tile_height and upscaled_width != tile_width:
        draw.rectangle([f_overlap_x, y, tile_width - f_overlap_x, tile_height], fill=255)
    elif x == 0 and y not in (0, upscaled_height - tile_height) and upscaled_height != tile_height and upscaled_width == tile_width:
        draw.rectangle([x, f_overlap_y, tile_width, tile_height - f_overlap_y], fill=255)
    elif x not in (0, upscaled_width - tile_width) and y not in (0, upscaled_height - tile_height) and upscaled_height != tile_height and upscaled_width != tile_width:
        draw.rectangle([f_overlap_x, f_overlap_y, tile_width - f_overlap_x, tile_height - f_overlap_y], fill=255)
    radius = (math.sqrt(overlap_x), math.sqrt(overlap_y))
    if overlap_x <= 64 or overlap_y <= 64:
        return mask.filter(ImageFilter.BoxBlur(radius=radius))
    return mask.filter(ImageFilter.GaussianBlur(radius=radius))


class CombineTiles(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Combine Tiles",
            display_name="Combine Tiles",
            category="Steudio/Divide and Conquer",
            is_input_list=True,
            inputs=[io.Image.Input("images"), DAC_DATA.Input("dac_data")],
            outputs=[io.Image.Output("image"), UI.Output("ui")],
        )

    @classmethod
    async def execute(
        cls, images: list[sdk.ImageRef], dac_data: list[dict[str, Any]],
    ) -> io.NodeOutput:
        if not images:
            raise ValueError("Combine Tiles needs at least one image")
        data = dac_data[0] if isinstance(dac_data, list) else dac_data
        values = [await _image_value(image) for image in images]
        value = torch.stack(values).squeeze(1)
        upscaled_width = int(data["upscaled_width"])
        upscaled_height = int(data["upscaled_height"])
        overlap_x = int(data["overlap_x"])
        overlap_y = int(data["overlap_y"])
        grid_x = int(data["grid_x"])
        grid_y = int(data["grid_y"])
        tile_order = int(data["tile_order"])
        tile_width, tile_height = value.shape[2], value.shape[1]
        coordinates, matrix = create_tile_coordinates(
            upscaled_width,
            upscaled_height,
            tile_width,
            tile_height,
            overlap_x,
            overlap_y,
            grid_x,
            grid_y,
            tile_order,
        )
        if len(values) != len(coordinates):
            raise ValueError(
                f"Combine Tiles received {len(values)} tiles for a "
                f"{len(coordinates)}-tile grid"
            )
        output = torch.zeros(
            (1, upscaled_height, upscaled_width, 3), dtype=value.dtype,
        )
        for index, (x, y) in enumerate(coordinates):
            mask = _tile_mask(
                tile_width, tile_height, x, y, upscaled_width,
                upscaled_height, overlap_x, overlap_y,
            )
            array = np.array(mask) / 255.0
            mask_tensor = torch.tensor(
                array, dtype=value.dtype,
            ).unsqueeze(0).unsqueeze(-1)
            region = output[:, y:y + tile_height, x:x + tile_width, :]
            region.mul_(1 - mask_tensor)
            region.add_(value[index] * mask_tensor)
        matrix_ui = "Divide and Conquer Matrix:\n" + "\n".join(
            " ".join(row) for row in matrix
        )
        return io.NodeOutput(await _image_output(output), matrix_ui)


class RatioCalculator(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Ratio Calculator",
            display_name="Ratio Calculator",
            category="Steudio/Utils",
            is_output_node=True,
            inputs=[io.Image.Input("image")],
            outputs=[io.AnyType.Output("ratio")],
        )

    @classmethod
    async def execute(cls, image: sdk.ImageRef) -> io.NodeOutput:
        height, width = await image.spatial_shape()
        gcd = math.gcd(width, height)
        simplified_width = width // gcd
        simplified_height = height // gcd
        closest_ratio = min(
            RATIO,
            key=lambda name: abs(
                simplified_width / simplified_height
                - RATIO[name][0] / RATIO[name][1]
            ),
        )
        text = f"{closest_ratio}\n{width * height:,} pixels"
        return io.NodeOutput(closest_ratio, ui={"text": text})


class RatioToSize(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Ratio to Size",
            display_name="Ratio to Size",
            category="Steudio/Utils",
            inputs=[
                io.Combo.Input("ratio", options=list(RATIO)),
                io.Float.Input(
                    "Megapixel", default=1.05, min=0.10, max=3.00, step=0.01,
                ),
                io.Float.Input(
                    "Precision", default=0.30, min=0.00, max=1.00, step=0.01,
                ),
            ],
            outputs=[
                io.Int.Output("width"),
                io.Int.Output("height"),
                UI.Output("ui"),
            ],
        )

    @classmethod
    async def execute(
        cls, ratio: str, Megapixel: float, Precision: float,
    ) -> io.NodeOutput:
        aspect_width, aspect_height = RATIO.get(ratio, (1, 1))
        total_pixels = int(Megapixel * 1_000_000)
        width = int((total_pixels * (aspect_width / aspect_height)) ** 0.5)
        height = int(width * (aspect_height / aspect_width))
        while True:
            width = width // 64 * 64
            height = height // 64 * 64
            if abs(width / height - aspect_width / aspect_height) <= Precision:
                break
            if width > 64 and height > 64:
                if width / height > aspect_width / aspect_height:
                    width -= 64
                else:
                    height -= 64
            else:
                break
        precision = round(
            aspect_width / aspect_height - width / height, 2,
        )
        text = (
            f"Ratio: {ratio}\nWidth: {width}\nHeight: {height}\n"
            f"Megapixel: {width * height:,}\nPrecision: {precision}\n"
        )
        return io.NodeOutput(int(width), int(height), text)


class SeedShifter(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Seed Shifter",
            display_name="Seed Shifter",
            category="Steudio/Utils",
            description=(
                "\nA simple and effective way to generate a “batch” of images "
                "with reproducible seed.\nSteudio\n"
            ),
            inputs=[
                io.Int.Input(
                    "seed_", default=0, min=0, max=0xffffffffffffffff,
                    step=1,
                ),
                io.Int.Input("seed_shifter", default=0, min=0),
                io.Int.Input("batch", default=1, min=1),
            ],
            outputs=[io.Int.Output("seeds", is_output_list=True)],
        )

    @classmethod
    async def execute(
        cls, seed_: int, seed_shifter: int, batch: int,
    ) -> io.NodeOutput:
        if not 1 <= int(batch) <= _MAX_SEQUENCE:
            raise ValueError(f"batch must be in [1, {_MAX_SEQUENCE}]")
        return io.NodeOutput([
            int(seed_) + int(seed_shifter) + index for index in range(int(batch))
        ])


class SequenceGenerator(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Sequence Generator",
            display_name="Sequence Generator",
            category="Steudio/Utils",
            description=(
                "\nx...y+z | Generates a sequence of numbers from x to y with "
                "a step of z.\nx...y#z | Generates z evenly spaced numbers between "
                "x and y.\n  x,y,z | Generates a list of x, y, z.\n    "
            ),
            is_output_node=True,
            inputs=[io.String.Input(
                "gen", default="0...1+0.1", multiline=False,
                dynamic_prompts=False,
            )],
            outputs=[
                io.Int.Output("INT", is_output_list=True),
                io.Float.Output("FLOAT", is_output_list=True),
            ],
        )

    @staticmethod
    def _number(value: str) -> float:
        try:
            return float(value)
        except ValueError:
            return 0.0

    @classmethod
    async def execute(cls, gen: str) -> io.NodeOutput:
        result: list[float] = []

        def append(value: float) -> None:
            if len(result) >= _MAX_SEQUENCE:
                raise ValueError(
                    f"Sequence Generator is limited to {_MAX_SEQUENCE} values"
                )
            result.append(round(value, 2))

        for raw in str(gen).split(","):
            element = raw.strip()
            if "..." not in element:
                append(cls._number(element))
                continue
            start_text, rest = element.split("...", 1)
            start = cls._number(start_text)
            if "#" in rest:
                end_text, count_text = rest.split("#", 1)
                end = cls._number(end_text)
                count = int(cls._number(count_text))
                if count < 0:
                    raise ValueError("sequence item count must be non-negative")
                if count > _MAX_SEQUENCE - len(result):
                    raise ValueError(
                        f"Sequence Generator is limited to {_MAX_SEQUENCE} values"
                    )
                if count == 1:
                    append(start)
                elif count > 1:
                    step = (end - start) / (count - 1)
                    for index in range(count):
                        append(start + index * step)
                continue
            end_text, step_text = rest.split("+", 1)
            end = cls._number(end_text)
            step = abs(cls._number(step_text))
            if step == 0:
                raise ValueError("sequence step must not be zero")
            if start > end:
                step = -step
            current = start
            while (step > 0 and current <= end) or (step < 0 and current >= end):
                append(current)
                current += step

        integers = list(map(int, result))
        floats = [float(f"{number:.2f}") for number in result]
        text = (
            f"{len(integers)} INT: {integers}\n"
            f"{len(floats)} FLOAT: {floats}"
        )
        return io.NodeOutput(integers, floats, ui={"text": text})


class LoadImagesIntoList(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("assets",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Load Images into List",
            display_name="Load Images into List",
            category="Steudio/Utils",
            inputs=[io.String.Input("directory", default="")],
            outputs=[io.Image.Output("image", is_output_list=True)],
        )

    @classmethod
    async def execute(cls, directory: str) -> io.NodeOutput:
        logical = str(directory).replace("\\", "/").strip("/")
        parts = PurePosixPath(logical).parts if logical else ()
        if "\x00" in logical or any(part in {"", ".", ".."} for part in parts):
            raise ValueError(
                "directory must be a logical subfolder of ComfyUI's input folder"
            )
        names = await sdk.ctx().assets.list(
            "input", prefix=logical, recursive=False,
        )
        names = sorted(
            name for name in names
            if PurePosixPath(name).suffix.lower() in _IMAGE_EXTENSIONS
        )
        if not names:
            raise FileNotFoundError(
                f"No valid image files found in input subfolder {logical!r}."
            )
        images = []
        for name in names:
            asset = await sdk.ctx().assets.resolve("input", name)
            images.append(await sdk.ctx().assets.load_image(asset))
        return io.NodeOutput(images)


class SimpleConfig(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Simple Config",
            display_name="Simple Config",
            category="Steudio/Utils",
            inputs=[
                io.Int.Input("steps", default=24, min=1, max=99),
                io.Combo.Input("sampler", options=SAMPLERS),
                io.Combo.Input("scheduler", options=SCHEDULERS),
            ],
            outputs=[
                io.Int.Output("STEPS"),
                io.Combo.Output("SAMPLER", options=SAMPLERS),
                io.Combo.Output("SCHEDULER", options=SCHEDULERS),
            ],
        )

    @classmethod
    async def execute(
        cls, steps: int, sampler: str, scheduler: str,
    ) -> io.NodeOutput:
        return io.NodeOutput(int(steps), str(sampler), str(scheduler))


class DisplayUI(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Display UI",
            display_name="Display UI",
            category="Steudio/Utils",
            is_output_node=True,
            inputs=[io.AnyType.Input("ui")],
            outputs=[],
        )

    @classmethod
    async def execute(cls, ui: Any = None) -> io.NodeOutput:
        value = "None"
        if isinstance(ui, str):
            value = ui
        elif isinstance(ui, (int, float, bool)):
            value = str(ui)
        return io.NodeOutput(ui={"text": (value,)})


NODE_CLASS_MAPPINGS = {
    "Divide and Conquer Algorithm": DivideAndConquerAlgorithm,
    "Combine Tiles": CombineTiles,
    "Divide Image and Select Tile": DivideImageAndSelectTile,
    "Ratio Calculator": RatioCalculator,
    "Ratio to Size": RatioToSize,
    "Seed Shifter": SeedShifter,
    "Sequence Generator": SequenceGenerator,
    "Load Images into List": LoadImagesIntoList,
    "Simple Config": SimpleConfig,
    "Display UI": DisplayUI,
}
NODE_DISPLAY_NAME_MAPPINGS = {name: name for name in NODE_CLASS_MAPPINGS}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
