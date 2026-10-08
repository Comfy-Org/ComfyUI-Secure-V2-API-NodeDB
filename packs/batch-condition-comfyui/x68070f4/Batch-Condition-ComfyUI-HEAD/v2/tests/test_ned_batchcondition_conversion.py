"""Pinned algorithms and dynamic UI, typed canonical CLIP protocol, actual guests."""
import asyncio, ast, copy, hashlib, importlib.util, json, os, shutil, subprocess, sys
from pathlib import Path
from types import SimpleNamespace
import pytest
import torch
sys.dont_write_bytecode = True
CORE = Path(os.environ["COMFY_CORE_ROOT"])
sys.path[:0] = [str(CORE), "/Users/ben/comfy/ComfyUI_secure_nodes/backend"]
from comfy.cli_args import args
args.cpu = True
import execution
import comfy.sd
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
from comfy_secure_nodes import packdb, packpatch
V2 = Path(__file__).resolve().parents[1]; PACK = V2.parent; SNAPSHOT = PACK.parent
DB = SNAPSHOT.parents[2]
PAIR = DB / "patches/batch-condition-comfyui/x68070f4/batch-condition-comfyui-x68070f4"
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path / "__init__.py", submodule_search_locations=[str(path)])
    mod = importlib.util.module_from_spec(spec); sys.modules[name] = mod; spec.loader.exec_module(mod)
    return mod
OLD = load("ned_batchcondition_old", PACK); NEW = load("ned_batchcondition_new", V2)
CLASSES = NEW.NODE_CLASS_MAPPINGS; SOURCE = OLD.NODE_CLASS_MAPPINGS; IDS = list(SOURCE)
for cls in CLASSES.values(): cls.GET_SCHEMA()
MOD = sys.modules[CLASSES[IDS[0]].__module__]
def manifest():
    return {"format": FORMAT, "runtime": manifest_declaration(V2), "web_directory": "js", "nodes": {
        key: {"module": "_secure_nodes", "class": cls.__name__, "sdk_refs": cls.SDK_REFS,
              "permissions": list(cls.SDK_PERMISSIONS),
              "methods": {k: False for k in ("validate_inputs", "fingerprint_inputs", "check_lazy_status")},
              "schema": encode_schema(copy.deepcopy(cls.GET_SCHEMA()))} for key, cls in CLASSES.items()}}
class Tokenizer:
    def tokenize_with_weights(self, text, return_word_ids=False, **kwargs):
        return {"l": [[(ord(char), 1.) for char in text]]}
class Stage:
    """Synthetic token arithmetic, not trained CLIP, behind canonical CLIP methods."""
    def __init__(self, dtype): self.dtype = dtype; self.encodes = []; self.options = []
    def reset_clip_options(self): self.options.append("reset")
    def set_clip_options(self, options): self.options.append(dict(options))
    def encode_token_weights(self, tokens):
        self.encodes.append(copy.deepcopy(tokens))
        values = [entry[0] * entry[1] for chunk in tokens["l"] for entry in chunk]
        cond = torch.tensor(values, dtype=self.dtype).reshape(1, len(values), 1).repeat(1, 1, 3)
        return cond, torch.tensor([[sum(values), len(values)]], dtype=self.dtype), {"source_extra": 7}
class Hooks:
    def get_hooks_for_clip_schedule(self): return [((0., .5), []), ((.5, 1.), [])]
    def reset(self): pass
def clip(dtype=torch.float32):
    c = object.__new__(comfy.sd.CLIP); c.tokenizer = Tokenizer(); c.tokenizer_options = {}; c.cond_stage_model = Stage(dtype)
    c.layer_idx = -2; c.use_clip_schedule = True; c.apply_hooks_to_conds = "recording-hooks"
    c.patcher = SimpleNamespace(forced_hooks=Hooks(), load_device=torch.device("cpu"), patch_hooks=lambda _: None)
    c.loads = []; c.load_model = lambda tokens: c.loads.append(copy.deepcopy(tokens))
    return c
def same(actual, expected):
    assert len(actual) == len(expected) == 1 and set(actual[0][1]) == {"pooled_output"}
    for a, b in ((actual[0][0], expected[0][0]), (actual[0][1]["pooled_output"], expected[0][1]["pooled_output"])):
        assert a.shape == b.shape and a.dtype == b.dtype and torch.equal(a, b)
