"""Public SDK boundary helpers; the original node methods own all computation."""
import json
import io as stdlib_io
import re

from comfy_api.latest import io, sdk

from ._secure_schema import _ROWS


class DependencyRefusal(RuntimeError):
    pass


def ensure_ui(node_id, ui):
    # The selected Guest protocol preserves JSON only within these bounds.
    # Refuse explicitly rather than drop embedded prompt/workflow fields.
    def check(value, depth=0):
        if depth > 8:
            raise RuntimeError(f"comfyui-pixaroma/{node_id} execution metadata exceeds the selected guest UI depth limit")
        if isinstance(value, dict):
            for item in value.values():
                check(item, depth + 1)
        elif isinstance(value, (list, tuple)):
            for item in value:
                check(item, depth + 1)
    check(ui)
    if len(json.dumps(ui)) > 256 * 1024:
        raise RuntimeError(f"comfyui-pixaroma/{node_id} execution metadata exceeds the selected guest UI size limit")


async def with_hidden(node_id, kwargs):
    """Use the same raw prompt fields V1 receives, including malformed values."""
    ctx = sdk.current_context()
    current = await ctx.graph.current_node_id()
    if str(current) in ("", "0"):
        raise RuntimeError(
            f"comfyui-pixaroma/{node_id} cannot read custom hidden state for "
            "prompt node id 0 with the selected graph API"
        )
    values = await ctx.graph.widget_values(node_id=current)
    output = dict(kwargs)
    fields = dict(_ROWS[node_id]["input_types"].get("hidden", {}))
    fields.update({"CropWidget": None} if node_id == "PixaromaCrop" else {})
    fields.update({"InpaintCropWidget": None} if node_id == "PixaromaInpaintCrop" else {})
    for name, spec in fields.items():
        if spec not in ("PROMPT", "UNIQUE_ID", "EXTRA_PNGINFO", "DYNPROMPT") and name in values:
            output[name] = values[name]
    # An absent input remains absent: the original function's default applies,
    # rather than the schema default (V1 does not populate hidden defaults).
    return output


