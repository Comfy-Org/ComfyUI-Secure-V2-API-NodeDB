"""Unregistered CPU MoCha stage: recording VAE, not trained inference."""
import ast
import asyncio
import copy
import importlib
import importlib.util
import itertools
import os
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace
import pytest
import torch

sys.dont_write_bytecode = True
V2 = Path(__file__).resolve().parents[1]
PACK = V2.parent
CORE = "/Users/ben/comfy/ComfyUI-secure-nodes"
sys.path[:0] = [CORE, "/Users/ben/comfy/ComfyUI_secure_nodes/backend"]
os.environ.setdefault("COMFY_CORE_ROOT", CORE)
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession


@pytest.fixture(autouse=True)
def small_cpu_threads():
    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    try:
        yield
    finally:
        torch.set_num_threads(previous)


def candidate():
    name = "_wan_mocha_algorithms"
    spec = importlib.util.spec_from_file_location(name, V2/"__init__.py", submodule_search_locations=[str(V2)])
    pkg = importlib.util.module_from_spec(spec)
    sys.modules[name] = pkg
    spec.loader.exec_module(pkg)
    assert "MochaEmbeds" not in pkg.NODE_CLASS_MAPPINGS and len(pkg.NODE_CLASS_MAPPINGS) == 63
    return importlib.import_module(name+".secure_mocha_algorithms")


def source():
    tree = ast.parse((PACK/"mocha/nodes.py").read_text())
    selected = [copy.deepcopy(n) for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef))]
    for node in selected:
        if isinstance(node, ast.FunctionDef):
            node.decorator_list = []  # Remove ambient-device autocast selection only.
    ns = dict(torch=torch, device=torch.device("cpu"), offload_device=torch.device("cpu"),
        mm=SimpleNamespace(soft_empty_cache=lambda: None), gc=SimpleNamespace(collect=lambda: None))
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(PACK/"mocha/nodes.py"), "exec"), ns)
    return SimpleNamespace(**ns)


