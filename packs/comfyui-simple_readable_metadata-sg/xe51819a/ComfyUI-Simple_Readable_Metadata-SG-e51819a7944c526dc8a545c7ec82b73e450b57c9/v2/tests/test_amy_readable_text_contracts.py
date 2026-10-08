"""Native source call/schema controls; filesystem activity is test-only."""
import ast
import asyncio
from datetime import datetime
import json
import os
import re
from types import SimpleNamespace
import pytest
from test_amy_readable_conversion import PACK, V2, NODES, EXPECTED
from test_amy_readable_input_bounds import LOADER
import sys

TEXT = sys.modules[NODES[EXPECTED[3]].__module__]
FILENAME = sys.modules[TEXT.parse_filename.__module__]

def native_save(root):
    path=V2.parent/"Simple_Readable_Metadata_Save_Text_SG.py"
    cls=next(x for x in ast.parse(path.read_bytes()).body if isinstance(x,ast.ClassDef))
    ns={"os":os,"json":json,"re":re,"datetime":datetime,
        "folder_paths":SimpleNamespace(get_output_directory=lambda:str(root))}
    exec(compile(ast.Module(body=[cls],type_ignores=[]),str(path),"exec"),ns)
    return ns[cls.name]()

@pytest.mark.parametrize("prefix", ["%date%","%time%","%date:yyyy-MM-dd_HH-mm-ss%", "%time:hh-mm-ss%",
    "nested/name_%date:yyMMdd%","plain","x_%unknown%"])
def test_native_date_token_math_on_exact_fixture_clock(tmp_path,monkeypatch,prefix):
    source=native_save(tmp_path)
    class Clock:
        @staticmethod
        def now():return datetime(2026,10,8,11,12,13)
    source.parse_filename.__func__.__globals__["datetime"]=Clock
    monkeypatch.setattr(FILENAME,"datetime",Clock)
    assert FILENAME.parse_filename(prefix)==source.parse_filename(prefix)

@pytest.mark.parametrize("extension,text,pretty",[("txt","",True),("txt","☀\nline",True),
    ("json",'{"☀":[1,2]}',True),("json","invalid JSON",True),("json",'{"n":1}',False),
    ("md","# ☀",True)])
def test_native_save_first_free_order_bytes_and_ui(tmp_path,monkeypatch,extension,text,pretty):
    native=tmp_path/"native";native.mkdir();managed=tmp_path/"managed";managed.mkdir()
    (native/f"note_00001.{extension}").write_text("kept")
    (managed/f"note_00001.{extension}").write_text("kept")
    expected=native_save(native).save_text(text,"note",extension,pretty)
    class Assets:
        async def exists(self,folder,name):return (managed/name).exists()
    class Output:
        async def write_text(self,content,name,folder,mode):
            assert folder=="output" and mode=="new_only"
            with (managed/name).open("x",encoding="utf-8") as stream:stream.write(content)
    monkeypatch.setattr(TEXT.sdk,"ctx",lambda:SimpleNamespace(assets=Assets(),output=Output()))
    actual=asyncio.run(NODES[EXPECTED[3]].execute(text,"note",extension,pretty))
    assert actual.ui==expected["ui"]
    assert (native/f"note_00002.{extension}").read_bytes()==(managed/f"note_00002.{extension}").read_bytes()
    assert (managed/f"note_00001.{extension}").read_text()=="kept"

def test_native_broad_write_failure_versus_explicit_managed_refusal(tmp_path,monkeypatch):
    source=native_save(tmp_path)
    source.save_text.__func__.__globals__["open"]=lambda *a,**k: (_ for _ in ()).throw(OSError("native failure"))
    assert source.save_text("text","native","txt",True)=={"ui":{"text_files":[]}}
    class Assets:
        async def exists(self,*args):return False
    class Output:
        async def write_text(self,*args,**kwargs):raise PermissionError("managed output denied")
    monkeypatch.setattr(TEXT.sdk,"ctx",lambda:SimpleNamespace(assets=Assets(),output=Output()))
    with pytest.raises(PermissionError,match="managed output denied"):
        asyncio.run(NODES[EXPECTED[3]].execute("text","native","txt",True))

@pytest.mark.parametrize("prefix",["/absolute","../escape","a/../b","a\\b","a\x00b"])
def test_logical_output_refusal_before_any_broker(prefix,monkeypatch):
    monkeypatch.setattr(TEXT.sdk,"ctx",lambda: (_ for _ in ()).throw(AssertionError("no side effect")))
    with pytest.raises(ValueError):asyncio.run(NODES[EXPECTED[3]].execute("text",prefix,"txt",True))

def test_all_declared_schema_defaults_options_types_names_and_categories(tmp_path):
    import comfy.samplers
    ns={"os":os,"folder_paths":SimpleNamespace(get_input_directory=lambda:str(tmp_path)),
        "comfy":SimpleNamespace(samplers=comfy.samplers)}
    files=["Simple_Readable_Metadata_MAX_SG.py","Simple_Readable_Metadata_SG.py",
        "Simple_Readable_Metadata_Text_Viewer_SG.py","Simple_Readable_Metadata_Save_Text_SG.py",
        "Simple_Readable_Metadata_VIDEO_SG.py","Simple_Readable_Metadata_Save_Prompt_SG.py"]
    native={}
    for file in files:
        for cls in [n for n in ast.parse((V2.parent/file).read_bytes()).body if isinstance(n,ast.ClassDef)]:
            cls.body=[n for n in cls.body if isinstance(n,ast.Assign) or isinstance(n,ast.FunctionDef) and n.name=="INPUT_TYPES"]
            exec(compile(ast.Module(body=[cls],type_ignores=[]),str(V2.parent/file),"exec"),ns)
            native[cls.name]=ns[cls.name]
    for name,cls in NODES.items():
        old=native[cls.__name__];schema=cls.GET_SCHEMA();inputs=cls.INPUT_TYPES()
        required=old.INPUT_TYPES()["required"]
        assert list(inputs["required"])==list(required)
        for key,value in required.items():
            if key in ("image","video"):continue # Explicit managed portable all-file catalogue.
            actual=inputs["required"][key]
            if isinstance(value[0],list):
                assert actual[0]=="COMBO" and actual[1]["options"]==value[0]
                assert actual[1]["multiselect"] is False
            else:assert actual[0]==value[0]
            for option,expected in (value[1] if len(value)>1 else {}).items():
                assert actual[1][option]==expected
        if "hidden" in old.INPUT_TYPES():
            assert {key:value[0] for key,value in inputs["hidden"].items()}==old.INPUT_TYPES()["hidden"]
        assert schema.category==old.CATEGORY and schema.is_output_node==old.OUTPUT_NODE
        for index,out in enumerate(schema.outputs):
            expected=old.RETURN_TYPES[index]
            assert (out.options if isinstance(expected,list) else out.get_io_type())==expected
            assert out.id==old.RETURN_NAMES[index]

def test_sampler_names_drift_refused_before_input_read(monkeypatch):
    class Models:
        async def sampling_names(self):return {"samplers":LOADER.SAMPLERS[::-1],"schedulers":LOADER.SCHEDULERS}
    monkeypatch.setattr(LOADER.sdk,"ctx",lambda:SimpleNamespace(models=Models()))
    with pytest.raises(ValueError,match="sampling names drifted"):
        asyncio.run(NODES[EXPECTED[0]].execute("no_read.png"))
