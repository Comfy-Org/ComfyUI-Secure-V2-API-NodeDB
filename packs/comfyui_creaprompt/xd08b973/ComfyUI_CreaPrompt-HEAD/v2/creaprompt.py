"""Secure CreaPrompt nodes backed only by the pack's pinned prompt catalogues."""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from comfy_api.latest import io


_ROOT = Path(__file__).resolve().parent
_DISABLED = "disabled"
_RANDOM = "🎲random"
_COLLECTION_LEGACY_LABEL = "collection.txt (legacy)"

# The legacy implementation used os.listdir() for execution order. Directory
# enumeration is not a portable wire contract, so the order observed in the
# pinned source tree is sealed explicitly here. CreaPrompt's own schema sorted
# its first catalogue; the other four schemas used these same observed orders.
_FILES: dict[str, tuple[str, ...]] = {
    "csv": (
        "3_7Sky_Malapris_OCOMA.csv", "1_6Haircolors_Thomas_Buyle.csv",
        "0_0Man.csv", "9_9Prevention_Malapris.csv", "2_9Vehicles.csv",
        "3_8Eras_Malapris.csv", "7_7Visual_effects_Lololerigolo.csv",
        "2_2Sports_Malapris_OCOMA.csv", "2_3Actions.csv",
        "8_1Styles_AdelAI_Realistic.csv", "3_5Special_Places.csv",
        "4_1Z_Style.csv", "3_3Places.csv",
        "1_4Haircuts_Thomas_Buyle.csv", "1_7Eyes_Style.csv",
        "2_6Fictional_Characters.csv", "9_9Accidents_Industry_Malapris.csv",
        "1_9Kontext_Transform_Man.csv", "2_8Humanoids.csv",
        "1_1Retro_woman_Lololerigolo.csv", "1_9Kontext_Transform_Woman.csv",
        "7_5Lighting.csv", "3_0Shotstyle.csv", "6_2Image_Quality.csv",
        "8_4Films_AdelAI_Realistic.csv", "1_9Fashion.csv",
        "4_0Artistic_Style.csv", "1_9Kontext_change_background.csv",
        "2_7Superheros_Lololerigolo.csv", "1_2Celebrity_Woman.csv",
        "1_2Celebrity_Man.csv", "3_6Locations.csv",
        "3_2Strange_place_Lololerigolo.csv",
        "5_0Furnitures_tables_Lololerigolo.csv", "2_1Erotic_OCOMA.csv",
        "1_1Posing.csv", "7_4Cameras.csv", "2_4Films_Scenes_Malapris.csv",
        "5_1Furnitures_cabinets_Lololerigolo.csv",
        "1_8Woman_Dress_Malapris_PJ.csv", "8_0Effects_AdelAI_Realistic.csv",
        "1_0Woman.csv", "4_2Artists.csv", "3_4Landscapes.csv",
        "2_0Expressions_Malapris.csv", "3_1Strange_building_Lololerigolo.csv",
        "2_5Animals.csv",
    ),
    "csv1": (
        "1_6Haircolors_Thomas_Buyle.csv", "3_3Places.csv",
        "1_4Haircuts_Thomas_Buyle.csv", "3_0Shotstyle.csv", "1_9Fashion.csv",
        "1_2Celebrity_Woman.csv", "1_8Woman_Dress_Malapris_PJ.csv",
        "1_0Woman.csv",
    ),
    "csv2": (
        "1_6Haircolors_Thomas_Buyle.csv", "0_0Man.csv", "3_3Places.csv",
        "1_4Haircuts_Thomas_Buyle.csv", "7_5Lighting.csv",
        "6_2Image_Quality.csv", "1_2Celebrity_Man.csv", "7_4Cameras.csv",
    ),
    "csv3": (
        "3_7Sky_Malapris_OCOMA.csv", "3_3Places.csv", "7_5Lighting.csv",
        "6_2Image_Quality.csv", "4_0Artistic_Style.csv", "7_4Cameras.csv",
        "4_2Artists.csv", "3_4Landscapes.csv", "2_5Animals.csv",
    ),
    "csv+weight": (
        "1_6Haircolors_Thomas_Buyle.csv", "1_4Haircuts_Thomas_Buyle.csv",
        "2_4Films_Scenes_Malapris.csv", "1_8Woman_Dress_Malapris_PJ.csv",
        "1_0Woman.csv",
    ),
}