async def materialize(value):
    if isinstance(value, sdk.TensorRef):
        return await value.raw()
    if isinstance(value, sdk.ValueRef):
        return await value.value()
    if isinstance(value, sdk.Ref):
        raise RuntimeError("Pixaroma text/image inspection cannot materialize a live engine reference")
    if isinstance(value, dict):
        return {key: await materialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [await materialize(item) for item in value]
    if isinstance(value, tuple):
        return tuple([await materialize(item) for item in value])
    return value


async def empty_latent(node_id, width, height, batch):
    # Core's EmptyLatentImage floors each spatial dimension to eight pixels.
    # Passing those exact floor dimensions preserves odd-sized API states too.
    try:
        return await sdk.LatentRef.empty(
            width=(width // 8) * 8, height=(height // 8) * 8,
            batch_size=batch, channels=4, spatial_downscale_ratio=8,
        )
    except ValueError as error:
        raise RuntimeError(
            f"comfyui-pixaroma/{node_id} empty latent exceeds the selected SDK's bounded allocation"
        ) from error


async def _wrap(kind, value):
    if kind == "IMAGE" and not isinstance(value, sdk.Ref):
        try:
            return await sdk.ImageRef.from_value(value)
        except (TypeError, ValueError) as error:
            raise RuntimeError(
                "comfyui-pixaroma/PixaromaImageInfo cannot publish this image "
                "through the selected SDK's bounded finite BHWC image API"
            ) from error
    if kind == "MASK" and not isinstance(value, sdk.Ref):
        # The selected base has no public MaskRef constructor. The existing
        # public latent noise-mask operation preserves the tensor and issues
        # the correctly typed MASK handle without private SDK access.
        container = await sdk.LatentRef.from_value({"noise_mask": value})
        return await container.noise_mask()
    if kind == "LATENT" and not isinstance(value, sdk.Ref):
        return await sdk.LatentRef.from_value(value)
    if kind in ("PIX_IMAGE_INFO", "PIXAROMA_CROP_INFO") and not isinstance(value, sdk.Ref):
        return await sdk.CondRef.from_value(value)
    return value


async def output(kinds, result):
    if isinstance(result, dict):
        values = result.get("result", ())
        ui = result.get("ui")
    else:
        values, ui = result, None
    return io.NodeOutput(*[
        await _wrap(kind, item) for kind, item in zip(kinds, values)
    ], ui=ui)


def check_builtin_font(node_id, raw):
    try:
        state = json.loads(raw) if raw else {}
    except Exception:
        return  # The original method owns malformed-state behavior.
    if isinstance(state, dict) and state.get("text"):
        font = state.get("font", "Roboto")
        if font not in {"Inter", "Roboto", "Montserrat", "Oswald", "PlayfairDisplay", "Lora", "BebasNeue", "Anton", "Caveat", "JetBrainsMono"}:
            raise RuntimeError(f"comfyui-pixaroma/{node_id} custom font {font!r} requires brokered font assets")


async def resize_preview(out):
    first = out["result"][0][:1]
    ref = await sdk.ImageRef.from_value(first)
    files = await sdk.current_context().ui.preview_images(ref)
    descriptor = files["images"][0]
    out["ui"]["pixaroma_image_resize"][0].update(descriptor)


async def overlay_preview(out, image):
    # Match the original's floor-to-byte conversion before the broker encodes.
    import numpy as np
    import torch
    frame = (image[:1].clamp(0, 1).cpu().numpy() * 255).astype(np.uint8)
    if frame.shape[-1] not in (3, 4):
        frame = np.repeat(frame[..., :1], 3, axis=-1)
    ref = await sdk.ImageRef.from_value(torch.from_numpy(frame.astype(np.float32) / 255.0))
    files = await sdk.current_context().ui.preview_images(ref)
    out["ui"]["pixaroma_text_overlay_base"] = [files["images"][0]]


def asset_name(value):
    text = str(value)
    match = re.search(r"\s+\[(input|output|temp)\]$", text)
    folder = match.group(1) if match else "input"
    name = text[:match.start()] if match else text
    name = name.replace("\\", "/")
    if name.startswith("/") or ":" in name or ".." in name.split("/"):
        raise RuntimeError("comfyui-pixaroma asset inputs require a brokered logical name, not a host filesystem path")
    if name.startswith("pixaroma_folders/"):
        raise RuntimeError("comfyui-pixaroma external-folder refresh requires brokered source-folder assets")
    return folder, name


async def open_image(node_id, image):
    folder, name = asset_name(image)
    ctx = sdk.current_context()
    asset = await ctx.assets.resolve(folder, name)
    data = await ctx.assets.read_bytes(asset)
    # Ask the native image loader for its current output dtype; then reuse the
    # original Pixaroma PIL decode/resize algorithm on the brokered bytes.
    native = await ctx.assets.load_image(asset)
    dtype = (await native.raw()).dtype
    from PIL import Image
    return Image.open(stdlib_io.BytesIO(data)), dtype, name


async def asset_fingerprint(value):
    folder, name = asset_name(value)
    ctx = sdk.current_context()
    asset = await ctx.assets.resolve(folder, name)
    return await ctx.assets.digest(asset, algorithm="sha256")


async def loader_fingerprint(node_id, fields):
    import hashlib
    import json
    from .nodes.node_load_image import _parse_state, _parse_orig_name
    ctx = sdk.current_context()
    folder, name = asset_name(fields.get("image", ""))
    asset = await ctx.assets.resolve(folder, name)
    digest = hashlib.sha256(await ctx.assets.read_bytes(asset))
    if node_id == "PixaromaLoadImage":
        digest.update((fields.get("LoadImagePixState", "") or "").encode("utf-8"))
    else:
        raw = fields.get("LoadImageMiniState", "")
        digest.update(json.dumps(_parse_state(raw), sort_keys=True).encode("utf-8"))
        digest.update((_parse_orig_name(raw) or "").encode("utf-8"))
    return digest.hexdigest()


async def crop_preview(node_id, out, image):
    if image is None:
        return out
    import numpy as np
    import torch
    if not isinstance(image, torch.Tensor) or image.ndim != 4 or not image.shape[0]:
        return out
    data = (image[:1].clamp(0, 1).cpu().numpy() * 255 + 0.5).astype(np.uint8)
    ref = await sdk.ImageRef.from_value(torch.from_numpy(data.astype(np.float32) / 255))
    preview = await sdk.current_context().ui.preview_images(ref)
    if not isinstance(out, dict):
        out = {"result": out, "ui": {}}
    out.setdefault("ui", {})["pixaroma_crop_source" if node_id == "PixaromaCrop" else "pixaroma_inpaint_source"] = preview["images"][:1]
    return out
