"""Whole seven-node conversion gates. No sealed/Linux/Cloud claim."""
import asyncio
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import numpy as np
import pytest
import torch
from PIL import Image, PngImagePlugin

sys.dont_write_bytecode = True
CORE = Path(os.environ["COMFY_CORE_ROOT"])
BACK = Path("/Users/ben/comfy/ComfyUI_secure_nodes/backend")
sys.path[:0] = [str(CORE), str(BACK)]
from comfy.cli_args import args
args.cpu = True
import execution
import folder_paths
from comfy_api.latest import _sdk, io
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes import packmanifest, packruntime, packdb, webassets
V2 = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("amy_readable_converted", V2 / "__init__.py",
    submodule_search_locations=[str(V2)])
PACK = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = PACK
spec.loader.exec_module(PACK)
NODES = PACK.NODE_CLASS_MAPPINGS
for node in NODES.values():
    node.GET_SCHEMA()
EXPECTED = ["SimpleReadableMetadataMAXSG", "SimpleReadableMetadataSG",
    "Simple Readable Metadata Text Viewer-SG", "SimpleReadableMetadataSaveTextSG",
    "SimpleReadableMetadataVideoSG", "SavePositivePromptSG", "SaveNegativePromptSG"]
OUT = Path("/Users/ben/popbot/raw-chats/outputs")
TAGS = json.loads((OUT / "amy-oct8-readable-tags-tag-1.json").read_bytes())["rows"]
SELECTED = [CORE / "comfy_api/latest/_sdk.py", CORE / "execution.py",
    BACK / "comfy_secure_nodes/transport/host.py", BACK / "comfy_secure_nodes/guest/__init__.py",
    BACK / "comfy_secure_nodes/webassets.py"]


def hashes():
    return [{"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in SELECTED]


def manifest():
    nodes = {}
    for name, cls in sorted(NODES.items()):
        nodes[name] = {"module": cls.__module__.split(".")[-1], "class": cls.__name__,
            "sdk_refs": getattr(cls, "SDK_REFS", False), "permissions": list(cls.SDK_PERMISSIONS),
            "methods": {key: key in cls.__dict__ for key in (
                "validate_inputs", "fingerprint_inputs", "check_lazy_status")},
            "schema": packmanifest.encode_schema(copy.deepcopy(cls.GET_SCHEMA()))}
    return {"format": packmanifest.FORMAT, "runtime": packruntime.manifest_declaration(V2),
        "nodes": nodes, "web_directory": "web",
        "frontend_permissions": ["clipboard.read", "clipboard.write"]}


def equal(left, right):
    if isinstance(left, torch.Tensor):
        assert type(right) is torch.Tensor and left.dtype == right.dtype and left.shape == right.shape
        assert torch.equal(left, right)
    elif isinstance(left, (tuple, list)):
        assert type(left) is type(right) and len(left) == len(right)
        for a, b in zip(left, right):
            equal(a, b)
    elif isinstance(left, dict):
        assert type(left) is type(right) and list(left) == list(right)
        for key in left:
            equal(left[key], right[key])
    else:
        assert type(left) is type(right) and left == right


def fixture(directory):
    metadata = json.dumps({
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "local.safetensors"}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "sunrise, ☀"}},
        "3": {"class_type": "KSampler", "inputs": {"seed": 42, "steps": 20, "cfg": 7.5,
            "sampler_name": "euler", "scheduler": "normal", "positive": ["2", 0]}}})
    image = Image.fromarray(np.arange(96, dtype=np.uint8).reshape(4, 6, 4), "RGBA")
    info = PngImagePlugin.PngInfo()
    info.add_text("prompt", metadata)
    image.save(directory / "pixels.png", pnginfo=info)
    video = next(row for row in TAGS if row["logical"] == "rational.mp4")
    shutil.copyfile(video["fixture"]["path"], directory / "rational.mp4")
    (directory / "not-media.txt").write_text("not a media decoder input")


