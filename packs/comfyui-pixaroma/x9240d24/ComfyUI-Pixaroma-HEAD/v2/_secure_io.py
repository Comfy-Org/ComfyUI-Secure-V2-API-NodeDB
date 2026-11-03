"""Asset, image-writer and LoRA boundaries using only selected public SDK calls."""
import base64
import io as stdlib_io
import json
import os
import re

import numpy as np
import torch
from PIL import Image

from comfy_api.latest import io, sdk
from . import _secure_boundary as boundary
from .nodes import _save_helpers as save_helpers


async def execute(node_id, fields):
    if node_id == "PixaromaCompare":
        results = []
        for slot, key in ((1, "image1"), (2, "image2")):
            ref = fields.get(key)
            if ref is None:
                continue
            tensor = await boundary.materialize(ref)
            pixels = np.clip(tensor[:1].cpu().numpy() * 255, 0, 255).astype(np.uint8)
            prepared = await sdk.ImageRef.from_value(torch.from_numpy(pixels.astype(np.float32) / 255))
            result = await sdk.current_context().ui.preview_images(prepared)
            results.extend([dict(value, slot=slot) for value in result["images"]])
        return io.NodeOutput(ui={"images": results})
    if node_id == "PixaromaPreview":
        return await preview(fields)
    if node_id == "PixaromaLoraLoader":
        return await lora(fields)
    if node_id == "PixaromaPromptReader":
        return await prompt_reader(fields)
    if node_id == "PixaromaSaveImage":
        return await save_image(fields)
    if node_id == "PixaromaXYPlot":
        raise RuntimeError("comfyui-pixaroma/PixaromaXYPlot is not yet converted to Secure Nodes V2: the source process-global eight-session LRU evicts cells and deletes grid PNGs; per-session KV does not preserve this lifecycle")
    raise RuntimeError(f"comfyui-pixaroma/{node_id} has no converted asset boundary")


async def metadata():
    context = await sdk.current_context().graph.execution_metadata()
    return context.get("prompt"), context.get("extra_pnginfo"), context.get("node_id")


async def quantized(ref):
    tensor = await boundary.materialize(ref)
    from .nodes._save_state import _tensor_to_pil
    frames = [torch.from_numpy(np.array(_tensor_to_pil(frame)).astype(np.float32) / 255) for frame in tensor]
    frames = [frame[..., None] if frame.ndim == 2 else frame for frame in frames]
    return await sdk.ImageRef.from_value(torch.stack(frames)), tensor


async def preview(fields):
    if str(fields.get("CivitaiMeta", "")).strip().lower() in ("1", "true", "yes", "on"):
        raise RuntimeError("comfyui-pixaroma/PixaromaPreview CivitaiMeta requires brokered model fingerprint metadata")
    original = fields["image"]
    prepared, tensor = await quantized(original)
    prefix = save_helpers._safe_prefix(fields.get("filename_prefix", "img")) or "Preview"
    ctx = sdk.current_context()
    prompt, extra, _ = await metadata()
    frame_metadata = save_helpers._json_safe({"prompt": prompt, "workflow": extra.get("workflow") if isinstance(extra, dict) else None})
    boundary.ensure_ui("PixaromaPreview", {"images": [{"_pixaroma_meta": frame_metadata}]})
    if fields.get("save_mode", "preview") == "save":
        result = await ctx.output.save_images(prepared, filename_prefix=prefix, compress_level=6, save_metadata=True)
        key = "images"
    else:
        result = await ctx.ui.preview_images(prepared)
        key = "pixaroma_preview_frames"
        await preview_cache(fields, result["images"])
    entries = result["images"]
    if entries:
        entries[0]["_pixaroma_meta"] = frame_metadata
    return io.NodeOutput(original, ui={key: entries})


async def preview_cache(fields, entries=None):
    if entries is None and fields.get("save_mode") != "preview":
        return float("nan")
    ctx = sdk.current_context()
    key = "pixaroma-preview/" + str(await ctx.graph.current_node_id())
    saved = await ctx.storage.get(key)
    state = json.loads(saved) if saved else {"generation": 0, "runs": []}
    kept = []
    missing = False
    for run in state["runs"]:
        present = all([await ctx.assets.exists("temp", name) for name in run])
        if present:
            kept.append(run)
        else:
            missing = True
    if entries is None:
        if missing:
            state["generation"] += 1
    else:
        state["runs"] = (kept + [[(entry.get("subfolder", "").rstrip("/") + "/" if entry.get("subfolder") else "") + entry["filename"] for entry in entries]])[-32:]
    await ctx.storage.set(key, json.dumps(state))
    return "pixaroma-preview-" + str(state["generation"])


