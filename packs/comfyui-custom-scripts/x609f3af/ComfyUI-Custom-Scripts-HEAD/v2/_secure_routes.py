"""Model sidecar data for the model-info dialogs, held in pack storage.

The legacy pack wrote notes, chosen previews and saved examples into files
beside the model weights. A confined pack has no such reach, and it does not
need one: none of this is model data, it is the pack's own record about a
model. Keyed by ``<type>/<name>`` in the pack's storage, it survives restarts
and stays inside the pack, which is where a pack's opinions belong.

Read-only metadata is different — that IS model data — so it is read through
the broker from the catalogued weight file itself.
"""
from comfy_api.latest import sdk

MAX_NOTE_BYTES = 64 * 1024
MAX_EXAMPLE_BYTES = 256 * 1024
MAX_EXAMPLES = 64
_TYPES = ("loras", "checkpoints", "embeddings", "vae", "controlnet",
          "upscale_models", "gligen", "hypernetworks", "style_models")


def _json(value, status=200):
    import json

    return {"status": status, "body": json.dumps(value)}


def _key(kind, model_type, name):
    if model_type not in _TYPES:
        raise ValueError(f"unknown model type {model_type!r}")
    if not name or "\x00" in name or ".." in name.replace("\\", "/").split("/"):
        raise ValueError("unsafe model name")
    return f"custom-scripts:{kind}:{model_type}/{name}"


def _target(request):
    query = request.get("query") or {}
    return str(query.get("type", "")), str(query.get("name", ""))


async def get_notes(request):
    model_type, name = _target(request)
    stored = await sdk.ctx().storage.get(_key("notes", model_type, name))
    return _json({"notes": stored or ""})


async def save_notes(request):
    model_type, name = _target(request)
    body = request.get("body") or ""
    if len(body.encode("utf-8")) > MAX_NOTE_BYTES:
        return _json({"ok": False, "error": "notes are too long"}, 413)
    await sdk.ctx().storage.set(_key("notes", model_type, name), body)
    return _json({"ok": True})


async def get_examples(request):
    model_type, name = _target(request)
    stored = await sdk.ctx().storage.get(_key("examples", model_type, name))
    return _json(stored or [])


async def save_example(request):
    import json

    model_type, name = _target(request)
    body = request.get("body") or "{}"
    if len(body.encode("utf-8")) > MAX_EXAMPLE_BYTES:
        return _json({"ok": False, "error": "example is too large"}, 413)
    submitted = json.loads(body)
    if not isinstance(submitted, dict):
        return _json({"ok": False, "error": "example must be an object"}, 400)
    entry_name = str(submitted.get("name") or "").strip()
    example = str(submitted.get("example") or "")
    if not entry_name:
        return _json({"ok": False, "error": "example needs a name"}, 400)
    key = _key("examples", model_type, name)
    existing = await sdk.ctx().storage.get(key) or []
    if not isinstance(existing, list):
        existing = []
    kept = [item for item in existing
            if isinstance(item, dict) and item.get("name") != entry_name]
    if len(kept) >= MAX_EXAMPLES:
        return _json({"ok": False, "error": "too many examples"}, 409)
    kept.append({"name": entry_name, "example": example})
    await sdk.ctx().storage.set(key, kept)
    return _json({"ok": True, "name": entry_name})


async def get_preview(request):
    model_type, name = _target(request)
    stored = await sdk.ctx().storage.get(_key("preview", model_type, name))
    return _json({"preview": stored or None})


async def save_preview(request):
    import json

    model_type, name = _target(request)
    submitted = json.loads(request.get("body") or "{}")
    if not isinstance(submitted, dict):
        return _json({"ok": False, "error": "preview must be an object"}, 400)
    filename = str(submitted.get("filename") or "")
    source = str(submitted.get("type") or "")
    # A preview is a reference to something the host already serves, never
    # bytes the pack chose: storing the name keeps the host the only party
    # that decides what /view will hand out.
    if not filename or source not in ("temp", "input", "output"):
        return _json({"ok": False, "error": "invalid preview reference"}, 400)
    await sdk.ctx().storage.set(
        _key("preview", model_type, name),
        {"filename": filename, "type": source},
    )
    return _json({"ok": True})


async def get_metadata(request):
    model_type, name = _target(request)
    _key("metadata", model_type, name)
    context = sdk.ctx()
    reference = await context.assets.resolve(model_type, name)
    _, metadata = await context.assets.load_state_dict(
        reference, return_metadata=True)
    return _json({"metadata": metadata or {}})