def test_complete_census_declared_shapes_and_managed_all_file_schema():
    assert list(NODES) == EXPECTED
    assert PACK.WEB_DIRECTORY == "./web"
    assert [len(cls.GET_SCHEMA().outputs) for cls in NODES.values()] == [17,8,1,0,10,1,1]
    for name, cls in NODES.items():
        schema = cls.GET_SCHEMA()
        schema.validate()
        assert schema.node_id == name and schema.display_name == PACK.NODE_DISPLAY_NAME_MAPPINGS[name]
        assert schema.is_output_node
    for name in EXPECTED[:2] + [EXPECTED[4]]:
        field = NODES[name].GET_SCHEMA().inputs[0].as_dict()
        assert field["remote"]["route"] == "/secure-nodes/assets/input?kind=file"
        assert field["options"] == [] and field["remote"]["initial_selection"] == "first"
        assert NODES[name].SDK_PERMISSIONS == (("assets", "raw", "models") if name == EXPECTED[0] else ("assets", "raw"))
    source = ast.parse((V2.parent / "__init__.py").read_bytes())
    literal = next(node.value for node in source.body if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "NODE_DISPLAY_NAME_MAPPINGS" for target in node.targets))
    assert PACK.NODE_DISPLAY_NAME_MAPPINGS == ast.literal_eval(literal)
    assert len(list((V2 / "web").glob("*.js"))) == 5
    assert manifest()["web_directory"] == "web"


@pytest.mark.parametrize("name", EXPECTED)
def test_each_input_and_output_schema_validates(name):
    encoded = packmanifest.encode_schema(copy.deepcopy(NODES[name].GET_SCHEMA()))
    assert encoded and manifest()["nodes"][name]["schema"] == encoded