async def lora(fields):
    from .nodes import _lora_helpers as helpers
    state = helpers.parse_state(fields.get("LoraLoaderState", "{}"))
    model, clip = fields["model"], fields.get("clip")
    ctx = sdk.current_context()
    resolved = []
    for entry in state["loras"]:
        if not entry.get("on") or entry["name"] == "(put LoRAs in models/loras)":
            continue
        name = entry["name"]
        if not await ctx.assets.exists("loras", name):
            print(f"[LoRA Loader Pixaroma] skipped (not found): {name}")
            continue
        sm = float(entry.get("sm", 0))
        sc = float(entry.get("sc", 0)) if clip is not None else 0.0
        if sm == 0 and sc == 0:
            resolved.append(entry)
            continue
        try:
            asset = await ctx.assets.resolve("loras", name)
            model, clip = await model.apply_lora(asset, clip, sm, sc)
            resolved.append(entry)
        except Exception as error:
            print(f"[LoRA Loader Pixaroma] failed to apply {name}: {error}")
    triggers = helpers.collect_triggers({"loras": resolved, "sep": state.get("sep", ", ")})
    return io.NodeOutput(model, clip, triggers)


async def prompt_reader(fields):
    from .nodes import _prompt_reader_helpers as helpers
    ctx = sdk.current_context()
    raw = fields.get("filename")
    wired = raw.strip() if isinstance(raw, str) else ""
    selected = wired or fields.get("image", "")
    folder, name = boundary.asset_name(selected)
    if wired and not await ctx.assets.exists(folder, name):
        extensions = (".png", ".webp", ".jpeg", ".jpg", ".bmp", ".gif", ".tiff", ".tif")
        stem = os.path.splitext(name.rsplit("/", 1)[-1])[0].lower()
        candidates = [value for value in await ctx.assets.list("input") if os.path.splitext(value.rsplit("/", 1)[-1])[0].lower() == stem]
        hint = name.rpartition("/")[0]
        candidates = [value for value in candidates if os.path.splitext(value)[1].lower() in extensions]
        candidates.sort(key=lambda value: (0 if hint and value.rpartition("/")[0] == hint else 1,
            extensions.index(os.path.splitext(value)[1].lower()), value.count("/"), value.lower()))
        if candidates:
            folder, name = "input", candidates[0]
        else:
            text = f"Could not find an image named '{wired}' in the input folder. Make sure the image sent by the connected node is present in ComfyUI's input folder."
            return io.NodeOutput(text, ui={"text": [text]})
    try:
        if not await ctx.assets.exists(folder, name):
            text = "No prompt metadata found in this image."
            return io.NodeOutput(text, ui={"text": [text]})
        asset = await ctx.assets.resolve(folder, name)
        data = await ctx.assets.read_bytes(asset)
    except (FileNotFoundError, ValueError):
        text = "No prompt metadata found in this image."
        return io.NodeOutput(text, ui={"text": [text]})
    chunks = helpers.read_png_text_chunks(stdlib_io.BytesIO(data))
    if "prompt" in chunks:
        try:
            graph = json.loads(chunks["prompt"])
        except Exception:
            graph = {}
        if isinstance(graph, dict) and any(isinstance(node, dict) and node.get("class_type") in ("PixaromaPromptReader", "PixaromaSketch", "PixaromaReferenceImages") for node in graph.values()):
            raise RuntimeError("comfyui-pixaroma/PixaromaPromptReader nested source-image/editor tracing requires brokered graph assets")
    result = helpers.read_prompt_from_image(stdlib_io.BytesIO(data))
    text = (result.get("text") or "") if result.get("found") else (result.get("message") or "No prompt found in this image.")
    return io.NodeOutput(text, ui={"text": [text]})