def _label(filename: str) -> str:
    return filename[3:-4]


def _lines(folder: str, filename: str) -> list[str]:
    return (_ROOT / folder / filename).read_text(encoding="utf-8").splitlines(
        keepends=True
    )


def _select_random_line(folder: str, label: str) -> str:
    filename = next(
        (item for item in _FILES[folder] if _label(item) == label), None
    )
    if filename is None:
        return ""
    lines = _lines(folder, filename)
    return random.choice(lines).strip() if lines else ""


def _collection_names() -> tuple[str, ...]:
    names = tuple(sorted(path.stem for path in (_ROOT / "collections").glob("*.txt")))
    return names or (_COLLECTION_LEGACY_LABEL,)


def _collection_line(name: str | None = None) -> str:
    path = _ROOT / "csv" / "collection.txt"
    if name and name != _COLLECTION_LEGACY_LABEL:
        candidate = _ROOT / "collections" / f"{name}.txt"
        if candidate.is_file():
            path = candidate
    lines = path.read_text(encoding="utf-8").splitlines()
    return random.choice(lines).strip()


def _category_inputs(
    folder: str, *, weighted: bool = False, sort_schema: bool = False
) -> list[io.Input]:
    filenames = sorted(_FILES[folder]) if sort_schema else _FILES[folder]
    inputs: list[io.Input] = []
    for filename in filenames:
        name = _label(filename)
        inputs.append(
            io.Combo.Input(
                name,
                options=[_DISABLED, _RANDOM, *_lines(folder, filename)],
                default=_DISABLED,
            )
        )
        if weighted:
            inputs.append(io.Float.Input(f"{name}: Weight", default=1.0, min=-3.0, max=3.0))
    return inputs


def _common_optional_inputs() -> list[io.Input]:
    return [
        io.Int.Input("Prompt_count", optional=True, default=1, min=1, max=1000),
        io.Combo.Input(
            "CreaPrompt_Collection",
            options=["disabled", "enabled"],
            optional=True,
            default="disabled",
        ),
        io.Int.Input(
            "seed", optional=True, default=0, min=0, max=1125899906842624
        ),
    ]


def _generate_prompt(folder: str, kwargs: dict[str, Any], *, weighted: bool) -> tuple[str, int]:
    seed = int(kwargs.get("seed", 0))
    count = int(kwargs.get("Prompt_count", 0))
    if kwargs.get("CreaPrompt_Collection", 0) == "enabled":
        return "\n".join(_collection_line() for _ in range(count)), seed

    prompts: list[str] = []
    for _ in range(count):
        values: list[str] = []
        for filename in _FILES[folder]:
            name = _label(filename)
            selected = kwargs.get(name, 0)
            value = (
                _select_random_line(folder, name)
                if selected == _RANDOM
                else selected.strip()
            )
            if weighted:
                weight = kwargs.get(f"{name}: Weight", 0)
                if weight not in (0, 1):
                    value = f"({value}:{weight:.1f})"
            if value != _DISABLED:
                values.append(value)
        prompts.append(",".join(values))
    return "\n".join(prompts), seed


def _make_prompt_node(
    node_id: str,
    display_name: str,
    folder: str,
    *,
    weighted: bool = False,
    sort_schema: bool = False,
) -> type[io.ComfyNode]:
    class PromptNode(io.ComfyNode):
        SDK_REFS = True
        SDK_PERMISSIONS = ()

        @classmethod
        def define_schema(cls) -> io.Schema:
            return io.Schema(
                node_id=node_id,
                display_name=display_name,
                category="CreaPrompt",
                inputs=[
                    *_category_inputs(
                        folder, weighted=weighted, sort_schema=sort_schema
                    ),
                    *_common_optional_inputs(),
                ],
                outputs=[io.String.Output("prompt"), io.Int.Output("seed")],
                not_idempotent=True,
            )

        @classmethod
        async def execute(cls, **kwargs: Any) -> io.NodeOutput:
            prompt, seed = _generate_prompt(folder, kwargs, weighted=weighted)
            return io.NodeOutput(prompt, seed)

    PromptNode.__name__ = f"{node_id.replace(' ', '_')}Secure"
    PromptNode.__qualname__ = PromptNode.__name__
    return PromptNode


