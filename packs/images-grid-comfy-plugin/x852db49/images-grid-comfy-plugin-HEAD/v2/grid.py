"""Pack-owned image-grid and annotation algorithms."""
from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont


STATIC_PATH = Path(__file__).with_name("static")
FONT_PATH = STATIC_PATH / "Roboto-Regular.ttf"
WIDEST_LETTER = "W"


@dataclass(frozen=True)
class Annotation:
    column_texts: list[str]
    row_texts: list[str]
    font: ImageFont.FreeTypeFont


def parse_texts(value: str) -> list[str]:
    return [
        result
        for item in value.split(";")
        if (result := item.strip()) != ""
    ]


def annotation_descriptor(
    column_texts: str, row_texts: str, font_size: int,
) -> dict[str, Any]:
    columns = parse_texts(column_texts)
    rows = parse_texts(row_texts)
    # Match the source node's eager font validation at descriptor creation.
    ImageFont.truetype(str(FONT_PATH), size=font_size)
    return {
        "secure_kind": "images_grid.annotation",
        "column_texts": columns,
        "row_texts": rows,
        "font_size": font_size,
    }


def annotation_from_descriptor(value: Any) -> Annotation:
    if not isinstance(value, dict) or value.get("secure_kind") != "images_grid.annotation":
        raise TypeError("annotation must come from the GridAnnotation node")
    if set(value) != {"secure_kind", "column_texts", "row_texts", "font_size"}:
        raise ValueError("annotation contains unsupported fields")
    columns = value["column_texts"]
    rows = value["row_texts"]
    size = value["font_size"]
    if (
        not isinstance(columns, list)
        or not isinstance(rows, list)
        or not all(isinstance(item, str) for item in columns + rows)
        or isinstance(size, bool)
        or not isinstance(size, int)
        or not 1 <= size <= 512
    ):
        raise ValueError("annotation has invalid text or font data")
    if len(columns) + len(rows) > 8_192:
        raise ValueError("annotation contains too many labels")
    if sum(len(item) for item in columns + rows) > 1_048_576:
        raise ValueError("annotation text exceeds the bounded size")
    return Annotation(
        column_texts=columns,
        row_texts=rows,
        font=ImageFont.truetype(str(FONT_PATH), size=size),
    )


def tensor_to_pillow(image: torch.Tensor) -> Image.Image:
    array = np.clip(
        255.0 * image.cpu().numpy().squeeze(), 0, 255,
    ).astype(np.uint8)
    return Image.fromarray(array)


def pillow_to_tensor(image: Image.Image) -> torch.Tensor:
    return torch.from_numpy(
        np.array(image).astype(np.float32) / 255.0,
    ).unsqueeze(0)


def create_images_grid_by_columns(
    images: list[Image.Image],
    gap: int,
    max_columns: int,
    annotation: Annotation | None = None,
) -> Image.Image:
    max_rows = (len(images) + max_columns - 1) // max_columns
    return _create_images_grid(images, gap, max_columns, max_rows, annotation)


def create_images_grid_by_rows(
    images: list[Image.Image],
    gap: int,
    max_rows: int,
    annotation: Annotation | None = None,
) -> Image.Image:
    max_columns = (len(images) + max_rows - 1) // max_rows
    return _create_images_grid(images, gap, max_columns, max_rows, annotation)


@dataclass
class _GridInfo:
    image: Image.Image
    gap: int
    one_image_size: tuple[int, int]


def _create_images_grid(
    images: list[Image.Image],
    gap: int,
    max_columns: int,
    max_rows: int,
    annotation: Annotation | None,
) -> Image.Image:
    size = images[0].size
    grid_width = size[0] * max_columns + (max_columns - 1) * gap
    grid_height = size[1] * max_rows + (max_rows - 1) * gap
    grid_image = Image.new("RGB", (grid_width, grid_height), color="white")
    _arrange_images_on_grid(
        grid_image, images=images, size=size,
        max_columns=max_columns, gap=gap,
    )
    if annotation is None:
        return grid_image
    return _create_grid_annotation(
        grid_info=_GridInfo(
            image=grid_image,
            gap=gap,
            one_image_size=size,
        ),
        column_texts=annotation.column_texts,
        row_texts=annotation.row_texts,
        font=annotation.font,
    )


