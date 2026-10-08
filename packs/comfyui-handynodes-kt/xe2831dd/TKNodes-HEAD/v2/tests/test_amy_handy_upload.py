"""Real registered upload handlers, managed publication, then source pixels."""
import asyncio
import io
import json
import types
from PIL import Image
import pytest
from comfy_secure_nodes import webassets
import test_amy_handy_assets as asset_proof
import test_amy_handy_v3 as proof

class Routes:
    def __init__(self):
        self.handlers = {}
    def route(self, path):
        def add(fn):
            self.handlers[path] = fn
            return fn
        return add
    get = post = put = delete = route

class Content:
    def __init__(self, payload):
        self.payload = payload
    async def iter_chunked(self, size):
        for offset in range(0, len(self.payload), size):
            yield self.payload[offset:offset+size]

class Request:
    def __init__(self, declaration=None, payload=b"", **match):
        self.value = declaration
        self.content_length = len(payload)
        self.content = Content(payload)
        self.match_info = match
    async def json(self):
        return self.value

def test_registered_upload_publication_exact_bytes_no_clobber_then_managed_load(tmp_path, monkeypatch):
    import folder_paths
    monkeypatch.setattr(folder_paths, "get_input_directory", lambda: str(tmp_path))
    server = types.SimpleNamespace(routes=Routes())
    webassets.register_routes(server)
    handlers = server.routes.handlers
    data = io.BytesIO()
    Image.new("RGBA", (3, 2), (33, 77, 129, 51)).save(data, "PNG")
    payload = data.getvalue()
    async def publish():
        before = (tmp_path / "managed/selected.png").read_bytes() if (tmp_path / "managed/selected.png").exists() else None
        result = await handlers["/secure-nodes/uploads"](Request({"name":"selected.png","subfolder":"managed","mime_type":"image/png","size":len(payload)}))
        upload_id = json.loads(result.body)["upload_id"]
        await handlers["/secure-nodes/uploads/{upload_id}/{index}"](Request(payload=payload, upload_id=upload_id, index="0"))
        if before is None:
            assert not (tmp_path / "managed/selected.png").exists()
        else:
            assert (tmp_path / "managed/selected.png").read_bytes() == before
        result = await handlers["/secure-nodes/uploads/{upload_id}/complete"](Request(upload_id=upload_id))
        return json.loads(result.body)
    async def run():
        first = await publish()
        # Native overwrite=true is deliberately replaced by managed publisher
        # collision suffixes, not an invented collision-refusal guarantee.
        second = await publish()
        assert first["path"] == "managed/selected.png"
        assert second["path"] == "managed/selected_1.png"
        assert (tmp_path / first["path"]).read_bytes() == payload
        assert (tmp_path / second["path"]).read_bytes() == payload
        rt = asset_proof.runtime()
        with proof._sdk.bind_runtime(rt.refs, rt.ctx, rt.ops):
            result = await proof.pack.NODE_CLASS_MAPPINGS["TKMultiImageSelect"].execute(image_1=first["path"], image_2=second["path"])
        assert [row["filename"] for row in result.result[0]] == [first["path"], second["path"]]
        assert [row["slot"] for row in result.result[0]] == [1, 2]
        assert result.result[0][0]["image"].shape == (1, 2, 3, 3)
        import torch
        assert torch.equal(result.result[0][0]["image"][0,0,0], torch.tensor([33,77,129],dtype=torch.float32)/255)
    asyncio.run(run())
