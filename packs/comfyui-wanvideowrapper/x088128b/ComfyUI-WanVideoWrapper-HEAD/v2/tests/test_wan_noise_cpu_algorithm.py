"""CPU algorithm evidence only; actual node dispatch is tested separately."""
import ast
import copy
import importlib
import importlib.util
from pathlib import Path
import sys
import pytest
import torch

sys.dont_write_bytecode=True
sys.path.insert(0,'/Users/ben/comfy/ComfyUI-secure-nodes')
V2=Path(__file__).resolve().parents[1]
PACK=V2.parent

def original():
    cls=next(item for item in ast.parse((PACK/'nodes_utility.py').read_text()).body
        if isinstance(item,ast.ClassDef) and item.name=='DrawGaussianNoiseOnImage')
    namespace={'torch':torch,'F':torch.nn.functional,'tqdm':lambda iterable,**kwargs:iterable}
    exec(compile(ast.Module(body=[cls],type_ignores=[]),str(PACK/'nodes_utility.py'),'exec'),namespace)
    return namespace['DrawGaussianNoiseOnImage']

def algorithm():
    name='_wan_noise_preparation'
    spec=importlib.util.spec_from_file_location(name,V2/'__init__.py',submodule_search_locations=[str(V2)])
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    assert module.NODE_CLASS_MAPPINGS['DrawGaussianNoiseOnImage'].SDK_PERMISSIONS==('raw',)
    return importlib.import_module(name+'.secure_noise_algorithms').draw_gaussian_noise_cpu

def cases():
    values=[]
    for dtype in (torch.float32,torch.float64):
        for batch,mask_batch in ((1,1),(3,1),(1,3),(5,2),(0,0)):
            for resized in (False,True):
                for variant in ('zeros','ones','half','fractional'):
                    image=torch.linspace(0,1,max(1,batch*4*5*3),dtype=dtype)[:batch*4*5*3].reshape(batch,4,5,3)
                    height,width=(3,2) if resized else (4,5)
                    mask=torch.zeros(mask_batch,height,width,dtype=dtype)
                    if variant=='ones':mask[:]=1
                    if variant=='half':mask[:,1:]=1
                    if variant=='fractional':mask[:,1:]=.8;mask[:,:1]=.2
                    values.append(dict(image=image,mask=mask,seed=12345))
    return values

def equal(expected,actual):
    assert len(actual)==len(expected)==1
    assert expected[0].shape==actual[0].shape and expected[0].dtype==actual[0].dtype
    assert expected[0].device==actual[0].device==torch.device('cpu')
    assert torch.equal(expected[0],actual[0])

def test_staged_cpu_gaussian_pixels_batch_masks_and_seed_exact():
    fn=algorithm();old=original()()
    for inputs in cases():equal(old.apply(**copy.deepcopy(inputs),device='cpu'),fn(**copy.deepcopy(inputs)))

def test_staged_cpu_gaussian_repeatability_inputs_and_global_rng_unchanged():
    fn=algorithm();inputs=cases()[3];before=copy.deepcopy(inputs)
    state=torch.random.get_rng_state().clone()
    one=fn(**inputs);two=fn(**inputs)
    equal(one,two)
    assert torch.equal(state,torch.random.get_rng_state())
    for key in ('image','mask'):assert torch.equal(inputs[key],before[key])
    assert not torch.equal(fn(**{**inputs,'seed':2})[0],one[0])

@pytest.mark.parametrize('inputs',[
    dict(image=torch.ones(1,3,4,4),mask=torch.ones(1,3,4),seed=0),
    dict(image=torch.ones(1,3,4,3),mask=torch.empty(0,3,4),seed=0),
    dict(image=torch.ones(1,3,4,3),mask=torch.ones(3,4),seed=0),
    dict(image=torch.ones(3,4,3),mask=torch.ones(1,3,4),seed=0),
    dict(image=torch.ones(1,3,4,3),mask=torch.ones(1,3,4),seed=-1.5),
    dict(image=torch.ones(1,3,4,3),mask=torch.ones(1,3,4),seed=2**65),
    dict(image=torch.ones(1,3,4,3),mask=torch.tensor([[[1.,0.,0.,0.],[0.,0.,0.,0.],[0.,0.,0.,0.]]]),seed=0),
])
def test_staged_cpu_native_malformed_errors(inputs):
    def failure(call):
        try:call()
        except Exception as error:return type(error).__name__,str(error)
        raise AssertionError('Expected native error')
    assert failure(lambda:original()().apply(**copy.deepcopy(inputs),device='cpu'))==failure(lambda:algorithm()(**copy.deepcopy(inputs)))

def test_staged_cpu_projected_quota_before_any_clone(monkeypatch):
    fn=algorithm()
    def forbidden(*args,**kwargs):raise AssertionError('Allocation before projected refusal')
    monkeypatch.setattr(torch.Tensor,'clone',forbidden)
    with pytest.raises(ValueError,match='projected'):
        fn(torch.tensor(.5).expand(1,1024,1100,3),torch.tensor(1.).expand(1,1024,1100))
