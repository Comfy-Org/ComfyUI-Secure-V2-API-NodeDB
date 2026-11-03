"""Finite image differential: source pixels, dtype, UI data and broker previews."""
import asyncio
import copy
import importlib
import io as stdlib_io
import json
from pathlib import Path
import signal
import sys
import tempfile
import traceback

sys.path.insert(0, "/tests")
import run_round1 as base
import numpy as np
from PIL import Image
from comfy_api.latest import _sdk as sdk
import folder_paths

CASES = json.loads(Path("/tests/image-cases.json").read_text())
RECEIPT = {"status": "RUNNING", "evidence": "gate, B13 sources 38f28c98",
    "scheduled_cases": len(CASES), "execution": "in-process SDK differential",
    "nodes": {}, "failures": [], "known_preview_boundary": "broker names and host-owned metadata; decoded pixels compared exactly"}


def fixture(value):
    if isinstance(value, list): return [fixture(v) for v in value]
    if not isinstance(value, dict): return value
    kind = value.get("__fixture__")
    if kind == "pattern":
        b, h, w, c = value["batch"], value["height"], value["width"], value["channels"]
        grid = np.indices((b, h, w, c))
        arr = ((grid[0]*47 + grid[1]*13 + grid[2]*7 + grid[3]*71) % 257) / 256
        return base.torch.tensor(arr, dtype=getattr(base.torch, value["dtype"]))
    if kind == "mask":
        b, h, w = value["batch"], value["height"], value["width"]
        yy, xx = np.indices((h,w))
        mask = ((xx-w/2)**2/(w/3)**2 + (yy-h/2)**2/(h/3)**2 < 1).astype(np.float32)
        return base.torch.from_numpy(np.tile(mask,(b,1,1)))
    if kind == "crop-info":
        return {"image": fixture({"__fixture__":"pattern", "channels":3,"batch":1,"dtype":"float32","height":31,"width":47}),
            "mask": fixture({"__fixture__":"mask","batch":1,"height":31,"width":47}),
            "x":7,"y":5,"w":16,"h":12,"blend":value["softness"],"blend_mode":value["mode"]}
    return {key: fixture(item) for key, item in value.items()}


def normalize_ui(value, previews):
    if isinstance(value,list): return [normalize_ui(item,previews) for item in value]
    if not isinstance(value,dict): return value
    output={}
    if value.get("filename") and value.get("type") in ("temp","output"):
        root=folder_paths.get_temp_directory() if value["type"]=="temp" else folder_paths.get_output_directory()
        path=Path(root)/value.get("subfolder","")/value["filename"]
        with Image.open(path) as image:
            previews.append((image.mode, np.array(image),dict(image.info)))
    for key,item in value.items():
        if key in ("filename","subfolder") and "type" in value: output[key]="<brokered-name>"
        else: output[key]=normalize_ui(item,previews)
    return output


async def compare(case,new):
    node=case["node"];fields=fixture(case["fields"])
    source=getattr(importlib.import_module("pixaroma_recovery_original."+base.ROWS[node]["module"]),node)
    original=getattr(source(),base.ROWS[node]["function"])(**fields)
    source_ui=original.get("ui") if isinstance(original,dict) else None
    source_values=original.get("result",()) if isinstance(original,dict) else original
    old_previews=[];expected_ui=normalize_ui(source_ui,old_previews)
    hidden=dict(base.ROWS[node]["input_types"].get("hidden",{}))
    hidden.update({"CropWidget":None} if node=="PixaromaCrop" else {})
    hidden.update({"InpaintCropWidget":None} if node=="PixaromaInpaintCrop" else {})
    arguments={key:value for key,value in fields.items() if key not in hidden}
    cls=new.NODE_CLASS_MAPPINGS[node]
    async def execute():
        wrapped=await sdk.wrap_inputs(sdk.current_runtime().refs,arguments)
        if case.get("refused_match"):
            try: await cls.execute(**wrapped)
            except RuntimeError as error:
                assert case["refused_match"] in str(error),str(error)
                return "REFUSED-AS-DESIGNED"
            raise AssertionError("expected named dependency refusal")
        output=await cls.execute(**wrapped)
        base.equivalent(await base.read_output(output.args),source_values)
        previews=[];actual_ui=normalize_ui(output.ui,previews)
        base.equivalent(actual_ui,expected_ui,"ui")
        assert len(previews)==len(old_previews)
        for (am,aa,ai),(em,ea,ei) in zip(previews,old_previews):
            assert am==em
            assert aa.dtype==ea.dtype and aa.shape==ea.shape
            assert np.array_equal(aa,ea)
        return "PIXELS-AND-VALUES-EXACT-UI-BOUNDARY" if case.get("ui_boundary") else "EXACT"
    return await base.in_runtime(base.plan_for(node,fields),execute)


async def main():
    base.namespace("pixaroma_recovery_original",base.PACK)
    base.namespace("pixaroma_recovery_original.nodes",base.PACK/"nodes")
    with tempfile.TemporaryDirectory(prefix="pixaroma-image-fixtures-") as tmp:
        for name in ("input","output","temp"):
            path=Path(tmp)/name;path.mkdir()
            getattr(folder_paths,"set_"+name+"_directory")(str(path))
        guard=base.GuestImports();sys.meta_path.insert(0,guard)
        import builtins
        real_import=builtins.__import__
        def guarded(name,globals=None,locals=None,fromlist=(),level=0):
            if level==0:guard.check(name,(globals or {}).get("__file__"))
            return real_import(name,globals,locals,fromlist,level)
        builtins.__import__=guarded
        try:
            new=base.load_v2()
            RECEIPT["schemas"]=base.encode_and_check(new)
            for index,case in enumerate(CASES):
                row=RECEIPT["nodes"].setdefault(case["node"],{})
                try:
                    verdict=await compare(case,new)
                    row[verdict]=row.get(verdict,0)+1
                except Exception as error:
                    row["MISMATCH"]=row.get("MISMATCH",0)+1
                    RECEIPT["failures"].append({"index":index,"node":case["node"],"label":case["label"],"type":type(error).__name__,"message":str(error),"traceback":traceback.format_exc()})
                    if len(RECEIPT["failures"])>=12:break
            RECEIPT["status"]="PASS" if not RECEIPT["failures"] else "FAIL"
        finally:
            builtins.__import__=real_import;sys.meta_path.remove(guard)


if __name__ == "__main__":
    try:asyncio.run(main())
    except BaseException as error:
        RECEIPT["status"]="FAIL";RECEIPT["failures"].append({"type":type(error).__name__,"message":str(error),"traceback":traceback.format_exc()})
    finally:
        signal.alarm(0)
        Path("/results/image-receipt.json").write_text(json.dumps(RECEIPT,indent=2,sort_keys=True)+"\n")
        print(json.dumps(RECEIPT,indent=2),flush=True)
    if RECEIPT["status"]!="PASS":raise SystemExit(1)