def converted(texts, c):
    async def run():
        refs = _sdk.InProcessRefResolver(); wrapped = _sdk.ClipRef._wrap(await refs.create("CLIP", c))
        with _sdk.bind_runtime(refs, None, _sdk.InProcessOps()):
            result = await CLASSES[IDS[0]].execute(wrapped, texts)
        return await refs.resolve(result.result[0])
    return asyncio.run(run())

def test_exact_three_source_registrations_schema_dynamic_contract_and_proxy():
    assert IDS == list(CLASSES) == ["CLIP Text Encode (Batch)", "String Input", "Batch String"]
    assert not hasattr(NEW, "NODE_DISPLAY_NAME_MAPPINGS") and NEW.WEB_DIRECTORY == OLD.WEB_DIRECTORY == "./js"
    for key, cls in CLASSES.items():
        schema = cls.GET_SCHEMA(); schema.validate(); old = SOURCE[key]
        assert schema.node_id == key and schema.category == old.CATEGORY
        assert tuple(o.io_type for o in schema.outputs) == old.RETURN_TYPES
        expected = old.INPUT_TYPES()["required"]
        assert [i.id for i in schema.inputs] == list(expected)
        for inp in schema.inputs:
            assert inp.io_type == expected[inp.id][0] and not inp.optional
            for k,v in (expected[inp.id][1] if len(expected[inp.id]) > 1 else {}).items(): assert inp.as_dict()[k] == v
        assert cls.SDK_PERMISSIONS == (("raw",) if key == IDS[0] else ())
    assert CLASSES[IDS[2]].GET_SCHEMA().accept_all_inputs
    proxy = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.ned_batchcondition_proxy")
    assert list(proxy.node_mappings) == IDS and proxy.web_directory == V2 / "js" and not proxy.routes

@pytest.mark.parametrize("text", ["", "hello", "\n<script>alert(1)</script>", "中文👋", "#comment\n(foo:1.2)", "a" * 4096])
def test_string_exact_native_passthrough_no_rendering(text):
    assert CLASSES[IDS[1]].execute(text).result == SOURCE[IDS[1]]().encode(text)

@pytest.mark.parametrize("count", [0, 1, 2, 8, 64])
def test_batch_contiguous_source_key_order_not_insertion_order(count):
    kwargs = {f"text{i+1}": f"phrase{i}👋" for i in reversed(range(count))}
    expected = SOURCE[IDS[2]]().encode(**kwargs)
    assert CLASSES[IDS[2]].execute(**kwargs).result == expected
    assert list(kwargs) == [f"text{i+1}" for i in reversed(range(count))]

@pytest.mark.parametrize("kwargs", [{"text2": "x"}, {"text1": "x", "extra": "y"}, {"text0": "x"}])
def test_noncontiguous_native_keyerror(kwargs):
    with pytest.raises(KeyError): SOURCE[IDS[2]]().encode(**kwargs)
    with pytest.raises(KeyError): CLASSES[IDS[2]].execute(**kwargs)

@pytest.mark.parametrize("dtype", [torch.float16, torch.float32, torch.float64, torch.bfloat16])
@pytest.mark.parametrize("texts", [["a"], ["a", "bc"], ["abc", "de"], ["ab", "cd", "ef"], ["中文", "🙂🙂🙂"], ["a", "bc", "def", "ghij"]])
def test_exact_unscheduled_canonical_encode_lcm_repeat_batch_and_pooled(dtype, texts):
    original, c = clip(dtype), clip(dtype)
    expected = SOURCE[IDS[0]]().encode(original, texts)[0]
    actual = converted(texts, c); same(actual, expected)
    assert c.loads == original.loads and c.cond_stage_model.options == original.cond_stage_model.options
    assert len(c.loads) == len(texts) and "source_extra" not in actual[0][1] and "hooks" not in actual[0][1]
    contrast = original.encode_from_tokens_scheduled(original.tokenize(texts[0]))
    assert len(contrast) == 2 and all("clip_start_percent" in row[1] for row in contrast)

