"""Secure Nodes V2 implementation of the WD14 tagger.

Only the generic, bounded ONNX inference primitive is host-owned.  The three
reviewed WD14 label catalogues, category semantics, thresholds, exclusions,
ordering, escaping, and output formatting remain pack code.
"""
from __future__ import annotations

import csv
import hashlib
import io as string_io
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Sequence

from comfy_api.latest import io, sdk


DEFAULT_MODEL = "wd-v1-4-moat-tagger-v2"
MODEL_NAMES = (
    "wd-eva02-large-tagger-v3",
    "wd-vit-tagger-v3",
    "wd-swinv2-tagger-v3",
    "wd-convnext-tagger-v3",
    "wd-v1-4-moat-tagger-v2",
    "wd-v1-4-convnextv2-tagger-v2",
    "wd-v1-4-convnext-tagger-v2",
    "wd-v1-4-convnext-tagger",
    "wd-v1-4-vit-tagger-v2",
    "wd-v1-4-swinv2-tagger-v2",
    "wd-v1-4-vit-tagger",
)

_MAX_CLASSES = 16_384
_MAX_EXCLUDE_CHARS = 65_536
_MAX_OUTPUT_CHARS = 192_000
_MAX_TOTAL_OUTPUT_CHARS = 768_000
_SCORE_PAGE = 512


@dataclass(frozen=True)
class ModelSpec:
    weight: sdk.HuggingFaceWeight
    catalog: str


@dataclass(frozen=True)
class CatalogSource:
    filename: str
    sha256: str
    repo_id: str
    revision: str


@dataclass(frozen=True)
class TagCatalog:
    names: tuple[str, ...]
    categories: tuple[int, ...]

    def __len__(self) -> int:
        return len(self.names)

    def category_range(self, category: int) -> tuple[int, int] | None:
        indices = [
            index
            for index, value in enumerate(self.categories)
            if value == category
        ]
        if not indices:
            return None
        start, end = indices[0], indices[-1] + 1
        if any(value != category for value in self.categories[start:end]):
            raise RuntimeError(
                f"WD14 category {category} is not a contiguous score range"
            )
        return start, end


def _weight(
    repo_id: str,
    revision: str,
    sha256: str,
) -> sdk.HuggingFaceWeight:
    return sdk.HuggingFaceWeight(
        repo_id=repo_id,
        filename="model.onnx",
        folder="onnx",
        revision=revision,
        sha256=sha256,
        on_demand=True,
    )


_MODEL_SPECS = {
    "wd-eva02-large-tagger-v3": ModelSpec(
        _weight(
            "SmilingWolf/wd-eva02-large-tagger-v3",
            "b25b82a03f7282e41aa2f257a52c7583b710bd1c",
            "9e768793060c7939b277ccb382783e8670e8a042d29d77aa736be0c8cc898bfc",
        ),
        "v3",
    ),
    "wd-vit-tagger-v3": ModelSpec(
        _weight(
            "SmilingWolf/wd-vit-tagger-v3",
            "7f6b584d0bd3f55c4531f14ba3d4761b2bccdc0f",
            "35f23693620b668f4d53fd3c62bf65e40af739bc52c7eb0fbc49258b58d065b6",
        ),
        "v3",
    ),
    "wd-swinv2-tagger-v3": ModelSpec(
        _weight(
            "SmilingWolf/wd-swinv2-tagger-v3",
            "627aef95638667ddcaa3ac8ae625e88ea5b02f51",
            "e6774bff34d43bd49f75a47db4ef217dce701c9847b546523eb85ff6dbba1db1",
        ),
        "v3",
    ),
    "wd-convnext-tagger-v3": ModelSpec(
        _weight(
            "SmilingWolf/wd-convnext-tagger-v3",
            "d39e46de298d27340111b64965e20b8185c407e6",
            "1b8a7abf13d9b8368267df47501d523789c4aeae66b2296ad98483239dfa32eb",
        ),
        "v3",
    ),
    "wd-v1-4-moat-tagger-v2": ModelSpec(
        _weight(
            "SmilingWolf/wd-v1-4-moat-tagger-v2",
            "8452cddf280b952281b6e102411c50e981cb2908",
            "b8cef913be4c9e8d93f9f903e74271416502ce0b4b04df0ff1e2f00df488aa03",
        ),
        "v2",
    ),
    "wd-v1-4-convnextv2-tagger-v2": ModelSpec(
        _weight(
            "SmilingWolf/wd-v1-4-convnextv2-tagger-v2",
            "dbd4dbe553ee51feb3bc745b614fb762080e3912",
            "e91daa19cd9e8725125b7d70702d1560855fb687f8d8c4218eddaa821f41834a",
        ),
        "v2",
    ),
    "wd-v1-4-convnext-tagger-v2": ModelSpec(
        _weight(
            "SmilingWolf/wd-v1-4-convnext-tagger-v2",
            "4b34d1b07bdd8e95494072648960b8a6adcbc0ff",
            "71f06ecb7b9df81d8f271da4d43997ea2ed363cdac29aa64fcb256c9631e656a",
        ),
        "v2",
    ),
    "wd-v1-4-convnext-tagger": ModelSpec(
        _weight(
            "SmilingWolf/wd-v1-4-convnext-tagger",
            "4036ca51f1c082b0e7c4496890bbf9eadad5764a",
            "b7d7c9923e0056a2def0f4418df01a1274467b3da8480f146b851289257734de",
        ),
        "v1",
    ),
    "wd-v1-4-vit-tagger-v2": ModelSpec(
        _weight(
            "SmilingWolf/wd-v1-4-vit-tagger-v2",
            "1f3f3e8ae769634e31e1ef696df11ec37493e4f2",
            "8a21cadd1f88a095094cafbffe3028c3cc3d97f4d58c54344c5994bcf48e24ac",
        ),
        "v2",
    ),
    "wd-v1-4-swinv2-tagger-v2": ModelSpec(
        _weight(
            "SmilingWolf/wd-v1-4-swinv2-tagger-v2",
            "cdb0c7fdc70646f0af29c6f80f8df564344a69b6",
            "04ec04fdf7db74b4fed7f4b52f52e04dec4dbad9e4d88d2d178f334079a29fde",
        ),
        "v2",
    ),
    "wd-v1-4-vit-tagger": ModelSpec(
        _weight(
            "SmilingWolf/wd-v1-4-vit-tagger",
            "213a7bd66d93407911b8217e806a95edc3593eed",
            "22e88a3226e427998fdf669bdbd035ee7040f3229796dd66ec35b8dd90e852b5",
        ),
        "v1",
    ),
}


