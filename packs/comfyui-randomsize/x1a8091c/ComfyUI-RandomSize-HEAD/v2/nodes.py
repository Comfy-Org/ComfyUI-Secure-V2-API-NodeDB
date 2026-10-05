"""Secure Nodes V2 backend for ComfyUI-RandomSize."""

from __future__ import annotations

import random

from comfy_api.latest import ComfyExtension, io


PRESETS: dict[str, tuple[str, ...]] = {
    "Preset": (
        "320x768", "384x640", "512x768", "448x576", "512x512",
        "576x448", "768x512", "640x384", "768x320",
    ),
    "FLUX.yaml": (
        "1920x1088", "1088x1920", "1920x1200", "1200x1920",
        "1920x1440", "1440x1920", "1024x1024", "1024x1536",
        "1536x1024", "1600x1200", "1200x1600", "1360x768",
        "768x1360",
    ),
    "640.yaml": (
        "320x1216", "384x1024", "448x896", "512x768", "640x640",
        "768x512", "896x448", "1024x384", "1216x320",
    ),
    "1024.yaml": (
        "512x2048", "576x1792", "640x1600", "704x1472", "768x1344",
        "832x1216", "896x1152", "960x1088", "1024x1024", "1088x960",
        "1152x896", "1216x832", "1344x768", "1472x704", "1600x640",
        "1792x576", "2048x512",
    ),
    "768.yaml": (
        "384x1536", "448x1280", "512x1152", "576x1024", "640x896",
        "704x832", "768x768", "832x704", "896x640", "1024x576",
        "1152x512", "1280x448", "1536x384",
    ),
    "512.yaml": (
        "256x1024", "320x768", "384x640", "448x576", "512x512",
        "576x448", "640x384", "768x320", "1024x256",
    ),
    "SD1.5.yaml": (
        "320x768", "384x640", "512x768", "448x576", "512x512",
        "576x448", "768x512", "640x384", "768x320",
    ),
    "SDXL.yaml": (
        "640x1536", "768x1344", "832x1216", "896x1152", "1024x1024",
        "1152x896", "1216x832", "1344x768", "1536x640",
    ),
    "896.yaml": (
        "448x1792", "512x1536", "576x1344", "640x1216", "704x1088",
        "768x1024", "832x960", "896x896", "960x832", "1024x768",
        "1088x704", "1216x640", "1344x576", "1536x512", "1792x448",
    ),
}

MAX_SEED = 0xFFFFFFFFFFFFFFFF


def choose_size(seed: int, preset: str) -> tuple[int, int, list[str], str]:
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError("seed must be an integer")
    if not 0 <= seed <= MAX_SEED:
        raise ValueError(f"seed must be between 0 and {MAX_SEED}")
    try:
        sizes = PRESETS[preset]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"unknown preset: {preset!r}") from exc
    selected = sizes[seed] if seed < len(sizes) else random.Random(seed).choice(sizes)
    marked = [f"*{size}*" if size == selected else size for size in sizes]
    width, height = (int(value) for value in selected.split("x"))
    return width, height, marked, selected


class RandomSize(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="JOJR_RandomSize",
            display_name="Random Size",
            category="utils",
            inputs=[
                io.Int.Input("seed", default=0, min=0, max=MAX_SEED),
                io.Combo.Input("preset", options=list(PRESETS)),
            ],
            outputs=[
                io.Int.Output(display_name="width"),
                io.Int.Output(display_name="height"),
            ],
            hidden=[io.Hidden.unique_id],
        )

    @classmethod
    def execute(
        cls,
        seed: int,
        preset: str,
        id: str | None = None,
    ) -> io.NodeOutput:
        del id
        width, height, sizes, selected = choose_size(seed, preset)
        return io.NodeOutput(
            width,
            height,
            ui={"sizes": sizes, "selected": [selected], "preset": [preset]},
        )


NODE_CLASS_MAPPINGS = {"JOJR_RandomSize": RandomSize}
NODE_DISPLAY_NAME_MAPPINGS = {"JOJR_RandomSize": "Random Size"}


class RandomSizeExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [RandomSize]


async def comfy_entrypoint() -> RandomSizeExtension:
    return RandomSizeExtension()