@pytest.mark.parametrize("texts", [[], [""], ["a", ""]])
def test_native_empty_list_and_zero_token_errors(texts):
    try: SOURCE[IDS[0]]().encode(clip(), texts)
    except Exception as error:
        with pytest.raises(type(error)): converted(texts, clip())
    else: pytest.fail("source unexpectedly admitted native error control")

def test_bounds_text_lcm_output_work_and_backing_before_repeat(monkeypatch):
    with pytest.raises(ValueError, match="count"): CLASSES[IDS[2]].execute(**{f"text{i+1}": "x" for i in range(65)})
    with pytest.raises(ValueError, match="byte"): CLASSES[IDS[1]].execute("🙂" * (MOD.MAX_TEXT_BYTES // 4 + 1))
    c = clip()
    with pytest.raises(ValueError, match="count"): converted(["x"] * 65, c)
    assert not c.loads
    monkeypatch.setattr(MOD, "MAX_LCM", 5)
    with pytest.raises(ValueError, match="LCM"): converted(["abc", "de"], clip())
    monkeypatch.setattr(MOD, "MAX_LCM", 65536)
    cond = torch.zeros(1, 3, 4); pool = torch.zeros(1, 2)
    monkeypatch.setattr(MOD, "MAX_OUTPUT_BYTES", 47)
    with pytest.raises(ValueError, match="byte"): MOD.repeat_batch([cond], [pool])
    monkeypatch.setattr(MOD, "MAX_OUTPUT_BYTES", 64 * 1024 * 1024)
    monkeypatch.setattr(MOD, "MAX_WORK_BYTES", 1)
    with pytest.raises(ValueError, match="workspace"): MOD.repeat_batch([cond], [pool])
    monkeypatch.setattr(MOD, "MAX_WORK_BYTES", 192 * 1024 * 1024)
    monkeypatch.setattr(MOD, "MAX_INPUT_BYTES", 80)
    with pytest.raises(ValueError, match="byte"): MOD.repeat_batch([torch.zeros(100)[:12].reshape(1,3,4)], [pool])

def test_actual_required_two_fresh_guests_outer_three_ids_raw_denial_and_recovery(tmp_path, monkeypatch):
    monkeypatch.setenv("COMFY_SECURE_SANDBOX_MODE", "required")
    async def run():
        prior = _sdk.providers.execution_backend; pids = []
        try:
            for render in range(2):
                fresh = tmp_path / str(render); shutil.copytree(V2, fresh)
                classes = load("ned_batchcondition_fresh_" + str(render), fresh).NODE_CLASS_MAPPINGS
                for cls in classes.values(): cls.GET_SCHEMA()
                session = await GuestSession("ned-batchcondition-" + str(render), guest_runtime_root=fresh).start()
                caps = ["raw"]
                class Backend:
                    async def dispatch(self, plan, local_call, runtime):
                        plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs, plan.input_types)
                        return await session.execute(plan, runtime, capabilities=tuple(caps), tenant="ned-batchcondition-"+str(render))
                _sdk.providers.register_execution_backend(Backend())
                async def outer(key, values):
                    cls = classes[key]
                    result = await execution._async_map_node_over_list(prompt_id="batchcondition-outer", unique_id=key,
                        obj=cls, input_data_all={k:[v] for k,v in values.items()}, func=cls.FUNCTION, v3_data=None)
                    return result[0].result
                try:
                    assert session.sandbox_kind == "seatbelt"
                    for text in ("", "<script>bad</script>中文"):
                        assert await outer(IDS[1], {"text": text}) == (text,)
                    for count in (0, 1, 4, 64):
                        values = {f"text{i+1}": str(i) for i in reversed(range(count))}
                        assert await outer(IDS[2], values) == SOURCE[IDS[2]]().encode(**values)
                    for dtype in (torch.float16, torch.float32, torch.float64, torch.bfloat16):
                        for texts in (["a", "bc"], ["abc", "de"], ["ab", "cd", "ef"]):
                            c = clip(dtype); expected = SOURCE[IDS[0]]().encode(clip(dtype), texts)[0]
                            actual = (await outer(IDS[0], {"clip": c, "texts": texts}))[0]
                            same(actual, expected); assert len(c.loads) == len(texts)
                    with pytest.raises(Exception, match="IndexError|list index"): await outer(IDS[0], {"clip": clip(), "texts": []})
                    with pytest.raises(Exception, match="ZeroDivisionError|division"): await outer(IDS[0], {"clip": clip(), "texts": [""]})
                    with pytest.raises(Exception, match="KeyError|text1"): await outer(IDS[2], {"text2": "x"})
                    with pytest.raises(Exception, match="count"): await outer(IDS[2], {f"text{i+1}": "x" for i in range(65)})
                    oversized_lcm = ["a" * 257, "b" * 263]
                    with pytest.raises(Exception, match="LCM token budget"):
                        await outer(IDS[0], {"clip": clip(), "texts": oversized_lcm})
                    caps.clear()
                    with pytest.raises(Exception, match="raw|permission|capabil"): await outer(IDS[0], {"clip": clip(), "texts": ["abc"]})
                    assert await outer(IDS[1], {"text": "no raw needed"}) == ("no raw needed",)
                    caps.append("raw")
                    same((await outer(IDS[0], {"clip": clip(), "texts": ["abc", "de"]}))[0], SOURCE[IDS[0]]().encode(clip(), ["abc", "de"])[0])
                    pids.append(session.last_guest_pid)
                finally: await session.kill()
        finally: _sdk.providers.register_execution_backend(prior)
        assert len(set(pids)) == 2 and os.getpid() not in pids
    asyncio.run(run())

def test_actual_opaque_worker_browser_dynamic_inputs_and_lifecycle():
    result = subprocess.run(["node", str(V2 / "tests/ned_batchcondition_browser.mjs")], text=True, capture_output=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS pinned add/remove" in result.stdout and "QUALIFIED" in result.stdout

def test_manifest_exact_pristine_git_stubs_resources_state_and_no_ambient_authority():
    assert json.loads((V2 / "secure-nodes.json").read_text()) == manifest()
    provenance = json.loads((V2 / "source-provenance.json").read_text())
    hashes = {p.relative_to(PACK).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in PACK.rglob("*") if p.is_file() and not p.is_relative_to(V2)}
    assert hashes == provenance["source_hashes"] and len(hashes) == 5
    for blob in provenance["remote_tree"]["tree"]:
        if blob["type"] == "blob":
            data = (PACK / blob["path"]).read_bytes()
            assert hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest() == blob["sha"]
    for name in ("LICENSE", "README.md"): assert (V2 / name).read_bytes() == (PACK / name).read_bytes()
    for name, sha in [("comfy-api.pyi", "89347b67e8ac93aceaa006ae76cfafd6985ec797de504faa0b72268520baeada"), ("comfy-api.d.ts", "2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090")]:
        assert hashlib.sha256((V2 / name).read_bytes()).hexdigest() == sha
    for path in V2.glob("*.py"):
        text = path.read_text()
        for bad in ("_from_raw", "_wrap(", "folder_paths", "PromptServer", "subprocess", "requests", "open("):
            assert bad not in text
        for n in ast.walk(ast.parse(text)):
            if isinstance(n, ast.Import): assert all(a.name in ("math", "torch") for a in n.names)
    assert not list(PACK.rglob("__pycache__")) and not list(PACK.rglob("*.pyc"))

def test_pair_and_zip_two_exact_reconstructions_and_wrong_source_refusal(tmp_path):
    expected, diff = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == expected
    assert PAIR.with_suffix(".diff").read_bytes() == diff.encode()
    for index in range(2):
        fresh = tmp_path / str(index) / "batch-condition-comfyui/x68070f4"; fresh.mkdir(parents=True)
        shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
        if index == 0: packpatch.apply(fresh, expected, diff)
        else: packpatch.apply_bundle(fresh, packpatch.bundle(expected, diff))
        packpatch.validate_tree(fresh / PACK.name / "v2", V2)
    fresh = tmp_path / "bad/batch-condition-comfyui/x68070f4"; fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    (fresh / PACK.name / "batch_condition.py").write_bytes(b"#wrong source")
    with pytest.raises(packpatch.PackPatchError): packpatch.apply(fresh, expected, diff)
    assert not (fresh / PACK.name / "v2").exists()
