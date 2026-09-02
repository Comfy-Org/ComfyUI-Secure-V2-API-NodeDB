"""Closed interaction messages used by the converted filter nodes.

The legacy pack installed a process-global HTTP route and polled one global
response slot.  Secure Nodes already owns the one-use request token, timeout,
tenant/pack/node scope, and response route, so this module keeps only the
pack's bounded payload and response validation.
"""
from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

from comfy_api.latest import sdk


MAX_TIMEOUT = 540.0
MAX_TEXT = 4096
MAX_TIP = 16_384
SAFE_SOUNDS = frozenset({"beep.mp3", "ding.mp3", "honk.mp3"})


class InteractionTimeout(Exception):
    pass


def bounded_text(value: Any, *, maximum: int = MAX_TEXT) -> str:
    text = "" if value is None else str(value)
    if "\x00" in text or len(text.encode("utf-8")) > maximum:
        raise ValueError("interaction text exceeds its bound")
    return text


def bounded_extras(values: Any) -> list[str]:
    if not isinstance(values, (list, tuple)) or len(values) != 3:
        raise TypeError("interaction extras must contain exactly three strings")
    return [bounded_text(value) for value in values]


def safe_sound(value: Any) -> str | None:
    """Accept only names of the three immutable audio assets in this pack."""
    text = "" if value is None else str(value).strip()
    if not text:
        return None
    if text in SAFE_SOUNDS:
        return text
    # Absolute paths, URLs, traversal, and names outside the bundled set are
    # deliberately refused.  The UI falls back to ding.mp3.
    print("cg-image-filter: external audiofile refused; using bundled sound")
    return None


def preview_identity(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        raise TypeError("preview identity must be an object")
    name = value.get("filename", value.get("name"))
    folder = value.get("type", "temp")
    subfolder = value.get("subfolder", "") or ""
    if (
        not isinstance(name, str)
        or not name
        or len(name.encode("utf-8")) > 255
        or "/" in name
        or "\\" in name
        or "\x00" in name
    ):
        raise ValueError("preview filename is invalid")
    if folder not in {"input", "temp", "output"}:
        raise ValueError("preview folder type is invalid")
    if not isinstance(subfolder, str) or len(subfolder.encode("utf-8")) > 1024:
        raise ValueError("preview subfolder is invalid")
    path = PurePosixPath(subfolder.replace("\\", "/"))
    if path.is_absolute() or any(part in {".."} for part in path.parts):
        raise ValueError("preview subfolder escapes its catalogue")
    return {"filename": name, "type": folder, "subfolder": path.as_posix() if subfolder else ""}


def preview_images(display: Any, *, maximum: int = 4096) -> list[dict[str, str]]:
    images = display.get("images") if isinstance(display, dict) else None
    if not isinstance(images, (list, tuple)) or not 1 <= len(images) <= maximum:
        raise ValueError("preview did not return a bounded image list")
    return [preview_identity(value) for value in images]


def _is_timeout(error: Exception) -> bool:
    remote_type = str(getattr(error, "remote_type", type(error).__name__))
    return remote_type in {"TimeoutError", "CancelledError"} and "timeout" in str(error).lower()


async def request(
    kind: str,
    payload: dict[str, Any],
    timeout: int | float,
    *,
    reuse_last: bool = False,
    remember: bool = False,
) -> Any:
    bounded_timeout = max(1.0, min(float(timeout), MAX_TIMEOUT))
    try:
        return await sdk.ctx().interact.request(
            kind,
            payload,
            timeout=bounded_timeout,
            reuse_last=bool(reuse_last),
            remember=bool(remember),
        )
    except Exception as error:
        # Permission/schema failures remain fail-closed.  Only the broker's
        # actual timeout is translated into the pack's legacy timeout policy.
        if _is_timeout(error):
            raise InteractionTimeout from error
        raise


async def interrupt(reason: str) -> None:
    await sdk.ctx().execution.interrupt()
    raise RuntimeError(reason)