def test_two_fresh_required_guests_all_seven_values_side_effects_denials(tmp_path, monkeypatch):
    before = hashes()
    input_root = tmp_path / "input"
    output_root = tmp_path / "output"
    input_root.mkdir()
    output_root.mkdir()
    fixture(input_root)
    for label,maximum in (("oversize.png",8*1024*1024),("oversize.mp4",512*1024)):
        with (input_root/label).open("wb") as stream:stream.truncate(maximum+1)
    monkeypatch.setattr(folder_paths, "get_input_directory", lambda: str(input_root))
    monkeypatch.setattr(folder_paths, "get_output_directory", lambda: str(output_root))
    monkeypatch.setenv("COMFY_SECURE_SANDBOX_MODE", "required")

    async def run():
        pids = []
        for render in range(2):
            session = await GuestSession("amy-readable-seven-" + str(render),
                guest_runtime_root=V2.parent).start()
            refs = _sdk.InProcessRefResolver()
            rows = []
            async def call(name, inputs, caps=None, prompt=None, extra=None, node_id="7", method="execute"):
                cls = NODES[name]
                plan = _sdk.ExecutionPlan(prompt_id="amy-readable-seven", node_id=node_id,
                    node_type=cls.__name__, node_module=cls.__module__, method=method,
                    input_mode="values",
                    inputs=inputs, text_inputs={k:v for k,v in inputs.items() if k=="text"},
                    prompt=prompt, extra_pnginfo=extra)
                runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps())
                result = await session.execute(plan, runtime, capabilities=cls.SDK_PERMISSIONS if caps is None else caps,
                    tenant="amy-readable-bounded-local")
                resolved = []
                for item in result.result or ():
                    resolved.append(await refs.resolve(item) if isinstance(item, _sdk.Ref) else item)
                return tuple(resolved), result.ui
            try:
                assert session.sandbox_kind == "seatbelt"
                for name, show in ((EXPECTED[1],"both"), (EXPECTED[0],"on")):
                    helper_mod = sys.modules[NODES[name].__module__]
                    helper = helper_mod.ImageAlgorithms() if name == EXPECTED[1] else helper_mod.MaxAlgorithms()
                    helper.input_label, helper.source_bytes = "pixels.png", (input_root / "pixels.png").read_bytes()
                    helper.sampler_names, helper.scheduler_names = helper_mod.SAMPLERS, helper_mod.SCHEDULERS
                    expected = helper.load_analyze_extract("pixels.png", show_info=show, emoji_in_readable_text=True)
                    actual, ui = await call(name, {"image":"pixels.png","show_info":show,"emoji_in_readable_text":True})
                    equal(expected["result"], actual)
                    equal(expected["ui"], ui)
                    assert actual[1].dtype == torch.float32 and actual[2].dtype == torch.float32
                    for caps in ((),("assets",),("raw",)):
                        with pytest.raises(Exception, match="capability|raw|assets|permission|granted"):
                            await call(name, {"image":"pixels.png","show_info":show,"emoji_in_readable_text":True},caps)
                    with pytest.raises(Exception, match="image|identify|decode"):
                        await call(name, {"image":"not-media.txt","show_info":show,"emoji_in_readable_text":True})
                    recovery,_ = await call(name, {"image":"pixels.png","show_info":show,"emoji_in_readable_text":False})
                    assert recovery[1].shape == actual[1].shape
                text = "literal <script>, ☀\nsecond line"
                assert await call(EXPECTED[2], {"text":text}, ()) == ((text,), {"text":[text]})
                with pytest.raises(Exception,match="UTF-8 text|bound|workload"):
                    await call(EXPECTED[2],{"text":"x"*65537},())
                assert await call(EXPECTED[2],{"text":text},())==((text,),{"text":[text]})
                for name,label,input_name in ((EXPECTED[1],"oversize.png","image"),
                    (EXPECTED[0],"oversize.png","image"),(EXPECTED[4],"oversize.mp4","video")):
                    with pytest.raises(Exception,match="encoded managed-input workload"):
                        await call(name,{input_name:label})
                for name, side in ((EXPECTED[5],"Positive"),(EXPECTED[6],"Negative")):
                    prompt = {"7":{"class_type":name,"inputs":{"text":["upstream",0]},"_meta":{"title":"original"}},
                        "8":{"class_type":"Other","inputs":{"text":"PRIVATE_OTHER_TEXT"}}}
                    extra = {"ordinary":"kept"}
                    unchanged = copy.deepcopy((prompt, extra))
                    with pytest.raises(Exception, match="output|permission|capability"):
                        await call(name,{"text":text},(),prompt,extra)
                    assert (prompt, extra) == unchanged
                    assert await call(name,{"text":text},prompt=prompt,extra=extra) == ((text,),{"text":[text]})
                    assert prompt["7"]["inputs"]["text"] == text
                    assert prompt["7"]["_meta"]["title"] == side+" Prompt (Saved)"
                    assert prompt["8"] == unchanged[0]["8"]
                    assert extra == {"ordinary":"kept",side+"Prompt_7":text}
                save = EXPECTED[3]
                for extension, content, pretty in (("txt",text,True),("json",'{"text":"☀","n":1}',True),("md",text,False)):
                    prefix = f"r{render}/{extension}"
                    result, ui = await call(save, dict(text=content, filename_prefix=prefix, file_format=extension, pretty_json=pretty))
                    assert result == ()
                    expected_text = json.dumps(json.loads(content), indent=2, ensure_ascii=False) if extension=="json" else content
                    assert (output_root / (prefix+"_00001."+extension)).read_text() == expected_text
                    assert ui == {"text_files":[{"filename":extension+"_00001."+extension,
                        "subfolder":f"r{render}","type":"output"}]}
                with pytest.raises(Exception,match="output|capability|permission"):
                    await call(save, dict(text=text,filename_prefix="denied",file_format="txt",pretty_json=True),("assets",))
                actual, ui = await call(EXPECTED[4], dict(video="rational.mp4",force_rate=12,max_frames=3,
                    resize_long_edge=64,emoji_in_readable_text=False))
                expected = sys.modules[NODES[EXPECTED[4]].__module__].analyze_video(
                    (input_root/"rational.mp4").read_bytes(),"rational.mp4",12,3,64,False)
                equal(expected["result"],actual)
                equal(expected["ui"],ui)
                for caps in ((),("assets",),("raw",)):
                    with pytest.raises(Exception,match="raw|assets|capability|permission|granted"):
                        await call(EXPECTED[4],dict(video="rational.mp4",force_rate=0,max_frames=1,resize_long_edge=0,
                            emoji_in_readable_text=True),caps)
                with pytest.raises(Exception,match="open video"):
                    await call(EXPECTED[4],dict(video="not-media.txt",force_rate=0,max_frames=1,resize_long_edge=0,
                        emoji_in_readable_text=True))
                recovered,_=await call(EXPECTED[4],dict(video="rational.mp4",force_rate=0,max_frames=1,resize_long_edge=0,
                    emoji_in_readable_text=True))
                assert recovered[3] == 1
                pids.append(session.last_guest_pid)
                assert session.last_guest_pid != os.getpid()
                print("READABLE_ACTUAL_SEVEN_REQUIRED",session.last_guest_pid,"seven actual entrypoints; denial and recovery")
            finally:
                await session.kill()
        assert len(set(pids)) == 2
    asyncio.run(run())
    assert hashes() == before, "shared sources changed during selected gate"