# These are immutable data resources, not runtime downloads.  Each file is an
# exact, hash-checked copy of selected_tags.csv from the named public model
# revision.  Models sharing a generation share the same catalogue bytes.
_CATALOG_SOURCES = {
    "v3": CatalogSource(
        "v3-selected-tags.csv",
        "298633d94d0031d2081c0893f29c82eab7f0df00b08483ba8f29d1e979441217",
        "SmilingWolf/wd-eva02-large-tagger-v3",
        "b25b82a03f7282e41aa2f257a52c7583b710bd1c",
    ),
    "v2": CatalogSource(
        "v2-selected-tags.csv",
        "8c8750600db36233a1b274ac88bd46289e588b338218c2e4c62bbc9f2b516368",
        "SmilingWolf/wd-v1-4-moat-tagger-v2",
        "8452cddf280b952281b6e102411c50e981cb2908",
    ),
    "v1": CatalogSource(
        "v1-selected-tags.csv",
        "898dbc30bec9a5173b5531fc9b3d6058ea79182832ec4a102facc33cae7669cd",
        "SmilingWolf/wd-v1-4-convnext-tagger",
        "4036ca51f1c082b0e7c4496890bbf9eadad5764a",
    ),
}

if tuple(_MODEL_SPECS) != MODEL_NAMES:
    raise RuntimeError("WD14 model catalogue order changed")

SDK_REQUIRED_WEIGHTS = tuple(
    _MODEL_SPECS[name].weight for name in MODEL_NAMES
)

# Avoid even a repeated broker lookup in a warm guest.  The host remains the
# authority and also caches atomically across guests and processes.
_RESOLVED_MODELS: dict[str, str] = {}


@lru_cache(maxsize=len(_CATALOG_SOURCES))
def load_catalog(generation: str) -> TagCatalog:
    """Load one reviewed, vendored label catalogue and verify its identity."""
    source = _CATALOG_SOURCES.get(str(generation))
    if source is None:
        raise ValueError(f"unknown WD14 label catalogue {generation!r}")
    data = (Path(__file__).with_name("catalogs") / source.filename).read_bytes()
    if hashlib.sha256(data).hexdigest() != source.sha256:
        raise RuntimeError(
            f"vendored WD14 label catalogue {source.filename!r} failed SHA-256"
        )
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise RuntimeError("WD14 label catalogue is not UTF-8") from error
    reader = csv.reader(string_io.StringIO(text, newline=""))
    if next(reader, None) != ["tag_id", "name", "category", "count"]:
        raise RuntimeError("WD14 label catalogue has an unexpected header")
    names: list[str] = []
    categories: list[int] = []
    for line_number, row in enumerate(reader, start=2):
        if len(row) != 4 or not row[1] or len(row[1]) > 512:
            raise RuntimeError(
                f"WD14 label catalogue row {line_number} is malformed"
            )
        try:
            category = int(row[2])
        except ValueError as error:
            raise RuntimeError(
                f"WD14 label catalogue row {line_number} has no category"
            ) from error
        names.append(row[1])
        categories.append(category)
    if not names or len(names) > _MAX_CLASSES:
        raise RuntimeError("WD14 label catalogue has an invalid class count")
    if 0 not in categories:
        raise RuntimeError("WD14 label catalogue contains no general tags")
    catalog = TagCatalog(tuple(names), tuple(categories))
    catalog.category_range(0)
    catalog.category_range(4)
    return catalog