class CreaPromptDynamic(io.ComfyNode):
    """Dynamic catalogue node; the optional remote-code enhancer is refused."""

    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        collections = list(_collection_names())
        enhancer_presets = [
            *json.loads((_ROOT / "enhancer_presets.json").read_text()),
            "Your instruction",
        ]
        return io.Schema(
            node_id="CreaPrompt_0",
            display_name="CreaPrompt Dynamic node",
            category="CreaPrompt",
            inputs=[
                io.String.Input(
                    "__csv_json",
                    default="{}",
                    multiline=True,
                    extra_dict={"input": False},
                ),
                io.Int.Input("Prompt_count", optional=True, default=1, min=1, max=1000),
                io.Combo.Input(
                    "CreaPrompt_Collection",
                    options=["disabled", "enabled"],
                    optional=True,
                    default="disabled",
                ),
                io.Combo.Input(
                    "Choose_collection",
                    options=collections,
                    optional=True,
                    default=collections[0],
                ),
                io.Int.Input(
                    "seed", optional=True, default=0, min=0, max=1125899906842624
                ),
                io.Combo.Input(
                    "Enhancer",
                    options=["disabled", "enabled"],
                    optional=True,
                    default="disabled",
                ),
                io.String.Input(
                    "Enhancer_model",
                    optional=True,
                    default="hfmaster/Qwen3-VL-4B",
                ),
                io.Combo.Input(
                    "Enhancer_precision",
                    options=["fp16", "bf16"],
                    optional=True,
                    default="fp16",
                ),
                io.Combo.Input(
                    "Enhancer_preset",
                    options=enhancer_presets,
                    optional=True,
                    default=enhancer_presets[0],
                ),
                io.String.Input(
                    "Enhancer_instruction", optional=True, default="", multiline=True
                ),
                io.Int.Input(
                    "Enhancer_max_tokens",
                    optional=True,
                    default=512,
                    min=64,
                    max=4096,
                    step=64,
                ),
                io.Boolean.Input("Use_image", optional=True, default=True),
                io.Boolean.Input("Use_text", optional=True, default=False),
                io.Boolean.Input("Use_categories", optional=True, default=True),
                io.Boolean.Input(
                    "Unload_after_generation", optional=True, default=True
                ),
                io.String.Input("text", optional=True, force_input=True),
                io.Image.Input("image", optional=True),
                io.Image.Input("image_2", optional=True),
                io.Image.Input("image_3", optional=True),
                io.Image.Input("video", optional=True),
            ],
            outputs=[io.String.Output("prompt"), io.Int.Output("seed")],
            not_idempotent=True,
        )

    @classmethod
    async def execute(cls, **kwargs: Any) -> io.NodeOutput:
        if kwargs.get("Enhancer", "disabled") == "enabled":
            raise PermissionError(
                "CreaPrompt Enhancer is unavailable in Secure Nodes: the pinned "
                "implementation accepts an arbitrary model repository, downloads an "
                "unpinned snapshot, and executes trust_remote_code"
            )

        dynamic = json.loads(str(kwargs.get("__csv_json", "{}")))
        if not isinstance(dynamic, dict):
            raise ValueError("__csv_json must encode a category object")
        if len(dynamic) > len(_FILES["csv"]):
            raise ValueError("too many CreaPrompt dynamic categories")

        seed = int(kwargs.get("seed", 0))
        count = int(kwargs.get("Prompt_count", 0))
        prompts: list[str] = []
        if kwargs.get("CreaPrompt_Collection", 0) == "enabled":
            collection = kwargs.get("Choose_collection")
            for _ in range(count):
                prompts.append(_collection_line(str(collection)))
                # The pinned Enhancer implementation collected one category
                # line after every collection choice even while Enhancer was
                # disabled. That line never reached the output, but random
                # category selections consumed RNG state and therefore changed
                # the next collection choice. Preserve that observable order.
                for filename in _FILES["csv"]:
                    name = _label(filename)
                    selected = dynamic.get(name, _DISABLED)
                    if selected == _RANDOM:
                        _select_random_line("csv", name)
        else:
            for _ in range(count):
                values: list[str] = []
                for filename in _FILES["csv"]:
                    name = _label(filename)
                    selected = dynamic.get(name, _DISABLED)
                    if not isinstance(selected, str):
                        raise TypeError(f"dynamic category {name!r} must be a string")
                    value = (
                        _select_random_line("csv", name)
                        if selected == _RANDOM
                        else selected.strip()
                    )
                    if value != _DISABLED:
                        values.append(value)
                prompts.append(",".join(values))
        return io.NodeOutput("\n".join(prompts), seed)