def test_production_outer_all_seven_types_hidden_owner_and_saved_png(tmp_path, monkeypatch):
    from comfy_execution.graph import DynamicPrompt
    from test_text_input_annotation import runtime_for
    from fixtures import text_annotation_probe_pack as png_probe
    input_root = tmp_path / "input"
    output_root = tmp_path / "output"
    input_root.mkdir()
    output_root.mkdir()
    fixture(input_root)
    monkeypatch.setattr(folder_paths,"get_input_directory",lambda:str(input_root))
    monkeypatch.setattr(folder_paths,"get_output_directory",lambda:str(output_root))
    monkeypatch.setattr(args,"disable_metadata",False)
    monkeypatch.setenv("COMFY_SECURE_SANDBOX_MODE","required")
    text = "sunrise, ☀"
    prompt = {"7":{"class_type":EXPECTED[5],"inputs":{"text":["1",0]},"_meta":{"title":"old"}},
        "8":{"class_type":EXPECTED[6],"inputs":{"text":["1",0]},"_meta":{"title":"old"}},
        "9":{"class_type":"foreign","inputs":{"text":"PRIVATE"}}}
    extra = {"workflow":{"nodes":[{"id":7,"title":"old"}]},"ordinary":"retained"}
    async def run():
        session=await GuestSession("amy-readable-production-seam",guest_runtime_root=V2.parent).start()
        seen=[]
        class Backend:
            async def dispatch(self,plan,local_call,runtime):
                seen.append((plan.node_type,plan.input_mode,dict(plan.text_inputs)))
                assert plan.input_mode=="values"
                return await session.execute(plan,runtime,capabilities=plan.permissions,
                    tenant="amy-readable-local-outer")
        monkeypatch.setattr(_sdk.providers,"execution_backend",Backend())
        try:
            for name,inputs,node_id in [
                (EXPECTED[1],dict(image="pixels.png",emoji_in_readable_text=True,show_info="both"),"1"),
                (EXPECTED[0],dict(image="pixels.png",show_info="on",emoji_in_readable_text=False),"2"),
                (EXPECTED[2],dict(text=text),"3"),
                (EXPECTED[3],dict(text=text,filename_prefix="outer",file_format="txt",pretty_json=True),"4"),
                (EXPECTED[4],dict(video="rational.mp4",force_rate=0,max_frames=1,resize_long_edge=0,
                    emoji_in_readable_text=False),"5"),
                (EXPECTED[5],dict(text=text),"7"),
                (EXPECTED[6],dict(text="blurry"),"8"),
            ]:
                cls=NODES[name]
                data,missing,v3_data=execution.get_input_data(inputs,cls,node_id,
                    dynprompt=DynamicPrompt(prompt),extra_data={"extra_pnginfo":extra})
                assert not missing
                output=await execution._async_map_node_over_list(
                    prompt_id="amy-outer",unique_id=node_id,obj=cls,input_data_all=data,
                    func="execute",v3_data=v3_data)
                result=output[0].result or ()
                assert len(result)==len(cls.GET_SCHEMA().outputs)
                if name in (EXPECTED[0],EXPECTED[1]):
                    assert type(result[1]) is torch.Tensor and type(result[2]) is torch.Tensor
                    assert result[1].shape==(1,4,6,3) and result[2].shape==(4,6)
                    assert type(result[6 if name==EXPECTED[1] else 11]) is int
                    if name==EXPECTED[0]:
                        for idx in (5,6,7,13):assert type(result[idx]) is float
                elif name==EXPECTED[4]:
                    assert type(result[1]) is torch.Tensor and type(result[2]) is torch.Tensor
                    assert type(result[3]) is type(result[4]) is type(result[9]) is int
                elif name!=EXPECTED[3]:
                    assert type(result[0]) is str
            assert len(seen)==7
            assert prompt["7"]["inputs"]["text"]==text and prompt["8"]["inputs"]["text"]=="blurry"
            assert prompt["7"]["_meta"]["title"]=="Positive Prompt (Saved)"
            assert prompt["8"]["_meta"]["title"]=="Negative Prompt (Saved)"
            assert prompt["9"]=={"class_type":"foreign","inputs":{"text":"PRIVATE"}}
            assert extra["PositivePrompt_7"]==text and extra["NegativePrompt_8"]=="blurry"
            image=torch.linspace(0,1,18).reshape(1,2,3,3)
            refs=_sdk.InProcessRefResolver()
            ref=_sdk.ImageRef._wrap(await refs.create("IMAGE",image))
            plan=_sdk.ExecutionPlan(prompt_id="amy-outer",node_id="10",node_type="SaveRecordedImage",
                node_module=png_probe.__name__,inputs={"image":ref,"filename":"annotated.png"},
                prompt=prompt,extra_pnginfo=extra)
            runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
            # Test-only downstream canonical saver node, not an eighth pack node.
            await session.execute(plan,runtime,capabilities=("output",))
            with Image.open(output_root/"annotated.png") as saved:
                assert json.loads(saved.info["prompt"])==prompt
                for key,value in extra.items():assert json.loads(saved.info[key])==value
                assert np.array_equal(np.asarray(saved), (image[0].numpy()*255).astype(np.uint8))
            print("READABLE_REAL_OUTER_SEVEN_AND_DOWNSTREAM_PNG",session.last_guest_pid)
        finally:
            await session.kill()
    asyncio.run(run())