async def save_image(fields):
    from .nodes import _save_state as source
    state = source._parse_state(fields.get("SaveImageState", ""))
    folder = str(state.get("folder", "") or "").replace("\\", "/").strip("/")
    if ":" in folder or ".." in folder.split("/") or str(state.get("folder", "")).startswith(("/", "\\")):
        raise RuntimeError("comfyui-pixaroma/PixaromaSaveImage external folder requires brokered output assets")
    if state.get("civitaiMeta"):
        raise RuntimeError("comfyui-pixaroma/PixaromaSaveImage civitaiMeta requires brokered model fingerprint metadata")
    raw_format = str(state.get("format", "png")).lower()
    fmt = "jpg" if raw_format in ("jpg", "jpeg") else "webp" if raw_format == "webp" else "png"
    if fmt == "jpg":
        raise RuntimeError("comfyui-pixaroma/PixaromaSaveImage JPEG requires the original subsampling policy unavailable in the selected SDK")
    if fmt == "webp" and state.get("embedWorkflow", True):
        raise RuntimeError("comfyui-pixaroma/PixaromaSaveImage WebP workflow EXIF requires an exact metadata writer profile")
    prepared, tensor = await quantized(fields["images"])
    ctx = sdk.current_context()
    if not bool(state.get("saveOnRun", True)):
        _, execution_extra, _ = await metadata()
        if source._strip_stale_preview(execution_extra) != execution_extra:
            raise RuntimeError("comfyui-pixaroma/PixaromaSaveImage preview workflow cleanup requires an exact temp metadata writer")
        previews = await ctx.ui.preview_images(prepared)
        entries = previews["images"][:16]
        if entries:
            entries[0]["_pixaroma_status"] = {"saved": 0, "folder": folder, "w": int(tensor.shape[2]), "h": int(tensor.shape[1]), "inside_output": True, "note": "Preview mode - nothing was written to your folder"}
        return io.NodeOutput(ui={"pixaroma_save_frames": entries})
    pattern = str(state.get("pattern") or source.DEFAULT_STATE["pattern"])
    name = fields.get("name")
    input_name = "" if name is None else name if isinstance(name, str) else str(name)
    input_name = source._MEDIA_EXT_RE.sub("", input_name.strip())
    input_name = input_name.replace("\\", "/") if state.get("inputSubfolders") else input_name.replace("\\", "_").replace("/", "_")
    pattern = source._expand_native_tokens(save_helpers._expand_date_tokens(pattern.replace("%input%", input_name)))
    pattern = pattern.replace("%width%", str(tensor.shape[2])).replace("%height%", str(tensor.shape[1]))
    relative = save_helpers._safe_prefix(pattern) or "image_%counter%"
    if any("%counter%" in part for part in relative.split("/")[:-1]):
        raise RuntimeError("comfyui-pixaroma/PixaromaSaveImage counter in a folder name requires brokered directory enumeration")
    try:
        digits = max(1, min(8, int(state.get("counterDigits", 3))))
    except Exception:
        digits = 3
    existing = set(await ctx.assets.list("output"))
    filenames = []
    extension = ".webp" if fmt == "webp" else ".png"
    for index in range(len(tensor)):
        base = relative.replace("%batch_num%", str(index))
        output_parent = ((folder + "/") if folder else "") + base.rpartition("/")[0]
        output_parent = output_parent.rstrip("/")
        children = [value.rsplit("/", 1)[-1] for value in existing if value.rpartition("/")[0] == output_parent]
        counter = save_helpers._next_counter_from_names(children, base.rsplit("/",1)[-1] + extension) if "%counter%" in base else 1
        suffix = 0
        while True:
            name = base.replace("%counter%", f"{counter:0{digits}}") if "%counter%" in base else base if not suffix else base + f"_{suffix:0{digits}}"
            name = (folder + "/" if folder else "") + name + extension
            if name not in existing:
                break
            counter += 1
            suffix += 1
        existing.add(name)
        filenames.append(name)
    try:
        quality = max(1, min(100, int(state.get("quality", 100))))
    except Exception:
        quality = 100
    embed = bool(state.get("embedWorkflow", True))
    extra = None
    if embed:
        _, execution_extra, _ = await metadata()
        extra = source._strip_stale_preview(execution_extra)
    result = await ctx.output.save_images(prepared, filenames=filenames, compress_level=4,
        image_format=fmt, quality=quality, lossless=bool(state.get("webpLossless", False)),
        save_metadata=embed, extra_metadata=extra)
    entries = result["images"]
    if entries:
        entries[0]["_pixaroma_status"] = {"saved": len(tensor), "folder": folder,
            "w": int(tensor.shape[2]), "h": int(tensor.shape[1]), "inside_output": True}
    return io.NodeOutput(ui={"images": entries})