class CreaPromptList(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="CreaPrompt List",
            display_name="CreaPrompt Multi Prompts",
            category="CreaPrompt",
            inputs=[
                io.String.Input("Multi_prompts", default="body_text", multiline=True),
                io.Int.Input("seed_base", force_input=True),
                io.String.Input("prefix", default="", multiline=True),
                io.String.Input("suffix", default="", multiline=True),
            ],
            outputs=[
                io.String.Output("prompt", is_output_list=True),
                io.Int.Output("seed", is_output_list=True),
                io.String.Output("prompt_debug"),
            ],
        )

    @classmethod
    async def execute(
        cls,
        Multi_prompts: str,
        seed_base: int,
        prefix: str = "",
        suffix: str = "",
    ) -> io.NodeOutput:
        lines = Multi_prompts.strip().split("\n")
        if prefix and suffix:
            prompts = [f"{prefix},{line},{suffix}" for line in lines]
            debug = [f"➡️{prefix},{line},{suffix}" for line in lines]
        elif prefix:
            prompts = [f"{prefix},{line}" for line in lines]
            debug = [f"➡️{prefix},{line}" for line in lines]
        elif suffix:
            prompts = [f"{line},{suffix}" for line in lines]
            debug = [f"➡️{line},{suffix}" for line in lines]
        else:
            prompts = lines
            debug = [f"➡️{line}" for line in lines]
        seeds = [int(seed_base) + index for index in range(len(prompts))]
        return io.NodeOutput(prompts, seeds, "\n".join(debug))


CreaPrompt = _make_prompt_node(
    "CreaPrompt", "CreaPrompt complete node", "csv", sort_schema=True
)
CreaPrompt_1 = _make_prompt_node(
    "CreaPrompt_1", "CreaPrompt node 1", "csv1"
)
CreaPrompt_2 = _make_prompt_node(
    "CreaPrompt_2", "CreaPrompt node 2", "csv2"
)
CreaPrompt_3 = _make_prompt_node(
    "CreaPrompt_3", "CreaPrompt node 3", "csv3"
)
CreaPrompt_4 = _make_prompt_node(
    "CreaPrompt_4", "CreaPrompt node with weight", "csv+weight", weighted=True
)

NODE_CLASS_MAPPINGS = {
    "CreaPrompt_0": CreaPromptDynamic,
    "CreaPrompt": CreaPrompt,
    "CreaPrompt_1": CreaPrompt_1,
    "CreaPrompt_2": CreaPrompt_2,
    "CreaPrompt_3": CreaPrompt_3,
    "CreaPrompt_4": CreaPrompt_4,
    "CreaPrompt List": CreaPromptList,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    node_id: node_class.define_schema().display_name
    for node_id, node_class in NODE_CLASS_MAPPINGS.items()
}
NODE_DISPLAY_NAME_MAPPINGS["CSL"] = "Comma Separated List"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
