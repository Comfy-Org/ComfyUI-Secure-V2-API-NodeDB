"""Real public SDK providers only; no overlay imports or fake model objects."""
import contextlib
import importlib
import os
from pathlib import Path
import sys
import types
from comfy_api.latest import io,sdk,_sdk
import torch
V2=Path(__file__).resolve().parents[1]
PACK=V2.parent
def namespace(name,path):
    if name not in sys.modules:
        m=types.ModuleType(name);m.__path__=[str(path)];m.__package__=name;sys.modules[name]=m
namespace('comfyroll_r10',V2)
namespace('comfyroll_v1_r10',PACK)
namespace('comfyroll_v1_r10.nodes',PACK/'nodes')
def module(name):return importlib.import_module('comfyroll_r10.'+name)
@contextlib.contextmanager
def runtime(node='R10Policy',permissions=(),prompt=None,extra=None):
    refs=_sdk.InProcessRefResolver()
    plan=sdk.ExecutionPlan(prompt_id='public-r10',node_id='1',node_type=node,prompt=prompt or {},extra_pnginfo=extra or {},permissions=permissions)
    context=_sdk.InProcessCtxProvider().build(plan)
    with _sdk.bind_runtime(refs,context,_sdk.InProcessOps()):
        try:yield refs,context
        finally:refs.clear()