class RecordingVAE:
    """Deterministic projection for shape/call comparison; no learned weights."""
    def __init__(self, dtype=torch.float32, factor=8):
        self.dtype = dtype
        self.upsampling_factor = factor
        self.calls = []
        self.moves = []
        self.model = self

    def to(self, device):
        self.moves.append(str(device))
        return self

    def encode(self, image, device, *, tiled):
        self.calls.append((image.clone(), str(device), tiled))
        # Produce one channel pattern then replicate16; preserve the input dtype.
        spatial = image.mean(dim=1, keepdim=True)[..., ::4, :image.shape[-2]//self.upsampling_factor*self.upsampling_factor:self.upsampling_factor,
            :image.shape[-1]//self.upsampling_factor*self.upsampling_factor:self.upsampling_factor]
        return spatial.repeat(1, 16, 1, 1, 1)


def fields(frames=5, dtype=torch.float32, two_refs=False, mask_batch=1, factor=8):
    image = torch.arange(frames*19*27*4, dtype=torch.float64).reshape(frames, 19, 27, 4).to(dtype)/1000
    ref1 = torch.arange(19*27*4, dtype=torch.float64).reshape(1, 19, 27, 4).to(dtype)/1500
    ref2 = ref1.flip(2) if two_refs else None
    mask = torch.linspace(-1, 2, mask_batch*19*27).reshape(mask_batch, 19, 27)
    mask[:, 0, :4] = torch.tensor([float("nan"), 0., .5, .5001])
    return dict(input_video=image, ref1=ref1, ref2=ref2, mask=mask,
        force_offload=True, tiled_vae=True)


def stage(inputs, vae):
    fn = candidate()
    prepared = fn.prepare_mocha_inputs(inputs["input_video"], inputs["ref1"], vae.dtype, inputs["ref2"])
    enc = [vae.encode(prepared[key], "cpu", tiled=inputs["tiled_vae"])
        for key in ("input_video", "ref1", "ref2") if prepared[key] is not None]
    return fn.assemble_mocha_embeds(enc[0], enc[1], inputs["mask"],
        num_frames=prepared["num_frames"], height=prepared["height"], width=prepared["width"],
        upsampling_factor=vae.upsampling_factor, dtype=vae.dtype, ref2_latents=enc[2] if len(enc)==3 else None)


def equal(old, new):
    if isinstance(old, torch.Tensor):
        assert isinstance(new, torch.Tensor) and old.shape == new.shape and old.dtype == new.dtype
        torch.testing.assert_close(old, new, rtol=0, atol=0, equal_nan=True)
    elif isinstance(old, dict):
        assert list(old) == list(new)
        for key in old:
            equal(old[key], new[key])
    elif isinstance(old, (list, tuple)):
        assert len(old) == len(new)
        for a, b in zip(old, new):
            equal(a, b)
    else:
        assert old == new and type(old) is type(new)


def test_exact_source_rotary_math_ast_after_bounded_preflight():
    old_tree = ast.parse((PACK/"mocha/nodes.py").read_text())
    new_tree = ast.parse((V2/"secure_mocha_algorithms.py").read_text())
    for name in ("rope_params_mocha", "rope_apply_mocha"):
        old = next(n for n in old_tree.body if getattr(n, "name", None) == name)
        new = next(n for n in new_tree.body if getattr(n, "name", None) == name)
        assert ast.dump(ast.Module(body=old.body, type_ignores=[]), include_attributes=False) == ast.dump(
            ast.Module(body=new.body[1:], type_ignores=[]), include_attributes=False)


def test_96_recording_vae_preprocessing_mask_and_reference_compositions_exact():
    count = 0
    for frames, dtype, two_refs, factor in itertools.product((1,2,4,5,8,9),
            (torch.float16,torch.bfloat16,torch.float32,torch.float64), (False,True), (8,16)):
        inputs = fields(frames, dtype, two_refs, factor=factor)
        original = RecordingVAE(dtype, factor)
        current = RecordingVAE(dtype, factor)
        old = source().MochaEmbeds().process(original, **copy.deepcopy(inputs))[0]
        new = stage(copy.deepcopy(inputs), current)
        equal(old, new)
        assert list(new) == ["seq_len","mocha_embeds","num_frames","target_shape","mocha_num_refs"]
        assert new["num_frames"] == (frames-1)//4*4+1
        assert len(original.calls) == len(current.calls) == (3 if two_refs else 2)
        for a, b in zip(original.calls, current.calls):
            equal(a[0], b[0]); assert a[1:] == b[1:]
        # Source physical moves are observed only on the recorder. Staged math
        # deliberately does not pretend to implement residency/offload.
        assert original.moves == ["cpu","cpu"] and current.moves == []
        count += 1
    assert count == 96


def test_noncontiguous_inputs_unchanged_global_rng_and_native_mask_nan():
    inputs = fields(two_refs=True)
    for key in ("input_video","ref1","ref2"):
        inputs[key] = inputs[key].transpose(1,2)
    before = copy.deepcopy(inputs)
    rng = torch.random.get_rng_state().clone()
    old = source().MochaEmbeds().process(RecordingVAE(), **copy.deepcopy(inputs))[0]
    new = stage(inputs, RecordingVAE())
    equal(old,new)
    assert torch.equal(rng,torch.random.get_rng_state())
    for key in ("input_video","ref1","ref2","mask"):
        equal(inputs[key],before[key])
    assert torch.isnan(new["mocha_embeds"]).any()


@pytest.mark.parametrize("variant",["mask_batch","mask_rank","video_rank","ref_rank"])
def test_native_malformed_recording_vae_pipeline_errors(variant):
    inputs = fields()
    if variant == "mask_batch": inputs["mask"] = inputs["mask"].repeat(2,1,1)
    if variant == "mask_rank": inputs["mask"] = inputs["mask"][0]
    if variant == "video_rank": inputs["input_video"] = inputs["input_video"][0]
    if variant == "ref_rank": inputs["ref1"] = inputs["ref1"][0]
    with pytest.raises(Exception) as old:
        source().MochaEmbeds().process(RecordingVAE(), **copy.deepcopy(inputs))
    with pytest.raises(type(old.value)) as new:
        stage(copy.deepcopy(inputs), RecordingVAE())
    assert str(old.value) == str(new.value)


def rotary_case(f, h, w, dtype=torch.float32, batch=1):
    head = 12
    freq = source().rope_params_mocha(64,head,start=-1)
    length = f*h*w
    x = torch.arange(batch*(length+3)*2*head, dtype=torch.float64).reshape(batch,length+3,2,head).to(dtype)/100
    return dict(x=x, grid_sizes=torch.tensor([[f,h,w]]*batch), freqs=freq)


def test_48_rotary_cases_even_and_bias_branches_tail_and_dtype():
    count = 0
    native_errors = 0
    for f, dtype, batch in itertools.product((4,5,6,7,8,9),
            (torch.float16,torch.bfloat16,torch.float32,torch.float64),(1,2)):
        inputs = rotary_case(f,2,3,dtype,batch)
        try:
            old = source().rope_apply_mocha(**copy.deepcopy(inputs))
        except Exception as error:
            with pytest.raises(type(error)) as new:
                candidate().rope_apply_mocha(**copy.deepcopy(inputs))
            assert str(new.value) == str(error)
            assert dtype == torch.bfloat16 and "view_as_complex" in str(error)
            native_errors += 1
        else:
            new = candidate().rope_apply_mocha(**copy.deepcopy(inputs))
            equal(old,new)
            equal(new[:,-3:],inputs["x"][:,-3:])
        count += 1
    assert count == 48 and native_errors == 12


def test_frequency_params_riflex_and_native_errors():
    count = 0
    for length, dim, start, k in itertools.product((0,8,32),(2,6,12),(-1,0,3),(0,1)):
        args = dict(max_seq_len=length,dim=dim,start=start,k=k,L_test=25)
        try:
            old = source().rope_params_mocha(**args)
        except Exception as error:
            with pytest.raises(type(error)) as new: candidate().rope_params_mocha(**args)
            assert str(new.value) == str(error)
        else:
            equal(old,candidate().rope_params_mocha(**args))
        count += 1
    assert count == 54
    with pytest.raises(AssertionError): candidate().rope_params_mocha(10,3)
    with pytest.raises(IndexError): candidate().rope_params_mocha(10,2,k=2)


def test_actual_sampler_frequency_call_shape_and_native_bad_rotary_layout():
    old = source()
    new = candidate()
    # Source loader dim5120/heads40 and dim1536/heads12 both produce d128;
    # preserve the exact sampler's three-part 1024-row/start=-1 construction.
    for k in (0,1,6):
        original = torch.cat([old.rope_params_mocha(1024,44,L_test=25,k=k,start=-1),
            old.rope_params_mocha(1024,42,start=-1),old.rope_params_mocha(1024,42,start=-1)],dim=1)
        current = torch.cat([new.rope_params_mocha(1024,44,L_test=25,k=k,start=-1),
            new.rope_params_mocha(1024,42,start=-1),new.rope_params_mocha(1024,42,start=-1)],dim=1)
        equal(original,current)
        assert current.shape == (1025,64) and current.dtype == torch.complex128
    for variant in ("wrong_freq_width","short_tokens","float_grid","empty_batch"):
        args = rotary_case(6,2,3)
        if variant == "wrong_freq_width": args["freqs"] = args["freqs"][:,:5]
        if variant == "short_tokens": args["x"] = args["x"][:,:2]
        if variant == "float_grid": args["grid_sizes"] = args["grid_sizes"].float()
        if variant == "empty_batch": args["grid_sizes"] = args["grid_sizes"][:0]
        with pytest.raises(Exception) as original: old.rope_apply_mocha(**copy.deepcopy(args))
        with pytest.raises(type(original.value)) as current: new.rope_apply_mocha(**copy.deepcopy(args))
        assert str(original.value) == str(current.value)


def test_projected_refusal_before_clone_interpolate_outer_or_rotary_allocations(monkeypatch):
    fn = candidate()
    def forbidden(*a,**kw): raise AssertionError("No allocation before quota refusal")
    monkeypatch.setattr(torch.Tensor,"clone",forbidden)
    with pytest.raises(ValueError,match="projected"):
        fn.prepare_mocha_inputs(torch.tensor(1.).expand(30,200,200,3),torch.zeros(1,2,3,3),torch.float32)
    monkeypatch.setattr(torch.nn.functional,"interpolate",forbidden)
    with pytest.raises(ValueError,match="projected"):
        fn.assemble_mocha_embeds(torch.zeros(1,16,1,1,1),torch.zeros(1,16,1,1,1),
            torch.tensor(1.).expand(1,1024,1024),num_frames=1,height=8192,width=8192,
            upsampling_factor=8,dtype=torch.float32)
    monkeypatch.setattr(torch,"outer",forbidden)
    with pytest.raises(ValueError,match="projected"):
        fn.rope_params_mocha(100000,1024)
    with pytest.raises(ValueError,match="projected"):
        fn.rope_params_mocha(0,100000000)
    with pytest.raises(ValueError,match="projected"):
        fn.rope_params_mocha(100000.,1024.)
    with pytest.raises(ValueError,match="finite"):
        fn.rope_params_mocha(float("inf"),12)
    with pytest.raises(ValueError,match="CPU"):
        fn.rope_apply_mocha(torch.empty(1,2,2,12,device="meta"),torch.tensor([[2,1,1]]),torch.ones(4,6))
    with pytest.raises(ValueError,match="grid"):
        fn.rope_apply_mocha(torch.zeros(1,2,2,12),torch.tensor([[1000001,1,1]]),torch.ones(4,6))


def scratch_probe(tmp_path, name):
    root = tmp_path/name
    root.mkdir()
    for filename in ("secure_mocha_algorithms.py","secure_tensor_nodes.py"):
        shutil.copyfile(V2/filename,root/filename)
    shutil.copyfile(V2/"tests/mocha_guest_probe.py",root/"__init__.py")
    package = "_jack_mocha_probe_"+name
    spec = importlib.util.spec_from_file_location(package,root/"__init__.py",submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[package] = module
    spec.loader.exec_module(module)
    return root,module.NODE_CLASS_MAPPINGS["JackWanMochaMathProbe"]


def test_actual_outer_math_two_fresh_raw_guests_and_denial(tmp_path,monkeypatch):
    monkeypatch.setenv("COMFY_SECURE_SANDBOX_MODE","required")
    monkeypatch.syspath_prepend(CORE)
    import execution
    async def run():
        previous = _sdk.providers.execution_backend
        pids = []
        try:
            for index in range(2):
                root,cls = scratch_probe(tmp_path,"original" if index==0 else "fresh")
                session = await GuestSession("wan-mocha-math",guest_runtime_root=root).start()
                assert session.sandbox_kind == "seatbelt"
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs = await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                        return await session.execute(plan,runtime,capabilities=("raw",),tenant="mocha-"+str(index))
                _sdk.providers.register_execution_backend(Backend())
                try:
                    fn = candidate()
                    for dtype in (torch.float32,torch.bfloat16):
                        inputs = fields(9,dtype,True)
                        prepared = fn.prepare_mocha_inputs(inputs["input_video"],inputs["ref1"],dtype,inputs["ref2"])
                        recorder = RecordingVAE(dtype)
                        encoded = [recorder.encode(prepared[key],"cpu",tiled=True) for key in ("input_video","ref1","ref2")]
                        cases = [
                            ("prepare",dict(input_video=inputs["input_video"],ref1=inputs["ref1"],ref2=inputs["ref2"],dtype_marker=torch.zeros(1,1,dtype=dtype)),prepared),
                            ("assemble",dict(latents=encoded[0],ref_latents=encoded[1],ref2_latents=encoded[2],mask=inputs["mask"],
                                num_frames=prepared["num_frames"],height=19,width=27,upsampling_factor=8,dtype_marker=torch.zeros(1,1,dtype=dtype)),
                                source().MochaEmbeds().process(RecordingVAE(dtype),**copy.deepcopy(inputs))[0])]
                        for mode,payload,expected in cases:
                            fields_,missing,meta = execution.get_input_data(dict(payload=payload,mode=mode),cls,"stage",None)
                            assert not missing
                            result = await execution._async_map_node_over_list(prompt_id="mocha-math",unique_id="stage",
                                obj=cls,input_data_all=fields_,func="execute",v3_data=meta)
                            equal(expected,result[0].result[0])
                            refs = _sdk.InProcessRefResolver()
                            plan = _sdk.ExecutionPlan("raw-denied","stage","JackWanMochaMathProbe",node_module=cls.__module__,
                                input_mode="values",input_types={"payload":"JACK_MOCHA_STAGE"},
                                inputs=await _sdk.wrap_inputs(refs,dict(payload=payload,mode=mode)),
                                permissions=("raw",),tier="sandbox")
                            runtime = _sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
                            with pytest.raises(Exception,match="raw"):
                                await session.execute(plan,runtime,capabilities=(),tenant="mocha-"+str(index))
                    pids.append(session.pid)
                finally:
                    await session.kill()
            assert len(set(pids))==2 and os.getpid() not in pids
        finally:
            _sdk.providers.register_execution_backend(previous)
    asyncio.run(run())