def test_three_loader_live_all_files_proxy_and_stale_queue_admission(tmp_path, monkeypatch):
    from test_remote_catalogue_admission import _validator
    root=tmp_path/"input"
    root.mkdir()
    monkeypatch.setattr(folder_paths,"get_input_directory",lambda:str(root))
    for name in ("z.txt","a.png","middle.mp4",".hidden","no-extension"):
        (root/name).write_bytes(b"native decoder decides format")
    (root/"nested").mkdir()
    (root/"nested/deep.png").write_bytes(b"not an immediate choice")
    expected=sorted(n for n in os.listdir(root) if (root/n).is_file())
    proxies={}
    for name in (EXPECTED[0],EXPECTED[1],EXPECTED[4]):
        cls=NODES[name]
        record=manifest()["nodes"][name]
        proxy=packdb._proxy_class("custom_nodes.amy_readable",V2/"loader_nodes.py",record)
        proxies[name]=proxy
        field="video" if name==EXPECTED[4] else "image"
        assert proxy.INPUT_TYPES()["required"][field][1]["options"]==expected
    validate=_validator(proxies)
    for name in proxies:
        inputs={item.id:item.default for item in NODES[name].GET_SCHEMA().inputs}
        if name==EXPECTED[0]:inputs["show_info"]="on"
        field="video" if name==EXPECTED[4] else "image"
        for choice in expected:
            inputs[field]=choice
            assert asyncio.run(validate(name,inputs))[0]
        inputs[field]="nested/deep.png"
        assert not asyncio.run(validate(name,inputs))[0]
    (root/"z.txt").unlink()
    assert webassets.remote_catalogue_options("/secure-nodes/assets/input?kind=file")==[n for n in expected if n!="z.txt"]
