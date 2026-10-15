"""Explicit bounded workload profile, distinct from upstream maxima."""
import json
import posixpath
import re
from io import BytesIO
from PIL import Image

TEXT_BYTES = 65536
ENCODED_IMAGE_BYTES = 8 * 1024 * 1024
IMAGE_PIXELS = 4194304
MAX_ITEMS = 4096


def text(value, limit=TEXT_BYTES):
    if not isinstance(value, str) or len(value) > limit or len(value.encode("utf-8")) > limit:
        raise ValueError("bounded UTF-8 text required")
    return value


def logical_label(value):
    text(value, 1024)
    if not value or value.startswith("/") or "\\" in value or re.search(r"[\x00-\x1f\x7f]", value):
        raise ValueError("managed logical label required")
    if any(part in ("", ".", "..") for part in value.split("/")):
        raise ValueError("managed label traversal refused")
    return value


def container_work(value):
    count, total, stack = 0, 0, [(value, 0)]
    while stack:
        item, depth = stack.pop()
        count += 1
        if count > MAX_ITEMS or depth > 32:
            raise ValueError("metadata item/depth workload exceeded")
        if isinstance(item, str):
            total += len(item.encode("utf-8"))
        elif isinstance(item, bytes):
            total += len(item)
        elif isinstance(item, dict):
            stack.extend((part, depth + 1) for pair in item.items() for part in pair)
        elif isinstance(item, (list, tuple)):
            stack.extend((part, depth + 1) for part in item)
        if total > TEXT_BYTES:
            raise ValueError("metadata text workload exceeded")


def json_work(value):
    # Bound depth before JSON parsing without evaluating or coercing data.
    depth, quoted, escaped = 0, False, False
    for char in text(value):
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            if depth > 32:
                raise ValueError("JSON nesting workload exceeded")
        elif char in "]}":
            depth -= 1
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        return None
    container_work(decoded)
    return decoded


def image_work(data):
    if not isinstance(data, bytes) or len(data) > ENCODED_IMAGE_BYTES:
        raise ValueError("encoded image workload exceeded")
    with Image.open(BytesIO(data)) as image:
        width, height = image.size
        if width < 1 or height < 1 or width * height > IMAGE_PIXELS:
            raise ValueError("projected image allocation workload exceeded")
        container_work(image.info)
        for key in ("prompt", "workflow"):
            if isinstance(image.info.get(key), str):
                json_work(image.info[key])
        if isinstance(image.info.get("exif"), bytes):
            exif = image.info["exif"].decode("utf-8", errors="ignore")
            if "prompt:" in exif:
                json_work(exif.split("prompt:", 1)[1].split("\x00", 1)[0])
    # Reserve RGB decode/transposition, float copies/output, alpha/mask and
    # source/metadata buffers before the retained algorithm allocates them.
    return width * height * 80 + len(data)
