"""Secure V2 implementation of the nineteen QQ Nodes registrations."""
from __future__ import annotations

import builtins
from typing import Any

from comfy_api.latest import io, sdk


LIST = io.Custom("LIST")
AXIS_VALUE = io.Custom("AXIS_VALUE")
PACK = io.Custom("PACK")
XY_GRID_CONTROL = io.Custom("XY_GRID_CONTROL")
NUMBER = io.Custom("NUMBER")

_MAX_LIST = 4_096
_MAX_TEXT_BYTES = 64 * 1024 * 1024
_AXIS_TYPES = (
    "STRING", "MODEL", "INT", "NUMBER", "FLOAT", "BOOLEAN", "VAE", "CLIP",
)
_AXIS_OUTPUTS = {
    "STRING": io.String,
    "MODEL": io.Model,
    "INT": io.Int,
    "NUMBER": NUMBER,
    "FLOAT": io.Float,
    "BOOLEAN": io.Boolean,
    "VAE": io.Vae,
    "CLIP": io.Clip,
}


def _any_inputs(*, label: bool = False) -> list[io.Input]:
    values = [io.AnyType.Input("input_a", extra_dict={"forceInput": True})]
    values.extend(
        io.AnyType.Input(
            f"input_{letter}", optional=True,
            extra_dict={"forceInput": True},
        )
        for letter in "bcdefg"
    )
    if label:
        values.append(io.String.Input("label", default="", optional=True))
    return values


def _truthy_values(first: Any, *optional: Any) -> list[Any]:
    values = [first]
    values.extend(value for value in optional if value)
    return values


def _is_axis_pack(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and value.get("secure_kind") == "qq.axis_pack"
        and set(value) == {"secure_kind", "label", "value"}
        and isinstance(value.get("label"), str)
        and isinstance(value.get("value"), list)
    )