def _render_indices(
    catalog: TagCatalog,
    character_indices: Sequence[int],
    general_indices: Sequence[int],
    exclude_tags: str,
    replace_underscore: bool,
    trailing_comma: bool,
) -> str:
    exclusions_text = str(exclude_tags)
    if len(exclusions_text) > _MAX_EXCLUDE_CHARS:
        raise ValueError("exclude_tags exceeds 65536 characters")
    exclusions = {
        value.strip() for value in exclusions_text.lower().split(",")
    }
    selected: list[str] = []
    previous = {-1: -1, 0: -1}
    for group, indices in ((-1, character_indices), (0, general_indices)):
        for raw_index in indices:
            index = int(raw_index)
            if index <= previous[group]:
                raise ValueError("classifier score indices are not strictly ordered")
            previous[group] = index
            if not 0 <= index < len(catalog):
                raise ValueError("classifier returned an out-of-range class index")
            expected = 4 if group == -1 else 0
            if catalog.categories[index] != expected:
                raise ValueError("classifier index escaped the requested WD14 range")
            original = catalog.names[index]
            name = (
                original.replace("_", " ")
                if replace_underscore
                else original
            )
            if name in exclusions:
                continue
            selected.append(name.replace("(", r"\(").replace(")", r"\)"))
    result = ("" if trailing_comma else ", ").join(
        name + (", " if trailing_comma else "") for name in selected
    )
    if len(result) > _MAX_OUTPUT_CHARS:
        raise ValueError("formatted WD14 tags exceed 192000 characters")
    return result


def format_tags(
    catalog: TagCatalog,
    scores: Sequence[float],
    threshold: float = 0.35,
    character_threshold: float = 0.85,
    exclude_tags: str = "",
    replace_underscore: bool = False,
    trailing_comma: bool = False,
) -> str:
    """Apply upstream's intended category selection and prompt formatting."""
    threshold = float(threshold)
    character_threshold = float(character_threshold)
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold must be in [0, 1]")
    if not 0.0 <= character_threshold <= 1.0:
        raise ValueError("character_threshold must be in [0, 1]")
    if len(scores) != len(catalog):
        raise ValueError(
            f"model returned {len(scores)} scores for {len(catalog)} labels"
        )
    characters: list[int] = []
    general: list[int] = []
    for index, (category, value) in enumerate(zip(
        catalog.categories, scores, strict=True
    )):
        score = float(value)
        if not math.isfinite(score):
            raise ValueError("model returned a non-finite score")
        if category == 4 and score > character_threshold:
            characters.append(index)
        elif category == 0 and score > threshold:
            general.append(index)
    return _render_indices(
        catalog,
        characters,
        general,
        str(exclude_tags),
        bool(replace_underscore),
        bool(trailing_comma),
    )


async def _select_indices(
    scores: Any,
    batch_index: int,
    bounds: tuple[int, int] | None,
    threshold: float,
) -> list[int]:
    if bounds is None:
        return []
    start, end = bounds
    offset = 0
    result: list[int] = []
    previous = start - 1
    pages = 0
    while True:
        page = await scores.select_above(
            int(batch_index),
            start,
            end,
            float(threshold),
            offset=offset,
            limit=_SCORE_PAGE,
        )
        if not isinstance(page, dict):
            raise TypeError("classifier score page must be a dictionary")
        items = page.get("items")
        if not isinstance(items, list) or len(items) > _SCORE_PAGE:
            raise ValueError("classifier score page has an invalid item count")
        for item in items:
            if not isinstance(item, dict):
                raise TypeError("classifier score item must be a dictionary")
            index = item.get("index")
            score = item.get("score")
            if type(index) is not int or not start <= index < end:
                raise ValueError("classifier returned an invalid class index")
            if index <= previous:
                raise ValueError("classifier score indices are not strictly ordered")
            if not isinstance(score, (int, float)) or not math.isfinite(float(score)):
                raise ValueError("classifier returned a non-finite score")
            if not float(score) > float(threshold):
                raise ValueError("classifier returned a score below the threshold")
            previous = index
            result.append(index)
        next_offset = page.get("next_offset")
        if next_offset is None:
            return result
        if type(next_offset) is not int or not offset < next_offset <= end - start:
            raise ValueError("classifier returned an invalid score-page offset")
        offset = next_offset
        pages += 1
        if pages > math.ceil((end - start) / _SCORE_PAGE) + 1:
            raise ValueError("classifier returned too many score pages")


