"""Admission/accounting tests only; no node/Guest parity credit from meta tensors."""
import importlib
import inspect
import torch
import pytest

def preflight(module,node,values):
    fn=module._preflight
    return fn(values) if len(inspect.signature(fn).parameters)==1 else fn(node,values)

def images(package):
    budget=importlib.import_module(package.__name__+'.secure_budget')
    for side in (1024,2048):
        for batch in range(2,13):
            for width in (2,4,8):
                assert budget.canvas(batch,side,side,3,itemsize=width)==batch*side*side*3*width
    with pytest.raises(ValueError,match='IMAGE|runtime'):
        budget.canvas(1,10**9,10**9,3)