def _bounded_list(value: Any, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise TypeError(f"{name} must be a LIST")
    if not 1 <= len(value) <= _MAX_LIST:
        raise ValueError(f"{name} must contain 1..{_MAX_LIST} values")
    return value


def _label(value: Any) -> str:
    if _is_axis_pack(value):
        return value["label"]
    return str(value)


def _format_prefix(prefix: str, text: str) -> str:
    return f"{prefix}: {text}" if prefix else text


def _insert_newlines(value: str, length: int) -> str:
    result = ""
    current_index = 0
    while current_index < len(value):
        if current_index + length >= len(value):
            result += value[current_index:]
            break
        next_cutoff = current_index + length
        space_index = value.rfind(" ", current_index, next_cutoff)
        if space_index > current_index:
            result += value[current_index:space_index] + "\n"
            current_index = space_index + 1
        else:
            result += value[current_index:next_cutoff] + "\n"
            current_index = next_cutoff
    return result


def _always_changed(**_kwargs: Any) -> float:
    return float("nan")


def _input_asset_name(value: Any) -> str:
    name = str(value).replace("\\", "/")
    parts = name.split("/")
    if (
        not name
        or name.startswith("/")
        or "\x00" in name
        or any(part in {"", ".", ".."} for part in parts)
    ):
        raise ValueError("text file name must stay inside managed input assets")
    return name


class AnyList(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Any List",
            category="QQNodes/List",
            inputs=_any_inputs(),
            outputs=[LIST.Output("output_0", display_name="LIST")],
        )

    @classmethod
    async def execute(
        cls,
        input_a: Any,
        input_b: Any = None,
        input_c: Any = None,
        input_d: Any = None,
        input_e: Any = None,
        input_f: Any = None,
        input_g: Any = None,
    ) -> io.NodeOutput:
        return io.NodeOutput(_truthy_values(
            input_a, input_b, input_c, input_d, input_e, input_f, input_g,
        ))


class AnyListIterator(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Any List Iterator",
            category="QQNodes/List",
            inputs=[io.Int.Input("counter", default=0), LIST.Input("list")],
            outputs=[AXIS_VALUE.Output("output_0", display_name="AXIS_VALUE")],
        )

    @classmethod
    async def execute(cls, counter: int, list: list[Any]) -> io.NodeOutput:
        values = _bounded_list(list, "list")
        return io.NodeOutput(values[int(counter) % len(values)])


class AxisPack(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Axis Pack",
            category="QQNodes/XYGrid Axis",
            inputs=_any_inputs(label=True),
            outputs=[PACK.Output("output_0", display_name="PACK")],
        )

    @classmethod
    async def execute(
        cls,
        input_a: Any,
        input_b: Any = None,
        input_c: Any = None,
        input_d: Any = None,
        input_e: Any = None,
        input_f: Any = None,
        input_g: Any = None,
        label: str = "",
    ) -> io.NodeOutput:
        return io.NodeOutput({
            "secure_kind": "qq.axis_pack",
            "label": str(label),
            "value": _truthy_values(
                input_a, input_b, input_c, input_d, input_e, input_f, input_g,
            ),
        })


class AxisUnpack(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Axis Unpack",
            category="QQNodes/XYGrid Axis",
            inputs=[AXIS_VALUE.Input("axis")],
            outputs=[
                AXIS_VALUE.Output(f"output_{letter}") for letter in "abcdefg"
            ],
        )

    @classmethod
    async def execute(cls, axis: Any) -> io.NodeOutput:
        if not _is_axis_pack(axis):
            raise TypeError("Axis Unpack requires a value produced by Axis Pack")
        values = axis["value"]
        if len(values) > 7:
            raise ValueError("Axis Pack contains more than seven values")
        return io.NodeOutput(*(values + [None] * (7 - len(values))))


class LoadLinesFromTextFile(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("assets",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Load Lines From Text File",
            category="QQNodes/Text",
            inputs=[io.Combo.Input(
                "file",
                options=[],
                remote=io.RemoteOptions(
                    route="/secure-nodes/text-files/input",
                    refresh_button=True,
                ),
            )],
            outputs=[LIST.Output("output_0", display_name="LIST")],
        )

    @classmethod
    async def execute(cls, file: str) -> io.NodeOutput:
        asset = await sdk.ctx().assets.resolve("input", _input_asset_name(file))
        if await sdk.ctx().assets.size(asset) > _MAX_TEXT_BYTES:
            raise ValueError("text file exceeds the 64 MiB asset-read bound")
        data = await sdk.ctx().assets.read_bytes(asset)
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError("selected text file is not UTF-8") from error
        # Upstream uses text-mode ``readlines()``, whose universal-newline
        # layer maps CRLF and lone CR to LF. The broker deliberately returns
        # bytes, so reproduce that normalization here before splitting.
        lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines(
            keepends=True,
        )
        if len(lines) > 1_000_000:
            raise ValueError("text file contains too many lines")
        return io.NodeOutput(lines)

    @classmethod
    async def validate_inputs(cls, file: str) -> bool | str:
        try:
            name = _input_asset_name(file)
            await sdk.ctx().assets.resolve("input", name)
        except (FileNotFoundError, ValueError):
            return f"Invalid text file: {file}"
        return True

    @classmethod
    async def fingerprint_inputs(cls, file: str) -> str:
        asset = await sdk.ctx().assets.resolve("input", _input_asset_name(file))
        return await sdk.ctx().assets.digest(asset)


class TextSplitter(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Text Splitter",
            category="QQNodes/Text",
            inputs=[
                io.String.Input("text", default=""),
                io.String.Input("delimiter", default=","),
            ],
            outputs=[LIST.Output("output_0", display_name="LIST")],
        )

    @classmethod
    async def execute(cls, text: str, delimiter: str) -> io.NodeOutput:
        result = str(text).split(str(delimiter))
        if len(result) > 1_000_000:
            raise ValueError("split result contains too many values")
        return io.NodeOutput(result)


class SliceList(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Slice List",
            category="QQNodes/List",
            inputs=[
                LIST.Input("list"),
                io.Int.Input("start", default=0),
                io.Int.Input("end", default=1),
            ],
            outputs=[LIST.Output("output_0", display_name="LIST")],
        )

    @classmethod
    async def execute(cls, list: list[Any], start: int, end: int) -> io.NodeOutput:
        if not isinstance(list, builtins.list):
            raise TypeError("list must be a LIST")
        return io.NodeOutput(list[int(start):int(end)])


class AnyToAny(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Any To Any",
            category="QQNodes/Utils",
            inputs=[io.AnyType.Input("any")],
            outputs=[io.AnyType.Output("output_0")],
        )

    @classmethod
    async def execute(cls, any: Any) -> io.NodeOutput:
        return io.NodeOutput(any)


class _AxisTo(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    NODE_ID = "Axis To Any"
    OUTPUT = io.AnyType

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id=cls.NODE_ID,
            category="QQNodes/XYGrid Axis",
            inputs=[AXIS_VALUE.Input("axis")],
            outputs=[cls.OUTPUT.Output("output_0")],
        )

    @classmethod
    async def execute(cls, axis: Any) -> io.NodeOutput:
        return io.NodeOutput(axis)


class AxisToAny(_AxisTo):
    pass


def _axis_class(output_type: str) -> type[_AxisTo]:
    return type(
        f"AxisTo{output_type}",
        (_AxisTo,),
        {
            "__module__": __name__,
            "NODE_ID": f"Axis To {output_type}",
            "OUTPUT": _AXIS_OUTPUTS[output_type],
        },
    )


class XYGridHelper(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    fingerprint_inputs = classmethod(_always_changed)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="XY Grid Helper",
            category="QQNodes/XYGrid",
            not_idempotent=True,
            inputs=[
                LIST.Input("row_list"),
                LIST.Input("column_list"),
                io.String.Input("row_prefix", default="", optional=True),
                io.String.Input("column_prefix", default="", optional=True),
                io.Int.Input(
                    "page_size", default=10, min=1, max=_MAX_LIST, optional=True,
                ),
                io.Int.Input(
                    "label_length", default=50, min=1, max=4_096, optional=True,
                ),
                io.Int.Input(
                    "font_size", default=50, min=1, max=512, optional=True,
                ),
                io.Int.Input(
                    "grid_gap", default=20, min=0, max=16_384, optional=True,
                ),
                io.Int.Input("index", default=0, optional=True),
            ],
            outputs=[
                AXIS_VALUE.Output("row_value", display_name="row_value"),
                AXIS_VALUE.Output("column_value", display_name="column_value"),
                XY_GRID_CONTROL.Output(
                    "xy_grid_control", display_name="xy_grid_control",
                ),
            ],
        )

    @classmethod
    async def execute(
        cls,
        row_list: list[Any],
        column_list: list[Any],
        row_prefix: str,
        column_prefix: str,
        page_size: int,
        label_length: int,
        font_size: int,
        grid_gap: int,
        index: int,
    ) -> io.NodeOutput:
        rows = _bounded_list(row_list, "row_list")
        columns = _bounded_list(column_list, "column_list")
        total = len(rows) * len(columns)
        if total > 16_777_216:
            raise ValueError("XY grid exceeds the bounded combination count")
        adjusted_index = int(index) % total
        row_index = adjusted_index // len(columns) % len(rows)
        page_index = row_index // int(page_size)
        images_per_page = int(page_size) * len(columns)
        row_annotation = ";".join(
            _insert_newlines(
                _format_prefix(str(row_prefix), _label(item)), int(label_length),
            )
            for item in rows[
                page_index * int(page_size):(page_index + 1) * int(page_size)
            ]
        )
        column_annotation = ";".join(
            _insert_newlines(
                _format_prefix(str(column_prefix), _label(item)), int(label_length),
            )
            for item in columns
        )
        control = (
            min(images_per_page, total - page_index * int(page_size)),
            adjusted_index % images_per_page,
            row_annotation,
            column_annotation,
            len(columns),
            int(font_size),
            int(grid_gap),
        )
        return io.NodeOutput(
            rows[row_index],
            columns[adjusted_index % len(columns)],
            control,
            ui={"total_images": [total]},
        )


class XYGridAccumulator(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = (
        "images.accumulate",
        "ui",
        "graph.block",
        "graph.expand",
        "graph.expand.external:GridAnnotation",
        "graph.expand.external:ImagesGridByColumns",
    )

    fingerprint_inputs = classmethod(_always_changed)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="XY Grid Accumulator",
            category="QQNodes/XYGrid",
            not_idempotent=True,
            enable_expand=True,
            inputs=[
                io.Image.Input("images"),
                XY_GRID_CONTROL.Input("xy_grid_control"),
            ],
            outputs=[io.Image.Output("images", display_name="images")],
            hidden=[io.Hidden.unique_id],
        )

    @classmethod
    async def execute(
        cls,
        images: sdk.ImageRef,
        xy_grid_control: list[Any] | tuple[Any, ...],
        unique_id: str,
    ) -> io.NodeOutput:
        del unique_id  # Host derives the storage identity from the active node.
        if not isinstance(xy_grid_control, (list, tuple)) or len(xy_grid_control) != 7:
            raise TypeError("xy_grid_control must come from XY Grid Helper")
        count, reset, row_texts, column_texts, max_columns, font_size, gap = (
            xy_grid_control
        )
        if any(isinstance(item, bool) or not isinstance(item, int) for item in (
            count, reset, max_columns, font_size, gap,
        )):
            raise TypeError("xy_grid_control contains invalid numeric values")
        if (
            not 1 <= count <= _MAX_LIST
            or not 0 <= reset < count
            or not 1 <= max_columns <= _MAX_LIST
            or not 1 <= font_size <= 512
            or not 0 <= gap <= 16_384
            or not isinstance(row_texts, str)
            or not isinstance(column_texts, str)
        ):
            raise ValueError("xy_grid_control is outside its bounded schema")

        page = await images.op(
            "image.accumulate",
            slot="xy_grid",
            reset=reset == 0,
            take=count,
            max_images=_MAX_LIST,
        )
        if not isinstance(page, dict) or set(page) != {"images", "ready", "buffered"}:
            raise RuntimeError("image accumulator returned an invalid result")
        page_images = page["images"]
        if not isinstance(page_images, sdk.ImageRef):
            raise RuntimeError("image accumulator did not return an IMAGE ref")
        ui = await sdk.ctx().ui.preview_images(page_images)
        if page["ready"] is not True:
            blocker = await sdk.ctx().graph.block(None)
            return io.NodeOutput(blocker, ui=ui)

        expansion = await sdk.ctx().graph.expand_nodes(
            [
                {
                    "id": "annotation",
                    "class_type": "GridAnnotation",
                    "inputs": {
                        "row_texts": row_texts,
                        "column_texts": column_texts,
                        "font_size": font_size,
                    },
                },
                {
                    "id": "grid",
                    "class_type": "ImagesGridByColumns",
                    "inputs": {
                        "images": page_images,
                        "annotation": {"node": "annotation", "output": 0},
                        "max_columns": max_columns,
                        "gap": gap,
                    },
                },
            ],
            [{"node": "grid", "output": 0}],
        )
        return io.NodeOutput(
            *expansion["result"], ui=ui, expand=expansion["expand"],
        )


NODE_CLASS_MAPPINGS = {
    "Any List": AnyList,
    "Any List Iterator": AnyListIterator,
    "Load Lines From Text File": LoadLinesFromTextFile,
    "XY Grid Helper": XYGridHelper,
    "XY Grid Accumulator": XYGridAccumulator,
    "Slice List": SliceList,
    "Axis Pack": AxisPack,
    "Axis Unpack": AxisUnpack,
    "Text Splitter": TextSplitter,
    "Any To Any": AnyToAny,
    "Axis To Any": AxisToAny,
}

for _output_type in _AXIS_TYPES:
    _generated = _axis_class(_output_type)
    globals()[_generated.__name__] = _generated
    NODE_CLASS_MAPPINGS[_generated.NODE_ID] = _generated

NODE_DISPLAY_NAME_MAPPINGS: dict[str, str] = {}


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