async def _download_once(model: str, spec: ModelSpec) -> str:
    logical = _RESOLVED_MODELS.get(model)
    if logical is not None:
        return logical
    weight = spec.weight
    logical = await sdk.ctx().models.download_huggingface_weights(
        weight.repo_id,
        weight.filename,
        weight.folder,
        revision=weight.revision,
        sha256=weight.sha256,
    )
    _RESOLVED_MODELS[model] = logical
    return logical


class WD14Tagger(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("models",)
    SDK_REQUIRED_WEIGHTS = SDK_REQUIRED_WEIGHTS

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="WD14Tagger|pysssss",
            display_name="WD14 Tagger 🐍",
            category="image",
            description=(
                "Interrogate an image batch with a hash-pinned public WD14 "
                "ONNX model. Weights are fetched from Hugging Face once, on "
                "demand, and then reused from the host cache."
            ),
            inputs=[
                io.Image.Input("image"),
                io.Combo.Input(
                    "model", options=list(MODEL_NAMES), default=DEFAULT_MODEL
                ),
                io.Float.Input(
                    "threshold", default=0.35, min=0.0, max=1.0, step=0.05
                ),
                io.Float.Input(
                    "character_threshold",
                    default=0.85,
                    min=0.0,
                    max=1.0,
                    step=0.05,
                ),
                io.Boolean.Input("replace_underscore", default=False),
                io.Boolean.Input("trailing_comma", default=False),
                io.String.Input("exclude_tags", default="", multiline=False),
            ],
            outputs=[io.String.Output("tags", is_output_list=True)],
            is_output_node=True,
        )

    @classmethod
    async def execute(
        cls,
        image: sdk.ImageRef,
        model: str,
        threshold: float,
        character_threshold: float,
        replace_underscore: bool,
        trailing_comma: bool,
        exclude_tags: str = "",
    ) -> io.NodeOutput:
        spec = _MODEL_SPECS.get(str(model))
        if spec is None:
            raise ValueError("model is not in the sealed WD14 catalogue")
        catalog = load_catalog(spec.catalog)
        batch_size = await image.batch_size()
        if batch_size < 1:
            raise ValueError("WD14 requires a non-empty image batch")
        threshold = float(threshold)
        character_threshold = float(character_threshold)
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be in [0, 1]")
        if not 0.0 <= character_threshold <= 1.0:
            raise ValueError("character_threshold must be in [0, 1]")
        character_range = catalog.category_range(4)
        general_range = catalog.category_range(0)
        await sdk.ctx().progress.update(0, batch_size)

        logical = await _download_once(str(model), spec)
        classifier = await sdk.ctx().models.load_onnx_image_classifier(
            logical,
            input_layout="NHWC",
            channel_order="BGR",
            resize_mode="fit_pad",
            input_scale=255.0,
            pad_color=(1.0, 1.0, 1.0),
            mean=(0.0, 0.0, 0.0),
            std=(1.0, 1.0, 1.0),
            activation="identity",
            resize_filter="lanczos",
        )
        scores = await classifier.predict_scores(image)
        shape = await scores.shape()
        if not isinstance(shape, (list, tuple)) or len(shape) != 2:
            raise ValueError("classifier returned an invalid score-matrix shape")
        score_batches, score_classes = int(shape[0]), int(shape[1])
        if score_batches != batch_size:
            raise ValueError(
                f"model returned {score_batches} batches for {batch_size} images"
            )
        if score_classes != len(catalog):
            raise ValueError(
                f"model returned {score_classes} scores for {len(catalog)} labels"
            )

        tags: list[str] = []
        for index in range(batch_size):
            characters = await _select_indices(
                scores,
                index,
                character_range,
                character_threshold,
            )
            general = await _select_indices(
                scores,
                index,
                general_range,
                threshold,
            )
            tags.append(
                _render_indices(
                    catalog,
                    characters,
                    general,
                    exclude_tags,
                    bool(replace_underscore),
                    bool(trailing_comma),
                )
            )
            if sum(len(value) for value in tags) > _MAX_TOTAL_OUTPUT_CHARS:
                raise ValueError("formatted WD14 batch exceeds 768000 characters")
            await sdk.ctx().progress.update(index + 1, batch_size)
        return io.NodeOutput(tags, ui={"tags": tags})


NODE_CLASS_MAPPINGS = {"WD14Tagger|pysssss": WD14Tagger}
NODE_DISPLAY_NAME_MAPPINGS = {"WD14Tagger|pysssss": "WD14 Tagger 🐍"}

__all__ = [
    "MODEL_NAMES",
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "SDK_REQUIRED_WEIGHTS",
    "TagCatalog",
    "format_tags",
    "load_catalog",
]
