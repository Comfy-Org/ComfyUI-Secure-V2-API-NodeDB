"""Pack-private H3 project routes over tenant-scoped storage."""
from __future__ import annotations

import json

from comfy_api.latest import sdk

from .project_nodes import (
    _key, _manifest, _name, _read_json, _save_manifest, _write_json,
)


def _json(value, status=200):
    return {"status": status, "body": json.dumps(value)}


def _query(request, key, default=""):
    return (request.get("query") or {}).get(key, default)


def _body(request):
    value = json.loads(request.get("body") or "{}")
    if not isinstance(value, dict):
        raise ValueError("request body must be an object")
    return value


async def projects(request):
    value = await _read_json("h3-project-index", [])
    return _json({"projects": value if isinstance(value, list) else []})


async def state(request):
    name = _name(_query(request, "name"))
    return _json(await _manifest(name, False))


async def create(request):
    body = _body(request)
    manifest = await _manifest(_name(body.get("name", "")), True)
    return _json(manifest)


async def approve(request):
    body = _body(request)
    name = _name(body.get("name", ""))
    manifest = await _manifest(name, False)
    pending = manifest.get("pending")
    if not isinstance(pending, dict):
        return _json({"ok": False, "error": "nothing pending"}, 409)
    approved = list(manifest.get("approved") or ())
    expected = len(approved) + 1
    if int(pending.get("index", 0)) != expected:
        return _json({"ok": False, "error": "pending clip is out of sequence"}, 409)
    manifest["approved"] = [*approved, pending]
    manifest["pending"] = None
    await _save_manifest(manifest)
    return _json({"ok": True, "state": manifest})


async def reject(request):
    body = _body(request)
    name = _name(body.get("name", ""))
    manifest = await _manifest(name, False)
    if manifest.get("pending") is None:
        return _json({"ok": False, "error": "nothing pending"}, 409)
    manifest["pending"] = None
    await _save_manifest(manifest)
    return _json({"ok": True, "state": manifest})


async def reopen(request):
    body = _body(request)
    name = _name(body.get("name", ""))
    manifest = await _manifest(name, False)
    approved = list(manifest.get("approved") or ())
    if not approved:
        return _json({"ok": False, "error": "project has no approved clip"}, 409)
    manifest["pending"] = approved.pop()
    manifest["approved"] = approved
    await _save_manifest(manifest)
    return _json({"ok": True, "state": manifest})


async def auto_approve(request):
    body = _body(request)
    name = _name(body.get("name", ""))
    manifest = await _manifest(name, False)
    manifest["auto_approve"] = bool(body.get("enabled"))
    await _save_manifest(manifest)
    return _json({"ok": True, "state": manifest})


async def select_take(request):
    body = _body(request)
    name = _name(body.get("name", ""))
    index, take = int(body.get("index", 0)), int(body.get("take", 0))
    manifest = await _manifest(name, False)
    chosen = next((item for item in manifest.get("takes", ())
                   if int(item.get("index", 0)) == index
                   and int(item.get("take", 0)) == take), None)
    if chosen is None:
        return _json({"ok": False, "error": "take does not exist"}, 404)
    if index != len(manifest.get("approved") or ()) + 1:
        return _json({"ok": False, "error": "only the next clip may be selected"}, 409)
    manifest["pending"] = chosen
    await _save_manifest(manifest)
    return _json({"ok": True, "state": manifest})


async def branch(request):
    body = _body(request)
    source_name = _name(body.get("name", ""))
    new_name = _name(body.get("new_name", ""))
    if source_name == new_name:
        return _json({"ok": False, "error": "branch needs a new project name"}, 409)
    if await sdk.ctx().storage.get(_key(new_name)) is not None:
        return _json({"ok": False, "error": "branch project already exists"}, 409)
    source = await _manifest(source_name, False)
    approved = list(source.get("approved") or ())
    index = int(body.get("index", len(approved)))
    take = int(body.get("take", 0))
    if not 1 <= index <= len(approved):
        return _json({"ok": False, "error": "branch index is not approved"}, 409)
    chosen = approved[index - 1]
    if take:
        chosen = next((item for item in source.get("takes", ())
                       if int(item.get("index", 0)) == index
                       and int(item.get("take", 0)) == take), None)
        if chosen is None:
            return _json({"ok": False, "error": "branch take does not exist"}, 404)
    branch_approved = [*approved[:index - 1], chosen]
    branch_takes = [item for item in source.get("takes", ())
                    if int(item.get("index", 0)) <= index]
    created = {
        "version": 2,
        "name": new_name,
        "width": int(source.get("width", 0)),
        "height": int(source.get("height", 0)),
        "approved": branch_approved,
        "pending": None,
        "takes": branch_takes[-500:],
        "auto_approve": False,
        "branched_from": {"project": source_name, "index": index,
                           "take": int(chosen.get("take", 0))},
    }
    await _save_manifest(created)
    project_index = await _read_json("h3-project-index", [])
    if not isinstance(project_index, list):
        project_index = []
    await _write_json(
        "h3-project-index", sorted(set([*project_index, new_name]))[-500:])
    return _json({"ok": True, "state": created})
