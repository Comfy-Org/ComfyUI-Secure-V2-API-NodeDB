"""Tenant-scoped H3 project source and sink nodes."""
from __future__ import annotations

import json
import posixpath
import re

import torch

from comfy_api.latest import io, sdk

from .nodes import NestedTensor, _audio, _streams, _video


H3Project = io.Custom("H3_PROJECT")
_PROJECT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,79}$")


def _name(value: str) -> str:
    value = str(value).strip()
    if not _PROJECT_RE.fullmatch(value) or ".." in value:
        raise ValueError("h3_suite: project name must be a safe plain name")
    return value


def _key(name: str) -> str:
    return f"h3-project:{_name(name)}"


async def _read_json(key: str, default):
    raw = await sdk.ctx().storage.get(key)
    if raw is None:
        return default
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError("h3_suite: project storage is corrupt") from error
    return value


async def _write_json(key: str, value) -> None:
    await sdk.ctx().storage.set(
        key, json.dumps(value, ensure_ascii=False, separators=(",", ":")))


async def _save_manifest(value: dict) -> None:
    await _write_json(_key(value["name"]), value)


async def _manifest(name: str, create: bool) -> dict:
    value = await _read_json(_key(name), None)
    if value is None:
        if not create:
            raise ValueError(f"h3_suite: project {name!r} does not exist")
        value = {
            "version": 2, "name": _name(name), "width": 0, "height": 0,
            "approved": [], "pending": None, "takes": [],
            "auto_approve": False,
        }
        await _save_manifest(value)
        index = await _read_json("h3-project-index", [])
        if not isinstance(index, list):
            index = []
        if value["name"] not in index:
            await _write_json(
                "h3-project-index", sorted([*index, value["name"]])[-500:])
    if not isinstance(value, dict) or value.get("name") != _name(name):
        raise ValueError("h3_suite: invalid project manifest")
    return value


async def _load_av(logical_name: str) -> sdk.LatentRef:
    asset = await sdk.ctx().assets.resolve("output", logical_name)
    data = await sdk.ctx().assets.load_state_dict(asset)
    if not isinstance(data, dict) or "video" not in data or "audio" not in data:
        raise ValueError("h3_suite: project latent has no video/audio streams")
    return await sdk.LatentRef.from_value({
        "samples": NestedTensor([data["video"], data["audio"]]),
    })


async def _placeholder() -> sdk.LatentRef:
    return await sdk.LatentRef.from_value({
        "samples": NestedTensor([
            torch.zeros((1, 24, 2, 4, 4)),
            torch.zeros((1, 32, 2, 4)),
        ])
    })


def _saved_video_name(result: dict) -> str:
    items = result.get("images") if isinstance(result, dict) else None
    item = items[0] if isinstance(items, list) and items else None
    if (
        not isinstance(item, dict)
        or item.get("type") != "output"
        or not isinstance(item.get("filename"), str)
        or not item["filename"]
    ):
        raise RuntimeError("h3_suite: video output returned no managed artifact")
    subfolder = item.get("subfolder") or ""
    if not isinstance(subfolder, str):
        raise RuntimeError("h3_suite: video output returned an invalid subfolder")
    logical = posixpath.normpath(posixpath.join(subfolder, item["filename"]))
    if logical.startswith("../") or logical in {".", ".."}:
        raise RuntimeError("h3_suite: video output escaped managed storage")
    return logical


