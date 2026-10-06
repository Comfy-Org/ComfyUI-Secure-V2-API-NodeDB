from __future__ import annotations

import asyncio
import copy
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import torch

sys.dont_write_bytecode = True
V2 = Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
DB = SNAPSHOT.parents[2]
BACKEND = Path("/Users/ben/comfy/ComfyUI_secure_nodes/backend")
CORE = Path("/Users/ben/comfy/ComfyUI-secure-nodes")
COMFYUI = Path("/Users/ben/comfy/ComfyUI")
for root in (BACKEND, CORE):
    sys.path.insert(0, str(root))
sys.path.append(str(COMFYUI))
os.environ.setdefault("COMFY_CORE_ROOT", str(CORE))

import execution
from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb, packpatch
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
from comfy_secure_nodes.transport.host import GuestSession

NODE = "comfypsi_blur_mask"
PAIR = DB / "patches/comfypsi-blur-mask/x25070eb/comfypsi-blur-mask-x25070eb"


def _load(name, root):
    for key in tuple(sys.modules):
        if key == name or key.startswith(name + "."):
            sys.modules.pop(key, None)
    spec = importlib.util.spec_from_file_location(name, root / "__init__.py", submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _secure(root=V2):
    return _load("_blur_mask_secure", root)


def _old(tmp_path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _load("_blur_mask_old", root)


def _manifest(module):
    node = module.BlurMask
    return {
        "format": FORMAT,
        "nodes": {
            NODE: {
                "class": "BlurMask",
                "module": "nodes",
                "permissions": ["raw"],
                "sdk_refs": False,
                "methods": {k: False for k in ("check_lazy_status", "fingerprint_inputs", "validate_inputs")},
                "schema": encode_schema(copy.deepcopy(node.GET_SCHEMA())),
            }
        },
        "runtime": manifest_declaration(V2),
        "web_directory": "web",
    }


def test_actual_census_schema_and_manifest(tmp_path):
    old, new = _old(tmp_path), _secure()
    assert set(old.NODE_CLASS_MAPPINGS) == set(new.NODE_CLASS_MAPPINGS) == {NODE}
    assert old.NODE_DISPLAY_NAME_MAPPINGS == new.NODE_DISPLAY_NAME_MAPPINGS
    schema = new.BlurMask.GET_SCHEMA()
    schema.validate()
    assert schema.node_id == NODE and schema.category == "comfypsi/mask"
    assert [x.id for x in schema.inputs] == ["mask", "blur"]
    assert [x.io_type for x in schema.inputs] == ["MASK", "FLOAT"]
    for key, value in old.NODE_CLASS_MAPPINGS[NODE].INPUT_TYPES()["required"]["blur"][1].items():
        assert getattr(schema.inputs[1], key) == value
    assert [x.io_type for x in schema.outputs] == ["MASK"]
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(new)
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.blur_mask_census")
    assert set(loaded.node_mappings) == {NODE} and not loaded.routes
    assert not loaded.frontend_permissions and loaded.web_directory
    assert (PACK / "web/js/app.js").read_text().count("app.registerExtension(") == 1


@pytest.mark.parametrize("shape", [(1, 1, 1), (1, 2, 3), (2, 9, 12), (3, 16, 17)])
@pytest.mark.parametrize("dtype", [torch.float32, torch.float64])
@pytest.mark.parametrize("blur", [-2.0, 0.0, 0.01, 0.5, 5.0, 100.0])
def test_exact_kernel_pixels_and_identity(tmp_path, shape, dtype, blur):
    value = torch.linspace(0, 1, shape[0] * shape[1] * shape[2], dtype=dtype).reshape(shape)
    value = value.transpose(1, 2)
    before = value.clone()
    rng = torch.get_rng_state().clone()
    expected = _old(tmp_path).NODE_CLASS_MAPPINGS[NODE]().main(value, blur)[0]
    actual = _secure().BlurMask.execute(value, blur).result[0]
    assert actual.shape == expected.shape and actual.dtype == expected.dtype
    assert torch.equal(actual, expected) and torch.equal(value, before)
    assert torch.equal(torch.get_rng_state(), rng)
    if blur <= 0:
        assert actual is value


@pytest.mark.parametrize(
    "mask,blur,error",
    [
        (None, 1, TypeError),
        (torch.zeros(2, 2), 1, ValueError),
        (torch.zeros(0, 2, 2), 1, ValueError),
        (torch.zeros(65, 2, 2), 1, ValueError),
        (torch.zeros(1, 2, 2, dtype=torch.int64), 1, TypeError),
        (torch.full((1, 2, 2), float("nan")), 1, ValueError),
        (torch.zeros(1, 2, 2), True, TypeError),
        (torch.zeros(1, 2, 2), "x", TypeError),
        (torch.zeros(1, 2, 2), float("inf"), ValueError),
        (torch.zeros(1, 2, 2), 101, ValueError),
    ],
)
def test_malformed_fail_closed(mask, blur, error):
    with pytest.raises(error):
        _secure().BlurMask.execute(mask, blur)


def test_bounds_before_algorithm(monkeypatch):
    node = _secure().BlurMask
    algorithm = sys.modules["_blur_mask_secure.nodes"].comfypsi_blur_mask
    monkeypatch.setattr(algorithm, "main", lambda *a: pytest.fail("algorithm entered"))
    for mask, blur in [(torch.zeros(1, 1, 8193), 1), (torch.zeros(64, 513, 513), 1), (torch.zeros(1, 1024, 1024), 100)]:
        with pytest.raises(ValueError):
            node.execute(mask, blur)


def test_real_guests_fresh_filesystem_denial_and_outer_mask(tmp_path):
    fresh = tmp_path / "fresh"
    shutil.copytree(V2, fresh)
    value = torch.linspace(0, 1, 2 * 9 * 11).reshape(2, 9, 11)

    async def run():
        refs = _sdk.InProcessRefResolver()
        mask = _sdk.MaskRef._wrap(await refs.create("MASK", value))
        pids = []
        for root in (V2, fresh):
            active_node = _secure(root).BlurMask
            session = await GuestSession("blur-mask-fresh", guest_runtime_root=root).start()
            try:
                for blur in (0.0, 0.5, 5.0, 100.0):
                    plan = _sdk.ExecutionPlan(
                        prompt_id="blur",
                        node_id="1",
                        node_type=active_node.__name__,
                        tier="sandbox",
                        node_module=active_node.__module__,
                        inputs={"mask": mask, "blur": blur},
                        input_mode="values",
                        permissions=("raw",),
                        method="execute",
                    )
                    runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps())
                    result = await session.execute(plan, runtime, capabilities=("raw",))
                    actual = await refs.resolve(result.result[0])
                    assert torch.equal(actual, active_node.execute(value, blur).result[0])
                    with pytest.raises(Exception, match="raw"):
                        await session.execute(plan, runtime, capabilities=())
                pids.append(session.last_guest_pid)
            finally:
                await session.kill()
        assert len(set(pids)) == 2 and os.getpid() not in pids
        node = _secure().BlurMask
        loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.blur_mask_outer")
        outer_node = loaded.node_mappings[NODE]
        assert tuple(outer_node.RETURN_TYPES) == ("MASK",)
        previous = _sdk.providers.execution_backend

        class Backend:
            session = None

            async def dispatch(self, plan, local_call, runtime):
                self.session = await GuestSession("blur-mask-outer", guest_runtime_root=V2).start()
                plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
                return await self.session.execute(plan, runtime, capabilities=("raw",))

        backend = Backend()
        _sdk.providers.register_execution_backend(backend)
        try:
            result = await execution._async_map_node_over_list(
                prompt_id="outer",
                unique_id="1",
                obj=outer_node,
                input_data_all={"mask": [value], "blur": [5.0]},
                func=outer_node.FUNCTION,
                v3_data=None,
            )
            actual = result[0].result[0]
            assert isinstance(actual, torch.Tensor) and torch.equal(actual, node.execute(value, 5.0).result[0])
        finally:
            _sdk.providers.register_execution_backend(previous)
            if backend.session:
                await backend.session.kill()

    asyncio.run(run())


def test_typed_frontend_width_lifecycle_isolation_and_typecheck():
    js = V2 / "web/js/app.js"
    harness = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(process.argv[1],'utf8').replace(/^import .*;$/m,'').replace(/export function/g,'function');
let active=new Set(),adds=0,removes=0;
const comfy={defs:{extend(selector,apply){assert.equal(selector,'comfypsi_blur_mask');adds++;
 let callback;apply({onCreated(fn){callback=fn;}});active.add(callback);
 return()=>{assert(active.delete(callback));removes++;};}}};
const context=vm.createContext({comfy});vm.runInContext(source,context);
const make=(id,height)=>({id,size:{width:100,height},getSize(){return {...this.size};},setSize(s){this.size={...s};}});
const first=make('1',71),otherGraph=make('1',140);for(const fn of active){fn(first);fn(otherGraph);}
assert.equal(first.size.width,225);assert.equal(first.size.height,71);
assert.equal(otherGraph.size.width,225);assert.equal(otherGraph.size.height,140);
vm.runInContext('install();install();',context);assert.equal(adds,1);
first.size.width=444;assert.equal(otherGraph.size.width,225);
vm.runInContext('dispose();dispose();',context);assert.equal(active.size,0);assert.equal(removes,1);
vm.runInContext('install();',context);assert.equal(adds,2);assert.equal(active.size,1);
const fresh=make('fresh',90);for(const fn of active)fn(fresh);assert.equal(fresh.size.width,225);
vm.runInContext('dispose();',context);assert.equal(active.size,0);assert.equal(removes,2);
console.log('frontend width/lifecycle PASS');
"""
    subprocess.run(["node", "-e", harness, str(js)], check=True, capture_output=True, text=True)
    subprocess.run(["node", "--check", str(js)], check=True, capture_output=True, text=True)
    subprocess.run(["tsc", "--noEmit", "-p", str(V2 / "tsconfig.json")], check=True, capture_output=True, text=True)


def test_source_resources_contract_security():
    assert (PACK / "src/node.py").read_bytes() == (V2 / "algorithm.py").read_bytes()
    assert (PACK / "LICENSE").read_bytes() == (V2 / "LICENSE").read_bytes()
    hashes = {
        "comfy-api.d.ts": "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3",
        "comfy-api.pyi": "50848a56eaf4f798de1a4f11faa7e3bd9b6254c2c61a94b5a9907aaa2b0cac78",
    }
    for file, digest in hashes.items():
        assert hashlib.sha256((V2 / file).read_bytes()).hexdigest() == digest
    sources = "\n".join((V2 / f).read_text() for f in ("nodes.py", "__init__.py", "algorithm.py", "web/js/app.js"))
    for token in (
        "_from_raw",
        "PromptServer",
        "folder_paths",
        "fetch(",
        "document",
        "window",
        "localStorage",
        "open(",
        "comfy.model_management",
    ):
        assert token not in sources
    assert "25070eb27c9e938745c167edae428e5986c81cc1" in (V2 / "SECURE_CONVERSION.md").read_text()


def test_exact_patch_and_cache_hygiene(tmp_path):
    manifest, diff = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes() == diff.encode()
    fresh = tmp_path / "comfypsi-blur-mask/x25070eb"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff)
    packpatch.validate_tree(fresh / PACK.name / "v2", V2)
    for pattern in ("__pycache__", "*.pyc", ".pytest_cache", ".ruff_cache"):
        assert not list(PACK.rglob(pattern))


if __name__ == "__main__":
    (V2 / "secure-nodes.json").write_text(json.dumps(_manifest(_secure()), indent=2) + "\n")
