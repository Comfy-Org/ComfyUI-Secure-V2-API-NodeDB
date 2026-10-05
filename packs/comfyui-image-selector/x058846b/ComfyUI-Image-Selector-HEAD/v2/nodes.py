"""Secure batch selector and duplicator nodes."""

from __future__ import annotations

from comfy_api.latest import io, sdk


_MAX_SELECTOR_CHARS = 65_536


def _parse_indices(expression: str, batch_size: int) -> list[int]:
    """Reproduce the legacy pack's one-based single/range syntax."""
    if not isinstance(expression, str):
        raise TypeError("selected_indexes must be a string")
    if len(expression) > _MAX_SELECTOR_CHARS:
        raise ValueError("selected_indexes is too large")
    if not 1 <= batch_size <= 4096:
        raise ValueError("batch size must be in [1, 4096]")

    selected: list[int] = []
    all_indices = list(range(batch_size))
    for segment in expression.strip().split(","):
        try:
            if ":" in segment:
                start_text, end_text = segment.strip().split(":", maxsplit=1)
                if start_text and end_text:
                    selected.extend(all_indices[
                        int(start_text) - 1:int(end_text) - 1])
                elif start_text:
                    selected.extend(all_indices[int(start_text) - 1:])
                elif end_text:
                    selected.extend(all_indices[:int(end_text) - 1])
            else:
                index = int(segment.strip()) - 1
                if index < batch_size:
                    selected.append(index)
        except (TypeError, ValueError):
            continue

    normalized: list[int] = []
    for index in selected:
        if index < -batch_size:
            raise IndexError("batch index is out of range")
        normalized.append(index + batch_size if index < 0 else index)
    return normalized


class ImageSelector(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ImageSelector",
            display_name="ImageSelector",
            category="image",
            inputs=[
                io.Image.Input("images"),
                io.String.Input(
                    "selected_indexes", default="1,2,3", multiline=False),
            ],
            outputs=[io.Image.Output()],
        )

    @classmethod
    async def execute(
        cls, images: sdk.ImageRef, selected_indexes: str,
    ) -> io.NodeOutput:
        indices = _parse_indices(
            selected_indexes, await images.batch_size())
        if not indices:
            return io.NodeOutput(images)
        return io.NodeOutput(await images.select_batch(indices))


class ImageDuplicator(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ImageDuplicator",
            display_name="ImageDuplicator",
            category="image",
            inputs=[
                io.Image.Input("images"),
                io.Int.Input(
                    "dup_times", default=2, min=1, max=16, step=1),
            ],
            outputs=[io.Image.Output()],
        )

    @classmethod
    async def execute(
        cls, images: sdk.ImageRef, dup_times: int,
    ) -> io.NodeOutput:
        return io.NodeOutput(await images.repeat_batch(dup_times))


class LatentSelector(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="LatentSelector",
            display_name="LatentSelector",
            category="latent",
            inputs=[
                io.Latent.Input("latent_image"),
                io.String.Input(
                    "selected_indexes", default="1,2,3", multiline=False),
            ],
            outputs=[io.Latent.Output()],
        )

    @classmethod
    async def execute(
        cls, latent_image: sdk.LatentRef, selected_indexes: str,
    ) -> io.NodeOutput:
        indices = _parse_indices(
            selected_indexes, await latent_image.batch_size())
        if not indices:
            return io.NodeOutput(latent_image)
        return io.NodeOutput(await latent_image.select_batch(indices))


class LatentDuplicator(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="LatentDuplicator",
            display_name="LatentDuplicator",
            category="latent",
            inputs=[
                io.Latent.Input("latent_image"),
                io.Int.Input(
                    "dup_times", default=2, min=1, max=16, step=1),
            ],
            outputs=[io.Latent.Output()],
        )

    @classmethod
    async def execute(
        cls, latent_image: sdk.LatentRef, dup_times: int,
    ) -> io.NodeOutput:
        return io.NodeOutput(await latent_image.repeat_batch(dup_times))


NODE_CLASS_MAPPINGS = {
    "ImageSelector": ImageSelector,
    "ImageDuplicator": ImageDuplicator,
    "LatentSelector": LatentSelector,
    "LatentDuplicator": LatentDuplicator,
}
