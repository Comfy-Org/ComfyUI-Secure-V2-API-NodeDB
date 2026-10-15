from __future__ import annotations

import ast
import asyncio
import copy
import hashlib
import importlib.util
import json
import os
import random
import shutil
import subprocess
import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest

sys.dont_write_bytecode = True
V2 = Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
DB = SNAPSHOT.parents[2]
CORE = Path("/Users/ben/comfy/ComfyUI-secure-nodes")
BACKEND = Path("/Users/ben/comfy/ComfyUI_secure_nodes/backend")
for root in (CORE, BACKEND):
    sys.path.insert(0, str(root))
os.environ.setdefault("COMFY_CORE_ROOT", str(CORE))
from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb, packpatch
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
from comfy_secure_nodes.transport.host import GuestSession

NODE = "jupo.AspectRatios.AspectRatios"
PAIR = DB / "patches/comfy-aspect-ratios/xc47658e/comfy-aspect-ratios-xc47658e"


def load(root, name):
    for key in tuple(sys.modules):
        if key == name or key.startswith(name + "."):
            sys.modules.pop(key)
    spec = importlib.util.spec_from_file_location(
        name, root / "__init__.py", submodule_search_locations=[str(root)]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def old():
    routes = []

    class Routes:
        def post(self, path):
            def register(f):
                routes.append(path)
                return f

            return register

    server = types.ModuleType("server")
    server.PromptServer = type(
        "PromptServer", (), {"instance": types.SimpleNamespace(routes=Routes())}
    )
    model = types.ModuleType("comfy.model_management")
    model.intermediate_device = lambda: "cpu"
    with patch.dict(sys.modules, {"server": server, "comfy.model_management": model}):
        module = load(PACK, "_jupo_old")
        module.algorithm = sys.modules[module.__name__ + ".py.nodes.aspect_ratios"]
    return module, routes


def secure(root=V2):
    return load(root, "_jupo_secure")


def manifest(m):
    cls = m.AspectRatios
    return {
        "format": FORMAT,
        "runtime": manifest_declaration(V2),
        "web_directory": "web",
        "frontend_permissions": [],
        "nodes": {
            NODE: {
                "module": "nodes",
                "class": "AspectRatios",
                "sdk_refs": True,
                "permissions": [],
                "schema": encode_schema(copy.deepcopy(cls.GET_SCHEMA())),
                "methods": {
                    x: False
                    for x in (
                        "validate_inputs",
                        "fingerprint_inputs",
                        "check_lazy_status",
                    )
                },
            }
        },
    }


def test_real_census_schema_routes_and_pure_function_identity():
    m, routes = old()
    n = secure()
    legacy = asyncio.run(asyncio.run(m.comfy_entrypoint()).get_node_list())
    assert len(legacy) == 1 and legacy[0].GET_SCHEMA().node_id == NODE
    assert routes == ["/jupo/AspectRatios/calc", "/jupo/AspectRatios/preset"]
    assert encode_schema(legacy[0].GET_SCHEMA()) == encode_schema(
        n.AspectRatios.GET_SCHEMA()
    )
    assert len(n.AspectRatios.GET_SCHEMA().inputs[-2].options) == 16
    entry = asyncio.run(n.comfy_entrypoint())
    assert asyncio.run(entry.get_node_list()) == [n.AspectRatios]
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.jupo_census")
    assert set(loaded.node_mappings) == {NODE} and not loaded.routes

    def func(path):
        return next(
            x
            for x in ast.parse(path.read_text()).body
            if isinstance(x, ast.FunctionDef) and x.name == "calc_resolution"
        )

    assert ast.dump(
        func(PACK / "py/nodes/aspect_ratios.py"), include_attributes=False
    ) == ast.dump(func(V2 / "algorithm.py"), include_attributes=False)
    assert (PACK / "web/extension/aspect-ratios.js").read_text().count(
        "app.registerExtension("
    ) == 1


CASES = [
    dict(
        base=256,
        fixed_side=f,
        step=s,
        aspect_w=w,
        aspect_h=h,
        batch_size=b,
        preset="none",
    )
    for f in ("none", "short", "long")
    for s in (8, 9, 16)
    for w, h in ((1, 1), (3, 4), (7, 5))
    for b in (1, 2)
]


@pytest.mark.parametrize("args", CASES)
def test_geometry_exact(args):
    m, _ = old()
    legacy = m.algorithm
    assert secure().nodes.calc_resolution(**args) == legacy.calc_resolution(**args)


def test_random_math_and_frontend_differential_lifecycle(tmp_path):
    m, _ = old()
    legacy = m.algorithm
    n = secure()
    rng = random.Random(921)
    matrix = []
    for value in legacy.ASPECT_RATIOS_PRESETS:
        if value == "none":
            continue
        w, h = map(int, value.split("]")[-1].strip().split(":"))
        args = [1024, "none", 8, w, h]
        matrix.append([args, legacy.calc_resolution(*args)])
    for _ in range(1000):
        args = [
            rng.randrange(8, 8193),
            rng.choice(["none", "short", "long"]),
            rng.randrange(8, 513),
            rng.randrange(1, 33),
            rng.randrange(1, 33),
        ]
        expect = legacy.calc_resolution(*args)
        assert n.nodes.calc_resolution(*args) == expect
        matrix.append([args, expect])
    dest = tmp_path / "matrix.json"
    dest.write_text(json.dumps(matrix))
    result = subprocess.run(
        [
            "node",
            "--experimental-vm-modules",
            str(V2 / "tests/frontend_harness.mjs"),
            str(V2 / "web/main.js"),
            str(dest),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS" in result.stdout


def test_frontend_uses_only_the_authoritative_types(tmp_path):
    source = (V2 / "web/main.js").read_text().replace('"/comfy/api/v2.js"', '"./api"')
    (tmp_path / "entry.js").write_text(source)
    (tmp_path / "api.ts").write_text(
        f"export declare const comfy: import({json.dumps(str(V2 / 'comfy-api.d.ts'))}).Comfy;\n"
    )
    result = subprocess.run(
        [
            "tsc",
            "--allowJs",
            "--checkJs",
            "--noEmit",
            "--skipLibCheck",
            "--target",
            "ES2022",
            "--module",
            "ESNext",
            "--moduleResolution",
            "bundler",
            str(tmp_path / "entry.js"),
            str(tmp_path / "api.ts"),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_guest_all_modes_zeros_bounds_denial_fresh_filesystem(tmp_path):
    import torch

    fresh = tmp_path / "fresh"
    shutil.copytree(V2, fresh)

    async def run():
        pids = []
        for root in (V2, fresh):
            cls = secure(root).AspectRatios
            refs = _sdk.InProcessRefResolver()
            session = await GuestSession("jupo-aspect", guest_runtime_root=root).start()
            try:

                async def execute(args):
                    plan = _sdk.ExecutionPlan(
                        prompt_id="jupo",
                        node_id="1",
                        node_type=cls.__name__,
                        tier="sandbox",
                        node_module=cls.__module__,
                        inputs=args,
                        input_mode="refs",
                        permissions=(),
                        method="execute",
                    )
                    runtime = _sdk.Runtime(
                        refs=refs,
                        ctx=_sdk.InProcessCtxProvider().build(plan),
                        ops=_sdk.InProcessOps(),
                    )
                    return await session.execute(plan, runtime, capabilities=())

                for args in CASES[::3]:
                    result = await execute(args)
                    latent, w, h = result.result
                    expected = secure().nodes.calc_resolution(**args)
                    assert (w, h) == expected
                    raw = await refs.resolve(latent)
                    samples = raw["samples"]
                    assert samples.shape == (args["batch_size"], 4, h // 8, w // 8)
                    assert samples.dtype == torch.float32 and not torch.count_nonzero(
                        samples
                    )
                    assert raw["downscale_ratio_spacial"] == 8
                    await refs.release(latent)
                for changed in (
                    {"batch_size": 65},
                    {"base": 8193},
                    {"aspect_w": True},
                    {"step": 8192},
                    {"base": 8192, "batch_size": 64},
                    {"fixed_side": "bad"},
                ):
                    with pytest.raises(Exception):
                        await execute(CASES[0] | changed)
                    assert not refs._table
                image = _sdk.ImageRef._wrap(
                    await refs.create("IMAGE", torch.zeros(1, 1, 1, 3))
                )
                with pytest.raises(Exception):
                    await execute(CASES[0] | {"base": image})
                await refs.release(image)
                pids.append(session.last_guest_pid)
                assert pids[-1] != os.getpid()
            finally:
                await session.kill()
        assert pids[0] != pids[1]

    asyncio.run(run())


def test_manifest_stubs_license_security_and_roundtrip(tmp_path):
    assert json.loads((V2 / "secure-nodes.json").read_text()) == manifest(secure())
    assert (
        hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest()
        == "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
    )
    assert (
        hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest()
        == "50848a56eaf4f798de1a4f11faa7e3bd9b6254c2c61a94b5a9907aaa2b0cac78"
    )
    assert (PACK / "LICENSE").read_bytes() == (V2 / "LICENSE").read_bytes()
    for filename in ("nodes.py", "algorithm.py", "web/main.js"):
        text = (V2 / filename).read_text()
        for banned in (
            "PromptServer",
            "folder_paths",
            "_from_raw",
            "import torch",
            "fetch(",
            "localStorage",
            "open(",
        ):
            assert banned not in text
    data, diff = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == data
    assert PAIR.with_suffix(".diff").read_bytes() == diff.encode()
    snap = tmp_path / "comfy-aspect-ratios/xc47658e"
    snap.mkdir(parents=True)
    shutil.copytree(PACK, snap / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(snap, data, diff)
    packpatch.validate_tree(snap / PACK.name / "v2", V2)
    assert not list(PACK.rglob("__pycache__")) and not list(PACK.rglob("*.pyc"))