def _arrange_images_on_grid(
    grid_image: Image.Image,
    /,
    images: list[Image.Image],
    size: tuple[int, int],
    max_columns: int,
    gap: int,
) -> None:
    for index, image in enumerate(images):
        x = (index % max_columns) * (size[0] + gap)
        y = (index // max_columns) * (size[1] + gap)
        grid_image.paste(image, (x, y))


def _create_grid_annotation(
    grid_info: _GridInfo,
    column_texts: list[str],
    row_texts: list[str],
    font: ImageFont.FreeTypeFont,
) -> Image.Image:
    if not column_texts and not row_texts:
        raise ValueError("Column text and row text is empty")
    grid = grid_info.image
    left_padding = 0
    top_padding = 0
    if row_texts:
        left_padding = int(
            max(
                font.getlength(split_text)
                for raw_text in row_texts
                for split_text in raw_text.split("\n")
            )
            + font.getlength(WIDEST_LETTER) * 2
        )
    if column_texts:
        top_padding = (
            max(item.count("\n") for item in column_texts) * int(font.size)
            + int(font.size * 2)
        )
    image = Image.new(
        "RGB",
        (grid.size[0] + left_padding, grid.size[1] + top_padding),
        color="white",
    )
    draw = ImageDraw.Draw(image)
    draw.font = font  # type: ignore[attr-defined]
    _paste_image_to_lower_left_corner(image, grid)
    if column_texts:
        _draw_column_text(
            draw=draw,
            texts=column_texts,
            grid_info=grid_info,
            left_padding=left_padding,
            top_padding=top_padding,
        )
    if row_texts:
        _draw_row_text(
            draw=draw,
            texts=row_texts,
            grid_info=grid_info,
            left_padding=left_padding,
            top_padding=top_padding,
        )
    return image


def _draw_column_text(
    draw: ImageDraw.ImageDraw,
    texts: list[str],
    grid_info: _GridInfo,
    left_padding: int,
    top_padding: int,
) -> None:
    index = 0
    x0 = left_padding
    y0 = 0
    x1 = left_padding + grid_info.one_image_size[0]
    y1 = top_padding
    while x0 != grid_info.image.size[0] + left_padding + grid_info.gap:
        index = _draw_text_by_xy((x0, y0, x1, y1), index, draw, texts)
        x0 += grid_info.one_image_size[0] + grid_info.gap
        x1 += grid_info.one_image_size[0] + grid_info.gap


def _draw_row_text(
    draw: ImageDraw.ImageDraw,
    texts: list[str],
    grid_info: _GridInfo,
    left_padding: int,
    top_padding: int,
) -> None:
    index = 0
    x0 = 0
    y0 = top_padding
    x1 = left_padding
    y1 = top_padding + grid_info.one_image_size[1]
    while y0 != grid_info.image.size[1] + top_padding + grid_info.gap:
        index = _draw_text_by_xy((x0, y0, x1, y1), index, draw, texts)
        y0 += grid_info.one_image_size[1] + grid_info.gap
        y1 += grid_info.one_image_size[1] + grid_info.gap


def _draw_text_by_xy(
    xy: tuple[int, int, int, int],
    index: int,
    draw: ImageDraw.ImageDraw,
    texts: list[str],
) -> int:
    with suppress(IndexError):
        _draw_center_text(draw, xy, texts[index])
    return index + 1


def _draw_center_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    text: str,
    fill: Any = "black",
) -> None:
    _, _, *text_size = draw.textbbox((0, 0), text)
    draw.multiline_text(
        (
            (xy[2] - text_size[0] + xy[0]) / 2,
            (xy[3] - text_size[1] + xy[1]) / 2,
        ),
        text,
        fill=fill,
    )


def _paste_image_to_lower_left_corner(
    base: Image.Image, image: Image.Image,
) -> None:
    base.paste(
        image,
        (base.size[0] - image.size[0], base.size[1] - image.size[1]),
    )