class H3ProjectHub(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw", "assets", "storage")

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="H3ProjectHub", display_name="H3 Project Hub",
            category="conditioning/minimax", not_idempotent=True,
            description="Resolve tenant-scoped project state into chain inputs.",
            inputs=[
                io.String.Input("project_name", default="MyProject"),
                io.Boolean.Input("create_if_missing", default=True),
                io.Vae.Input("vae", optional=True),
                io.Vae.Input("audio_vae", optional=True),
                io.Int.Input("width", default=0, min=0, max=4096, force_input=True, optional=True),
                io.Int.Input("height", default=0, min=0, max=4096, force_input=True, optional=True),
            ],
            outputs=[
                H3Project.Output("project"), io.Latent.Output("context_latent"),
                io.Boolean.Output("chain_active"), io.String.Output("status"),
                io.Int.Output("width"), io.Int.Output("height"),
                io.Latent.Output("anchor_latent"),
            ],
        )

    @classmethod
    async def execute(cls, project_name, create_if_missing=True, vae=None,
                      audio_vae=None, width=0, height=0):
        manifest = await _manifest(project_name, bool(create_if_missing))
        width, height = int(width), int(height)
        if bool(width) != bool(height):
            raise ValueError("h3_suite: project size needs width and height")
        if width and height:
            current = (int(manifest.get("width", 0)), int(manifest.get("height", 0)))
            if all(current) and current != (width, height):
                raise ValueError("h3_suite: project resolution cannot change")
            manifest["width"], manifest["height"] = width, height
            await _save_manifest(manifest)

        approved = list(manifest.get("approved") or ())
        context = await _placeholder()
        anchor = await _placeholder()
        if approved:
            context = await _load_av(approved[-1]["latent"])
            try:
                anchor = await _load_av(approved[0]["latent"])
            except Exception:
                anchor = await _placeholder()
        next_index = len(approved) + 1
        prior_takes = [item for item in manifest.get("takes", ())
                       if int(item.get("index", 0)) == next_index]
        next_take = len(prior_takes) + 1
        pending = manifest.get("pending")
        bits = [f"{len(approved)} approved"]
        if pending:
            bits.append(f"clip {pending['index']} take {pending['take']} PENDING REVIEW")
        bits.append(f"next render: clip{next_index:03}_take{next_take:02}")
        if manifest.get("width") and manifest.get("height"):
            bits.append(f"{manifest['width']}x{manifest['height']}")
        else:
            bits.append("size not set yet")
        return io.NodeOutput(
            {"name": manifest["name"]}, context, bool(approved),
            " | ".join(bits), int(manifest.get("width", 0)),
            int(manifest.get("height", 0)), anchor)


class H3ProjectSave(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw", "output", "storage")

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="H3ProjectSave", display_name="H3 Project Save",
            category="conditioning/minimax", is_output_node=True,
            description="Save one H3 render and its AV latent into project state.",
            inputs=[H3Project.Input("project"), io.Latent.Input("latent"),
                    io.Image.Input("images"),
                    io.Int.Input("fps", default=24, min=1, max=120),
                    io.Audio.Input("audio", optional=True)],
            outputs=[io.String.Output("basename")],
            hidden=[io.Hidden.prompt, io.Hidden.extra_pnginfo],
        )

    @classmethod
    async def execute(cls, project, latent, images, fps, audio=None,
                      prompt=None, extra_pnginfo=None):
        if not isinstance(project, dict) or set(project) != {"name"}:
            raise ValueError("h3_suite: invalid project handle")
        name = _name(project["name"])
        manifest = await _manifest(name, False)
        approved = list(manifest.get("approved") or ())
        index = len(approved) + 1
        takes = list(manifest.get("takes") or ())
        take = 1 + sum(1 for item in takes if int(item.get("index", 0)) == index)
        basename = f"clip_{index:03}_take{take}"

        parts = _streams(await latent.value())
        video_latent, audio_latent = _video(parts), _audio(parts)
        state = await sdk.ValueRef.from_value({
            "video": video_latent, "audio": audio_latent,
        })
        prefix = f"h3_projects/{name}/clips/{basename}"
        latent_name = await sdk.ctx().output.save_state_dict(
            state, prefix,
            metadata={"format": "h3_motion_context_av_v2",
                      "h3_project": name, "h3_clip": basename})
        video_result = await sdk.ctx().output.save_video(
            images, audio=audio, fps=float(fps), filename_prefix=prefix,
            format="mp4", codec="h264", save_output=True,
            save_metadata=True, audio_codec="aac")
        frame_count = await images.batch_size()
        image_height, image_width = await images.spatial_shape()
        entry = {
            "index": index, "take": take, "basename": basename,
            "latent": latent_name, "video": _saved_video_name(video_result),
            "meta": {"frames": frame_count, "fps": int(fps),
                     "width": image_width, "height": image_height},
        }
        takes.append(entry)
        manifest["takes"] = takes[-500:]
        if manifest.get("auto_approve"):
            manifest["approved"] = approved + [entry]
            manifest["pending"] = None
        else:
            manifest["pending"] = entry
        if not manifest.get("width"):
            manifest["width"], manifest["height"] = image_width, image_height
        await _save_manifest(manifest)
        return io.NodeOutput(basename)


NODE_CLASS_MAPPINGS = {
    "H3ProjectHub": H3ProjectHub,
    "H3ProjectSave": H3ProjectSave,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "H3ProjectHub": "H3 Project Hub",
    "H3ProjectSave": "H3 Project Save",
}
