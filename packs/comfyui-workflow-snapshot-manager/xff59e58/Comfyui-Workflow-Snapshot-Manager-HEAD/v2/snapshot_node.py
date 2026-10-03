import base64
import io as bytes_io

from comfy_api.latest import io, sdk


_MAX_LABEL_CHARS = 500


def _thumbnail_from_tensor(value) -> str | None:
    try:
        import torch
        from PIL import Image

        if not isinstance(value, torch.Tensor):
            return None
        if value.ndim != 4 or value.shape[0] < 1 or value.shape[3] not in (3, 4):
            return None
        frame = value[0, :, :, :3]
        array = frame.clamp(0, 1).mul(255).byte().cpu().numpy()
        image = Image.fromarray(array, mode="RGB")
        image.thumbnail((200, 150), Image.Resampling.LANCZOS)
        buffer = bytes_io.BytesIO()
        image.save(buffer, format="JPEG", quality=75)
        return base64.b64encode(buffer.getvalue()).decode("ascii")
    except Exception:
        return None


async def _make_thumbnail(value) -> str | None:
    if not isinstance(value, sdk.TensorRef):
        return None
    try:
        return _thumbnail_from_tensor(await value.raw())
    except Exception:
        return None


class SaveSnapshot(io.ComfyNode):
    """Pass a value through and ask the pack frontend to capture the workflow."""

    SDK_REFS = True
    SDK_PERMISSIONS = ("raw", "ui")

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="SaveSnapshot",
            display_name="Save Snapshot",
            category="Snapshot Manager",
            description=(
                "Capture a named workflow snapshot when this output node runs, "
                "while passing its input through unchanged."
            ),
            inputs=[
                io.AnyType.Input("value"),
                io.String.Input("label", default="Node Trigger"),
            ],
            outputs=[io.AnyType.Output("value")],
            is_output_node=True,
        )

    @classmethod
    def validate_inputs(cls, label: str, **_kwargs):
        if not isinstance(label, str):
            return "label must be a string"
        if len(label) > _MAX_LABEL_CHARS:
            return f"label must be at most {_MAX_LABEL_CHARS} characters"
        return True

    @classmethod
    def fingerprint_inputs(cls, **_kwargs):
        return float("NaN")

    @classmethod
    async def execute(cls, value, label="Node Trigger") -> io.NodeOutput:
        safe_label = label.strip()[:_MAX_LABEL_CHARS] or "Node Trigger"
        payload = {"label": safe_label}
        thumbnail = await _make_thumbnail(value)
        if thumbnail is not None:
            payload["thumbnail"] = thumbnail
        return io.NodeOutput(
            value,
            ui={"snapshot_manager_capture": [payload]},
        )
